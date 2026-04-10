from datetime import datetime
from pathlib import Path
import re

import pandas as pd

from ..config import Config
from ..extensions import db
from ..models import AirQualityRecord, DataImportLog, ForecastValidationRecord, ModelMetric, PredictionRecord
from .aqi_service import calculate_aqi


COLUMN_ALIASES = {
    "city": {"city", "城市", "城市名称"},
    "province": {"province", "省份", "所属省份"},
    "record_time": {"recordtime", "record_time", "datetime", "date", "日期", "时间", "监测时间"},
    "pm25": {"pm25", "pm2.5", "pm_25", "细颗粒物", "细颗粒物pm25"},
    "pm10": {"pm10", "pm_10", "可吸入颗粒物", "可吸入颗粒物pm10"},
    "so2": {"so2", "二氧化硫"},
    "no2": {"no2", "二氧化氮"},
    "co": {"co", "一氧化碳"},
    "o3": {"o3", "臭氧", "o31h", "o3_1h", "o3实时"},
    "o3_8h": {"o38h", "o3_8h", "o3-8h", "臭氧8小时", "臭氧8小时平均"},
    "temperature": {"temperature", "temp", "气温", "温度"},
    "humidity": {"humidity", "湿度", "相对湿度"},
    "wind_speed": {"windspeed", "wind_speed", "风速"},
    "pressure": {"pressure", "气压"},
    "source_name": {"sourcename", "source_name", "来源", "数据来源"},
}


def _normalize_column_name(name):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(name).strip().lower())


def _rename_columns(df):
    renamed = {}
    for column in df.columns:
        normalized = _normalize_column_name(column)
        matched = None
        for canonical, aliases in COLUMN_ALIASES.items():
            if normalized in {_normalize_column_name(alias) for alias in aliases}:
                matched = canonical
                break
        renamed[column] = matched or normalized
    return df.rename(columns=renamed)


def _read_dataframe(file_path):
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)
    raise ValueError("仅支持 CSV、XLSX、XLS 文件导入。")


def _ensure_required_columns(df, mode):
    required = {"city", "record_time", "pm25", "pm10", "so2", "no2", "co"}
    if mode == "daily":
        if "o3_8h" not in df.columns and "o3" in df.columns:
            raise ValueError("当前文件更像实时报数据：检测到 o3，但缺少日报必需字段 o3_8h。请切换为“实时报”模式重新导入。")
        required.add("o3_8h")
    else:
        required.add("o3")

    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"导入文件缺少必要字段：{', '.join(missing)}")


def _to_float(value, field_name):
    if pd.isna(value):
        raise ValueError(f"{field_name} 不能为空。")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 不是有效数值。") from exc


def _standardize_city_name(value):
    city_name = str(value).strip()
    if city_name.endswith("市"):
        city_name = city_name[:-1]
    return city_name


def _upsert_air_quality_record(payload):
    existing = AirQualityRecord.query.filter_by(
        city=payload["city"],
        record_time=payload["record_time"],
    ).first()

    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        return "updated"

    db.session.add(AirQualityRecord(**payload))
    return "inserted"


def _clear_forecast_cache(cities):
    if not cities:
        return
    PredictionRecord.query.filter(PredictionRecord.city.in_(cities)).delete(synchronize_session=False)
    ModelMetric.query.filter(ModelMetric.city.in_(cities)).delete(synchronize_session=False)
    ForecastValidationRecord.query.filter(ForecastValidationRecord.city.in_(cities)).delete(synchronize_session=False)


def _import_air_quality_path(file_path, safe_name, mode="daily", source_name="manual-upload"):
    file_path = Path(file_path)
    if not file_path.exists():
        raise ValueError("待导入文件不存在，请检查采集或上传是否成功。")

    mode = mode if mode in {"daily", "realtime"} else "daily"

    log = DataImportLog(
        file_name=safe_name,
        mode=mode,
        source_name=source_name,
        status="running",
        total_rows=0,
        success_rows=0,
        inserted_rows=0,
        updated_rows=0,
        message="文件已接收，开始清洗与计算 AQI。",
    )
    db.session.add(log)
    db.session.commit()

    try:
        df = _rename_columns(_read_dataframe(file_path))
        _ensure_required_columns(df, mode)
        df = df.dropna(how="all")
        df["record_time"] = pd.to_datetime(df["record_time"], errors="coerce")
        df = df.dropna(subset=["city", "record_time"])

        log.total_rows = int(len(df))
        success_rows = 0
        inserted_rows = 0
        updated_rows = 0
        cities = set()

        for _, row in df.iterrows():
            pollutant_payload = {
                "so2": _to_float(row["so2"], "SO2"),
                "no2": _to_float(row["no2"], "NO2"),
                "co": _to_float(row["co"], "CO"),
                "o3": _to_float(row["o3_8h"] if mode == "daily" else row["o3"], "O3"),
                "pm10": _to_float(row["pm10"], "PM10"),
                "pm25": _to_float(row["pm25"], "PM2.5"),
            }
            aqi_result = calculate_aqi(pollutant_payload, mode=mode)
            payload = {
                "city": _standardize_city_name(row["city"]),
                "province": str(row.get("province", "未知")).strip() or "未知",
                "record_time": row["record_time"].to_pydatetime(),
                "aqi": aqi_result["aqi"],
                "level": aqi_result["level"],
                "primary_pollutant": aqi_result["primary_pollutant"],
                "pm25": pollutant_payload["pm25"],
                "pm10": pollutant_payload["pm10"],
                "so2": pollutant_payload["so2"],
                "no2": pollutant_payload["no2"],
                "co": pollutant_payload["co"],
                "o3": pollutant_payload["o3"],
                "temperature": float(row.get("temperature", 20.0) if not pd.isna(row.get("temperature", 20.0)) else 20.0),
                "humidity": float(row.get("humidity", 55.0) if not pd.isna(row.get("humidity", 55.0)) else 55.0),
                "wind_speed": float(row.get("wind_speed", 2.5) if not pd.isna(row.get("wind_speed", 2.5)) else 2.5),
                "pressure": float(row.get("pressure", 1012.0) if not pd.isna(row.get("pressure", 1012.0)) else 1012.0),
                "source_name": str(row.get("source_name", source_name)).strip() or source_name,
            }
            result = _upsert_air_quality_record(payload)
            cities.add(payload["city"])
            success_rows += 1
            if result == "inserted":
                inserted_rows += 1
            else:
                updated_rows += 1

        _clear_forecast_cache(sorted(cities))

        log.status = "success"
        log.success_rows = success_rows
        log.inserted_rows = inserted_rows
        log.updated_rows = updated_rows
        log.message = f"成功导入 {success_rows} 行，覆盖城市 {len(cities)} 个。"
        db.session.commit()

        return {
            "status": log.status,
            "file_name": safe_name,
            "mode": mode,
            "total_rows": log.total_rows,
            "success_rows": success_rows,
            "inserted_rows": inserted_rows,
            "updated_rows": updated_rows,
            "cities": sorted(cities),
            "message": log.message,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as exc:
        db.session.rollback()
        fail_log = db.session.get(DataImportLog, log.id)
        if fail_log:
            fail_log.status = "failed"
            fail_log.message = str(exc)[:250]
            db.session.commit()
        raise


def import_air_quality_dataset(file_storage, mode="daily"):
    if not file_storage or not file_storage.filename:
        raise ValueError("请选择需要导入的 CSV 或 Excel 文件。")

    mode = mode if mode in {"daily", "realtime"} else "daily"
    upload_dir = Path(Config.IMPORT_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_name = Path(file_storage.filename).name
    target_path = upload_dir / f"{timestamp}_{safe_name}"
    file_storage.save(target_path)
    return _import_air_quality_path(target_path, safe_name, mode=mode, source_name="manual-upload")

def import_air_quality_file(file_path, mode="daily", source_name="manual-upload", file_name=None):
    path = Path(file_path)
    safe_name = file_name or path.name
    return _import_air_quality_path(path, safe_name, mode=mode, source_name=source_name)

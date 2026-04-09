from collections import Counter
from datetime import datetime

from ..models import (
    AirQualityRecord,
    CrawlArtifact,
    CrawlTaskLog,
    DataImportLog,
    ForecastValidationRecord,
    ModelMetric,
    PredictionRecord,
)


def _level_color(level):
    mapping = {
        "优": "#2abf6d",
        "良": "#f2c94c",
        "轻度污染": "#ff9f43",
        "中度污染": "#ff6b6b",
        "重度污染": "#c44569",
    }
    return mapping.get(level, "#4b7bec")


def _suggestion(level):
    messages = {
        "优": "空气质量优，适宜户外活动与通勤。",
        "良": "空气质量良，敏感人群外出请适度防护。",
        "轻度污染": "建议减少长时间户外运动，关注老人儿童。",
        "中度污染": "建议佩戴口罩，必要时开启空气净化设备。",
        "重度污染": "建议减少外出并及时查看预警信息。",
    }
    return messages.get(level, "请持续关注空气质量变化。")


def _status_label(status):
    mapping = {
        "success": "成功",
        "failed": "失败",
        "running": "进行中",
    }
    return mapping.get(status, status or "--")


def _mode_label(mode):
    mapping = {
        "daily": "日报",
        "realtime": "实时报",
    }
    return mapping.get(mode, mode or "--")


def _empty_overview(city=""):
    return {
        "has_data": False,
        "message": "暂无空气质量数据，请先在预测页面导入真实数据。",
        "city": city or "--",
        "province": "--",
        "record_time": "--",
        "level": "--",
        "primary_pollutant": "--",
        "suggestion": "请先导入真实空气质量数据。",
        "metrics": {
            "aqi": None,
            "pm25": None,
            "pm10": None,
            "so2": None,
            "no2": None,
            "co": None,
            "o3": None,
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "pressure": None,
        },
        "comparison": {
            "city_rank": 0,
            "city_count": 0,
            "national_avg_aqi": None,
        },
    }


def _empty_trend(city="", year=None):
    return {
        "has_data": False,
        "message": "暂无趋势数据，请先导入真实空气质量数据。",
        "city": city or "--",
        "year": year,
        "monthly": [],
        "distribution": [],
        "ranking": [],
    }


def _empty_forecast(city=""):
    return {
        "has_data": False,
        "message": "暂无预测结果，请先导入真实小时数据并生成 XGBoost 预测。",
        "city": city or "--",
        "generated_at": "--",
        "hourly": [],
        "model_metrics": [],
        "validation": [],
    }


def _empty_screen():
    return {
        "has_data": False,
        "message": "暂无大屏数据，请先导入真实空气质量数据。",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "avg_aqi": "--",
            "best_city": "--",
            "worst_city": "--",
            "excellent_rate": "--",
            "alarm_count": 0,
        },
        "ranking": [],
        "distribution": [],
        "trend": [],
        "forecast_wave": [],
        "alerts": [],
        "crawler": [],
    }


def list_cities():
    rows = AirQualityRecord.query.with_entities(AirQualityRecord.city).distinct().order_by(AirQualityRecord.city).all()
    return [row[0] for row in rows]


def list_years():
    rows = (
        AirQualityRecord.query.with_entities(AirQualityRecord.record_time)
        .order_by(AirQualityRecord.record_time.asc())
        .all()
    )
    years = sorted({row[0].year for row in rows}, reverse=True)
    return years


def get_latest_city_record(city):
    return (
        AirQualityRecord.query.filter_by(city=city)
        .order_by(AirQualityRecord.record_time.desc())
        .first()
    )


def get_overview(city):
    latest = get_latest_city_record(city)
    if not latest:
        return _empty_overview(city)

    all_latest = []
    for name in list_cities():
        record = get_latest_city_record(name)
        if record:
            all_latest.append(record)

    ranking = sorted(all_latest, key=lambda item: item.aqi, reverse=True)
    city_rank = next((index + 1 for index, item in enumerate(ranking) if item.city == city), 0)

    return {
        "has_data": True,
        "message": "",
        "city": latest.city,
        "province": latest.province,
        "record_time": latest.record_time.strftime("%Y-%m-%d %H:%M"),
        "level": latest.level,
        "primary_pollutant": latest.primary_pollutant,
        "suggestion": _suggestion(latest.level),
        "metrics": {
            "aqi": latest.aqi,
            "pm25": latest.pm25,
            "pm10": latest.pm10,
            "so2": latest.so2,
            "no2": latest.no2,
            "co": latest.co,
            "o3": latest.o3,
            "temperature": latest.temperature,
            "humidity": latest.humidity,
            "wind_speed": latest.wind_speed,
            "pressure": latest.pressure,
        },
        "comparison": {
            "city_rank": city_rank,
            "city_count": len(ranking),
            "national_avg_aqi": round(sum(item.aqi for item in ranking) / max(len(ranking), 1), 1),
        },
    }


def get_trend(city, year):
    records = (
        AirQualityRecord.query.filter(
            AirQualityRecord.city == city,
            AirQualityRecord.record_time >= datetime(year, 1, 1),
            AirQualityRecord.record_time < datetime(year + 1, 1, 1),
        )
        .order_by(AirQualityRecord.record_time.asc())
        .all()
    )

    if not records:
        return _empty_trend(city, year)

    monthly_map = {month: [] for month in range(1, 13)}
    for record in records:
        monthly_map[record.record_time.month].append(record)

    monthly = []
    level_counter = Counter()
    for month in range(1, 13):
        month_records = monthly_map[month]
        if not month_records:
            continue

        level_counter.update(item.level for item in month_records)
        monthly.append(
            {
                "month": f"{month}月",
                "aqi_max": max(item.aqi for item in month_records),
                "aqi_min": min(item.aqi for item in month_records),
                "aqi_avg": round(sum(item.aqi for item in month_records) / len(month_records), 1),
                "pm25_avg": round(sum(item.pm25 for item in month_records) / len(month_records), 1),
                "pm10_avg": round(sum(item.pm10 for item in month_records) / len(month_records), 1),
                "no2_avg": round(sum(item.no2 for item in month_records) / len(month_records), 1),
                "o3_avg": round(sum(item.o3 for item in month_records) / len(month_records), 1),
            }
        )

    latest_records = []
    for name in list_cities():
        record = get_latest_city_record(name)
        if record:
            latest_records.append(record)

    ranking = [
        {
            "city": item.city,
            "aqi": item.aqi,
            "level": item.level,
            "color": _level_color(item.level),
        }
        for item in sorted(latest_records, key=lambda item: item.aqi, reverse=True)
    ]

    distribution = [
        {"name": name, "value": value, "color": _level_color(name)}
        for name, value in level_counter.items()
    ]

    return {
        "has_data": True,
        "message": "",
        "city": city,
        "year": year,
        "monthly": monthly,
        "distribution": distribution,
        "ranking": ranking,
    }


def get_forecast(city):
    def query_prediction_records():
        return (
            PredictionRecord.query.filter_by(city=city)
            .order_by(PredictionRecord.forecast_time.asc())
            .all()
        )

    def query_metrics():
        return (
            ModelMetric.query.filter_by(city=city)
            .order_by(ModelMetric.mae.asc())
            .all()
        )

    def query_validation_records():
        return (
            ForecastValidationRecord.query.filter_by(city=city)
            .order_by(ForecastValidationRecord.validation_time.asc())
            .all()
        )

    records = query_prediction_records()
    metrics = query_metrics()
    validation_records = query_validation_records()

    latest_source_record = get_latest_city_record(city)
    generated_at = records[0].generated_at if records else None
    has_formal_xgboost = any(item.model_name == "XGBoost" for item in metrics)
    should_regenerate = (
        not records
        or not metrics
        or not validation_records
        or not has_formal_xgboost
        or (latest_source_record and generated_at and generated_at < latest_source_record.record_time)
    )

    if should_regenerate:
        from .forecast_service import generate_forecast_for_city

        generation_result = generate_forecast_for_city(city)
        if generation_result.get("status") != "success":
            empty_payload = _empty_forecast(city)
            empty_payload["message"] = generation_result.get("message", empty_payload["message"])
            return empty_payload

        records = query_prediction_records()
        metrics = query_metrics()
        validation_records = query_validation_records()

    hourly = [
        {
            "time": item.forecast_time.strftime("%m-%d %H:%M"),
            "actual_aqi": item.actual_aqi,
            "lstm_aqi": item.lstm_aqi,
            "xgboost_aqi": item.xgboost_aqi,
            "ensemble_aqi": item.ensemble_aqi,
            "pm25_pred": item.pm25_pred,
            "pm10_pred": item.pm10_pred,
        }
        for item in records
    ]

    return {
        "has_data": bool(records or metrics),
        "message": "" if (records or metrics) else "暂无预测结果，请先导入真实小时数据并生成 XGBoost 预测。",
        "city": city,
        "generated_at": records[0].generated_at.strftime("%Y-%m-%d %H:%M") if records else "",
        "hourly": hourly,
        "model_metrics": [
            {
                "model": item.model_name,
                "mae": item.mae,
                "rmse": item.rmse,
                "r2": item.r2,
            }
            for item in metrics
        ],
        "validation": [
            {
                "date": item.validation_time.strftime("%m-%d %H:%M"),
                "actual": item.actual_aqi,
                "predicted": item.ensemble_aqi,
                "error": item.error_value,
                "trend": item.trend_aqi,
                "xgboost": item.xgboost_aqi,
            }
            for item in validation_records
        ],
    }


def get_crawler_status(page=1, page_size=10):
    page = max(int(page or 1), 1)
    page_size = max(min(int(page_size or 10), 50), 1)
    task_query = CrawlTaskLog.query.order_by(CrawlTaskLog.run_at.desc())
    total = task_query.count()
    tasks = task_query.offset((page - 1) * page_size).limit(page_size).all()
    artifacts = CrawlArtifact.query.order_by(CrawlArtifact.crawled_at.desc()).limit(8).all()
    return {
        "tasks": [
            {
                "id": item.id,
                "task_name": item.task_name,
                "source_name": item.source_name,
                "target_url": item.target_url,
                "status": item.status,
                "status_label": _status_label(item.status),
                "records_count": item.records_count,
                "message": item.message,
                "run_at": item.run_at.strftime("%Y-%m-%d %H:%M"),
            }
            for item in tasks
        ],
        "artifacts": [
            {
                "source_name": item.source_name,
                "category": item.category,
                "title": item.title,
                "article_url": item.article_url,
                "published_at": item.published_at,
                "crawled_at": item.crawled_at.strftime("%Y-%m-%d %H:%M"),
            }
            for item in artifacts
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 1,
        },
    }


def get_import_logs():
    logs = DataImportLog.query.order_by(DataImportLog.created_at.desc()).limit(10).all()
    return {
        "logs": [
            {
                "file_name": item.file_name,
                "mode": item.mode,
                "mode_label": _mode_label(item.mode),
                "status": item.status,
                "status_label": _status_label(item.status),
                "total_rows": item.total_rows,
                "success_rows": item.success_rows,
                "inserted_rows": item.inserted_rows,
                "updated_rows": item.updated_rows,
                "message": item.message,
                "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for item in logs
        ]
    }


def get_screen_payload(city: str | None = None):
    latest_records = []
    for city_name in list_cities():
        record = get_latest_city_record(city_name)
        if record:
            latest_records.append(record)

    if not latest_records:
        return _empty_screen()

    ranking = sorted(latest_records, key=lambda item: item.aqi, reverse=True)
    avg_aqi = round(sum(item.aqi for item in ranking) / max(len(ranking), 1), 1)
    excellent_rate = round(sum(1 for item in ranking if item.aqi <= 100) / max(len(ranking), 1) * 100, 1)
    worst_city = ranking[0] if ranking else None
    best_city = ranking[-1] if ranking else None
    alert_board = [item for item in ranking if item.aqi > 100]
    selected_city = city if city in {item.city for item in latest_records} else (best_city.city if best_city else latest_records[0].city)
    selected_record = get_latest_city_record(selected_city)
    latest_year = selected_record.record_time.year if selected_record else (list_years()[0] if list_years() else datetime.now().year)
    trend_source = get_trend(selected_city, latest_year)["monthly"]
    crawler = get_crawler_status()
    forecast = get_forecast(selected_city)["hourly"][:12]

    distribution_map = Counter(item.level for item in ranking)

    return {
        "has_data": True,
        "message": "",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "selected_city": selected_city,
        "selected_year": latest_year,
        "summary": {
            "avg_aqi": avg_aqi,
            "best_city": best_city.city if best_city else "--",
            "worst_city": worst_city.city if worst_city else "--",
            "excellent_rate": excellent_rate,
            "alarm_count": len(alert_board),
        },
        "ranking": [
            {"city": item.city, "aqi": item.aqi, "level": item.level}
            for item in ranking
        ],
        "distribution": [
            {"name": name, "value": value}
            for name, value in distribution_map.items()
        ],
        "trend": trend_source,
        "forecast_wave": forecast,
        "alerts": [
            {
                "city": item.city,
                "aqi": item.aqi,
                "level": item.level,
                "primary_pollutant": item.primary_pollutant,
            }
            for item in alert_board[:5]
        ],
        "crawler": crawler["tasks"][:4],
    }

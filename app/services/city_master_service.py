from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re

import requests

from ..config import Config


GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
CITY_MASTER_FIELDS = [
    "city",
    "province",
    "query_name",
    "province_en",
    "latitude",
    "longitude",
    "timezone",
    "enabled",
    "resolved_name",
    "admin1",
    "admin2",
    "last_resolved_at",
]

PROVINCE_EN_TO_CN = {
    "Anhui": "安徽省",
    "Beijing": "北京市",
    "Chongqing": "重庆市",
    "Fujian": "福建省",
    "Gansu": "甘肃省",
    "Guangdong": "广东省",
    "Guangxi": "广西壮族自治区",
    "Guizhou": "贵州省",
    "Hainan": "海南省",
    "Hebei": "河北省",
    "Heilongjiang": "黑龙江省",
    "Henan": "河南省",
    "Hong Kong": "香港特别行政区",
    "Hubei": "湖北省",
    "Hunan": "湖南省",
    "Inner Mongolia": "内蒙古自治区",
    "Jiangsu": "江苏省",
    "Jiangxi": "江西省",
    "Jilin": "吉林省",
    "Liaoning": "辽宁省",
    "Macau": "澳门特别行政区",
    "Ningxia": "宁夏回族自治区",
    "Qinghai": "青海省",
    "Shaanxi": "陕西省",
    "Shandong": "山东省",
    "Shanghai": "上海市",
    "Shanxi": "山西省",
    "Sichuan": "四川省",
    "Taiwan": "台湾省",
    "Tianjin": "天津市",
    "Tibet": "西藏自治区",
    "Xinjiang": "新疆维吾尔自治区",
    "Xinjiang (XPCC)": "新疆维吾尔自治区",
    "Yunnan": "云南省",
    "Zhejiang": "浙江省",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").strip().lower())


def _normalize_city_name(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized.endswith("市"):
        normalized = normalized[:-1]
    return _normalize_text(normalized)


def _to_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _deduplicate_queries(queries: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in queries:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _query_variants(query_name: str) -> list[str]:
    compact = query_name.replace("'", "").replace("-", "").replace("’", "").strip()
    return _deduplicate_queries([query_name, compact, compact.replace(" ", "")])


def _province_keys(row: dict) -> set[str]:
    keys = set()
    province_en = str(row.get("province_en") or "")
    province_cn = str(row.get("province") or "")
    keys.add(_normalize_text(province_en))
    keys.add(_normalize_text(re.sub(r"\(.*?\)", "", province_en)))
    keys.add(_normalize_text(province_cn))
    for suffix in ["省", "市", "自治区", "特别行政区", "壮族自治区", "回族自治区", "维吾尔自治区"]:
        if province_cn.endswith(suffix):
            keys.add(_normalize_text(province_cn[: -len(suffix)]))
    return {item for item in keys if item}


def _admin1_matches_province(row: dict, admin1: str) -> bool:
    admin_norm = _normalize_text(admin1)
    if not admin_norm:
        return False
    keys = _province_keys(row)
    return any(admin_norm == item or admin_norm.startswith(item) or item.startswith(admin_norm) for item in keys)


def _seed_rows_from_package() -> list[dict]:
    from china_cities import get_cities

    seen = set()
    rows = []
    for item in get_cities():
        province_cn = PROVINCE_EN_TO_CN.get(item.province, item.province)
        key = (item.name_cn, province_cn)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "city": item.name_cn,
                "province": province_cn,
                "query_name": item.name_en,
                "province_en": item.province,
                "latitude": "",
                "longitude": "",
                "timezone": "Asia/Shanghai",
                "enabled": "0",
                "resolved_name": "",
                "admin1": "",
                "admin2": "",
                "last_resolved_at": "",
            }
        )
    rows.sort(key=lambda item: (item["province"], item["city"]))
    return rows


def save_city_master(rows: list[dict]) -> None:
    path = Config.CITY_MASTER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CITY_MASTER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_city_master() -> list[dict]:
    path = Config.CITY_MASTER_PATH
    if not path.exists():
        rows = _seed_rows_from_package()
        save_city_master(rows)
        return rows

    with path.open("r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = []
        for row in reader:
            parsed = {field: row.get(field, "") for field in CITY_MASTER_FIELDS}
            parsed["province"] = PROVINCE_EN_TO_CN.get(parsed["province"], parsed["province"])
            if not parsed["province"] and parsed.get("province_en"):
                parsed["province"] = PROVINCE_EN_TO_CN.get(parsed["province_en"], parsed["province_en"])
            if parsed["latitude"]:
                parsed["latitude"] = float(parsed["latitude"])
            if parsed["longitude"]:
                parsed["longitude"] = float(parsed["longitude"])
            parsed["enabled"] = "1" if _to_bool(parsed["enabled"]) else "0"
            rows.append(parsed)
        return rows


def _candidate_queries(row: dict) -> list[str]:
    city_cn = row["city"]
    query_name = row["query_name"]
    city_base = city_cn[:-1] if city_cn.endswith("市") else city_cn
    return _deduplicate_queries(
        [
            *_query_variants(query_name),
            city_cn,
            city_base,
            f"{query_name} City",
        ]
    )


def _country_codes_for_row(row: dict) -> list[str]:
    province = row.get("province")
    if province == "香港特别行政区":
        return ["HK"]
    if province == "澳门特别行政区":
        return ["MO"]
    return ["CN"]


def _query_geocoding(query: str, country_code: str, timeout: int = 6) -> list[dict]:
    response = requests.get(
        GEOCODING_API,
        params={
            "name": query,
            "count": 10,
            "countryCode": country_code,
        },
        timeout=timeout,
        headers={"User-Agent": "AirQualitySystem/1.0"},
    )
    response.raise_for_status()
    return response.json().get("results", [])


def _score_result(row: dict, result: dict, query: str) -> int:
    score = 0
    result_admin1 = _normalize_text(result.get("admin1", ""))
    result_name = _normalize_text(result.get("name", ""))
    query_norm = _normalize_text(query)
    city_cn = _normalize_text(row["city"])
    city_cn_base = _normalize_text(row["city"][:-1] if row["city"].endswith("市") else row["city"])
    query_name = _normalize_text(row["query_name"])

    if _admin1_matches_province(row, result.get("admin1", "")):
        score += 50
    else:
        score -= 60
    if result_name in {query_norm, city_cn, city_cn_base, query_name}:
        score += 30
    if query_name and query_name == result_name:
        score += 20
    if city_cn and city_cn == result_name:
        score += 20
    if city_cn_base and city_cn_base == result_name:
        score += 15

    feature_code = (result.get("feature_code") or "").upper()
    if feature_code in {"PPLC", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPL"}:
        score += 8

    population = result.get("population") or 0
    if population:
        score += min(int(population // 500000), 10)
    return score


def _resolve_single_row(row: dict, timeout: int = 6) -> dict:
    best_result = None
    best_score = -1

    for query in _candidate_queries(row):
        for country_code in _country_codes_for_row(row):
            try:
                results = _query_geocoding(query, country_code=country_code, timeout=timeout)
            except Exception:
                continue
            for result in results:
                score = _score_result(row, result, query)
                if score > best_score:
                    best_score = score
                    best_result = result
        if best_score >= 80:
            break

    updated = row.copy()
    updated["last_resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if best_result:
        if not _admin1_matches_province(row, best_result.get("admin1", "")):
            best_result = None
    if best_result:
        updated["latitude"] = float(best_result["latitude"])
        updated["longitude"] = float(best_result["longitude"])
        updated["timezone"] = best_result.get("timezone") or "Asia/Shanghai"
        updated["enabled"] = "1"
        updated["resolved_name"] = best_result.get("name", "")
        updated["admin1"] = best_result.get("admin1", "")
        updated["admin2"] = best_result.get("admin2", "")
    else:
        updated["enabled"] = "0"
    return updated


def resolve_missing_city_coordinates(rows: list[dict], targets: list[tuple[str, str]] | None = None, max_workers: int = 6) -> list[dict]:
    indexed = {(item["city"], item["province"]): idx for idx, item in enumerate(rows)}
    pending = []
    for item in rows:
        key = (item["city"], item["province"])
        if targets and key not in targets:
            continue
        if item.get("latitude") and item.get("longitude"):
            continue
        pending.append(item)

    if not pending:
        return rows

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_resolve_single_row, item): item for item in pending}
        completed = 0
        for future in as_completed(futures):
            resolved = future.result()
            key = (resolved["city"], resolved["province"])
            rows[indexed[key]] = resolved
            completed += 1
            if completed % 50 == 0:
                save_city_master(rows)

    save_city_master(rows)
    return rows


def get_city_master(scope: str = "all", province: str | None = None, cities: list[str] | None = None, resolve_missing: bool = False) -> list[dict]:
    rows = load_city_master()
    target_cities = {_normalize_city_name(item) for item in (cities or [])}
    targets = []
    for item in rows:
        if scope == "province" and province and item["province"] != province:
            continue
        if scope == "city" and target_cities and _normalize_city_name(item["city"]) not in target_cities:
            continue
        targets.append(item)

    if resolve_missing:
        target_keys = [(item["city"], item["province"]) for item in targets]
        rows = resolve_missing_city_coordinates(rows, targets=target_keys)
        targets = [item for item in rows if (item["city"], item["province"]) in set(target_keys)]

    return targets


def get_resolved_city_master(scope: str = "all", province: str | None = None, cities: list[str] | None = None, resolve_missing: bool = False) -> tuple[list[dict], list[str]]:
    items = get_city_master(scope=scope, province=province, cities=cities, resolve_missing=resolve_missing)
    resolved = []
    unresolved = []
    for item in items:
        if item.get("latitude") and item.get("longitude") and _to_bool(item.get("enabled")):
            resolved.append(item)
        else:
            unresolved.append(item["city"])
    return resolved, unresolved


def city_master_metadata() -> dict:
    rows = load_city_master()
    provinces = sorted({item["province"] for item in rows})
    resolved_count = sum(1 for item in rows if item.get("latitude") and item.get("longitude") and _to_bool(item.get("enabled")))
    auto_enabled = Config.AUTO_REALTIME_COLLECTION_ENABLED
    strategy_summary = (
        f"当前版本以手动触发为主，实时采集单次回补最近 {Config.LIVE_COLLECTION_HOURS} 小时数据，"
        f"历史采集按 {Config.COLLECTION_CHUNK_DAYS} 天切片、每批 {Config.COLLECTION_BATCH_SIZE} 个城市执行。"
    )
    if auto_enabled:
        strategy_summary = (
            f"已配置自动实时采集，计划每 {Config.REALTIME_COLLECTION_INTERVAL_SECONDS} 秒执行一次；"
            f"{strategy_summary}"
        )
    else:
        strategy_summary = (
            f"当前未开启自动实时采集；{strategy_summary}"
        )
    return {
        "total_cities": len(rows),
        "resolved_cities": resolved_count,
        "unresolved_cities": len(rows) - resolved_count,
        "provinces": provinces,
        "strategy": {
            "auto_realtime_enabled": auto_enabled,
            "realtime_interval_seconds": Config.REALTIME_COLLECTION_INTERVAL_SECONDS if auto_enabled else 0,
            "configured_interval_seconds": Config.REALTIME_COLLECTION_INTERVAL_SECONDS,
            "realtime_window_hours": Config.LIVE_COLLECTION_HOURS,
            "history_chunk_days": Config.COLLECTION_CHUNK_DAYS,
            "batch_size": Config.COLLECTION_BATCH_SIZE,
            "request_timeout_seconds": Config.CRAWLER_TIMEOUT,
            "realtime_mode": "自动定时" if auto_enabled else "手动触发",
            "history_mode": "手动触发",
            "public_report_mode": "手动触发",
            "summary": strategy_summary,
        },
    }

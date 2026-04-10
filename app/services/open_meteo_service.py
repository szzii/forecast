from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from ..config import Config


AIR_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_API = "https://api.open-meteo.com/v1/forecast"
AIR_VARS = "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone"
WEATHER_VARS = "temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure"
CSV_FIELDS = [
    "city",
    "province",
    "record_time",
    "pm25",
    "pm10",
    "so2",
    "no2",
    "co",
    "o3",
    "temperature",
    "humidity",
    "wind_speed",
    "pressure",
    "source_name",
]


def fetch_json(url: str, params: dict, timeout: int = 30):
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={"User-Agent": "AirQualitySystem/1.0"},
    )
    response.raise_for_status()
    return response.json()


def _chunked(items: list[dict], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _date_chunks(start_date: date, end_date: date, chunk_days: int):
    current = start_date
    while current <= end_date:
        chunk_end = min(end_date, current + timedelta(days=chunk_days - 1))
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def _build_common_params(cities: list[dict]) -> dict:
    return {
        "latitude": ",".join(str(item["latitude"]) for item in cities),
        "longitude": ",".join(str(item["longitude"]) for item in cities),
        "timezone": ",".join(item.get("timezone", "Asia/Shanghai") or "Asia/Shanghai" for item in cities),
    }


def _ensure_payload_list(payload):
    if isinstance(payload, list):
        return payload
    return [payload]


def _rows_from_payload(city_info: dict, air_payload: dict, weather_payload: dict, source_name: str) -> list[dict]:
    air_hourly = air_payload["hourly"]
    weather_hourly = weather_payload["hourly"]
    weather_index = {time: idx for idx, time in enumerate(weather_hourly["time"])}
    now = datetime.now()

    rows = []
    for idx, record_time in enumerate(air_hourly["time"]):
        weather_idx = weather_index.get(record_time)
        if weather_idx is None:
            continue
        try:
            record_dt = datetime.fromisoformat(record_time)
        except ValueError:
            record_dt = datetime.strptime(record_time, "%Y-%m-%dT%H:%M")
        if record_dt > now:
            continue
        co_micrograms = air_hourly["carbon_monoxide"][idx]
        pm25 = air_hourly["pm2_5"][idx]
        pm10 = air_hourly["pm10"][idx]
        so2 = air_hourly["sulphur_dioxide"][idx]
        no2 = air_hourly["nitrogen_dioxide"][idx]
        o3 = air_hourly["ozone"][idx]
        # 关键污染物任一缺测则跳过该小时，避免导入时报"不能为空"
        if any(v is None for v in (pm25, pm10, so2, no2, o3)):
            continue
        rows.append(
            {
                "city": city_info["city"],
                "province": city_info["province"],
                "record_time": record_time.replace("T", " "),
                "pm25": pm25,
                "pm10": pm10,
                "so2": so2,
                "no2": no2,
                "co": round((co_micrograms or 0) / 1000, 3),
                "o3": o3,
                "temperature": weather_hourly["temperature_2m"][weather_idx],
                "humidity": weather_hourly["relative_humidity_2m"][weather_idx],
                "wind_speed": weather_hourly["wind_speed_10m"][weather_idx],
                "pressure": weather_hourly["surface_pressure"][weather_idx],
                "source_name": source_name,
            }
        )
    return rows


def fetch_realtime_batch_rows(cities: list[dict], hours: int = 24, timeout: int = 30, source_name: str = "open-meteo-live") -> list[dict]:
    common_params = {
        **_build_common_params(cities),
        "past_hours": hours,
        "forecast_hours": 0,
    }
    air_payload = fetch_json(AIR_API, {**common_params, "hourly": AIR_VARS}, timeout=timeout)
    weather_payload = fetch_json(WEATHER_API, {**common_params, "hourly": WEATHER_VARS}, timeout=timeout)
    air_payloads = _ensure_payload_list(air_payload)
    weather_payloads = _ensure_payload_list(weather_payload)

    rows = []
    for city_info, air_item, weather_item in zip(cities, air_payloads, weather_payloads):
        rows.extend(_rows_from_payload(city_info, air_item, weather_item, source_name=source_name))
    return rows


def collect_realtime_rows(
    hours: int = 24,
    timeout: int = 30,
    cities: list[dict] | None = None,
    batch_size: int | None = None,
    progress_callback=None,
) -> tuple[list[dict], list[str]]:
    if not cities:
        return [], []

    rows: list[dict] = []
    failed_cities: list[str] = []
    size = batch_size or Config.COLLECTION_BATCH_SIZE

    for batch_index, city_batch in enumerate(_chunked(cities, size), start=1):
        try:
            rows.extend(fetch_realtime_batch_rows(city_batch, hours=hours, timeout=timeout))
            if progress_callback:
                progress_callback(batch_index, len(rows), [], [item["city"] for item in city_batch])
        except Exception:
            batch_failed = [item["city"] for item in city_batch]
            failed_cities.extend(batch_failed)
            if progress_callback:
                progress_callback(batch_index, len(rows), batch_failed, [item["city"] for item in city_batch])

    rows.sort(key=lambda item: (item["city"], item["record_time"]))
    return rows, failed_cities


def iter_history_rows(
    cities: list[dict],
    start_date: date,
    end_date: date,
    timeout: int = 30,
    batch_size: int | None = None,
    chunk_days: int | None = None,
    source_name: str = "open-meteo-history",
):
    size = batch_size or Config.COLLECTION_BATCH_SIZE
    date_chunk_size = chunk_days or Config.COLLECTION_CHUNK_DAYS

    date_ranges = list(_date_chunks(start_date, end_date, date_chunk_size))
    total_chunks = len(date_ranges)

    for chunk_index, (chunk_start, chunk_end) in enumerate(date_ranges, start=1):
        city_batches = list(_chunked(cities, size))
        total_batches = len(city_batches)
        for batch_index, city_batch in enumerate(city_batches, start=1):
            meta = {
                "chunk_start": chunk_start.isoformat(),
                "chunk_end": chunk_end.isoformat(),
                "chunk_index": chunk_index,
                "chunk_total": total_chunks,
                "batch_index": batch_index,
                "batch_total": total_batches,
                "city_count": len(city_batch),
                "cities": [item["city"] for item in city_batch],
            }
            common_params = {
                **_build_common_params(city_batch),
                "start_date": chunk_start.isoformat(),
                "end_date": chunk_end.isoformat(),
            }
            try:
                air_payload = fetch_json(AIR_API, {**common_params, "hourly": AIR_VARS}, timeout=timeout)
                weather_payload = fetch_json(WEATHER_API, {**common_params, "hourly": WEATHER_VARS}, timeout=timeout)
                air_payloads = _ensure_payload_list(air_payload)
                weather_payloads = _ensure_payload_list(weather_payload)

                rows = []
                for city_info, air_item, weather_item in zip(city_batch, air_payloads, weather_payloads):
                    rows.extend(_rows_from_payload(city_info, air_item, weather_item, source_name=source_name))
                yield rows, [], meta
            except Exception:
                yield [], [item["city"] for item in city_batch], meta


def append_csv_rows(rows: list[dict], output_path: Path, write_header: bool = False) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a"
    with output_path.open(mode, newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def save_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

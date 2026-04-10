import math
from decimal import Decimal, ROUND_HALF_UP


AQI_BREAKPOINTS = [0, 50, 100, 150, 200, 300, 400, 500]

POLLUTANT_BREAKPOINTS = {
    "daily": {
        "so2": [0, 50, 150, 475, 800, 1600, 2100, 2620],
        "no2": [0, 40, 80, 180, 280, 565, 750, 940],
        "co": [0, 2, 4, 14, 24, 36, 48, 60],
        "o3": [0, 100, 160, 215, 265, 800],
        "pm10": [0, 50, 120, 250, 350, 420, 500, 600],
        "pm25": [0, 35, 60, 115, 150, 250, 350, 500],
    },
    "realtime": {
        "so2": [0, 150, 500, 650, 800],
        "no2": [0, 100, 200, 700, 1200, 2340, 3090, 3840],
        "co": [0, 5, 10, 35, 60, 90, 120, 150],
        "o3": [0, 160, 200, 300, 400, 800, 1000, 1200],
        "pm10": [0, 50, 120, 250, 350, 420, 500, 600],
        "pm25": [0, 35, 60, 115, 150, 250, 350, 500],
    },
}

POLLUTANT_LABELS = {
    "so2": "SO2",
    "no2": "NO2",
    "co": "CO",
    "o3": "O3",
    "pm10": "PM10",
    "pm25": "PM2.5",
}


def _round_half_up(value, digits=0):
    quant = "1" if digits == 0 else f"1.{'0' * digits}"
    return float(Decimal(str(value)).quantize(Decimal(quant), rounding=ROUND_HALF_UP))


def _normalize_input_value(pollutant, value):
    digits = 1 if pollutant == "co" else 0
    return _round_half_up(value, digits)


def _resolve_breakpoints(mode, pollutant):
    if mode not in POLLUTANT_BREAKPOINTS:
        raise ValueError("统计模式仅支持 daily 或 realtime。")
    return POLLUTANT_BREAKPOINTS[mode][pollutant]


def calculate_iaqi(pollutant, concentration, mode="daily"):
    cp = _normalize_input_value(pollutant, concentration)
    breakpoints = _resolve_breakpoints(mode, pollutant)

    if pollutant == "so2" and mode == "realtime" and cp > 800:
        return 200
    if pollutant == "o3" and mode == "daily" and cp > 800:
        return 300

    if cp <= breakpoints[0]:
        return 0

    for index in range(1, len(breakpoints)):
        if cp <= breakpoints[index]:
            bp_lo = breakpoints[index - 1]
            bp_hi = breakpoints[index]
            iaqi_lo = AQI_BREAKPOINTS[index - 1]
            iaqi_hi = AQI_BREAKPOINTS[index]
            value = ((iaqi_hi - iaqi_lo) / (bp_hi - bp_lo)) * (cp - bp_lo) + iaqi_lo
            return math.ceil(value)

    return 500


def classify_aqi(aqi):
    if aqi <= 50:
        return "优"
    if aqi <= 100:
        return "良"
    if aqi <= 150:
        return "轻度污染"
    if aqi <= 200:
        return "中度污染"
    if aqi <= 300:
        return "重度污染"
    return "严重污染"


def calculate_aqi(payload, mode="daily"):
    if mode not in {"daily", "realtime"}:
        raise ValueError("统计模式仅支持 daily 或 realtime。")

    pollutant_values = {
        "so2": payload["so2"],
        "no2": payload["no2"],
        "co": payload["co"],
        "o3": payload["o3"],
        "pm10": payload["pm10"],
        "pm25": payload["pm25"],
    }
    iaqi_map = {
        pollutant: calculate_iaqi(pollutant, value, mode=mode)
        for pollutant, value in pollutant_values.items()
    }
    aqi = max(iaqi_map.values())
    level = classify_aqi(aqi)

    primary_pollutants = [
        POLLUTANT_LABELS[pollutant]
        for pollutant, value in iaqi_map.items()
        if value == aqi and aqi > 50
    ]
    primary_pollutant = "、".join(primary_pollutants) if primary_pollutants else "无"

    return {
        "aqi": int(aqi),
        "level": level,
        "primary_pollutant": primary_pollutant,
        "iaqi": iaqi_map,
    }

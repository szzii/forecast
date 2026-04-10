from __future__ import annotations

from .repository import get_forecast

# AQI 等级颜色与描述
_LEVEL_META = {
    "优":     {"color": "#2abf6d", "short": "空气优良"},
    "良":     {"color": "#a3c94a", "short": "空气较好"},
    "轻度污染": {"color": "#ff9f43", "short": "轻度污染"},
    "中度污染": {"color": "#ff6b6b", "short": "中度污染"},
    "重度污染": {"color": "#c0392b", "short": "重度污染"},
    "严重污染": {"color": "#7d1f1f", "short": "严重污染"},
}

# 活动在各 AQI 级别下的建议
_ACTIVITY_RULES = [
    {
        "key": "run",
        "label": "跑步/健步走",
        "icon": "🏃",
        "thresholds": [
            (50,  "good",    "适宜，尽情享受户外运动"),
            (100, "ok",      "可以，建议避开早晚高峰"),
            (150, "caution", "谨慎，建议减少剧烈运动"),
            (200, "bad",     "不建议，敏感人群请在室内"),
            (999, "danger",  "禁止，严重损害呼吸系统"),
        ],
    },
    {
        "key": "kids",
        "label": "儿童户外活动",
        "icon": "🧒",
        "thresholds": [
            (50,  "good",    "非常适合，让孩子尽情玩耍"),
            (100, "ok",      "可以，注意补水"),
            (150, "caution", "建议缩短户外时间"),
            (200, "bad",     "不建议，尽量留在室内"),
            (999, "danger",  "禁止外出，严格室内防护"),
        ],
    },
    {
        "key": "elder",
        "label": "老年人外出",
        "icon": "👴",
        "thresholds": [
            (50,  "good",    "非常适合，可长时间户外活动"),
            (100, "ok",      "适合，避免长时间剧烈活动"),
            (150, "caution", "谨慎，心肺疾病患者需注意"),
            (200, "bad",     "不建议，请减少外出"),
            (999, "danger",  "禁止，心肺疾病患者危险"),
        ],
    },
    {
        "key": "commute",
        "label": "通勤骑行",
        "icon": "🚴",
        "thresholds": [
            (50,  "good",    "畅快骑行，无需防护"),
            (100, "ok",      "可以骑行，时间不宜过长"),
            (150, "caution", "建议佩戴口罩出行"),
            (200, "bad",     "建议换乘公共交通"),
            (999, "danger",  "请驾车或公共交通出行"),
        ],
    },
    {
        "key": "mask",
        "label": "口罩建议",
        "icon": "😷",
        "thresholds": [
            (50,  "good",    "无需佩戴"),
            (100, "ok",      "一般无需，敏感人群可备用"),
            (150, "caution", "建议佩戴普通口罩"),
            (200, "bad",     "建议佩戴 N95 口罩"),
            (999, "danger",  "必须全程佩戴 N95 口罩"),
        ],
    },
    {
        "key": "window",
        "label": "开窗通风",
        "icon": "🪟",
        "thresholds": [
            (50,  "good",    "可随时开窗，换气效果佳"),
            (100, "ok",      "适合开窗，避开早晚高峰"),
            (150, "caution", "建议减少开窗时间"),
            (200, "bad",     "关窗，使用空气净化器"),
            (999, "danger",  "严禁开窗，保持室内密封"),
        ],
    },
]


def _aqi_to_level(aqi: float) -> str:
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


def _activity_advice(aqi: float) -> list[dict]:
    result = []
    for act in _ACTIVITY_RULES:
        for limit, status, text in act["thresholds"]:
            if aqi <= limit:
                result.append({
                    "key": act["key"],
                    "label": act["label"],
                    "icon": act["icon"],
                    "status": status,
                    "text": text,
                })
                break
    return result


def _peak_advice(aqi: float) -> str:
    if aqi <= 50:
        return "空气优良，随时出行均佳。"
    if aqi <= 100:
        return "空气较好，建议避开早晚交通高峰。"
    if aqi <= 150:
        return "轻度污染，减少户外停留时间，敏感人群注意。"
    if aqi <= 200:
        return "中度污染，尽量缩短外出，户外必要时戴 N95。"
    if aqi <= 300:
        return "重度污染，请尽量留在室内，必须外出须做好防护。"
    return "严重污染，禁止户外活动，室内保持密封，使用空气净化器。"


def _extract_hour(time_label: str) -> int | None:
    try:
        return int(str(time_label).split(" ")[-1].split(":")[0])
    except (TypeError, ValueError, AttributeError, IndexError):
        return None


def get_advice(city: str) -> dict:
    forecast = get_forecast(city)

    if not forecast.get("has_data") or not forecast.get("hourly"):
        return {
            "has_data": False,
            "message": forecast.get("message", "暂无预测数据，请先生成预测。"),
            "city": city,
        }

    hourly = forecast["hourly"]

    # 各小时预测 AQI
    aqi_series = [
        {"time": item["time"], "aqi": round(item["ensemble_aqi"] or 0, 1)}
        for item in hourly
        if item.get("ensemble_aqi") is not None
    ]

    if not aqi_series:
        return {"has_data": False, "message": "预测数据不完整。", "city": city}

    aqi_values = [h["aqi"] for h in aqi_series]
    avg_aqi = round(sum(aqi_values) / len(aqi_values), 1)
    min_aqi = min(aqi_values)
    max_aqi = max(aqi_values)

    # 最佳出行时段（AQI 最低的连续 / 离散 top-3 小时）
    sorted_hours = sorted(aqi_series, key=lambda x: x["aqi"])
    best_hours = sorted_hours[:3]
    worst_hours = sorted_hours[-3:][::-1]

    # 分时段摘要：上午(0-11) / 下午(12-17) / 晚上(18-23)
    def period_avg(label_filter):
        items = [h["aqi"] for h in aqi_series if label_filter(h["time"])]
        return round(sum(items) / len(items), 1) if items else None

    def is_morning(time_label):
        hour = _extract_hour(time_label)
        return hour is not None and hour < 12

    def is_afternoon(time_label):
        hour = _extract_hour(time_label)
        return hour is not None and 12 <= hour < 18

    def is_evening(time_label):
        hour = _extract_hour(time_label)
        return hour is not None and hour >= 18

    periods = [
        {"label": "上午", "avg_aqi": period_avg(is_morning)},
        {"label": "下午", "avg_aqi": period_avg(is_afternoon)},
        {"label": "晚上", "avg_aqi": period_avg(is_evening)},
    ]
    periods = [p for p in periods if p["avg_aqi"] is not None]
    for p in periods:
        p["level"] = _aqi_to_level(p["avg_aqi"])
        p["color"] = _LEVEL_META[p["level"]]["color"]

    # 整体建议
    overall_level = _aqi_to_level(avg_aqi)
    overall_color = _LEVEL_META[overall_level]["color"]
    overall_text = _peak_advice(avg_aqi)

    # 活动建议（基于全天平均）
    activities = _activity_advice(avg_aqi)

    # 色带时间轴（带颜色）
    timeline = [
        {
            "time": h["time"],
            "aqi": h["aqi"],
            "level": _aqi_to_level(h["aqi"]),
            "color": _LEVEL_META[_aqi_to_level(h["aqi"])]["color"],
        }
        for h in aqi_series
    ]

    return {
        "has_data": True,
        "city": city,
        "generated_at": forecast["generated_at"],
        "summary": {
            "avg_aqi": avg_aqi,
            "min_aqi": min_aqi,
            "max_aqi": max_aqi,
            "level": overall_level,
            "color": overall_color,
            "text": overall_text,
        },
        "best_hours": [
            {**h, "level": _aqi_to_level(h["aqi"]), "color": _LEVEL_META[_aqi_to_level(h["aqi"])]["color"]}
            for h in best_hours
        ],
        "worst_hours": [
            {**h, "level": _aqi_to_level(h["aqi"]), "color": _LEVEL_META[_aqi_to_level(h["aqi"])]["color"]}
            for h in worst_hours
        ],
        "periods": periods,
        "activities": activities,
        "timeline": timeline,
    }

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math

import numpy as np

try:
    import xgboost as xgb
except ImportError:  # pragma: no cover - 依赖缺失时给出运行期提示
    xgb = None

from ..extensions import db
from ..models import AirQualityRecord, ForecastValidationRecord, ModelMetric, PredictionRecord


MIN_REQUIRED_RECORDS = 18
MAX_LAG = 6


@dataclass
class SupervisedDataset:
    features: np.ndarray
    labels: np.ndarray
    timestamps: list[datetime]
    indices: list[int]


@dataclass
class BoosterResult:
    booster: object | None
    metrics: dict
    validation_predictions: list[float]
    validation_actuals: list[float]
    validation_timestamps: list[datetime]
    validation_indices: list[int]


def _clamp(value: float, lower: float = 0.0, upper: float = 500.0) -> float:
    return max(lower, min(upper, float(value)))


def _hour_sin_cos(dt: datetime) -> tuple[float, float]:
    radians = 2 * math.pi * (dt.hour / 24)
    return math.sin(radians), math.cos(radians)


def _weekday_sin_cos(dt: datetime) -> tuple[float, float]:
    radians = 2 * math.pi * (dt.weekday() / 7)
    return math.sin(radians), math.cos(radians)


def _find_same_hour_reference(records: list[AirQualityRecord], target_time: datetime) -> AirQualityRecord:
    for record in reversed(records):
        if record.record_time.hour == target_time.hour:
            return record
    return records[-1]


def _predict_trend(records: list[AirQualityRecord], target_time: datetime) -> tuple[float, AirQualityRecord]:
    same_hour = _find_same_hour_reference(records, target_time)
    latest = records[-1]
    last_values = [item.aqi for item in records[-3:]]
    if len(last_values) == 1:
        recent_avg = last_values[0]
    elif len(last_values) == 2:
        recent_avg = last_values[0] * 0.4 + last_values[1] * 0.6
    else:
        recent_avg = last_values[0] * 0.2 + last_values[1] * 0.3 + last_values[2] * 0.5

    short_trend = latest.aqi - records[-2].aqi if len(records) >= 2 else 0
    prediction = same_hour.aqi * 0.5 + recent_avg * 0.35 + (latest.aqi + short_trend * 0.5) * 0.15
    return round(_clamp(prediction), 1), same_hour


def _series_window_mean(values: list[float], size: int) -> float:
    window = values[-size:] if len(values) >= size else values
    return float(sum(window) / max(len(window), 1))


def _build_feature_vector(values: list[float], target_time: datetime, context_values: list[float] | None = None) -> list[float]:
    hour_sin, hour_cos = _hour_sin_cos(target_time)
    weekday_sin, weekday_cos = _weekday_sin_cos(target_time)

    feature = [
        float(values[-1]),
        float(values[-2]),
        float(values[-3]),
        float(values[-6]),
        _series_window_mean(values, 3),
        _series_window_mean(values, 6),
        float(values[-1] - values[-2]),
        float(values[-1] - _series_window_mean(values, 3)),
        hour_sin,
        hour_cos,
        weekday_sin,
        weekday_cos,
        1.0 if target_time.weekday() >= 5 else 0.0,
    ]

    if context_values is not None:
        feature.extend(
            [
                float(context_values[-1]),
                float(context_values[-2]),
                _series_window_mean(context_values, 3),
            ]
        )
    return feature


def _build_supervised_dataset(records: list[AirQualityRecord], target_field: str) -> SupervisedDataset:
    values = [float(getattr(item, target_field)) for item in records]
    aqi_values = [float(item.aqi) for item in records]

    features = []
    labels = []
    timestamps = []
    indices = []

    for index in range(MAX_LAG, len(records)):
        target_time = records[index].record_time
        history_values = values[:index]
        history_aqi = aqi_values[:index]
        features.append(
            _build_feature_vector(
                history_values,
                target_time,
                context_values=history_aqi if target_field != "aqi" else None,
            )
        )
        labels.append(values[index])
        timestamps.append(target_time)
        indices.append(index)

    return SupervisedDataset(
        features=np.array(features, dtype=float),
        labels=np.array(labels, dtype=float),
        timestamps=timestamps,
        indices=indices,
    )


def _metrics(actuals: list[float], predictions: list[float]) -> dict:
    if not actuals:
        return {"mae": 0.0, "rmse": 0.0, "r2": 0.0}

    actual_arr = np.array(actuals, dtype=float)
    pred_arr = np.array(predictions, dtype=float)
    mae = float(np.mean(np.abs(actual_arr - pred_arr)))
    rmse = float(np.sqrt(np.mean((actual_arr - pred_arr) ** 2)))
    ss_res = float(np.sum((actual_arr - pred_arr) ** 2))
    ss_tot = float(np.sum((actual_arr - np.mean(actual_arr)) ** 2))
    r2 = 0.0 if ss_tot == 0 else float(1 - ss_res / ss_tot)
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "r2": round(r2, 4)}


def _validation_size(sample_count: int) -> int:
    if sample_count <= 10:
        return 2
    return max(4, min(8, sample_count // 4))


def _train_xgboost(dataset: SupervisedDataset) -> BoosterResult:
    if xgb is None:
        raise RuntimeError("当前环境未安装 xgboost，暂时无法生成正式预测结果。")
    if len(dataset.labels) < 10:
        raise RuntimeError("当前城市的有效训练样本不足，至少需要 10 条监督样本。")

    validation_size = _validation_size(len(dataset.labels))
    split_index = len(dataset.labels) - validation_size
    if split_index < 6:
        raise RuntimeError("当前城市的训练样本不足，无法完成训练集与验证集划分。")

    train_matrix = xgb.DMatrix(dataset.features[:split_index], label=dataset.labels[:split_index])
    validation_matrix = xgb.DMatrix(dataset.features[split_index:], label=dataset.labels[split_index:])
    params = {
        "objective": "reg:squarederror",
        "eta": 0.05,
        "max_depth": 4,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 1,
        "lambda": 1.0,
        "alpha": 0.0,
        "seed": 42,
        "verbosity": 0,
    }
    validation_model = xgb.train(
        params,
        train_matrix,
        num_boost_round=180,
        evals=[(train_matrix, "train"), (validation_matrix, "validation")],
        early_stopping_rounds=18,
        verbose_eval=False,
    )
    best_rounds = validation_model.best_iteration + 1 if validation_model.best_iteration is not None else 80
    validation_predictions = validation_model.predict(
        validation_matrix,
        iteration_range=(0, best_rounds),
    )

    full_matrix = xgb.DMatrix(dataset.features, label=dataset.labels)
    full_model = xgb.train(
        params,
        full_matrix,
        num_boost_round=max(best_rounds, 40),
        verbose_eval=False,
    )

    return BoosterResult(
        booster=full_model,
        metrics=_metrics(dataset.labels[split_index:].tolist(), validation_predictions.tolist()),
        validation_predictions=[round(float(item), 1) for item in validation_predictions.tolist()],
        validation_actuals=[round(float(item), 1) for item in dataset.labels[split_index:].tolist()],
        validation_timestamps=dataset.timestamps[split_index:],
        validation_indices=dataset.indices[split_index:],
    )


def _predict_with_booster(
    booster,
    history_values: list[float],
    target_time: datetime,
    context_values: list[float] | None = None,
    upper: float = 500.0,
) -> float | None:
    if booster is None:
        return None
    features = np.array(
        [_build_feature_vector(history_values, target_time, context_values=context_values)],
        dtype=float,
    )
    prediction = float(booster.predict(xgb.DMatrix(features))[0])
    return round(_clamp(prediction, upper=upper), 1)


def _predict_pm(reference_value: float, latest_value: float, latest_aqi: float, predicted_aqi: float) -> float:
    ratio_value = latest_value / latest_aqi if latest_aqi else 0
    return round(_clamp(reference_value * 0.55 + predicted_aqi * ratio_value * 0.45, 0, 500), 1)


def _predict_component(reference_value: float, latest_value: float, latest_aqi: float, predicted_aqi: float, upper: float = 500.0) -> float:
    ratio_value = latest_value / latest_aqi if latest_aqi else 0
    return round(_clamp(reference_value * 0.55 + predicted_aqi * ratio_value * 0.45, 0, upper), 1)


def _blend_weights(trend_metrics: dict, xgboost_metrics: dict) -> tuple[float, float]:
    trend_error = max(float(trend_metrics.get("mae", 0.0)), 0.1)
    xgboost_error = max(float(xgboost_metrics.get("mae", 0.0)), 0.1)
    trend_score = 1 / trend_error
    xgboost_score = 1 / xgboost_error
    total = trend_score + xgboost_score
    return trend_score / total, xgboost_score / total


def generate_forecast_for_city(city: str, horizon: int = 24) -> dict:
    if xgb is None:
        return {
            "status": "failed",
            "message": "当前环境未安装 xgboost，请先执行 requirements.txt 中的依赖安装。",
        }

    records = (
        AirQualityRecord.query.filter_by(city=city)
        .order_by(AirQualityRecord.record_time.asc())
        .all()
    )
    if len(records) < MIN_REQUIRED_RECORDS:
        return {
            "status": "failed",
            "message": f"当前城市至少需要 {MIN_REQUIRED_RECORDS} 条连续小时数据，才能训练正式 XGBoost 预测模型。",
        }

    try:
        aqi_result = _train_xgboost(_build_supervised_dataset(records, "aqi"))
        pm25_result = _train_xgboost(_build_supervised_dataset(records, "pm25"))
        pm10_result = _train_xgboost(_build_supervised_dataset(records, "pm10"))
        so2_result = _train_xgboost(_build_supervised_dataset(records, "so2"))
        no2_result = _train_xgboost(_build_supervised_dataset(records, "no2"))
        co_result = _train_xgboost(_build_supervised_dataset(records, "co"))
        o3_result = _train_xgboost(_build_supervised_dataset(records, "o3"))
    except RuntimeError as exc:
        return {"status": "failed", "message": str(exc)}

    trend_predictions = []
    for original_index, target_time in zip(aqi_result.validation_indices, aqi_result.validation_timestamps):
        trend_prediction, _ = _predict_trend(records[:original_index], target_time)
        trend_predictions.append(trend_prediction)

    trend_metrics = _metrics(aqi_result.validation_actuals, trend_predictions)
    trend_weight, xgboost_weight = _blend_weights(trend_metrics, aqi_result.metrics)
    ensemble_predictions = [
        round(trend_prediction * trend_weight + xgb_prediction * xgboost_weight, 1)
        for trend_prediction, xgb_prediction in zip(trend_predictions, aqi_result.validation_predictions)
    ]
    ensemble_metrics = _metrics(aqi_result.validation_actuals, ensemble_predictions)

    generated_at = datetime.now().replace(minute=0, second=0, microsecond=0)
    latest = records[-1]

    PredictionRecord.query.filter_by(city=city).delete()
    ModelMetric.query.filter_by(city=city).delete()
    ForecastValidationRecord.query.filter_by(city=city).delete()

    db.session.add_all(
        [
            ModelMetric(
                city=city,
                model_name="趋势基线",
                mae=trend_metrics["mae"],
                rmse=trend_metrics["rmse"],
                r2=trend_metrics["r2"],
                updated_at=generated_at,
            ),
            ModelMetric(
                city=city,
                model_name="XGBoost",
                mae=aqi_result.metrics["mae"],
                rmse=aqi_result.metrics["rmse"],
                r2=aqi_result.metrics["r2"],
                updated_at=generated_at,
            ),
            ModelMetric(
                city=city,
                model_name="融合模型",
                mae=ensemble_metrics["mae"],
                rmse=ensemble_metrics["rmse"],
                r2=ensemble_metrics["r2"],
                updated_at=generated_at,
            ),
        ]
    )

    for index, validation_time in enumerate(aqi_result.validation_timestamps):
        db.session.add(
            ForecastValidationRecord(
                city=city,
                validation_time=validation_time,
                generated_at=generated_at,
                actual_aqi=aqi_result.validation_actuals[index],
                trend_aqi=trend_predictions[index],
                xgboost_aqi=aqi_result.validation_predictions[index],
                ensemble_aqi=ensemble_predictions[index],
                error_value=round(abs(aqi_result.validation_actuals[index] - ensemble_predictions[index]), 1),
            )
        )

    prediction_rows = []
    aqi_history = [float(item.aqi) for item in records]
    pm25_history = [float(item.pm25) for item in records]
    pm10_history = [float(item.pm10) for item in records]
    so2_history = [float(item.so2) for item in records]
    no2_history = [float(item.no2) for item in records]
    co_history = [float(item.co) for item in records]
    o3_history = [float(item.o3) for item in records]

    for step in range(1, horizon + 1):
        forecast_time = latest.record_time + timedelta(hours=step)
        trend_prediction, reference = _predict_trend(records, forecast_time)
        xgboost_prediction = _predict_with_booster(aqi_result.booster, aqi_history, forecast_time)
        if xgboost_prediction is None:
            xgboost_prediction = trend_prediction
        ensemble_prediction = round(
            trend_prediction * trend_weight + xgboost_prediction * xgboost_weight,
            1,
        )

        pm25_prediction = _predict_with_booster(
            pm25_result.booster,
            pm25_history,
            forecast_time,
            context_values=aqi_history,
        )
        pm10_prediction = _predict_with_booster(
            pm10_result.booster,
            pm10_history,
            forecast_time,
            context_values=aqi_history,
        )
        if pm25_prediction is None:
            pm25_prediction = _predict_pm(reference.pm25, latest.pm25, latest.aqi, ensemble_prediction)
        if pm10_prediction is None:
            pm10_prediction = _predict_pm(reference.pm10, latest.pm10, latest.aqi, ensemble_prediction)
        so2_prediction = _predict_with_booster(so2_result.booster, so2_history, forecast_time, context_values=aqi_history)
        no2_prediction = _predict_with_booster(no2_result.booster, no2_history, forecast_time, context_values=aqi_history)
        co_prediction = _predict_with_booster(co_result.booster, co_history, forecast_time, context_values=aqi_history, upper=50.0)
        o3_prediction = _predict_with_booster(o3_result.booster, o3_history, forecast_time, context_values=aqi_history)
        if so2_prediction is None:
            so2_prediction = _predict_component(reference.so2, latest.so2, latest.aqi, ensemble_prediction)
        if no2_prediction is None:
            no2_prediction = _predict_component(reference.no2, latest.no2, latest.aqi, ensemble_prediction)
        if co_prediction is None:
            co_prediction = _predict_component(reference.co, latest.co, latest.aqi, ensemble_prediction, upper=50.0)
        if o3_prediction is None:
            o3_prediction = _predict_component(reference.o3, latest.o3, latest.aqi, ensemble_prediction)

        prediction_rows.append(
            PredictionRecord(
                city=city,
                forecast_time=forecast_time,
                generated_at=generated_at,
                actual_aqi=reference.aqi,
                lstm_aqi=trend_prediction,
                xgboost_aqi=xgboost_prediction,
                ensemble_aqi=ensemble_prediction,
                pm25_pred=pm25_prediction,
                pm10_pred=pm10_prediction,
                so2_pred=so2_prediction,
                no2_pred=no2_prediction,
                co_pred=co_prediction,
                o3_pred=o3_prediction,
            )
        )
        aqi_history.append(ensemble_prediction)
        pm25_history.append(pm25_prediction)
        pm10_history.append(pm10_prediction)
        so2_history.append(so2_prediction)
        no2_history.append(no2_prediction)
        co_history.append(co_prediction)
        o3_history.append(o3_prediction)

    db.session.add_all(prediction_rows)
    db.session.commit()

    return {
        "status": "success",
        "message": f"已完成 {city} 的正式 XGBoost 训练，并基于最近 {len(records)} 条小时数据生成未来 {horizon} 小时预测。",
        "validation": [
            {
                "date": item.strftime("%m-%d %H:%M"),
                "actual": aqi_result.validation_actuals[index],
                "predicted": ensemble_predictions[index],
                "error": round(abs(aqi_result.validation_actuals[index] - ensemble_predictions[index]), 1),
            }
            for index, item in enumerate(aqi_result.validation_timestamps)
        ],
        "metrics": [
            {"model": "趋势基线", **trend_metrics},
            {"model": "XGBoost", **aqi_result.metrics},
            {"model": "融合模型", **ensemble_metrics},
        ],
        "generated_at": generated_at.strftime("%Y-%m-%d %H:%M"),
    }

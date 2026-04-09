from datetime import datetime

from .extensions import db


class AirQualityRecord(db.Model):
    __tablename__ = "air_quality_records"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(50), nullable=False, index=True)
    province = db.Column(db.String(50), nullable=False)
    record_time = db.Column(db.DateTime, nullable=False, index=True)
    aqi = db.Column(db.Integer, nullable=False)
    level = db.Column(db.String(20), nullable=False)
    primary_pollutant = db.Column(db.String(30), nullable=False)
    pm25 = db.Column(db.Float, nullable=False)
    pm10 = db.Column(db.Float, nullable=False)
    so2 = db.Column(db.Float, nullable=False)
    no2 = db.Column(db.Float, nullable=False)
    co = db.Column(db.Float, nullable=False)
    o3 = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    wind_speed = db.Column(db.Float, nullable=False)
    pressure = db.Column(db.Float, nullable=False)
    source_name = db.Column(db.String(60), default="system-seed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PredictionRecord(db.Model):
    __tablename__ = "prediction_records"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(50), nullable=False, index=True)
    forecast_time = db.Column(db.DateTime, nullable=False, index=True)
    generated_at = db.Column(db.DateTime, nullable=False, index=True)
    actual_aqi = db.Column(db.Float, nullable=False)
    lstm_aqi = db.Column(db.Float, nullable=False)
    xgboost_aqi = db.Column(db.Float, nullable=False)
    ensemble_aqi = db.Column(db.Float, nullable=False)
    pm25_pred = db.Column(db.Float, nullable=False)
    pm10_pred = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ModelMetric(db.Model):
    __tablename__ = "model_metrics"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(50), nullable=False, index=True)
    model_name = db.Column(db.String(30), nullable=False)
    mae = db.Column(db.Float, nullable=False)
    rmse = db.Column(db.Float, nullable=False)
    r2 = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, index=True)


class ForecastValidationRecord(db.Model):
    __tablename__ = "forecast_validation_records"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(50), nullable=False, index=True)
    validation_time = db.Column(db.DateTime, nullable=False, index=True)
    generated_at = db.Column(db.DateTime, nullable=False, index=True)
    actual_aqi = db.Column(db.Float, nullable=False)
    trend_aqi = db.Column(db.Float, nullable=False)
    xgboost_aqi = db.Column(db.Float, nullable=False)
    ensemble_aqi = db.Column(db.Float, nullable=False)
    error_value = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CrawlTaskLog(db.Model):
    __tablename__ = "crawl_task_logs"

    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(80), nullable=False)
    source_name = db.Column(db.String(80), nullable=False)
    target_url = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    records_count = db.Column(db.Integer, default=0, nullable=False)
    message = db.Column(db.String(255), default="", nullable=False)
    run_at = db.Column(db.DateTime, nullable=False, index=True)


class CrawlArtifact(db.Model):
    __tablename__ = "crawl_artifacts"

    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    article_url = db.Column(db.String(255), nullable=False)
    published_at = db.Column(db.String(30), default="", nullable=False)
    crawled_at = db.Column(db.DateTime, nullable=False, index=True)


class DataImportLog(db.Model):
    __tablename__ = "data_import_logs"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    source_name = db.Column(db.String(80), nullable=False, default="manual-upload")
    status = db.Column(db.String(20), nullable=False)
    total_rows = db.Column(db.Integer, default=0, nullable=False)
    success_rows = db.Column(db.Integer, default=0, nullable=False)
    inserted_rows = db.Column(db.Integer, default=0, nullable=False)
    updated_rows = db.Column(db.Integer, default=0, nullable=False)
    message = db.Column(db.String(255), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class AutoCollectionSetting(db.Model):
    __tablename__ = "auto_collection_settings"

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    interval_seconds = db.Column(db.Integer, nullable=False, default=1800)
    collection_hours = db.Column(db.Integer, nullable=False, default=24)
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(20), nullable=False, default="idle")
    last_message = db.Column(db.String(255), nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

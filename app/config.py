import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "air-quality-demo-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'air_quality_demo.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    CRAWLER_TIMEOUT = int(os.getenv("CRAWLER_TIMEOUT", "15"))
    LIVE_COLLECTION_HOURS = int(os.getenv("LIVE_COLLECTION_HOURS", "24"))
    COLLECTION_BATCH_SIZE = int(os.getenv("COLLECTION_BATCH_SIZE", "20"))
    COLLECTION_CHUNK_DAYS = int(os.getenv("COLLECTION_CHUNK_DAYS", "31"))
    AUTO_REALTIME_COLLECTION_ENABLED = os.getenv("AUTO_REALTIME_COLLECTION_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y"}
    REALTIME_COLLECTION_INTERVAL_SECONDS = int(os.getenv("REALTIME_COLLECTION_INTERVAL_SECONDS", "1800"))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    IMPORT_UPLOAD_DIR = BASE_DIR / "data" / "uploads"
    CITY_MASTER_PATH = BASE_DIR / "data" / "china_city_master.csv"

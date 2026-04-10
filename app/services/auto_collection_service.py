from __future__ import annotations

from datetime import datetime
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import Config
from ..extensions import db
from ..models import AutoCollectionSetting
from .collection_queue_service import enqueue_collection_job


JOB_ID = "auto_realtime_collection"
_scheduler = BackgroundScheduler(daemon=True)
_scheduler_lock = Lock()
_scheduler_started = False
_app_ref = None


def _get_or_create_setting() -> AutoCollectionSetting:
    setting = AutoCollectionSetting.query.first()
    if setting:
        return setting

    setting = AutoCollectionSetting(
        enabled=Config.AUTO_REALTIME_COLLECTION_ENABLED,
        interval_seconds=max(Config.REALTIME_COLLECTION_INTERVAL_SECONDS, 60),
        collection_hours=max(Config.LIVE_COLLECTION_HOURS, 1),
        last_status="idle",
        last_message="自动采集尚未执行。",
        updated_at=datetime.now(),
    )
    db.session.add(setting)
    db.session.commit()
    return setting


def _apply_schedule() -> None:
    if _app_ref is None:
        return

    with _app_ref.app_context():
        setting = _get_or_create_setting()
        enabled = bool(setting.enabled)
        interval_seconds = max(int(setting.interval_seconds), 60)

    job = _scheduler.get_job(JOB_ID)
    if job:
        _scheduler.remove_job(JOB_ID)

    if not enabled:
        return

    _scheduler.add_job(
        func=_run_auto_collection_job,
        trigger="interval",
        seconds=interval_seconds,
        id=JOB_ID,
        max_instances=1,
        replace_existing=True,
        coalesce=True,
    )


def ensure_scheduler_started(app) -> None:
    global _scheduler_started, _app_ref

    with _scheduler_lock:
        _app_ref = app
        if not _scheduler_started:
            _scheduler.start()
            _scheduler_started = True
        _apply_schedule()


def _run_auto_collection_job() -> None:
    if _app_ref is None:
        return

    queue_auto_collection_now(_app_ref, deduplicate=True)


def get_auto_collection_payload() -> dict:
    setting = _get_or_create_setting()
    job = _scheduler.get_job(JOB_ID) if _scheduler_started else None
    next_run_at = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job and job.next_run_time else ""
    return {
        "enabled": bool(setting.enabled),
        "interval_seconds": int(setting.interval_seconds),
        "collection_hours": int(setting.collection_hours),
        "last_run_at": setting.last_run_at.strftime("%Y-%m-%d %H:%M:%S") if setting.last_run_at else "",
        "last_status": setting.last_status,
        "last_message": setting.last_message,
        "next_run_at": next_run_at,
    }


def update_auto_collection_setting(enabled: bool, interval_seconds: int, collection_hours: int) -> dict:
    setting = _get_or_create_setting()
    setting.enabled = bool(enabled)
    setting.interval_seconds = max(int(interval_seconds), 60)
    setting.collection_hours = max(int(collection_hours), 1)
    setting.updated_at = datetime.now()
    if not setting.last_message:
        setting.last_message = "自动采集设置已更新。"
    db.session.commit()
    _apply_schedule()
    return get_auto_collection_payload()


def run_auto_collection_now() -> dict:
    setting = _get_or_create_setting()
    setting.last_run_at = datetime.now()
    setting.last_status = "running"
    setting.last_message = "自动采集任务执行中..."
    setting.updated_at = datetime.now()
    db.session.commit()

    from ..crawlers.open_meteo_collector import OpenMeteoRealtimeCollector

    result = OpenMeteoRealtimeCollector(hours=setting.collection_hours).run()
    setting.last_run_at = datetime.now()
    setting.last_status = result.get("status", "failed")
    setting.last_message = result.get("message", "")[:255]
    setting.updated_at = datetime.now()
    db.session.commit()
    return result


def queue_auto_collection_now(app, deduplicate: bool = False) -> dict:
    return enqueue_collection_job(
        app=app,
        worker=run_auto_collection_now,
        queue_key="auto_realtime_collection",
        deduplicate=deduplicate,
    )


def begin_auto_collection_run() -> None:
    setting = _get_or_create_setting()
    setting.last_run_at = datetime.now()
    setting.last_status = "running"
    setting.last_message = "自动采集任务执行中..."
    setting.updated_at = datetime.now()
    db.session.commit()


def finish_auto_collection_run(result: dict) -> dict:
    setting = _get_or_create_setting()
    setting.last_run_at = datetime.now()
    setting.last_status = result.get("status", "failed")
    setting.last_message = result.get("message", "")[:255]
    setting.updated_at = datetime.now()
    db.session.commit()
    return result

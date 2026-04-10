from __future__ import annotations

from queue import Queue
from threading import Lock, Thread
from typing import Callable

from .task_progress_service import append_task_log, get_task, update_task


QueueWorker = Callable[[], dict]


_queue: Queue[dict] = Queue()
_worker_lock = Lock()
_worker_started = False
_queued_keys: set[str] = set()
_running_keys: set[str] = set()


def _finalize_task(task_id: str, result: dict) -> None:
    final_status = result.get("status", "success")
    current_task = get_task(task_id) or {}
    current_progress = int(current_task.get("progress", 0) or 0)
    update_task(
        task_id,
        status=final_status,
        status_label="Success" if final_status == "success" else "Failed",
        progress=100 if final_status == "success" else min(current_progress, 99),
        message=result.get("message", ""),
        finished_at=current_task.get("finished_at", "") or __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        result=result,
    )
    append_task_log(
        task_id,
        result.get("message", "Task finished."),
        "success" if final_status == "success" else "error",
    )


def _run_item(item: dict) -> None:
    task_id = item.get("task_id")
    queue_key = item.get("queue_key")
    on_started = item.get("on_started")
    on_finished = item.get("on_finished")
    on_error = item.get("on_error")

    with _worker_lock:
        if queue_key:
            _queued_keys.discard(queue_key)
            _running_keys.add(queue_key)

    try:
        if task_id:
            update_task(task_id, status="running", status_label="Running", progress=2)
            append_task_log(task_id, "Task started from the single collection queue.")

        if on_started:
            on_started()

        with item["app"].app_context():
            result = item["worker"]()

        if on_finished:
            on_finished(result)

        if task_id:
            _finalize_task(task_id, result)
    except Exception as exc:
        if on_error:
            on_error(exc)

        if task_id:
            update_task(
                task_id,
                status="failed",
                status_label="Failed",
                message=str(exc),
                finished_at=__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            append_task_log(task_id, f"Task terminated with an error: {exc}", "error")
    finally:
        with _worker_lock:
            if queue_key:
                _running_keys.discard(queue_key)
        _queue.task_done()


def _worker_loop() -> None:
    while True:
        item = _queue.get()
        _run_item(item)


def ensure_collection_queue_started() -> None:
    global _worker_started

    with _worker_lock:
        if _worker_started:
            return
        thread = Thread(target=_worker_loop, daemon=True)
        thread.start()
        _worker_started = True


def enqueue_collection_job(
    *,
    app,
    worker: QueueWorker,
    task_id: str | None = None,
    queue_key: str | None = None,
    deduplicate: bool = False,
    queued_message: str | None = None,
    on_started: Callable[[], None] | None = None,
    on_finished: Callable[[dict], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> dict:
    ensure_collection_queue_started()

    with _worker_lock:
        if queue_key and deduplicate and (queue_key in _queued_keys or queue_key in _running_keys):
            return {
                "status": "queued",
                "message": "A collection task of the same type is already queued or running.",
            }
        if queue_key:
            _queued_keys.add(queue_key)
        queue_size = _queue.qsize()

    if task_id:
        message = queued_message or f"Queued successfully. {queue_size} task(s) ahead."
        update_task(task_id, status="pending", status_label="Queued", progress=0, message=message)
        append_task_log(task_id, message)

    _queue.put(
        {
            "app": app,
            "worker": worker,
            "task_id": task_id,
            "queue_key": queue_key,
            "on_started": on_started,
            "on_finished": on_finished,
            "on_error": on_error,
        }
    )

    return {
        "status": "queued",
        "queue_size": queue_size,
    }

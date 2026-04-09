from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4


_TASKS: dict[str, dict] = {}
_LOCK = Lock()


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_task(task_type: str, title: str, metadata: dict | None = None) -> str:
    task_id = uuid4().hex
    with _LOCK:
        _TASKS[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "title": title,
            "status": "pending",
            "status_label": "等待中",
            "progress": 0,
            "message": "",
            "started_at": _now_text(),
            "finished_at": "",
            "result": None,
            "metadata": metadata or {},
            "logs": [
                {
                    "time": _now_text(),
                    "level": "info",
                    "message": "任务已创建，等待执行。",
                }
            ],
        }
    return task_id


def append_task_log(task_id: str, message: str, level: str = "info") -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task["logs"].append(
            {
                "time": _now_text(),
                "level": level,
                "message": message,
            }
        )
        task["logs"] = task["logs"][-200:]


def update_task(task_id: str, **fields) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task.update(fields)


def get_task(task_id: str) -> dict | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        return deepcopy(task) if task else None


def run_task_in_background(app, task_id: str, worker: Callable[[], dict]) -> None:
    def runner():
        try:
            update_task(task_id, status="running", status_label="执行中", progress=2)
            append_task_log(task_id, "后台任务已启动。")
            with app.app_context():
                result = worker()
            final_status = result.get("status", "success")
            update_task(
                task_id,
                status=final_status,
                status_label="成功" if final_status == "success" else "失败",
                progress=100 if final_status == "success" else min(get_task(task_id).get("progress", 0), 99),
                message=result.get("message", ""),
                finished_at=_now_text(),
                result=result,
            )
            append_task_log(task_id, result.get("message", "任务执行完成。"), "success" if final_status == "success" else "error")
        except Exception as exc:
            update_task(
                task_id,
                status="failed",
                status_label="失败",
                message=str(exc),
                finished_at=_now_text(),
            )
            append_task_log(task_id, f"任务异常终止：{exc}", "error")

    thread = Thread(target=runner, daemon=True)
    thread.start()

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path

from ..config import BASE_DIR, Config
from ..extensions import db
from ..models import CrawlTaskLog
from ..services.city_master_service import get_resolved_city_master
from ..services.import_service import import_air_quality_file
from ..services.open_meteo_service import collect_realtime_rows, save_csv


class OpenMeteoRealtimeCollector:
    source_name = "Open-Meteo API"
    task_name = "真实小时空气质量采集"
    target_url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(self, timeout: int | None = None, hours: int | None = None):
        self.timeout = timeout or Config.CRAWLER_TIMEOUT
        self.hours = hours or Config.LIVE_COLLECTION_HOURS

    def run(self) -> dict:
        return self.run_with_progress()

    def run_with_progress(self, progress_callback=None) -> dict:
        run_at = datetime.now()
        try:
            if progress_callback:
                progress_callback(5, "正在加载城市主数据并解析可用坐标...")
            cities, unresolved_cities = get_resolved_city_master(resolve_missing=True)
            if progress_callback:
                progress_callback(10, f"已准备 {len(cities)} 个可采集城市，开始分批抓取真实小时数据...")

            total_batches = max(math.ceil(len(cities) / Config.COLLECTION_BATCH_SIZE), 1)

            def batch_progress(completed_batches, total_rows, batch_failed, batch_cities):
                progress = min(18 + int(completed_batches / total_batches * 62), 82)
                if progress_callback:
                    city_text = "、".join(batch_cities[:6])
                    if len(batch_cities) > 6:
                        city_text = f"{city_text} 等 {len(batch_cities)} 个城市"
                    if batch_failed:
                        progress_callback(
                            progress,
                            f"第 {completed_batches}/{total_batches} 批抓取完成，累计 {total_rows} 行；本批失败城市：{'、'.join(batch_failed[:8])}",
                            level="error",
                        )
                    else:
                        progress_callback(
                            progress,
                            f"第 {completed_batches}/{total_batches} 批抓取完成，累计 {total_rows} 行；本批城市：{city_text}",
                        )

            rows, failed_cities = collect_realtime_rows(
                hours=self.hours,
                timeout=self.timeout,
                cities=cities,
                progress_callback=batch_progress,
            )
            if not rows:
                raise ValueError("未获取到任何真实小时数据，请稍后重试。")

            timestamp = run_at.strftime("%Y%m%d_%H%M%S")
            file_name = f"real_air_quality_realtime_{timestamp}.csv"
            output_path = Path(BASE_DIR) / "data" / file_name
            if progress_callback:
                progress_callback(88, f"抓取完成，正在生成 CSV 文件：{file_name}")
            save_csv(rows, output_path)

            if progress_callback:
                progress_callback(93, "CSV 已生成，正在导入数据库并计算 AQI...")
            import_result = import_air_quality_file(
                output_path,
                mode="realtime",
                source_name="open-meteo-live",
                file_name=file_name,
            )
            city_count = len(import_result.get("cities", []))
            message = f"已采集并导入 {import_result.get('success_rows', 0)} 条小时数据，覆盖 {city_count} 个城市。"
            all_failed = failed_cities + unresolved_cities
            if all_failed:
                message = f"{message} 未完成城市：{'、'.join(all_failed[:20])}"
                if len(all_failed) > 20:
                    message = f"{message} 等 {len(all_failed)} 个。"
                else:
                    message = f"{message}。"

            db.session.add(
                CrawlTaskLog(
                    task_name=self.task_name,
                    source_name=self.source_name,
                    target_url=self.target_url,
                    status="success",
                    records_count=len(rows),
                    message=message[:250],
                    run_at=run_at,
                )
            )
            db.session.commit()
            if progress_callback:
                progress_callback(100, message)
            return {
                "status": "success",
                "run_at": run_at.strftime("%Y-%m-%d %H:%M"),
                "records_count": len(rows),
                "city_count": city_count,
                "failed_cities": all_failed,
                "file_name": file_name,
                "import_result": import_result,
                "message": message,
                }
        except Exception as exc:
            db.session.rollback()
            db.session.add(
                CrawlTaskLog(
                    task_name=self.task_name,
                    source_name=self.source_name,
                    target_url=self.target_url,
                    status="failed",
                    records_count=0,
                    message=str(exc)[:250],
                    run_at=run_at,
                )
            )
            db.session.commit()
            if progress_callback:
                progress_callback(0, f"真实小时数据采集失败：{exc}", level="error")
            return {
                "status": "failed",
                "run_at": run_at.strftime("%Y-%m-%d %H:%M"),
                "records_count": 0,
                "message": str(exc),
            }

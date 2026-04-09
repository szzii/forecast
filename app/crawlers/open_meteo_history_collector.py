from __future__ import annotations

from datetime import date, datetime
import math
from pathlib import Path

from ..config import BASE_DIR, Config
from ..extensions import db
from ..models import CrawlTaskLog
from ..services.city_master_service import get_resolved_city_master
from ..services.import_service import import_air_quality_file
from ..services.open_meteo_service import append_csv_rows, iter_history_rows


class OpenMeteoHistoryCollector:
    source_name = "Open-Meteo API"
    task_name = "历史区间空气质量采集"
    target_url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(
        self,
        start_date: date,
        end_date: date,
        scope: str = "all",
        province: str | None = None,
        cities: list[str] | None = None,
        timeout: int | None = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.scope = scope if scope in {"all", "province", "city"} else "all"
        self.province = province
        self.cities = cities or []
        self.timeout = timeout or Config.CRAWLER_TIMEOUT

    def _scope_label(self) -> str:
        if self.scope == "province" and self.province:
            return self.province
        if self.scope == "city" and self.cities:
            if len(self.cities) == 1:
                return self.cities[0]
            return f"{self.cities[0]}等{len(self.cities)}城"
        return "all"

    def run(self) -> dict:
        return self.run_with_progress()

    def run_with_progress(self, progress_callback=None) -> dict:
        run_at = datetime.now()
        try:
            if progress_callback:
                progress_callback(3, "正在加载城市主数据并解析可用坐标...")
            cities, unresolved_cities = get_resolved_city_master(
                scope=self.scope,
                province=self.province,
                cities=self.cities,
                resolve_missing=True,
            )
            if not cities:
                raise ValueError("当前范围内没有可用城市坐标，请先生成城市主数据。")
            if progress_callback:
                progress_callback(8, f"已选定 {len(cities)} 个可采集城市，开始拆分日期区间与城市批次。")

            timestamp = run_at.strftime("%Y%m%d_%H%M%S")
            scope_label = self._scope_label()
            file_name = (
                f"air_quality_history_{scope_label}_{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}_{timestamp}.csv"
            )
            output_path = Path(BASE_DIR) / "data" / file_name

            total_rows = 0
            failed_cities = list(unresolved_cities)
            wrote_header = False
            day_count = (self.end_date - self.start_date).days + 1
            chunk_total = math.ceil(day_count / Config.COLLECTION_CHUNK_DAYS)
            batch_total = math.ceil(len(cities) / Config.COLLECTION_BATCH_SIZE)
            total_steps = max(chunk_total * batch_total, 1)
            processed_steps = 0

            for rows, batch_failed, meta in iter_history_rows(
                cities,
                start_date=self.start_date,
                end_date=self.end_date,
                timeout=self.timeout,
                source_name="open-meteo-history",
            ):
                processed_steps += 1
                progress = min(10 + int(processed_steps / total_steps * 75), 88)
                if progress_callback:
                    progress_callback(
                        progress,
                        f"正在采集第 {processed_steps}/{total_steps} 批：{meta['chunk_start']} 至 {meta['chunk_end']}，"
                        f"{meta['city_count']} 个城市。",
                    )
                if rows:
                    append_csv_rows(rows, output_path, write_header=not wrote_header)
                    wrote_header = True
                    total_rows += len(rows)
                    if progress_callback:
                        progress_callback(
                            progress,
                            f"第 {processed_steps}/{total_steps} 批完成，新增 {len(rows)} 行数据，累计 {total_rows} 行。",
                        )
                if batch_failed:
                    failed_cities.extend(batch_failed)
                    if progress_callback:
                        progress_callback(
                            progress,
                            f"第 {processed_steps}/{total_steps} 批有 {len(batch_failed)} 个城市未完成：{'、'.join(batch_failed[:8])}",
                        )

            if total_rows == 0:
                raise ValueError("未获取到历史空气质量数据，请缩小时间范围后重试。")

            if progress_callback:
                progress_callback(92, "历史数据抓取完成，正在导入数据库并计算 AQI...")
            import_result = import_air_quality_file(
                output_path,
                mode="realtime",
                source_name="open-meteo-history",
                file_name=file_name,
            )
            city_count = len(import_result.get("cities", []))
            message = (
                f"已采集 {self.start_date.isoformat()} 至 {self.end_date.isoformat()} 的历史小时数据，"
                f"共导入 {import_result.get('success_rows', 0)} 行，覆盖 {city_count} 个城市。"
            )
            if failed_cities:
                unique_failed = sorted(set(failed_cities))
                message = f"{message} 未完成城市：{'、'.join(unique_failed[:20])}"
                if len(unique_failed) > 20:
                    message = f"{message} 等 {len(unique_failed)} 个。"
                else:
                    message = f"{message}。"

            db.session.add(
                CrawlTaskLog(
                    task_name=self.task_name,
                    source_name=self.source_name,
                    target_url=self.target_url,
                    status="success",
                    records_count=total_rows,
                    message=message[:250],
                    run_at=run_at,
                )
            )
            db.session.commit()
            if progress_callback:
                progress_callback(100, f"历史采集完成，成功导入 {import_result.get('success_rows', 0)} 行，覆盖 {city_count} 个城市。")
            return {
                "status": "success",
                "run_at": run_at.strftime("%Y-%m-%d %H:%M"),
                "records_count": total_rows,
                "city_count": city_count,
                "selected_city_count": len(cities),
                "failed_cities": sorted(set(failed_cities)),
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
                progress_callback(0, f"历史采集失败：{exc}", level="error")
            return {
                "status": "failed",
                "run_at": run_at.strftime("%Y-%m-%d %H:%M"),
                "records_count": 0,
                "message": str(exc),
            }

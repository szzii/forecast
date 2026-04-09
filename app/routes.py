from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from .config import Config
from .crawlers.mee_crawler import MEEPublicReportCrawler
from .crawlers.open_meteo_collector import OpenMeteoRealtimeCollector
from .crawlers.open_meteo_history_collector import OpenMeteoHistoryCollector
from .services.city_master_service import city_master_metadata
from .services.auto_collection_service import (
    begin_auto_collection_run,
    finish_auto_collection_run,
    get_auto_collection_payload,
    run_auto_collection_now,
    update_auto_collection_setting,
)
from .services.forecast_service import generate_forecast_for_city
from .services.import_service import import_air_quality_dataset
from .services.repository import (
    get_crawler_status,
    get_forecast,
    get_import_logs,
    get_overview,
    get_screen_payload,
    get_trend,
    list_cities,
    list_years,
)
from .services.task_progress_service import append_task_log, create_task, get_task, run_task_in_background, update_task


pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__, url_prefix="/api")


@pages.route("/")
def home():
    return render_template("index.html")


@pages.route("/trend")
def trend():
    return render_template("trend.html")


@pages.route("/forecast")
def forecast():
    return render_template("forecast.html")


@pages.route("/collect")
def collect():
    return render_template("collect.html")


@pages.route("/screen")
def screen():
    return render_template("screen.html")


@api.route("/cities")
def cities():
    cities_data = list_cities()
    years = list_years()
    return jsonify(
        {
            "cities": cities_data,
            "default_city": "南京" if "南京" in cities_data else (cities_data[0] if cities_data else ""),
            "years": years,
            "default_year": years[0] if years else datetime.now().year,
        }
    )


@api.route("/overview")
def overview():
    city = request.args.get("city", "南京")
    return jsonify(get_overview(city))


@api.route("/trend")
def trend_data():
    city = request.args.get("city", "南京")
    years = list_years()
    year = int(request.args.get("year", str(years[0] if years else datetime.now().year)))
    return jsonify(get_trend(city, year))


@api.route("/forecast")
def forecast_data():
    city = request.args.get("city", "南京")
    return jsonify(get_forecast(city))


@api.route("/forecast/generate", methods=["POST"])
def generate_forecast():
    city = request.get_json(silent=True) or {}
    target_city = city.get("city") or request.args.get("city", "南京")
    result = generate_forecast_for_city(target_city)
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


@api.route("/crawler")
def crawler_data():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 10, type=int)
    return jsonify(get_crawler_status(page=page, page_size=page_size))


@api.route("/crawler/run", methods=["POST"])
def run_crawler():
    crawler = MEEPublicReportCrawler()
    return jsonify(crawler.run())


@api.route("/collector/realtime/run", methods=["POST"])
def run_realtime_collector():
    collector = OpenMeteoRealtimeCollector()
    result = collector.run()
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


@api.route("/collector/metadata")
def collector_metadata():
    return jsonify(city_master_metadata())


@api.route("/collector/auto-settings")
def collector_auto_settings():
    return jsonify(get_auto_collection_payload())


@api.route("/collector/auto-settings", methods=["POST"])
def update_collector_auto_settings():
    payload = request.get_json(silent=True) or request.form or {}
    enabled = str(payload.get("enabled", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    interval_seconds = payload.get(
        "interval_seconds",
        current_app.config.get("REALTIME_COLLECTION_INTERVAL_SECONDS", Config.REALTIME_COLLECTION_INTERVAL_SECONDS),
    )
    collection_hours = payload.get(
        "collection_hours",
        current_app.config.get("LIVE_COLLECTION_HOURS", Config.LIVE_COLLECTION_HOURS),
    )
    try:
        result = update_auto_collection_setting(
            enabled=enabled,
            interval_seconds=int(interval_seconds),
            collection_hours=int(collection_hours),
        )
    except ValueError:
        return jsonify({"status": "failed", "message": "自动采集间隔和采集时长必须为整数。"}), 400
    result["status"] = "success"
    result["message"] = "自动采集定时任务设置已保存。"
    return jsonify(result)


@api.route("/collector/auto-settings/run-now", methods=["POST"])
def run_collector_auto_settings_now():
    result = run_auto_collection_now()
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


@api.route("/collector/realtime/start", methods=["POST"])
def start_realtime_collector():
    task_id = create_task(
        task_type="realtime_collection",
        title="真实小时数据采集",
        metadata={"hours": current_app.config.get("LIVE_COLLECTION_HOURS", Config.LIVE_COLLECTION_HOURS)},
    )
    app = current_app._get_current_object()

    def worker():
        collector = OpenMeteoRealtimeCollector()
        begin_auto_collection_run()

        def progress_callback(progress, message, level="info"):
            update_task(task_id, progress=progress, message=message)
            append_task_log(task_id, message, level=level)

        result = collector.run_with_progress(progress_callback=progress_callback)
        finish_auto_collection_run(result)
        return result

    run_task_in_background(app, task_id, worker)
    task = get_task(task_id)
    return jsonify(task), 202


@api.route("/collector/realtime/tasks/<task_id>")
def realtime_collector_task(task_id):
    task = get_task(task_id)
    if not task:
        return jsonify({"status": "failed", "message": "未找到该实时采集任务。"}), 404
    return jsonify(task)


@api.route("/collector/history/run", methods=["POST"])
def run_history_collector():
    payload = request.get_json(silent=True) or request.form or {}
    start_date_text = payload.get("start_date")
    end_date_text = payload.get("end_date")
    if not start_date_text or not end_date_text:
        return jsonify({"status": "failed", "message": "请提供开始日期和结束日期。"}), 400

    try:
        start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_text, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"status": "failed", "message": "日期格式应为 YYYY-MM-DD。"}), 400

    if start_date > end_date:
        return jsonify({"status": "failed", "message": "开始日期不能晚于结束日期。"}), 400

    scope = payload.get("scope", "all")
    province = payload.get("province")
    cities = payload.get("cities") or []
    if isinstance(cities, str):
        cities = [item.strip() for item in cities.split(",") if item.strip()]

    collector = OpenMeteoHistoryCollector(
        start_date=start_date,
        end_date=end_date,
        scope=scope,
        province=province,
        cities=cities,
    )
    result = collector.run()
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


@api.route("/collector/history/start", methods=["POST"])
def start_history_collector():
    payload = request.get_json(silent=True) or request.form or {}
    start_date_text = payload.get("start_date")
    end_date_text = payload.get("end_date")
    if not start_date_text or not end_date_text:
        return jsonify({"status": "failed", "message": "请提供开始日期和结束日期。"}), 400

    try:
        start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_text, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"status": "failed", "message": "日期格式应为 YYYY-MM-DD。"}), 400

    if start_date > end_date:
        return jsonify({"status": "failed", "message": "开始日期不能晚于结束日期。"}), 400

    scope = payload.get("scope", "all")
    province = payload.get("province")
    cities = payload.get("cities") or []
    if isinstance(cities, str):
        cities = [item.strip() for item in cities.split(",") if item.strip()]

    task_id = create_task(
        task_type="history_collection",
        title="历史范围采集",
        metadata={
            "start_date": start_date_text,
            "end_date": end_date_text,
            "scope": scope,
            "province": province or "",
            "cities": cities,
        },
    )
    app = current_app._get_current_object()

    def worker():
        collector = OpenMeteoHistoryCollector(
            start_date=start_date,
            end_date=end_date,
            scope=scope,
            province=province,
            cities=cities,
        )

        def progress_callback(progress, message, level="info"):
            update_task(task_id, progress=progress, message=message)
            append_task_log(task_id, message, level=level)

        return collector.run_with_progress(progress_callback=progress_callback)

    run_task_in_background(app, task_id, worker)
    task = get_task(task_id)
    return jsonify(task), 202


@api.route("/collector/history/tasks/<task_id>")
def history_collector_task(task_id):
    task = get_task(task_id)
    if not task:
        return jsonify({"status": "failed", "message": "未找到该历史采集任务。"}), 404
    return jsonify(task)


@api.route("/imports")
def import_logs():
    return jsonify(get_import_logs())


@api.route("/imports", methods=["POST"])
def import_data():
    mode = request.form.get("mode", "daily")
    file_storage = request.files.get("file")
    try:
        result = import_air_quality_dataset(file_storage, mode=mode)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"status": "failed", "message": str(exc)}), 400


@api.route("/screen")
def screen_data():
    city = request.args.get("city")
    return jsonify(get_screen_payload(city))


@pages.route("/sample-import-file")
def sample_import_file():
    sample_path = Path(__file__).resolve().parent.parent / "data" / "air_quality_import_template.csv"
    return send_file(sample_path, as_attachment=True)


def register_blueprints(app):
    app.register_blueprint(pages)
    app.register_blueprint(api)

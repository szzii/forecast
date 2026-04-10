from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.city_master_service import get_resolved_city_master
from app.services.open_meteo_service import collect_realtime_rows, save_csv


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path("data") / f"real_air_quality_realtime_{timestamp}.csv"

    cities, unresolved_cities = get_resolved_city_master(resolve_missing=True)
    rows, failed_cities = collect_realtime_rows(hours=24, timeout=30, cities=cities)
    if not rows:
        raise SystemExit("未获取到任何真实小时数据。")

    save_csv(rows, output_path)

    print(f"saved={output_path}")
    print(f"rows={len(rows)}")
    print(f"cities={len(cities)}")
    if failed_cities or unresolved_cities:
        print(f"failed_cities={','.join(sorted(set(failed_cities + unresolved_cities)))}")


if __name__ == "__main__":
    main()

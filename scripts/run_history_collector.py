from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.crawlers.open_meteo_history_collector import OpenMeteoHistoryCollector


def main() -> None:
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    app = create_app()
    with app.app_context():
        result = OpenMeteoHistoryCollector(
            start_date=start_date,
            end_date=end_date,
            scope="all",
        ).run()
        print(result)


if __name__ == "__main__":
    main()

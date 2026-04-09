from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.crawlers.open_meteo_collector import OpenMeteoRealtimeCollector


def main() -> None:
    app = create_app()
    with app.app_context():
        result = OpenMeteoRealtimeCollector().run()
        print(result)


if __name__ == "__main__":
    main()

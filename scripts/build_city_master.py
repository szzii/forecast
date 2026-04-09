from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.city_master_service import load_city_master, resolve_missing_city_coordinates


def main() -> None:
    rows = load_city_master()
    rows = resolve_missing_city_coordinates(rows, max_workers=8)
    resolved = sum(1 for item in rows if item.get("latitude") and item.get("longitude") and item.get("enabled") == "1")
    print(f"total={len(rows)}")
    print(f"resolved={resolved}")
    print(f"unresolved={len(rows) - resolved}")


if __name__ == "__main__":
    main()

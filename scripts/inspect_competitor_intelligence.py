from commercepilot.db.session import SessionLocal
from commercepilot.services.competitor_intelligence import (
    analyze_competitor_prices,
)


def main() -> None:
    with SessionLocal() as session:
        changes = analyze_competitor_prices(session, "NOVA-AUDIO-001")

    for change in changes:
        print(change.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

from app.db.session import SessionLocal
from app.services.seed import seed_foundation_data


def main() -> None:
    db = SessionLocal()
    try:
        seed_foundation_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()


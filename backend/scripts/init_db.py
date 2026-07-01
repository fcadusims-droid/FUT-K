"""Create every table (idempotent). Run once before starting the API:

    DATABASE_URL=postgresql+psycopg://fie_app:pw@localhost/fie_dev python scripts/init_db.py
"""

from __future__ import annotations

from app.db import engine, init_db


def main():
    init_db()
    print(f"Schema ready at {engine.url}")


if __name__ == "__main__":
    main()

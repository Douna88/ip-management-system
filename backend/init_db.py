"""Database initialization: create tables + load the full demo dataset.

Run `python init_db.py` on a fresh database to reproduce the complete showcase
data (94 trademarks, 6 patents, 5 employees, fee standards, bonus rules, ...).

The dataset is stored in `seed_data.sql` and loaded by `seed_demo.load_demo_data`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import engine, SessionLocal, Base
from app.models import SysUser
from seed_demo import load_demo_data


def init_db():
    """Create all tables and load the full demo dataset."""
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    db = SessionLocal()

    # Check if already seeded
    if db.query(SysUser).count() > 0:
        print("Database already has data. Skipping seed.")
        db.close()
        return

    load_demo_data(db)
    db.close()

    print("\n=== Database initialization complete! ===")
    print("Login: admin / admin123")
    print("API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    init_db()

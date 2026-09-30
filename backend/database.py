"""
Life-Link: Database Configuration & Schema Migration
Using SQLite for a simple, zero-configuration local database.
Includes auto-migration helper to safely ensure new columns exist without breaking existing databases.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database file stored locally in the backend directory
SQLALCHEMY_DATABASE_URL = "sqlite:///./lifelink.db"

# connect_args={"check_same_thread": False} is required for SQLite with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Each instance of SessionLocal will be a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our SQLAlchemy models to inherit from
Base = declarative_base()


def ensure_schema_upgrades(db_engine):
    """
    Safely inspects existing SQLite tables and adds any newly introduced columns.
    Ensures backwards compatibility with existing databases.
    """
    with db_engine.connect() as conn:
        # Check emergency_requests columns
        try:
            res = conn.execute(text("PRAGMA table_info(emergency_requests)")).fetchall()
            existing_cols = {row[1] for row in res}
            if existing_cols:
                if "user_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE emergency_requests ADD COLUMN user_id INTEGER"))
                if "requester_name" not in existing_cols:
                    conn.execute(text("ALTER TABLE emergency_requests ADD COLUMN requester_name TEXT"))
                if "hospital_confirmed" not in existing_cols:
                    conn.execute(text("ALTER TABLE emergency_requests ADD COLUMN hospital_confirmed BOOLEAN DEFAULT 0"))
                if "screening_status" not in existing_cols:
                    conn.execute(text("ALTER TABLE emergency_requests ADD COLUMN screening_status TEXT DEFAULT 'PENDING'"))
                if "donation_completed" not in existing_cols:
                    conn.execute(text("ALTER TABLE emergency_requests ADD COLUMN donation_completed BOOLEAN DEFAULT 0"))
                conn.commit()
        except Exception as e:
            print("Auto-migration notice (emergency_requests):", e)

        # Check donors columns
        try:
            res = conn.execute(text("PRAGMA table_info(donors)")).fetchall()
            existing_cols = {row[1] for row in res}
            if existing_cols:
                if "user_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE donors ADD COLUMN user_id INTEGER"))
                conn.commit()
        except Exception as e:
            print("Auto-migration notice (donors):", e)


def get_db():
    """
    Dependency that provides a database session for each request
    and ensures it is properly closed when the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

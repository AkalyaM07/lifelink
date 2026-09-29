"""
Life-Link: Database Configuration
Using SQLite for a simple, zero-configuration local database.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database file stored locally in the backend directory
SQLALCHEMY_DATABASE_URL = "sqlite:///./lifelink.db"

# connect_args={"check_same_thread": False} is required for SQLite with FastAPI
# because FastAPI handles requests across multiple threads.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Each instance of SessionLocal will be a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our SQLAlchemy models to inherit from
Base = declarative_base()


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

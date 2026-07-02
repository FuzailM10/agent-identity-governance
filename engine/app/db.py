"""Database wiring for the control plane.

SQLAlchemy is our ORM: it maps Python objects <-> Postgres tables so we
don't write raw SQL for everything. `Base` is the parent class every table
model inherits from; `get_db()` hands each request a short-lived session.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Default matches docker-compose; overridable via env for other environments.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/aig",
)

# pool_pre_ping avoids "server closed the connection" errors after idle time.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
Database configuration and session management for SQLAlchemy.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator
import os
import logging

from app.core.config import settings
from app.models.collection import Base

# Import all models to register them with Base
from app.models.collection import Collection
from app.models.chat import ChatSession, ChatMessage

# Configure logging
logger = logging.getLogger(__name__)

# Create engine with appropriate settings
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite specific configuration
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,  # Allow multiple threads
            "timeout": 20,  # 20 second timeout
        },
        echo=settings.DEBUG,  # Log SQL queries in debug mode
    )

    # Enable WAL mode for better concurrency in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()
else:
    # PostgreSQL or other database configuration
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


def drop_tables():
    """Drop all database tables (use with caution!)."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session with proper cleanup.

    Usage:
        with get_db_session() as db:
            result = db.query(Collection).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.

    Usage in FastAPI endpoints:
        @router.get("/")
        async def endpoint(db: Session = Depends(get_db)):
            return db.query(Collection).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize database with tables and default data."""
    try:
        # Create tables
        create_tables()

        # Check if database file exists and is accessible
        if settings.DATABASE_URL.startswith("sqlite"):
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            if os.path.exists(db_path):
                file_size = os.path.getsize(db_path)
                logger.info(f"Database file: {db_path} (size: {file_size} bytes)")
            else:
                logger.info(f"Database file will be created at: {db_path}")

        logger.info("Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def get_db_info() -> dict:
    """Get database information and status."""
    try:
        info = {
            "database_url": settings.DATABASE_URL,
            "engine_name": engine.name,
            "tables": list(Base.metadata.tables.keys()),
        }

        if settings.DATABASE_URL.startswith("sqlite"):
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            info.update(
                {
                    "file_exists": os.path.exists(db_path),
                    "file_size": os.path.getsize(db_path)
                    if os.path.exists(db_path)
                    else 0,
                    "file_path": db_path,
                }
            )

        # Test connection
        with get_db_session() as db:
            # Simple query to test connection
            result = db.execute("SELECT 1").scalar()
            info["connection_test"] = "success" if result == 1 else "failed"

        return info

    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {
            "error": str(e),
            "database_url": settings.DATABASE_URL,
            "connection_test": "failed",
        }


class DatabaseManager:
    """Database manager for handling common database operations."""

    @staticmethod
    def health_check() -> dict:
        """Perform database health check."""
        try:
            with get_db_session() as db:
                # Test basic query
                result = db.execute("SELECT 1").scalar()

                # Get table counts
                table_counts = {}
                for table_name in Base.metadata.tables.keys():
                    try:
                        count = db.execute(
                            f"SELECT COUNT(*) FROM {table_name}"
                        ).scalar()
                        table_counts[table_name] = count
                    except Exception as e:
                        table_counts[table_name] = f"error: {e}"

                return {
                    "status": "healthy",
                    "connection": "ok",
                    "tables": table_counts,
                    "database_info": get_db_info(),
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection": "failed",
            }

    @staticmethod
    def reset_database():
        """Reset database by dropping and recreating all tables."""
        logger.warning("Resetting database - all data will be lost!")
        drop_tables()
        create_tables()
        logger.info("Database reset completed")


# Initialize database on import
if __name__ != "__main__":
    init_database()

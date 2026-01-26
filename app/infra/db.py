"""
SQLAlchemy database models and configuration.

Architecture Decision: Why SQLAlchemy?
- Provides ORM for cleaner code and prevents SQL injection
- Supports async operations for non-blocking database access
- Easy to migrate to PostgreSQL or other databases if needed
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Boolean, Text, ForeignKey


# Base class for all models
class Base(DeclarativeBase):
    pass


class TaskModel(Base):
    """SQLAlchemy model for Task entity"""
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TimeEntryModel(Base):
    """SQLAlchemy model for TimeEntry entity"""
    __tablename__ = "time_entries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    was_interrupted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interruption_handled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class DatabaseEngine:
    """
    Manages database connection and session lifecycle.
    
    Singleton pattern ensures only one engine exists per application.
    """
    _instance: Optional['DatabaseEngine'] = None
    
    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    
    @classmethod
    def get_instance(cls, db_url: Optional[str] = None) -> 'DatabaseEngine':
        """Get or create the database engine instance"""
        if cls._instance is None:
            if db_url is None:
                # Default: Store in user's AppData on Windows, ~/.local/share on Linux
                if os.name == 'nt':  # Windows
                    data_dir = Path(os.getenv('APPDATA')) / 'TimeTracker'
                else:  # Linux/Mac
                    data_dir = Path.home() / '.local' / 'share' / 'timetracker'
                
                data_dir.mkdir(parents=True, exist_ok=True)
                db_path = data_dir / 'timetracker.db'
                db_url = f"sqlite+aiosqlite:///{db_path}"
            
            cls._instance = cls(db_url)
        return cls._instance
    
    async def create_tables(self):
        """Create all tables in the database"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    def get_session(self) -> AsyncSession:
        """Get a new database session"""
        return self.session_factory()


# Convenience functions
def get_engine(db_url: Optional[str] = None) -> DatabaseEngine:
    """Get the database engine instance"""
    return DatabaseEngine.get_instance(db_url)


async def init_db(db_url: Optional[str] = None):
    """Initialize the database (create tables)"""
    engine = get_engine(db_url)
    await engine.create_tables()

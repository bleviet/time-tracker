"""
Repository Pattern Implementation.

Architecture Decision: Why Repository Pattern?
Separates data access logic from business logic. Makes it easy to:
- Switch database implementations
- Add caching
- Mock data for testing
- Change data sources (local DB to cloud API)
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Task, TimeEntry
from app.infra.db import TaskModel, TimeEntryModel, get_engine


class TaskRepository:
    """
    Handles all Task-related database operations.
    
    Converts between domain models (Pydantic) and ORM models (SQLAlchemy).
    """
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
    
    async def _get_session(self) -> AsyncSession:
        """Get session - either injected or create new one"""
        if self.session:
            return self.session
        engine = get_engine()
        return engine.get_session()
    
    async def get_all_active(self) -> List[Task]:
        """Get all non-archived tasks"""
        session = await self._get_session()
        async with session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.is_active == True)
            )
            task_models = result.scalars().all()
            return [Task.model_validate(tm) for tm in task_models]
    
    async def get_by_id(self, task_id: int) -> Optional[Task]:
        """Get a specific task by ID"""
        session = await self._get_session()
        async with session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            task_model = result.scalar_one_or_none()
            return Task.model_validate(task_model) if task_model else None
    
    async def create(self, task: Task) -> Task:
        """Create a new task"""
        session = await self._get_session()
        async with session:
            task_model = TaskModel(
                name=task.name,
                description=task.description,
                is_active=task.is_active,
                created_at=task.created_at
            )
            session.add(task_model)
            await session.commit()
            await session.refresh(task_model)
            return Task.model_validate(task_model)
    
    async def update(self, task: Task) -> Task:
        """Update an existing task"""
        session = await self._get_session()
        async with session:
            await session.execute(
                update(TaskModel)
                .where(TaskModel.id == task.id)
                .values(
                    name=task.name,
                    description=task.description,
                    is_active=task.is_active,
                    archived_at=task.archived_at
                )
            )
            await session.commit()
            return await self.get_by_id(task.id)
    
    async def archive(self, task_id: int) -> None:
        """Archive a task (soft delete)"""
        session = await self._get_session()
        async with session:
            await session.execute(
                update(TaskModel)
                .where(TaskModel.id == task_id)
                .values(is_active=False, archived_at=datetime.now())
            )
            await session.commit()


class TimeEntryRepository:
    """
    Handles all TimeEntry-related database operations.
    """
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
    
    async def _get_session(self) -> AsyncSession:
        """Get session - either injected or create new one"""
        if self.session:
            return self.session
        engine = get_engine()
        return engine.get_session()
    
    async def create(self, entry: TimeEntry) -> TimeEntry:
        """Create a new time entry"""
        session = await self._get_session()
        async with session:
            entry_model = TimeEntryModel(
                task_id=entry.task_id,
                start_time=entry.start_time,
                end_time=entry.end_time,
                duration_seconds=entry.duration_seconds,
                was_interrupted=entry.was_interrupted,
                interruption_handled=entry.interruption_handled,
                notes=entry.notes,
                created_at=entry.created_at
            )
            session.add(entry_model)
            await session.commit()
            await session.refresh(entry_model)
            return TimeEntry.model_validate(entry_model)
    
    async def update(self, entry: TimeEntry) -> TimeEntry:
        """Update an existing time entry"""
        session = await self._get_session()
        async with session:
            await session.execute(
                update(TimeEntryModel)
                .where(TimeEntryModel.id == entry.id)
                .values(
                    end_time=entry.end_time,
                    duration_seconds=entry.duration_seconds,
                    was_interrupted=entry.was_interrupted,
                    interruption_handled=entry.interruption_handled,
                    notes=entry.notes
                )
            )
            await session.commit()
            result = await session.execute(
                select(TimeEntryModel).where(TimeEntryModel.id == entry.id)
            )
            entry_model = result.scalar_one()
            return TimeEntry.model_validate(entry_model)
    
    async def get_by_task(self, task_id: int, start_date: Optional[datetime] = None, 
                          end_date: Optional[datetime] = None) -> List[TimeEntry]:
        """Get all time entries for a specific task, optionally filtered by date range"""
        session = await self._get_session()
        async with session:
            query = select(TimeEntryModel).where(TimeEntryModel.task_id == task_id)
            
            if start_date:
                query = query.where(TimeEntryModel.start_time >= start_date)
            if end_date:
                query = query.where(TimeEntryModel.start_time <= end_date)
            
            result = await session.execute(query.order_by(TimeEntryModel.start_time.desc()))
            entry_models = result.scalars().all()
            return [TimeEntry.model_validate(em) for em in entry_models]
    
    async def get_active_entry(self) -> Optional[TimeEntry]:
        """Get the currently active (not ended) time entry"""
        session = await self._get_session()
        async with session:
            result = await session.execute(
                select(TimeEntryModel)
                .where(TimeEntryModel.end_time.is_(None))
                .order_by(TimeEntryModel.start_time.desc())
            )
            entry_model = result.scalar_one_or_none()
            return TimeEntry.model_validate(entry_model) if entry_model else None
    
    async def get_interrupted_entries(self) -> List[TimeEntry]:
        """Get all interrupted entries that haven't been handled yet"""
        session = await self._get_session()
        async with session:
            result = await session.execute(
                select(TimeEntryModel).where(
                    and_(
                        TimeEntryModel.was_interrupted == True,
                        TimeEntryModel.interruption_handled == False
                    )
                )
            )
            entry_models = result.scalars().all()
            return [TimeEntry.model_validate(em) for em in entry_models]

    async def delete(self, entry_id: int) -> None:
        """Delete a time entry by ID"""
        session = await self._get_session()
        async with session:
            await session.execute(
                select(TimeEntryModel).where(TimeEntryModel.id == entry_id)
            )
            # Fetch first to ensure it exists or directly delete?
            # SQLAlchemy delete statement is efficient.
            from sqlalchemy import delete
            await session.execute(
                delete(TimeEntryModel).where(TimeEntryModel.id == entry_id)
            )
            await session.commit()

    async def has_overlap(self, start_time: datetime, end_time: datetime, ignore_id: Optional[int] = None) -> bool:
        """
        Check if there are any existing entries that overlap with the given time range.
        
        Args:
            start_time: Start of the proposed entry
            end_time: End of the proposed entry
            ignore_id: Optional ID to exclude from check (for updates)
            
        Returns:
            True if overlap exists, False otherwise
        """
        session = await self._get_session()
        async with session:
            # Overlap logic: (StartA < EndB) and (EndA > StartB)
            # Use coalesce for end_time to handle active tasks (end_time is None -> assume now)
            # But query against database NULLs is tricky. 
            # If end_time is NULL in DB, it means it's active.
            # Active tasks effectively extend to infinity (or 'now') for overlap purposes.
            # However, for manual entry plausibility, we mainly care about completed entries or strictly active ones.
            # Let's keep it simple: just check typical overlap logic.
            
            # Simple overlap: 
            # existing.start < new.end AND existing.end > new.start
            
            query = select(TimeEntryModel).where(
                and_(
                    TimeEntryModel.start_time < end_time,
                    # Handle NULL end_time (active task) as overlap if start < new.end
                    # Ideally active task end_time is effectively "now" or "future"
                    # For safety, let's treat NULL end_time as "overlapping everything after start"
                    (TimeEntryModel.end_time == None) | (TimeEntryModel.end_time > start_time)
                )
            )
            
            if ignore_id:
                query = query.where(TimeEntryModel.id != ignore_id)
                
            result = await session.execute(query.limit(1))
            return result.first() is not None

    async def get_overlapping(self, task_id: int, start_time: datetime, end_time: datetime) -> List[TimeEntry]:
        """Get all time entries for a specific task that overlap with the given time range"""
        session = await self._get_session()
        async with session:
            query = select(TimeEntryModel).where(
                and_(
                    TimeEntryModel.task_id == task_id,
                    TimeEntryModel.start_time < end_time,
                    (TimeEntryModel.end_time == None) | (TimeEntryModel.end_time > start_time)
                )
            ).order_by(TimeEntryModel.start_time.desc())
            
            result = await session.execute(query)
            entry_models = result.scalars().all()
            return [TimeEntry.model_validate(em) for em in entry_models]

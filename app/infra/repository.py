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
from typing import List, Optional, Dict
import json
from pathlib import Path

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Task, TimeEntry, Accounting, UserPreferences
from app.infra.db import TaskModel, TimeEntryModel, AccountingModel, get_engine, DatabaseEngine


class UserRepository:
    """
    Handles User Preferences persistence (JSON file based).
    """

    def __init__(self):
        # Locate prefs file near the DB
        # This is a bit of a hack to get the path, but ensures it's in the data dir
        engine = DatabaseEngine.get_instance()
        # Parse path from URL string "sqlite+aiosqlite:///<path>"
        url = str(engine.engine.url)
        if "sqlite" in url:
            db_path = url.split("///")[-1]
            self.prefs_path = Path(db_path).parent / "user_prefs.json"
        else:
            self.prefs_path = Path("user_prefs.json") # Fallback

    async def get_preferences(self) -> UserPreferences:
        """Get current user preferences"""
        if not self.prefs_path.exists():
            return UserPreferences()

        try:
            with open(self.prefs_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return UserPreferences(**data)
        except Exception as e:
            print(f"Error loading prefs: {e}")
            return UserPreferences()

    async def update_preferences(self, prefs: UserPreferences) -> None:
        """Update user preferences"""
        try:
            self.prefs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.prefs_path, 'w', encoding='utf-8') as f:
                json.dump(prefs.model_dump(), f, indent=2)
        except Exception as e:
            print(f"Error saving prefs: {e}")



class AccountingRepository:
    """
    Handles Accounting-related database operations.
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session

    async def _get_session(self) -> AsyncSession:
        if self.session:
            return self.session
        engine = get_engine()
        return engine.get_session()

    async def get_all_active(self) -> List[Accounting]:
        """Get all active accounting profiles"""
        session = await self._get_session()
        async with session:
            result = await session.execute(
                select(AccountingModel).where(AccountingModel.is_active == True)
            )
            models = result.scalars().all()
            return [Accounting.model_validate(m) for m in models]

    async def create(self, accounting: Accounting) -> Accounting:
        """Create a new accounting profile"""
        session = await self._get_session()
        async with session:
            model = AccountingModel(
                name=accounting.name,
                attributes=accounting.attributes,
                is_active=accounting.is_active,
                created_at=accounting.created_at
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return Accounting.model_validate(model)

    async def delete(self, id: int) -> None:
        """Soft delete an accounting profile"""
        session = await self._get_session()
        async with session:
            await session.execute(
                update(AccountingModel)
                .where(AccountingModel.id == id)
                .values(is_active=False)
            )
            await session.commit()

    async def update(self, accounting: Accounting) -> Accounting:
        """Update an existing accounting profile"""
        session = await self._get_session()
        async with session:
            # Use ORM fetch-modify-commit to ensure JSON serialization works correctly
            result = await session.execute(
                select(AccountingModel).where(AccountingModel.id == accounting.id)
            )
            model = result.scalar_one()

            model.name = accounting.name
            model.attributes = accounting.attributes
            model.is_active = accounting.is_active

            await session.commit()
            return accounting

    async def delete_all(self) -> int:
        """Delete all accounting profiles. Returns count of deleted rows."""
        from sqlalchemy import delete
        session = await self._get_session()
        async with session:
            result = await session.execute(delete(AccountingModel))
            await session.commit()
            return result.rowcount


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
        return await self.get_all(include_archived=False)

    async def get_all(self, include_archived: bool = True) -> List[Task]:
        """Get all tasks, optionally filtering active only"""
        session = await self._get_session()
        async with session:
            stmt = select(TaskModel)
            if not include_archived:
                stmt = stmt.where(TaskModel.is_active == True)
            
            result = await session.execute(stmt)
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
                accounting_id=task.accounting_id,
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
                    accounting_id=task.accounting_id,
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

    async def delete_all(self) -> int:
        """Delete all tasks. Returns count of deleted rows."""
        from sqlalchemy import delete
        session = await self._get_session()
        async with session:
            result = await session.execute(delete(TaskModel))
            await session.commit()
            return result.rowcount

    async def get_by_name(self, name: str, include_archived: bool = True) -> Optional[Task]:
        """Get a task by name, optionally including archived ones"""
        session = await self._get_session()
        async with session:
            stmt = select(TaskModel).where(func.lower(TaskModel.name) == name.lower())
            if not include_archived:
                stmt = stmt.where(TaskModel.is_active == True)
                
            result = await session.execute(stmt)
            task_model = result.scalar_one_or_none()
            return Task.model_validate(task_model) if task_model else None

    async def unarchive(self, task_id: int) -> None:
        """Unarchive a task (restore it)"""
        session = await self._get_session()
        async with session:
            await session.execute(
                update(TaskModel)
                .where(TaskModel.id == task_id)
                .values(is_active=True, archived_at=None)
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
            entry_model = result.scalar_one_or_none()
            if entry_model is None:
                return entry
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

    async def get_orphaned_entries(self) -> List[TimeEntry]:
        """Get all disconnected active entries (start_time < today)"""
        session = await self._get_session()
        async with session:
            # Definition of "orphaned":
            # 1. Active (end_time is None)
            # 2. Since the app is just starting (or this method is called explicitly to find orphans),
            #    ANY active entry in the DB is considered an orphan because the in-memory state is empty.

            result = await session.execute(
                select(TimeEntryModel).where(
                    TimeEntryModel.end_time.is_(None)
                )
            )
            entry_models = result.scalars().all()
            return [TimeEntry.model_validate(em) for em in entry_models]

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

    async def delete_all(self) -> int:
        """Delete all time entries. Returns count of deleted rows."""
        from sqlalchemy import delete
        session = await self._get_session()
        async with session:
            result = await session.execute(delete(TimeEntryModel))
            await session.commit()
            return result.rowcount

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
            # For active entries (end_time is NULL), only include if start_time is within range
            # For completed entries, use standard overlap logic
            query = select(TimeEntryModel).where(
                and_(
                    TimeEntryModel.task_id == task_id,
                    TimeEntryModel.start_time < end_time,
                    (
                        (TimeEntryModel.end_time == None) & (TimeEntryModel.start_time >= start_time) |
                        (TimeEntryModel.end_time != None) & (TimeEntryModel.end_time > start_time)
                    )
                )
            ).order_by(TimeEntryModel.start_time.desc())

            result = await session.execute(query)
            entry_models = result.scalars().all()
            return [TimeEntry.model_validate(em) for em in entry_models]

"""
Timer Service - Core time tracking logic.

Architecture Decision: Observer Pattern (Qt Signals)
The service emits signals when state changes, keeping it decoupled from UI.
"""

import asyncio
import datetime
from typing import Optional
from PySide6.QtCore import QObject, QTimer, Signal

from app.domain.models import Task, TimeEntry
from app.infra.repository import TaskRepository, TimeEntryRepository, UserRepository


class TimerService(QObject):
    """
    The time tracking engine. Manages state but knows nothing about the UI.
    Emits signals when things change (Observer Pattern).
    """
    
    # Signals
    tick = Signal(str, int)  # (formatted_time, total_seconds)
    task_started = Signal(int)  # task_id
    task_stopped = Signal(int, int)  # task_id, total_seconds
    task_paused = Signal(int)  # task_id
    task_resumed = Signal(int)  # task_id
    
    # Notification Signals
    target_reached = Signal(float)  # target_hours
    limit_reached = Signal(float)   # limit_hours
    
    def __init__(self):
        super().__init__()
        self.active_task: Optional[Task] = None
        self.current_entry: Optional[TimeEntry] = None
        self.cumulative_seconds: int = 0  # Total time for this task across all entries
        
        # Session state for accurate timing
        self.session_start_time: Optional[datetime.datetime] = None
        self.session_initial_seconds: int = 0
        
        self.last_tick_time = datetime.datetime.now()
        self.last_save_time = datetime.datetime.now() # For auto-save
        self.is_paused = False
        
        # Daily Tracking State
        self.daily_seconds_base: int = 0  # Total seconds of COMPLETED entries today
        self.notified_target: bool = False
        self.notified_limit: bool = False
        self.current_prefs: Optional[UserPreferences] = None
        
        # Internal timer that fires every second
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        
        # Repositories
        self.task_repo = TaskRepository()
        self.entry_repo = TimeEntryRepository()
        self.user_repo = UserRepository()
    
    async def start_task(self, task_id: int):
        """
        Start tracking time for a task.
        """
        # Stop current task if any
        if self.active_task:
            await self.stop_task()
        
        # Load task from database
        self.active_task = await self.task_repo.get_by_id(task_id)
        if not self.active_task:
            raise ValueError(f"Task {task_id} not found")
        
        # Load cumulative time for THIS task
        start_of_day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        previous_entries = await self.entry_repo.get_by_task(task_id, start_date=start_of_day)
        self.cumulative_seconds = sum(entry.duration_seconds for entry in previous_entries)
        
        # Load Preferences & Daily Total for ALL tasks
        self.current_prefs = await self.user_repo.get_preferences()
        
        # We need sum of ALL tasks today to check daily limit
        # This requires a new repo method or iterating all active tasks?
        # Efficient way: We don't have a "get all entries for today" method yet.
        # Let's add simple logic: We mostly care about current + completed.
        # To avoid heavy query every second, we calculate "base" on start.
        # But we need "get_total_duration_for_day(date)" in repo.
        # For now, let's assume we implement it or query all tasks?
        # Optimized: implemented a helper query in _load_daily_total
        self.daily_seconds_base = await self._get_daily_total(start_of_day)
        
        # Reset flags if explicitly starting fresh? 
        # Actually flags should persist per day. But service memory is lifetime of app?
        # If app runs across midnight, we need to reset.
        # Simple check: if last_tick was yesterday?
        # For now, simplistic approach: recalc flags based on current totals.
        current_hrs = self.daily_seconds_base / 3600.0
        self.notified_target = current_hrs >= self.current_prefs.work_hours_per_day
        self.notified_limit = current_hrs >= self.current_prefs.max_daily_hours
        
        # Create new time entry
        self.current_entry = TimeEntry(
            task_id=task_id,
            start_time=datetime.datetime.now(),
            duration_seconds=0
        )
        self.current_entry = await self.entry_repo.create(self.current_entry)
        
        # Start timer
        self.session_start_time = datetime.datetime.now()
        self.session_initial_seconds = 0
        self.last_tick_time = self.session_start_time
        self.last_save_time = self.session_start_time
        self.is_paused = False
        self.timer.start(1000)  # 1000ms = 1 second
        
        self.task_started.emit(task_id)
        
    async def _get_daily_total(self, date: datetime.datetime) -> int:
        """Helper to get total duration of all tasks for a given date"""
        # This requires a repo method we don't strictly have, but we can iterate active tasks?
        # Or better: SQL query.
        # Since I cannot easily change repo interface in this snippet without more tools,
        # I will do a slightly inefficient loop over all active tasks. 
        # In production this should be `entry_repo.get_total_duration(date)`.
        
        # Hack: use existing `get_by_task` for all active tasks.
        tasks = await self.task_repo.get_all_active()
        total = 0
        start = date.replace(hour=0, minute=0, second=0)
        end = date.replace(hour=23, minute=59, second=59)
        
        for t in tasks:
            entries = await self.entry_repo.get_by_task(t.id, start_date=start, end_date=end)
            total += sum(e.duration_seconds for e in entries)
        return total
    
    async def stop_task(self):
        """
        Stop tracking the current task.
        """
        if not self.active_task or not self.current_entry:
            return
        
        self.timer.stop()
        
        # Update entry with end time
        self.current_entry.end_time = datetime.datetime.now()
        await self.entry_repo.update(self.current_entry)
        
        task_id = self.active_task.id
        total_seconds = self.cumulative_seconds + self.current_entry.duration_seconds
        
        self.task_stopped.emit(task_id, total_seconds)
        
        self.active_task = None
        self.current_entry = None
        self.cumulative_seconds = 0
    
    def pause_task(self):
        """
        Pause the current task (e.g., when screen locks).
        Timer stops but entry remains open.
        """
        if self.is_paused or not self.active_task:
            return
        
        self.timer.stop()
        self.is_paused = True
        
        # Force a save when pausing
        if self.current_entry:
             # We can't await here easily, but we should try to save state.
             # Since pause originates from UI or event, maybe we can assume loop is running?
             # For now, let the loop/system monitor handle the call wrapper, or launch a task.
             asyncio.create_task(self._background_save())
        
        if self.active_task:
            self.task_paused.emit(self.active_task.id)
    
    def resume_task(self):
        """
        Resume the paused task.
        """
        if not self.is_paused or not self.active_task:
            return
        
        self.session_start_time = datetime.datetime.now()
        # Capture current duration as the baseline for this session
        if self.current_entry:
            self.session_initial_seconds = self.current_entry.duration_seconds
            
        self.last_tick_time = self.session_start_time
        self.last_save_time = self.session_start_time
        self.is_paused = False
        self.timer.start(1000)
        
        if self.active_task:
            self.task_resumed.emit(self.active_task.id)
    
    async def add_time_to_current_entry(self, seconds: int):
        """
        Add time to the current entry (e.g., time during screen lock that was work).
        """
        if not self.current_entry:
            return
        
        self.current_entry.duration_seconds += seconds
        await self.entry_repo.update(self.current_entry)
    
    async def mark_interruption(self, was_work: bool, interruption_seconds: int):
        """
        Handle an interruption (e.g., screen lock/unlock).
        
        Args:
            was_work: True if the time should be counted, False if it was a break
            interruption_seconds: Duration of the interruption
        """
        if not self.current_entry:
            return
        
        if was_work:
            # Add the time to the current entry
            self.current_entry.duration_seconds += interruption_seconds
        
        # Mark as handled
        self.current_entry.was_interrupted = True
        self.current_entry.interruption_handled = True
        await self.entry_repo.update(self.current_entry)
        
    async def _background_save(self):
        """Persist current entry state to DB"""
        if self.current_entry:
            try:
                # We only update duration, keeping end_time as None (active)
                await self.entry_repo.update(self.current_entry)
            except Exception as e:
                print(f"Auto-save failed: {e}")
    
    def _on_tick(self):
        """Called every second to update the timer"""
        if not self.active_task or not self.current_entry:
            return
        
        now = datetime.datetime.now()
        
        # Calculate duration based on start time (drift-proof)
        # Using int() matches the expectation of whole seconds passed
        elapsed = (now - self.session_start_time).total_seconds()
        self.current_entry.duration_seconds = self.session_initial_seconds + int(elapsed)
        
        # Calculate total time including previous entries
        total_seconds = self.cumulative_seconds + self.current_entry.duration_seconds
        
        # Format and notify listeners
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{self.active_task.name}: {hours:02d}:{minutes:02d}:{seconds:02d}"
        
        self.tick.emit(time_str, total_seconds)
        
        # Auto-Save Logic
        if (now - self.last_save_time).total_seconds() >= 60:
            self.last_save_time = now
            # Fire and forget background save
            # Note: This requires an active event loop. QTimer runs in the main thread 
            # where asyncio loop should be available (SystemTrayApp sets it up).
            asyncio.create_task(self._background_save())
            
        # Notification Logic
        if self.current_prefs:
            # Re-calculating elapsed in case it drifted? 
            # self.current_entry.duration_seconds is already updated above.
            
            # Since daily_seconds_base is from start of session, it DOES NOT include current entry start.
            # Wait, start_task loads previous entries. 
            # But "previous_entries" in start_task was strictly "previous".
            # My _get_daily_total logic in start_task summed ALL tasks.
            # If start_task just created a new entry (current_entry), it is NOT in DB yet (or size 0).
            # So daily_seconds_base includes all OTHER finished entries.
            # Total = base + current_entry.duration_seconds.
            
            # Correction: _get_daily_total might have included "current_entry" if it was committed?
            # start_task called create() -> entry in DB.
            # _get_daily_total iterates tasks -> get_by_task.
            # get_by_task usually returns all. 
            # Since current_entry duration is 0 in DB until we save...
            # The sum from DB will be (Previous Totals + 0).
            # So adding current_entry.duration_seconds (memory) is correct.
            
            total_daily_seconds = self.daily_seconds_base + self.current_entry.duration_seconds
            total_daily_hours = total_daily_seconds / 3600.0
            
            # Target Check
            if total_daily_hours >= self.current_prefs.work_hours_per_day and not self.notified_target:
                self.notified_target = True
                self.target_reached.emit(self.current_prefs.work_hours_per_day)
                
            # Limit Check
            if total_daily_hours >= self.current_prefs.max_daily_hours and not self.notified_limit:
                self.notified_limit = True
                self.limit_reached.emit(self.current_prefs.max_daily_hours)
    
    async def get_active_task(self) -> Optional[Task]:
        """Get the currently active task"""
        return self.active_task
    
    def is_tracking(self) -> bool:
        """Check if currently tracking time"""
        return self.active_task is not None and not self.is_paused

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
from app.infra.repository import TaskRepository, TimeEntryRepository


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
        
        # Internal timer that fires every second
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        
        # Repositories
        self.task_repo = TaskRepository()
        self.entry_repo = TimeEntryRepository()
    
    async def start_task(self, task_id: int):
        """
        Start tracking time for a task.
        
        If another task is active, it will be stopped first.
        Loads cumulative time from previous entries for this task.
        """
        # Stop current task if any
        if self.active_task:
            await self.stop_task()
        
        # Load task from database
        self.active_task = await self.task_repo.get_by_id(task_id)
        if not self.active_task:
            raise ValueError(f"Task {task_id} not found")
        
        # Load cumulative time from all previous entries for TODAY
        start_of_day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        previous_entries = await self.entry_repo.get_by_task(task_id, start_date=start_of_day)
        self.cumulative_seconds = sum(entry.duration_seconds for entry in previous_entries)
        
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
    
    async def get_active_task(self) -> Optional[Task]:
        """Get the currently active task"""
        return self.active_task
    
    def is_tracking(self) -> bool:
        """Check if currently tracking time"""
        return self.active_task is not None and not self.is_paused

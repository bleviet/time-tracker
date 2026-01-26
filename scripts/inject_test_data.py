"""
Injects a Pause task and entry to verify report exclusion logic.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.repository import TaskRepository, TimeEntryRepository
from app.domain.models import Task, TimeEntry

async def main():
    task_repo = TaskRepository()
    entry_repo = TimeEntryRepository()
    
    # 1. Create or Get "Pause" task
    tasks = await task_repo.get_all_active()
    pause_task = next((t for t in tasks if t.name == "Pause"), None)
    
    if not pause_task:
        print("Creating 'Pause' task...")
        pause_task = await task_repo.create(Task(name="Pause", description="Break time"))
    else:
        print(f"Found existing 'Pause' task: {pause_task.id}")
        
    # 2. Add entry for Jan 26, 2026 (Mon) - 1 hour
    start = datetime(2026, 1, 26, 12, 0, 0)
    end = start + timedelta(hours=1)
    
    print(f"Adding 1 hour Pause entry on {start.date()}...")
    entry = TimeEntry(
        task_id=pause_task.id,
        start_time=start,
        end_time=end,
        duration_seconds=3600,
        notes="Lunch break"
    )
    await entry_repo.create(entry)
    print("Entry created.")

if __name__ == "__main__":
    asyncio.run(main())

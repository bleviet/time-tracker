"""
Data Seeder for Time Tracker.
Populates the database with realistic data for testing and demo purposes.
"""

import asyncio
import sys
import os
import random
from datetime import datetime, timedelta, date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.repository import TaskRepository, TimeEntryRepository
from app.domain.models import Task, TimeEntry
from app.infra.db import get_engine, Base

async def reset_database():
    """Delete the existing database file to ensure a fresh seed"""
    if os.name == 'nt':  # Windows
        data_dir = Path(os.getenv('APPDATA')) / 'TimeTracker'
    else:  # Linux/Mac
        data_dir = Path.home() / '.local' / 'share' / 'timetracker'
    
    db_path = data_dir / 'timetracker.db'
    if db_path.exists():
        print(f"Removing existing database at: {db_path}")
        try:
            db_path.unlink()
            print("Database removed.")
        except PermissionError:
            print("ERROR: Could not remove database. It might be in use.")
            sys.exit(1)
    else:
        print(f"No existing database found at: {db_path}")

async def seed():
    await reset_database()
    print("Starting data seeding...")
    
    # Initialize DB (creates tables if needed)
    engine = get_engine()
    async with engine.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    task_repo = TaskRepository()
    entry_repo = TimeEntryRepository()

    # 1. Create Tasks
    task_names = ["Software Development", "Meetings", "General Admin", "Deep Work", "Pause"]
    tasks_map = {}
    
    existing_tasks = await task_repo.get_all_active()
    existing_names = {t.name for t in existing_tasks}
    
    for name in task_names:
        if name not in existing_names:
            print(f"Creating task: {name}")
            task = await task_repo.create(Task(name=name, description=f"Default {name} task"))
            tasks_map[name] = task
        else:
            print(f"Task exists: {name}")
            tasks_map[name] = next(t for t in existing_tasks if t.name == name)

    # 2. Generate Time Entries for January 2026
    # Pattern: Mon-Fri, 9am - 5pm
    # - 9:00 - 12:00: Deep Work / Dev
    # - 12:00 - 13:00: Pause (Lunch)
    # - 13:00 - 14:00: Meetings / Admin
    # - 14:00 - 17:00: Dev
    
    start_date = date(2026, 1, 1)
    end_date = date(2026, 1, 31)
    
    # Check if we already have entries to avoid dupes? 
    # For now, simplistic approach: just add. In real usage, maybe clean first.
    
    current = start_date
    while current <= end_date:
        # Skip weekends
        if current.weekday() >= 5: # Sat=5, Sun=6
            current += timedelta(days=1)
            continue
            
        # Simulating entries for a day
        day_date = datetime.combine(current, datetime.min.time())
        
        # 1. Morning Block (9:00 - 12:00)
        task = tasks_map["Software Development"] if random.random() > 0.3 else tasks_map["Deep Work"]
        await entry_repo.create(TimeEntry(
            task_id=task.id,
            start_time=day_date.replace(hour=9, minute=0),
            end_time=day_date.replace(hour=12, minute=0),
            duration_seconds=3 * 3600,
            notes="Morning session"
        ))
        
        # 2. Lunch Break (12:00 - 13:00)
        await entry_repo.create(TimeEntry(
            task_id=tasks_map["Pause"].id,
            start_time=day_date.replace(hour=12, minute=0),
            end_time=day_date.replace(hour=13, minute=0),
            duration_seconds=1 * 3600,
            notes="Lunch"
        ))
        
        # 3. Afternoon Meeting/Admin (13:00 - 14:00)
        task = tasks_map["Meetings"] if random.random() > 0.5 else tasks_map["General Admin"]
        await entry_repo.create(TimeEntry(
            task_id=task.id,
            start_time=day_date.replace(hour=13, minute=0),
            end_time=day_date.replace(hour=14, minute=0),
            duration_seconds=1 * 3600,
            notes="Sync"
        ))
        
        # 4. Late Afternoon Dev (14:00 - 17:00)
        await entry_repo.create(TimeEntry(
            task_id=tasks_map["Software Development"].id,
            start_time=day_date.replace(hour=14, minute=0),
            end_time=day_date.replace(hour=17, minute=0),
            duration_seconds=3 * 3600,
            notes="Feature work"
        ))
        
        print(f"Generated entries for {current}")
        current += timedelta(days=1)

    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed())

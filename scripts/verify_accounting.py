import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add app to path
sys.path.append(os.getcwd())

from app.infra.db import init_db, async_sessionmaker, AccountingModel, TaskModel, TimeEntryModel, get_engine
from app.infra.repository import UserRepository, AccountingRepository, TaskRepository, TimeEntryRepository
from app.domain.models import Accounting, Task, TimeEntry
from app.services.accounting_matrix_service import AccountingMatrixService, ReportConfiguration as MatrixConfig
from sqlalchemy import text

async def migrate_db():
    print("Migrating DB (checking schema)...")
    engine = get_engine()
    async with engine.engine.connect() as conn:
        try:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN accounting_id INTEGER REFERENCES accounting(id)"))
            await conn.commit()
            print("   Added accounting_id to tasks.")
        except Exception as e:
            print(f"   Schema up to date or migration skipped: {e}")

async def main():
    print("Initializing DB...")
    await init_db()
    await migrate_db()
    
    user_repo = UserRepository()
    acc_repo = AccountingRepository()
    task_repo = TaskRepository()
    entry_repo = TimeEntryRepository()
    # report_service = ReportService() # Deprecated for this test
    matrix_service = AccountingMatrixService()
    
    print("1. Setting User Preferences...")
    prefs = await user_repo.get_preferences()
    prefs.accounting_columns = ["Cost Center", "Project Code"]
    await user_repo.update_preferences(prefs)
    
    # ... (creation steps 2-4 same) ...
    print("2. Creating Accounting Profile...")
    profile = Accounting(
        name="Verification Profile",
        attributes={"Cost Center": "CC-Test", "Project Code": "PROJ-X"}
    )
    saved_profile = await acc_repo.create(profile)
    print(f"   Created Profile: {saved_profile.name} (ID: {saved_profile.id})")
    
    print("3. Creating Task...")
    task = Task(
        name="Verification Task",
        accounting_id=saved_profile.id
    )
    saved_task = await task_repo.create(task)
    print(f"   Created Task: {saved_task.name} (ID: {saved_task.id})")
    
    print("4. Creating Time Entry...")
    start = datetime.now() - timedelta(hours=2)
    end = datetime.now()
    entry = TimeEntry(
        task_id=saved_task.id,
        start_time=start,
        end_time=end,
        duration_seconds=7200,
        notes="Verification Note"
    )
    saved_entry = await entry_repo.create(entry)
    print("   Created Entry")
    
    print("5. Generating Matrix Report...")
    period = f"{start.month:02d}.{start.year}"
    config = MatrixConfig(
        period=period,
        time_off_configs=[],
        excluded_tasks=[]
    )
    report_content = await matrix_service.generate_report(config)
    
    print("\n--- REPORT OUTPUT ---")
    print(report_content)
    print("---------------------\n")
    
    # Assertions
    print("Verifying Content...")
    if "Task name" not in report_content:
        print("FAIL: 'Task name' header missing")
    if "Accounting Profile" not in report_content:
        print("FAIL: 'Accounting Profile' header missing")
    if "Cost Center" not in report_content:
        print("FAIL: 'Cost Center' header missing")
    if "CC-Test" not in report_content:
         print("FAIL: 'CC-Test' value missing")
    
    # Check for Matrix specific date header for today
    today_header = matrix_service._format_german_date(start.date())
    if today_header not in report_content:
         print(f"FAIL: Date header '{today_header}' missing")
         
    print("SUCCESS: Matrix data verified!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

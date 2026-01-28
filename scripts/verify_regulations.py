
import asyncio
import datetime
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.models import UserPreferences, Task, TimeEntry, Accounting
from app.services.accounting_matrix_service import AccountingMatrixService
from app.services.timer_service import TimerService
from app.services.matrix_report_service import ReportConfiguration

async def test_report_overtime():
    print("--- Testing Report Overtime & Compliance ---")
    
    # Mock Repositories
    service = AccountingMatrixService()
    service.task_repo = AsyncMock()
    service.entry_repo = AsyncMock()
    service.acc_repo = AsyncMock()
    service.user_repo = AsyncMock()
    
    # Setup Data
    # 1 Task, 1 Profile
    acc = Accounting(id=1, name="Project A", attributes={})
    task = Task(id=10, name="Dev", accounting_id=1)
    
    # Entries: 10 Hours on Day 1 (Overtime +2h if target 8h)
    today = datetime.date(2026, 1, 1) # Thursday
    entry = TimeEntry(
        id=100, task_id=10, 
        start_time=datetime.datetime.combine(today, datetime.time(9,0)),
        end_time=datetime.datetime.combine(today, datetime.time(19,0)),
        duration_seconds=10 * 3600
    )
    
    # Setup Mocks
    service.task_repo.get_all_active.return_value = [task]
    service.acc_repo.get_all_active.return_value = [acc]
    service.entry_repo.get_by_task.return_value = [entry]
    
    # Preferences: Target 8h, Max 9.5h (to trigger warning)
    prefs = UserPreferences(
        work_hours_per_day=8.0,
        enable_german_compliance=True,
        max_daily_hours=9.5
    )
    service.user_repo.get_preferences.return_value = prefs
    
    # Generate Report
    config = ReportConfiguration(
        period="01.2026",
        # date_range is property, derived from period. 
        # But ReportConfiguration usually takes period string.
        # Wait, date_range is a property, I can't init it.
        # Does generate_report use config.date_range? Yes.
        # But ReportConfiguration calculates date_range from period.
        # period="01.2026" implies Jan 2026.
    )
    # Mock date_range property if necessary, or let it work?
    # Standard ReportConfiguration derives it.
    # But wait, date_range property relies on period string.
    # period="01.2026".

    
    csv_output = await service.generate_report(config)
    print("Generated CSV Snippet:")
    print(csv_output)
    
    # Assertions
    # 1 check total
    assert "10,0" in csv_output 
    # 2 check target
    assert "Daily Target" in csv_output
    assert "8,0" in csv_output
    # 3 check overtime (10-8 = +2)
    assert "Overtime" in csv_output
    assert "+2,0" in csv_output or "2,0" in csv_output
    # 4 check warning (>9.5)
    assert "Compliance Notes" in csv_output
    assert "> 9.5h!" in csv_output
    
    print("SUCCESS: Report Overtime Verified")

def test_timer_logic():
    print("\n--- Testing Timer Service Notification Logic ---")
    
    # Setup Service
    timer = TimerService()
    # Mock Repos for background save
    timer.entry_repo = AsyncMock()
    timer.task_repo = AsyncMock()
    
    timer.active_task = Task(id=1, name="Test")
    timer.current_entry = TimeEntry(id=1, task_id=1, start_time=datetime.datetime.now())
    
    # Mock Signals
    timer.target_reached = MagicMock()
    timer.limit_reached = MagicMock()
    
    # Mock Prefs
    prefs = UserPreferences(work_hours_per_day=8.0, max_daily_hours=10.0)
    timer.current_prefs = prefs
    timer.daily_seconds_base = 0 # No previous works
    
    # 1. Simulate 7.9 hours
    elapsed_7_9 = int(7.9 * 3600)
    timer.session_start_time = datetime.datetime.now() - datetime.timedelta(seconds=elapsed_7_9)
    timer.session_initial_seconds = 0
    timer._on_tick() # Manual trigger
    
    timer.target_reached.emit.assert_not_called()
    timer.limit_reached.emit.assert_not_called()
    
    # 2. Simulate 8.1 hours (Target Reached)
    elapsed_8_1 = int(8.1 * 3600)
    timer.session_start_time = datetime.datetime.now() - datetime.timedelta(seconds=elapsed_8_1)
    timer._on_tick()
    
    assert timer.target_reached.emit.called
    assert not timer.limit_reached.emit.called
    
    # Reset for limit check
    timer.target_reached.emit.reset_mock()
    
    # 3. Simulate 10.1 hours (Limit Reached)
    elapsed_10_1 = int(10.1 * 3600)
    timer.session_start_time = datetime.datetime.now() - datetime.timedelta(seconds=elapsed_10_1)
    timer._on_tick()
    
    assert timer.limit_reached.emit.called
    
    print("SUCCESS: Timer Logic Verified")

async def main():
    await test_report_overtime()
    test_timer_logic()

if __name__ == "__main__":
    asyncio.run(main())

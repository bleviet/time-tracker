"""
Tests for the Matrix Report Service.
"""

import pytest
import datetime
from pathlib import Path
from app.domain.models import Task, TimeEntry
from app.infra.repository import TaskRepository, TimeEntryRepository
from app.services.matrix_report_service import MatrixReportService, ReportConfiguration, TimeOffConfig

@pytest.mark.asyncio
async def test_matrix_report_generation(db_session, monkeypatch):
    """
    Test full report generation flow:
    1. Create standard task and 'Pause' task.
    2. Add entries.
    3. Run report generation.
    4. Verify CSV content.
    """
    
    # Mock the session in repositories to use our test session
    # (Since repositories instantiate their own session by default, use dependency injection or mock)
    # Our Repository allows session injection!
    task_repo = TaskRepository(session=db_session)
    entry_repo = TimeEntryRepository(session=db_session)
    
    # We need to monkeypatch the service to use our repos with injected session
    # Or better, refactor Service to accept them, but for now let's patch the init of the service
    # Actually, the service creates new instances in the method if not injected.
    # The current MatrixReportService __init__ creates `self.task_repo = TaskRepository()`.
    # Let's verify source code of MatrixReportService... 
    # It does `self.task_repo = TaskRepository()`.
    # We need to hot-swap these attributes on the instance.
    
    service = MatrixReportService()
    service.task_repo = task_repo
    service.entry_repo = entry_repo

    # 1. Setup Data
    task_dev = await task_repo.create(Task(name="Development", description="Coding"))
    task_pause = await task_repo.create(Task(name="Pause", description="Break"))
    
    # Add Entry for Dev: Jan 1st 2026, 4 hours
    await entry_repo.create(TimeEntry(
        task_id=task_dev.id,
        start_time=datetime.datetime(2026, 1, 1, 9, 0),
        end_time=datetime.datetime(2026, 1, 1, 13, 0),
        duration_seconds=4 * 3600
    ))
    
    # Add Entry for Pause: Jan 1st 2026, 1 hour
    await entry_repo.create(TimeEntry(
        task_id=task_pause.id,
        start_time=datetime.datetime(2026, 1, 1, 13, 0),
        end_time=datetime.datetime(2026, 1, 1, 14, 0),
        duration_seconds=1 * 3600
    ))

    # 2. Configure Report
    config = ReportConfiguration(
        period="2026-01",
        time_off_configs=[
            TimeOffConfig(
                task_name="Vacation",
                days=[datetime.date(2026, 1, 2)], # Jan 2nd is vacation
                daily_hours=8.0
            ),
            TimeOffConfig(
                task_name="Sickness",
                days=[datetime.date(2026, 1, 3)], # Jan 3rd is sickness
                daily_hours=8.0
            )
        ],
        excluded_tasks=["Pause"]
    )
    
    # 3. Generate
    csv_str = await service.generate_report(config)
    lines = csv_str.strip().split('\n')
    
    # 4. Verify
    # Header check
    assert "Task name" in lines[0]
    assert "01. Jan 26" in lines[0] # Check date format
    
    # Find rows
    dev_row = next((l for l in lines if l.startswith("Development")), None)
    pause_row = next((l for l in lines if l.startswith("Pause")), None)
    total_row = next((l for l in lines if l.startswith("Total Work")), None)
    
    # Check for Sickness and Vacation rows
    vacation_row = next((l for l in lines if l.startswith("Vacation")), None)
    sickness_row = next((l for l in lines if l.startswith("Sickness")), None)

    assert dev_row is not None
    assert pause_row is not None
    assert total_row is not None
    assert vacation_row is not None
    assert sickness_row is not None
    
    # Check Dev hours (Jan 1)
    # Col 1=Task, 2=User1, 3=User2, 4=Total, 5=Jan 1
    # 4.0 hours
    assert "4,0" in dev_row 

    # Check Pause hours (Jan 1)
    # 1.0 hours
    assert "1,0" in pause_row
    
    # Check Total Work
    # Should include Dev (4.0) + Vacation (8.0 on Jan 2)
    # Should NOT include Pause (1.0)
    # Total = 12.0
    # Let's check the specific values
    # Total Row format: Total Work;;;12,0;4,0;8,0;...
    
    print(csv_str) # For debugging if fails

    # Verify Vacation logic (Jan 2)
    assert "8,0" in total_row
    
    # Verify Sickness logic (Jan 3) -> should also be 8.0 in total
    # Check that Sickness row has 8,0 at Jan 3 position
    # and Total Work has 8,0 there too.
    
    # Verify Grand Total
    # Dev(4) + Vacation(8) + Sickness(8) = 20
    # Pause is excluded
    assert "20,0" in total_row 

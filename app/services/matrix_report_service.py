"""
Matrix Report Service.

Generates a spreadsheet-like report where days are columns and tasks are rows.
Supports configuration for vacations, excluded tasks, and specific date ranges.
"""

import datetime
import calendar
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from app.domain.models import Task, TimeEntry
from app.infra.repository import TaskRepository, TimeEntryRepository

logger = logging.getLogger(__name__)


class TimeOffConfig(BaseModel):
    """Configuration for time off (vacation, sickness, etc)."""
    task_name: str = Field(..., description="Name of the task to log time against")
    days: List[datetime.date] = Field(default_factory=list, description="List of dates")
    daily_hours: float = Field(default=8.0, description="Hours to attribute per day")


class ReportConfiguration(BaseModel):
    """
    Configuration for a matrix report.
    Usually loaded from a YAML file.
    """
    period: str = Field(..., description="Year-Month in format YYYY-MM")
    output_path: Optional[str] = Field(None, description="Path to save the generated CSV")
    
    time_off_configs: List[TimeOffConfig] = Field(
        default_factory=list, 
        description="Configurations for various types of time off (Vacation, Sickness)"
    )
    
    # Backward compatibility helper (optional, or just remove)
    def __init__(self, **data):
        # Migrating vacation_config to time_off_configs if present
        if 'vacation_config' in data and data['vacation_config']:
            if 'time_off_configs' not in data:
                data['time_off_configs'] = []
            # We assume data['vacation_config'] is a dict or obj
            # But Pydantic validation runs after. 
            # Let's simple rely on the user using the new format or 
            # if we want to support the old one, we need to do it carefully.
            # For now, let's assume valid new config or we add it to the list.
            vc = data.pop('vacation_config')
            data['time_off_configs'].append(vc)
        super().__init__(**data)
    
    excluded_tasks: List[str] = Field(
        default_factory=list, 
        description="Tasks that should be listed but NOT counted in totals (e.g. Pause, Break)"
    )
    
    # Optional styling or column headers could go here
    user_columns: List[str] = Field(
        default_factory=lambda: ["User Column 1", "User Column 2"],
        description="Extra placeholder columns to match user's template"
    )

    @property
    def start_date(self) -> datetime.date:
        """Derive start date from period string."""
        year, month = map(int, self.period.split('-'))
        return datetime.date(year, month, 1)

    @property
    def end_date(self) -> datetime.date:
        """Derive end date from period string."""
        year, month = map(int, self.period.split('-'))
        _, last_day = calendar.monthrange(year, month)
        return datetime.date(year, month, last_day)
    
    @property
    def date_range(self) -> List[datetime.date]:
        """Return list of all dates in the period."""
        start = self.start_date
        end = self.end_date
        delta = end - start
        return [start + datetime.timedelta(days=i) for i in range(delta.days + 1)]


class MatrixReportService:
    """
    Service to generate Matrix CSV reports.
    """

    def __init__(self):
        self.task_repo = TaskRepository()
        self.entry_repo = TimeEntryRepository()

    async def generate_report(self, config: ReportConfiguration) -> str:
        """
        Generates the matrix report based on configuration.
        Returns the CSV content as a string.
        """
        # 1. Fetch Data
        tasks = await self.task_repo.get_all_active()
        
        # We need to fetch entries for the entire range
        # Note: repo expects datetime, so we convert dates
        start_dt = datetime.datetime.combine(config.start_date, datetime.time.min)
        end_dt = datetime.datetime.combine(config.end_date, datetime.time.max)
        
        # 2. Build Data Matrix
        # Map[TaskName, Map[Date, Hours]]
        matrix: Dict[str, Dict[datetime.date, float]] = {task.name: {} for task in tasks}
        
        # Initialize dates for all tasks to 0.0 only if we want dense matrix, 
        # but sparse is fine too. Let's keep it sparse and fill checks later.
        
        # 3. Process Real Time Entries
        for task in tasks:
            entries = await self.entry_repo.get_by_task(
                task.id, 
                start_date=start_dt, 
                end_date=end_dt
            )
            
            for entry in entries:
                date_key = entry.start_time.date()
                hours = entry.duration_seconds / 3600.0
                
                current = matrix[task.name].get(date_key, 0.0)
                matrix[task.name][date_key] = current + hours

        # 4. Process Time Off (Vacation, Sickness, etc)
        for time_off in config.time_off_configs:
            t_name = time_off.task_name
            
            if t_name not in matrix:
                matrix[t_name] = {}
            
            for d in time_off.days:
                if config.start_date <= d <= config.end_date:
                    matrix[t_name][d] = time_off.daily_hours

        # 5. Format Output
        return self._format_csv(matrix, config)

    def _format_csv(self, matrix: Dict[str, Dict[datetime.date, float]], config: ReportConfiguration) -> str:
        """
        Internal method to render the CSV string.
        """
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n') # Semicolon for Excel compatibility in EU

        # Header Row 1: Columns
        # Task Name; [User Cols]; Total Hours; Date 1; Date 2...
        dates = config.date_range
        header = ["Task name"] + config.user_columns + ["Total hours"]
        
        # Date headers: "Do, 1. Jan 26"
        # We'll use a standard format for now, or try to match the user's example
        # User example: "Do, 1. Jan 26" -> German DayName, Day. Month Year
        # We will use simple %a %d. %b %y for now, or English if system locale.
        # Let's stick to %Y-%m-%d for simplicity/machine reading unless specifically asked, 
        # BUT user asked for "Exceptional UX" and "example.csv" has formatted dates.
        # Let's try to mimic the nice format.
        date_headers = [d.strftime("%a, %d. %b %y") for d in dates]
        header.extend(date_headers)
        
        writer.writerow(header)

        # Rows
        # Split tasks into: Included and Excluded
        included_rows = []
        excluded_rows = []
        
        # Calculate Subtotals per Day
        # Map[Date, TotalHours]
        day_totals = {d: 0.0 for d in dates}

        sorted_task_names = sorted(matrix.keys())
        
        for task_name in sorted_task_names:
            is_excluded = task_name in config.excluded_tasks
            
            row_data = matrix[task_name]
            
            # Calculate row total
            # For excluded tasks, we still verify if we should sum them (User said "not counted to the total time")
            # But the ROW total probably should show the sum of that task.
            row_total = sum(row_data.get(d, 0.0) for d in dates)
            
            # Check if this task is a time-off task
            is_time_off = any(t.task_name == task_name for t in config.time_off_configs)
            
            if row_total == 0 and task_name not in config.excluded_tasks and not is_time_off:
                 # Optional: Skip empty tasks? 
                 # classic reports usually skip empty unless specific.
                 continue

            # Prepare CSV Row
            # Name, UserCols..., Total, D1...
            csv_row = [task_name] + [""] * len(config.user_columns) + [f"{row_total:.1f}".replace('.', ',')] # formatted float
            
            for d in dates:
                val = row_data.get(d, 0.0)
                if val > 0:
                    csv_row.append(f"{val:.1f}".replace('.', ','))
                    if not is_excluded:
                        day_totals[d] += val
                else:
                    csv_row.append("")
            
            if is_excluded:
                excluded_rows.append(csv_row)
            else:
                included_rows.append(csv_row)

        # Write Included Rows
        writer.writerows(included_rows)
        
        # Write "Total" Row (Sum of Included) - Optional but good for UX
        # User's example doesn't explicitly have a "Total" row at the bottom in the standard list, 
        # but usually you want one.
        # However, the user said "Report it in the table at the very bottom" for paused tasks.
        # Let's add a Divider or Space?
        
        writer.writerow([]) # Empty line
        
        # Write Excluded Rows
        if excluded_rows:
            writer.writerows(excluded_rows)

        # Let's write a "Grand Total" row for legitimate work?
        # User didn't strictly ask for a Grand Total row, but implied "counted to the total time".
        # Let's add a "Total Work" row.
        total_row = ["Total Work"] + [""] * len(config.user_columns)
        
        grand_total = sum(day_totals.values())
        total_row.append(f"{grand_total:.1f}".replace('.', ','))
        
        for d in dates:
            val = day_totals[d]
            if val > 0:
                total_row.append(f"{val:.1f}".replace('.', ','))
            else:
                total_row.append("")
        
        writer.writerow(total_row)

        return output.getvalue()

import io

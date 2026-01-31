"""
Domain Models using Pydantic for validation.

Architecture Decision: Why Pydantic?
Pydantic provides runtime data validation, ensuring data integrity when loading
from JSON config files or database. It also provides easy serialization/deserialization.
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class Accounting(BaseModel):
    """
    Represents an accounting profile/cost object.

    Attributes are dynamic based on UserPreferences.accounting_columns.
    Example: {"Cost Center": "100", "Project": "A-1"}
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    attributes: Dict[str, str] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class Task(BaseModel):
    """
    Represents a trackable task/project.

    Examples: "Software Development", "Meetings", "General Admin"
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: bool = True

    # Link to Accounting Profile
    accounting_id: Optional[int] = None

    created_at: datetime = Field(default_factory=datetime.now)
    archived_at: Optional[datetime] = None

    # Computed fields
    total_seconds: int = 0  # Computed from time entries


class TimeEntry(BaseModel):
    """
    Represents a single time tracking session.

    A session starts when a task is activated and ends when:
    - User stops tracking
    - User switches to another task
    - System detects lock/logout
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    task_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0  # Cached for performance

    # For handling interruptions (logout/lock)
    was_interrupted: bool = False
    interruption_handled: bool = False

    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class UserPreferences(BaseModel):
    """
    User configuration and preferences.

    This allows users to customize behavior without touching code.
    """
    model_config = ConfigDict(from_attributes=True)

    # German-specific settings
    german_state: str = Field(default="BY", description="Two-letter German state code")
    respect_holidays: bool = Field(default=True, description="Disable tracking on holidays")
    respect_weekends: bool = Field(default=True, description="Disable tracking on weekends")

    # Accounting Settings
    accounting_columns: List[str] = Field(
        default_factory=list,
        description="User-defined columns for accounting profiles (e.g. ['Cost Center', 'GL Account'])"
    )

    # Auto-pause settings
    auto_pause_on_lock: bool = Field(default=True, description="Pause when screen locks")
    ask_on_unlock: bool = Field(default=True, description="Ask user about time during lock")
    auto_pause_threshold_minutes: int = Field(
        default=0,
        description="Only ask if absence was longer than this"
    )

    # Report settings
    default_report_template: str = "monthly_report.txt"
    reports_directory: Optional[str] = None

    # UI settings
    show_seconds_in_tray: bool = True
    minimize_to_tray: bool = True
    start_with_windows: bool = False
    theme: str = Field(default="auto", description="Theme: 'light', 'dark', or 'auto' (follows system)")
    font_scale: float = Field(default=1.0, ge=0.5, le=2.0, description="Font scale factor (0.5 to 2.0)")
    language: str = Field(default="auto", description="UI language: 'en', 'de', or 'auto' (detect from system)")

    # Work Regulations
    work_hours_per_day: float = Field(default=8.0, description="Target daily working hours")
    enable_german_compliance: bool = Field(default=False, description="Enable German ArbZG compliance checks")
    check_breaks: bool = Field(default=False, description="Check for mandatory breaks")
    check_rest_periods: bool = Field(default=False, description="Check for rest periods")
    max_daily_hours: float = Field(default=10.0, description="Absolute maximum daily working hours")

    # Backup settings
    backup_enabled: bool = Field(default=False, description="Enable automatic backups")
    backup_frequency_days: int = Field(default=7, description="Backup frequency in days (1=daily, 7=weekly)")
    backup_time: str = Field(default="09:00", description="Time of day for automatic backup (HH:MM)")
    backup_directory: Optional[str] = Field(default=None, description="Custom backup directory path")
    backup_retention_count: int = Field(default=5, description="Number of backup files to keep")
    last_backup_date: Optional[str] = Field(default=None, description="ISO date of last backup")

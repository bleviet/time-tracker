"""
Matrix Report Service - Configuration Models.

This module provides the configuration models for matrix report generation.
The actual report generation is handled by AccountingMatrixService which provides
richer functionality including accounting profile support.
"""

import datetime
import calendar
import logging
from typing import List, Optional, Any
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated

logger = logging.getLogger(__name__)


def parse_german_date(v: Any) -> Any:
    """Parse German date format (DD.MM.YYYY) or pass through datetime.date objects."""
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        try:
            return datetime.datetime.strptime(v, "%d.%m.%Y").date()
        except ValueError:
            pass
    return v


GermanDate = Annotated[datetime.date, BeforeValidator(parse_german_date)]


class TimeOffConfig(BaseModel):
    """Configuration for time off (vacation, sickness, etc)."""
    task_name: str = Field(..., description="Name of the time-off task (e.g., 'Vacation', 'Sickness')")
    days: List[GermanDate] = Field(default_factory=list, description="List of dates for this time off")
    daily_hours: float = Field(default=8.0, description="Hours per day for this time off type")


class ReportConfiguration(BaseModel):
    """
    Configuration for a matrix report.
    Usually loaded from a YAML file.
    """
    period: str = Field(..., description="Year-Month in format YYYY-MM or MM.YYYY")
    output_path: Optional[str] = Field(None, description="Path to save the generated CSV")

    time_off_configs: List[TimeOffConfig] = Field(
        default_factory=list,
        description="Configurations for various types of time off (Vacation, Sickness)"
    )

    excluded_tasks: List[str] = Field(
        default_factory=list,
        description="Tasks that should be listed but NOT counted in totals (e.g. Pause, Break)"
    )

    user_columns: List[str] = Field(
        default_factory=lambda: ["User Column 1", "User Column 2"],
        description="Extra placeholder columns to match user's template"
    )

    @property
    def start_date(self) -> datetime.date:
        """Calculate start date from period string."""
        year, month = self._parse_period()
        return datetime.date(year, month, 1)

    @property
    def end_date(self) -> datetime.date:
        """Calculate end date from period string."""
        year, month = self._parse_period()
        last_day = calendar.monthrange(year, month)[1]
        return datetime.date(year, month, last_day)

    @property
    def date_range(self) -> List[datetime.date]:
        """Generate list of dates in the period."""
        dates = []
        current = self.start_date
        while current <= self.end_date:
            dates.append(current)
            current += datetime.timedelta(days=1)
        return dates

    def _parse_period(self) -> tuple[int, int]:
        """Parse period string to (year, month) tuple."""
        if "-" in self.period:
            # Format: YYYY-MM
            parts = self.period.split("-")
            return int(parts[0]), int(parts[1])
        elif "." in self.period:
            # Format: MM.YYYY
            parts = self.period.split(".")
            return int(parts[1]), int(parts[0])
        else:
            raise ValueError(f"Invalid period format: {self.period}")

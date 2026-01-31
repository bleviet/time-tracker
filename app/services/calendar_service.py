"""
Calendar Service - Handles German holidays and working day logic.

Architecture Decision: Strategy Pattern
This allows easy extension to support other countries' calendars in the future.
"""

import datetime
import holidays


class CalendarService:
    """
    Handles German holiday logic.
    Separated from timer logic for Separation of Concerns.
    """

    def __init__(self, german_state: str = 'BY', respect_holidays: bool = True,
                 respect_weekends: bool = True):
        """
        Initialize with German state code.

        Args:
            german_state: Two-letter German state code (e.g., 'BY' for Bavaria)
            respect_holidays: Whether to consider holidays as non-working days
            respect_weekends: Whether to consider weekends as non-working days
        """
        self.german_state = german_state
        self.respect_holidays = respect_holidays
        self.respect_weekends = respect_weekends

        # Initialize holidays for Germany with specified state
        # Detect language from app setting
        from app.i18n import get_language
        lang = get_language()

        # 'holidays' library uses 'de' for German, 'en' for English
        # For Germany (DE), it usually supports 'de' (default) and 'en'.
        # We enforce it based on app setting.
        self.de_holidays = holidays.country_holidays('DE', subdiv=german_state, language=lang)

    def is_working_day(self, date_obj: datetime.date) -> bool:
        """
        Check if a given date is a working day.

        Args:
            date_obj: The date to check

        Returns:
            True if it's a working day, False otherwise
        """
        # Check weekend (Saturday=5, Sunday=6)
        if self.respect_weekends and date_obj.weekday() > 4:
            return False

        # Check holiday
        if self.respect_holidays and date_obj in self.de_holidays:
            return False

        return True

    def get_holiday_name(self, date_obj: datetime.date) -> str:
        """
        Get the name of the holiday for a given date.

        Args:
            date_obj: The date to check

        Returns:
            Holiday name or empty string if not a holiday
        """
        return self.de_holidays.get(date_obj, "")

    def is_weekend(self, date_obj: datetime.date) -> bool:
        """Check if date is a weekend"""
        return date_obj.weekday() > 4

    def is_holiday(self, date_obj: datetime.date) -> bool:
        """Check if date is a German holiday"""
        return date_obj in self.de_holidays

    def get_working_days_in_range(self, start_date: datetime.date,
                                   end_date: datetime.date) -> int:
        """
        Count working days in a date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            Number of working days
        """
        working_days = 0
        current = start_date

        while current <= end_date:
            if self.is_working_day(current):
                working_days += 1
            current += datetime.timedelta(days=1)

        return working_days

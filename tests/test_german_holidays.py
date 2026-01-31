"""
Tests for German state-specific holidays.

These tests verify that different German states have different public holidays,
ensuring the holidays library correctly handles regional variations.
"""

import datetime
import pytest
from app.services.calendar_service import CalendarService


# German states with their codes
GERMAN_STATES = [
    "BW",  # Baden-Württemberg
    "BY",  # Bavaria
    "BE",  # Berlin
    "BB",  # Brandenburg
    "HB",  # Bremen
    "HH",  # Hamburg
    "HE",  # Hesse
    "MV",  # Mecklenburg-Vorpommern
    "NI",  # Lower Saxony
    "NW",  # North Rhine-Westphalia
    "RP",  # Rhineland-Palatinate
    "SL",  # Saarland
    "SN",  # Saxony
    "ST",  # Saxony-Anhalt
    "SH",  # Schleswig-Holstein
    "TH",  # Thuringia
]


class TestGermanHolidaysNationalwide:
    """Test holidays that are the same across all German states."""

    @pytest.mark.parametrize("state", GERMAN_STATES)
    def test_new_year_is_holiday_in_all_states(self, state: str):
        """New Year's Day (January 1st) is a public holiday in all states."""
        service = CalendarService(german_state=state)
        new_year = datetime.date(2026, 1, 1)
        assert service.is_holiday(new_year), f"New Year should be a holiday in {state}"

    @pytest.mark.parametrize("state", GERMAN_STATES)
    def test_german_unity_day_is_holiday_in_all_states(self, state: str):
        """German Unity Day (October 3rd) is a public holiday in all states."""
        service = CalendarService(german_state=state)
        unity_day = datetime.date(2026, 10, 3)
        assert service.is_holiday(unity_day), f"German Unity Day should be a holiday in {state}"

    @pytest.mark.parametrize("state", GERMAN_STATES)
    def test_christmas_day_is_holiday_in_all_states(self, state: str):
        """Christmas Day (December 25th) is a public holiday in all states."""
        service = CalendarService(german_state=state)
        christmas = datetime.date(2026, 12, 25)
        assert service.is_holiday(christmas), f"Christmas Day should be a holiday in {state}"

    @pytest.mark.parametrize("state", GERMAN_STATES)
    def test_second_christmas_day_is_holiday_in_all_states(self, state: str):
        """Second Christmas Day (December 26th) is a public holiday in all states."""
        service = CalendarService(german_state=state)
        second_christmas = datetime.date(2026, 12, 26)
        assert service.is_holiday(second_christmas), f"Second Christmas Day should be a holiday in {state}"

    @pytest.mark.parametrize("state", GERMAN_STATES)
    def test_good_friday_is_holiday_in_all_states(self, state: str):
        """Good Friday is a public holiday in all states."""
        service = CalendarService(german_state=state)
        # Good Friday 2026 is April 3rd
        good_friday = datetime.date(2026, 4, 3)
        assert service.is_holiday(good_friday), f"Good Friday should be a holiday in {state}"

    @pytest.mark.parametrize("state", GERMAN_STATES)
    def test_easter_monday_is_holiday_in_all_states(self, state: str):
        """Easter Monday is a public holiday in all states."""
        service = CalendarService(german_state=state)
        # Easter Monday 2026 is April 6th
        easter_monday = datetime.date(2026, 4, 6)
        assert service.is_holiday(easter_monday), f"Easter Monday should be a holiday in {state}"


class TestGermanHolidaysRegional:
    """Test holidays that differ between German states."""

    def test_epiphany_is_holiday_only_in_specific_states(self):
        """
        Epiphany (January 6th) is only a holiday in:
        - Baden-Württemberg (BW)
        - Bavaria (BY)
        - Saxony-Anhalt (ST)
        """
        epiphany = datetime.date(2026, 1, 6)
        states_with_epiphany = {"BW", "BY", "ST"}

        for state in GERMAN_STATES:
            service = CalendarService(german_state=state)
            if state in states_with_epiphany:
                assert service.is_holiday(epiphany), (
                    f"Epiphany should be a holiday in {state}"
                )
            else:
                assert not service.is_holiday(epiphany), (
                    f"Epiphany should NOT be a holiday in {state}"
                )

    def test_corpus_christi_is_holiday_only_in_specific_states(self):
        """
        Corpus Christi (Fronleichnam) is only a holiday in:
        - Baden-Württemberg (BW)
        - Bavaria (BY)
        - Hesse (HE)
        - North Rhine-Westphalia (NW)
        - Rhineland-Palatinate (RP)
        - Saarland (SL)
        - Saxony (SN) - partially
        - Thuringia (TH) - partially

        Note: In SN and TH it's only in certain municipalities, but the holidays
        library may treat it differently.
        """
        # Corpus Christi 2026 is June 4th (60 days after Easter Sunday)
        corpus_christi = datetime.date(2026, 6, 4)
        states_with_corpus_christi = {"BW", "BY", "HE", "NW", "RP", "SL"}

        for state in ["BW", "BY", "HE", "NW", "RP", "SL"]:
            service = CalendarService(german_state=state)
            assert service.is_holiday(corpus_christi), (
                f"Corpus Christi should be a holiday in {state}"
            )

        # States definitely without Corpus Christi
        for state in ["BE", "BB", "HB", "HH", "MV", "NI", "SH"]:
            service = CalendarService(german_state=state)
            assert not service.is_holiday(corpus_christi), (
                f"Corpus Christi should NOT be a holiday in {state}"
            )

    def test_assumption_day_is_holiday_only_in_specific_states(self):
        """
        Assumption Day (August 15th) is only a holiday in:
        - Bavaria (BY) - in predominantly Catholic communities
        - Saarland (SL)
        """
        assumption_day = datetime.date(2026, 8, 15)

        service_sl = CalendarService(german_state="SL")
        assert service_sl.is_holiday(assumption_day), (
            "Assumption Day should be a holiday in Saarland"
        )

        # States definitely without Assumption Day
        for state in ["BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SH"]:
            service = CalendarService(german_state=state)
            assert not service.is_holiday(assumption_day), (
                f"Assumption Day should NOT be a holiday in {state}"
            )

    def test_reformation_day_is_holiday_only_in_specific_states(self):
        """
        Reformation Day (October 31st) is only a holiday in:
        - Brandenburg (BB)
        - Bremen (HB)
        - Hamburg (HH)
        - Mecklenburg-Vorpommern (MV)
        - Lower Saxony (NI)
        - Saxony (SN)
        - Saxony-Anhalt (ST)
        - Schleswig-Holstein (SH)
        - Thuringia (TH)
        """
        reformation_day = datetime.date(2026, 10, 31)
        states_with_reformation = {"BB", "HB", "HH", "MV", "NI", "SN", "ST", "SH", "TH"}

        for state in GERMAN_STATES:
            service = CalendarService(german_state=state)
            if state in states_with_reformation:
                assert service.is_holiday(reformation_day), (
                    f"Reformation Day should be a holiday in {state}"
                )
            else:
                assert not service.is_holiday(reformation_day), (
                    f"Reformation Day should NOT be a holiday in {state}"
                )

    def test_all_saints_day_is_holiday_only_in_specific_states(self):
        """
        All Saints' Day (November 1st) is only a holiday in:
        - Baden-Württemberg (BW)
        - Bavaria (BY)
        - North Rhine-Westphalia (NW)
        - Rhineland-Palatinate (RP)
        - Saarland (SL)
        """
        all_saints = datetime.date(2026, 11, 1)
        states_with_all_saints = {"BW", "BY", "NW", "RP", "SL"}

        for state in GERMAN_STATES:
            service = CalendarService(german_state=state)
            if state in states_with_all_saints:
                assert service.is_holiday(all_saints), (
                    f"All Saints' Day should be a holiday in {state}"
                )
            else:
                assert not service.is_holiday(all_saints), (
                    f"All Saints' Day should NOT be a holiday in {state}"
                )

    def test_repentance_day_is_holiday_only_in_saxony(self):
        """
        Repentance and Prayer Day (Buß- und Bettag) is only a public holiday in Saxony (SN).
        It falls on the Wednesday before the last Sunday of the church year.
        """
        # Repentance Day 2026 is November 18th
        repentance_day = datetime.date(2026, 11, 18)

        service_sn = CalendarService(german_state="SN")
        assert service_sn.is_holiday(repentance_day), (
            "Repentance Day should be a holiday in Saxony"
        )

        # All other states should NOT have it
        for state in GERMAN_STATES:
            if state != "SN":
                service = CalendarService(german_state=state)
                assert not service.is_holiday(repentance_day), (
                    f"Repentance Day should NOT be a holiday in {state}"
                )


class TestGermanHolidaysDifferenceBetweenStates:
    """Test that demonstrates clear differences in holiday counts between states."""

    def test_states_have_different_holiday_counts(self):
        """Different states should have different numbers of public holidays in a year."""
        holiday_counts = {}

        for state in GERMAN_STATES:
            service = CalendarService(german_state=state)
            count = 0
            current = datetime.date(2026, 1, 1)
            end = datetime.date(2026, 12, 31)

            while current <= end:
                if service.is_holiday(current):
                    count += 1
                current += datetime.timedelta(days=1)

            holiday_counts[state] = count

        # Verify that there are differences (not all states have the same count)
        unique_counts = set(holiday_counts.values())
        assert len(unique_counts) > 1, (
            f"Expected different holiday counts between states, "
            f"but all states have the same count: {holiday_counts}"
        )

        # Bavaria and Saxony typically have more holidays
        assert holiday_counts["BY"] >= holiday_counts["BE"], (
            "Bavaria should have at least as many holidays as Berlin"
        )

    def test_working_days_differ_between_states(self):
        """Working days in a year should differ between states due to different holidays."""
        working_day_counts = {}

        for state in GERMAN_STATES:
            service = CalendarService(german_state=state)
            working_days = service.get_working_days_in_range(
                datetime.date(2026, 1, 1),
                datetime.date(2026, 12, 31)
            )
            working_day_counts[state] = working_days

        # Verify that there are differences
        unique_counts = set(working_day_counts.values())
        assert len(unique_counts) > 1, (
            f"Expected different working day counts between states, "
            f"but all states have the same count: {working_day_counts}"
        )


class TestCalendarServiceConfiguration:
    """Test CalendarService configuration options."""

    def test_respect_holidays_can_be_disabled(self):
        """When respect_holidays is False, holidays should not affect working day status."""
        service = CalendarService(
            german_state="BY",
            respect_holidays=False,
            respect_weekends=True
        )

        # Christmas 2026 is a Friday (weekday)
        christmas = datetime.date(2026, 12, 25)
        assert service.is_working_day(christmas), (
            "Christmas should be a working day when holidays are not respected"
        )

    def test_respect_weekends_can_be_disabled(self):
        """When respect_weekends is False, weekends should not affect working day status."""
        service = CalendarService(
            german_state="BY",
            respect_holidays=True,
            respect_weekends=False
        )

        # January 3, 2026 is a Saturday
        saturday = datetime.date(2026, 1, 3)
        assert service.is_working_day(saturday), (
            "Saturday should be a working day when weekends are not respected"
        )

    def test_holiday_name_is_returned(self):
        """The get_holiday_name method should return the holiday name."""
        service = CalendarService(german_state="BY")

        # Test Christmas
        christmas = datetime.date(2026, 12, 25)
        name = service.get_holiday_name(christmas)
        assert name, "Christmas should have a holiday name"
        assert "Weihnacht" in name or "Christmas" in name, (
            f"Expected Christmas-related name, got: {name}"
        )

    def test_non_holiday_returns_empty_name(self):
        """Non-holidays should return an empty string for the holiday name."""
        service = CalendarService(german_state="BY")

        # January 2, 2026 is a regular Friday
        regular_day = datetime.date(2026, 1, 2)
        name = service.get_holiday_name(regular_day)
        assert name == "", f"Regular day should have no holiday name, got: {name}"


import datetime
import csv
import io
import logging
from typing import List, Dict, Any
from PySide6.QtCore import QLocale

from app.i18n import tr

from app.domain.models import UserPreferences
from app.infra.repository import TaskRepository, TimeEntryRepository, AccountingRepository, UserRepository
from app.services.matrix_report_service import ReportConfiguration
from app.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)

class AccountingMatrixService:
    """
    Generates a Matrix-style report enriched with Accounting information.
    Aggregates by Accounting Profile.
    Rows: Accounting Profiles (with joined Task Names)
    Columns: Task, Profile, [Accounting Cols], Total, [Days...]
    Includes Footer Rows: Total, Daily Target, Overtime, Compliance Notes.
    """

    def __init__(self, german_state: str = 'BY'):
        self.task_repo = TaskRepository()
        self.entry_repo = TimeEntryRepository()
        self.acc_repo = AccountingRepository()
        self.user_repo = UserRepository()
        self.calendar_service = CalendarService(german_state=german_state)

    async def generate_report(self, config: ReportConfiguration) -> str:
        # 1. Fetch Data
        tasks = await self.task_repo.get_all_active()
        accounting_profiles = await self.acc_repo.get_all_active()
        prefs = await self.user_repo.get_preferences()

        acc_map = {acc.id: acc for acc in accounting_profiles}
        acc_columns = prefs.accounting_columns

        start_dt = datetime.datetime.combine(config.start_date, datetime.time.min)
        end_dt = datetime.datetime.combine(config.end_date, datetime.time.max)

        # 2. Build Aggregation Structures
        # Key: Tuple(Name, Frozenset(Attributes)) or None (for unassigned)
        # Value: Dict[Date, float]
        matrix: Dict[Any, Dict[datetime.date, float]] = {}

        # Map Key -> Set of Task Names
        acc_tasks_map: Dict[Any, set] = {}

        # Track special days for Day Info row
        vacation_dates = set()
        sickness_dates = set()

        # 3. Process Entries
        for task in tasks:
            # Determine Aggregation Key logic
            acc_id = task.accounting_id
            key = None

            if acc_id and acc_id in acc_map:
                acc = acc_map[acc_id]
                # Key by Content (Name + Attributes) to merge duplicates
                key = (acc.name, frozenset(acc.attributes.items()))

            # Initialize if new key
            if key not in matrix:
                matrix[key] = {}
                acc_tasks_map[key] = set()

            acc_tasks_map[key].add(task.name)

            entries = await self.entry_repo.get_by_task(
                task.id,
                start_date=start_dt,
                end_date=end_dt
            )

            t_lower = task.name.lower()
            is_vac_task = "vacation" in t_lower or "urlaub" in t_lower
            is_sick_task = "sickness" in t_lower or "krank" in t_lower

            for entry in entries:
                date_key = entry.start_time.date()
                hours = entry.duration_seconds / 3600.0
                matrix[key][date_key] = matrix[key].get(date_key, 0.0) + hours

                # Tag status if hours exist
                if hours > 0:
                    if is_vac_task:
                        vacation_dates.add(date_key)
                    elif is_sick_task:
                        sickness_dates.add(date_key)

        # 4. Process Time Off (if configured)
        for time_off in config.time_off_configs:
            # Treat Time Off as Unassigned (None)
            key = None
            if key not in matrix:
                matrix[key] = {}
                acc_tasks_map[key] = set()

            acc_tasks_map[key].add(time_off.task_name)

            t_lower = time_off.task_name.lower()
            is_vac = "vacation" in t_lower or "urlaub" in t_lower
            is_sick = "sickness" in t_lower or "krank" in t_lower

            for d in time_off.days:
                if config.start_date <= d <= config.end_date:
                    matrix[key][d] = matrix[key].get(d, 0.0) + time_off.daily_hours
                    if is_vac:
                         vacation_dates.add(d)
                    elif is_sick:
                         sickness_dates.add(d)

        # 5. Format CSV
        return self._format_csv(matrix, acc_tasks_map, acc_columns, config, prefs, vacation_dates, sickness_dates)

    def _format_csv(self,
                    matrix: Dict[Any, Dict[datetime.date, float]],
                    acc_tasks_map: Dict[Any, set],
                    acc_columns: List[str],
                    config: ReportConfiguration,
                    prefs: UserPreferences,
                    vacation_dates: set[datetime.date],
                    sickness_dates: set[datetime.date]) -> str:

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n')

        dates = config.date_range
        locale = QLocale()

        # Helper for number formatting
        def fmt_num(val: float) -> str:
            return locale.toString(val, 'f', 1)

        # Header: Task name(s), Accounting Profile, [Cols], Total hours, [Dates]
        header = [tr("report.col_task"), tr("report.col_profile")] + acc_columns + [tr("report.col_total")]
        header.extend([self._format_date(d) for d in dates])
        writer.writerow(header)

        # 1b. Day Info Row (Holiday, Vacation, Sickness)
        # We need to scan entries/calendar to determine status per day.
        # Priority: Holiday > Sickness > Vacation
        status_row = [tr("report.row_info")] + [""] * (len(acc_columns) + 2) # +2 for Profile + Total

        # Pre-calc statuses
        day_statuses = {}
        for d in dates:
            status = ""
            # 1. Holiday
            if self.calendar_service.is_holiday(d):
                name = self.calendar_service.get_holiday_name(d)
                status = f"{tr('status.holiday')}: {name}" if name else tr("status.holiday")
            else:
                # 2. Check for Vacation/Sickness using pre-calced sets
                if d in sickness_dates:
                    status = tr("status.sickness")
                elif d in vacation_dates:
                    status = tr("status.vacation")

            day_statuses[d] = status
            status_row.append(status)

        writer.writerow(status_row)

        # Prepare Rows - split into assigned and unassigned accounting
        assigned_rows = []  # Has accounting profile
        unassigned_rows = []  # No accounting profile

        for key, row_data in matrix.items():
            # Resolve Accounting Info from Key
            acc_name = ""
            acc_attrs = {}

            if key is not None:
                acc_name = key[0]
                acc_attrs = dict(key[1])

            task_names = sorted(list(acc_tasks_map[key]))
            task_names_str = ", ".join(task_names)

            item = {
                'task_names_str': task_names_str,
                'acc_name': acc_name,
                'acc_attrs': acc_attrs,
                'row_data': row_data
            }

            # Separate by accounting assignment
            if key is not None:
                assigned_rows.append(item)
            else:
                unassigned_rows.append(item)

        # Sort assigned rows by Accounting Profile Name
        assigned_rows.sort(key=lambda x: x['acc_name'])
        unassigned_rows.sort(key=lambda x: x['task_names_str'])

        day_totals = {d: 0.0 for d in dates}

        # Write assigned rows (tasks WITH accounting)
        for item in assigned_rows:
            row_data = item['row_data']
            acc_name = item['acc_name']
            rows_total_hours = sum(row_data.values())

            if rows_total_hours == 0:
                continue

            row = [item['task_names_str'], acc_name]
            for col in acc_columns:
                row.append(item['acc_attrs'].get(col, ""))

            row.append(fmt_num(rows_total_hours))

            for d in dates:
                val = row_data.get(d, 0.0)
                if val > 0:
                    row.append(fmt_num(val))
                    day_totals[d] += val
                else:
                    row.append("")

            writer.writerow(row)

        # Spacer for Footer Rows
        # Header: Task(1), Profile(1), Cols(N), Total(1)
        padding = [""] * (1 + len(acc_columns))

        # 1. Total Work
        writer.writerow([])
        total_row = [tr("report.row_total")] + padding
        grand_total = sum(day_totals.values())
        total_row.append(fmt_num(grand_total))

        for d in dates:
            val = day_totals[d]
            if val > 0:
                total_row.append(fmt_num(val))
            else:
                total_row.append("")
        writer.writerow(total_row)

        # 2. Daily Target (Footer Row 2)
        # Note: Holidays and weekends have 0 target hours
        target_row = [tr("report.row_target")] + padding
        # Calculate totals
        total_target = 0.0
        day_targets = {}
        for d in dates:
            # Only count as working day if Mon-Fri AND not a holiday
            is_weekday = d.weekday() < 5
            is_holiday = self.calendar_service.is_holiday(d)
            if is_weekday and not is_holiday:
                day_targets[d] = prefs.work_hours_per_day
                total_target += prefs.work_hours_per_day
            else:
                day_targets[d] = 0.0

        target_row.append(fmt_num(total_target))
        for d in dates:
            val = day_targets[d]
            target_row.append(fmt_num(val))
        writer.writerow(target_row)

        # 3. Overtime (Footer Row 3)
        ot_row = [tr("report.row_overtime")] + padding
        total_ot = grand_total - total_target
        # Use simple formatting for overtime to include sign if possible?
        # QLocale doesn't force sign always, but usually handles negative.
        # Python's f"{val:+.1f}" forces sign.
        # But we need locale specific separator.
        # We can do: ("+" if total_ot > 0 else "") + fmt_num(total_ot)
        # Or just rely on negative sign.
        ot_row.append(fmt_num(total_ot))

        for d in dates:
            actual = day_totals.get(d, 0.0)
            target = day_targets.get(d, 0.0)
            diff = actual - target
            ot_row.append(fmt_num(diff))
        writer.writerow(ot_row)

        # 4. Compliance Warnings (Footer Row 4 - Optional)
        if prefs.enable_german_compliance:
            notes_row = [tr("report.row_compliance")] + padding + [""] # skip total col
            has_warnings = False
            notes_list = []

            for d in dates:
                actual = day_totals.get(d, 0.0)
                note = ""
                # Check absolute limit
                if actual > prefs.max_daily_hours:
                    note = f"> {prefs.max_daily_hours}h!"
                    has_warnings = True

                notes_list.append(note)

            if has_warnings:
                 notes_row.extend(notes_list)
                 writer.writerow(notes_row)

        # 5. Unassigned Tasks Section (for information only)
        if unassigned_rows:
            writer.writerow([])
            writer.writerow([])
            writer.writerow([tr("report.unassigned_title")])
            writer.writerow([])

            # Write unassigned rows header (same as main header)
            writer.writerow(header)

            for item in unassigned_rows:
                row_data = item['row_data']
                rows_total_hours = sum(row_data.values())

                if rows_total_hours == 0:
                    continue

                row = [item['task_names_str'], ""]  # No accounting profile
                for col in acc_columns:
                    row.append("")  # No accounting attributes

                row.append(fmt_num(rows_total_hours))

                for d in dates:
                    val = row_data.get(d, 0.0)
                    if val > 0:
                        row.append(fmt_num(val))
                    else:
                        row.append("")

                writer.writerow(row)

        return output.getvalue()

    def _format_date(self, date_obj: datetime.date) -> str:
        """
        Format date using system locale.
        e.g. 'ddd, dd. MMM yy' (German) or 'ddd, MMM dd, yy' (English)
        """
        loc = QLocale()
        if loc.language() == QLocale.German:
             return loc.toString(date_obj, "ddd, dd. MMM yy")
        else:
             return loc.toString(date_obj, "ddd, MMM dd, yy")


"""
Excel Report Service using XlsxWriter.
Generates rich Excel reports with Dashboards and formatted Data tables.
"""

import datetime
import calendar
from pathlib import Path
from typing import Dict, List, Optional, Any
import xlsxwriter

from app.domain.models import Task, TimeEntry, UserPreferences
from app.infra.repository import TaskRepository, TimeEntryRepository, UserRepository, AccountingRepository
from app.services.matrix_report_service import ReportConfiguration
from app.services.calendar_service import CalendarService
from app.i18n import tr

class ExcelReportService:
    """
    Generates .xlsx reports with:
    - Tab 1: Detailed Data (Matrix format matching CSV)
    - Tab 2: Dashboard (KPIs + Charts)
    """

    def __init__(self, german_state: str = 'BY'):
        self.german_state = german_state
        self.calendar_service = CalendarService(german_state=german_state)

    async def generate_report(self, config: ReportConfiguration) -> str:
        """
        Generate the Excel report and save to config.output_path.
        Returns the path as string.
        """
        # 1. Fetch Data
        data = await self._fetch_data(config)

        # 2. Create Workbook
        workbook = xlsxwriter.Workbook(config.output_path)

        # Colors & Formats
        fmt_header = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1
        })
        fmt_date = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': 1})
        fmt_duration = workbook.add_format({'num_format': '[h]:mm:ss', 'border': 1})
        fmt_number = workbook.add_format({'border': 1})

        # --- TAB 1: DATA ---
        ws_data = workbook.add_worksheet("Data")
        self._create_data_sheet(workbook, ws_data, data, fmt_header, fmt_date, fmt_duration, fmt_number)

        # --- TAB 2: DASHBOARD ---
        ws_dash = workbook.add_worksheet("Dashboard")
        self._create_dashboard_sheet(workbook, ws_dash, data, config.period)

        workbook.close()
        return config.output_path

    async def _fetch_data(self, config: ReportConfiguration) -> Dict:
        """Fetch and aggregate data for the report in matrix format"""
        entry_repo = TimeEntryRepository()
        task_repo = TaskRepository()
        acc_repo = AccountingRepository()
        user_repo = UserRepository()

        # Parse period
        try:
            month_str, year_str = config.period.split('.')
            month, year = int(month_str), int(year_str)
        except ValueError:
            now = datetime.datetime.now()
            month, year = now.month, now.year

        start_date = datetime.datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime.datetime(year, month, last_day, 23, 59, 59)

        # Build date range
        dates = []
        current = datetime.date(year, month, 1)
        while current.month == month:
            dates.append(current)
            current += datetime.timedelta(days=1)

        # Fetch Entities
        tasks = await task_repo.get_all_active()
        acc_profiles = await acc_repo.get_all_active()
        prefs = await user_repo.get_preferences()

        # Build Accounting Map
        acc_map = {acc.id: acc for acc in acc_profiles}
        acc_columns = prefs.accounting_columns

        # Matrix structure: Key -> {date: hours}
        # Key: Tuple(Name, Frozenset(Attributes)) or None (for unassigned)
        matrix: Dict[Any, Dict[datetime.date, float]] = {}
        acc_tasks_map: Dict[Any, set] = {}

        # Track special days
        vacation_dates = set()
        sickness_dates = set()

        # Aggregations for Dashboard
        total_seconds = 0
        by_accounting = {}
        by_day = {d: 0 for d in range(1, last_day + 1)}
        vacation_seconds = 0
        sickness_seconds = 0

        no_accounting_label = tr("report.dashboard.no_accounting")

        for task in tasks:
            if task.id in config.excluded_tasks:
                continue

            # Determine Aggregation Key
            acc_id = task.accounting_id
            key = None
            acc_name = no_accounting_label

            if acc_id and acc_id in acc_map:
                acc = acc_map[acc_id]
                key = (acc.name, frozenset(acc.attributes.items()))
                acc_name = acc.name

            if key not in matrix:
                matrix[key] = {}
                acc_tasks_map[key] = set()

            acc_tasks_map[key].add(task.name)

            entries = await entry_repo.get_by_task(task.id, start_date, end_date)

            t_lower = task.name.lower()
            is_vac_task = "vacation" in t_lower or "urlaub" in t_lower
            is_sick_task = "sickness" in t_lower or "krank" in t_lower

            for entry in entries:
                duration = entry.duration_seconds
                if duration <= 0:
                    continue

                date_key = entry.start_time.date()
                hours = duration / 3600.0
                matrix[key][date_key] = matrix[key].get(date_key, 0.0) + hours

                # Aggregations for dashboard
                total_seconds += duration
                if is_vac_task:
                    category_name = tr("status.vacation")
                    vacation_seconds += duration
                elif is_sick_task:
                    category_name = tr("status.sickness")
                    sickness_seconds += duration
                else:
                    category_name = acc_name
                by_accounting[category_name] = by_accounting.get(category_name, 0) + duration
                by_day[entry.start_time.day] = by_day.get(entry.start_time.day, 0) + duration

                if hours > 0:
                    if is_vac_task:
                        vacation_dates.add(date_key)
                    elif is_sick_task:
                        sickness_dates.add(date_key)

        # Process Time Off configs
        for time_off in config.time_off_configs:
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
                    duration_seconds = time_off.daily_hours * 3600.0
                    total_seconds += duration_seconds
                    by_day[d.day] = by_day.get(d.day, 0) + duration_seconds
                    if is_vac:
                        vacation_seconds += duration_seconds
                        vacation_dates.add(d)
                    elif is_sick:
                        sickness_seconds += duration_seconds
                        sickness_dates.add(d)

        if vacation_seconds > 0:
            by_accounting[tr("status.vacation")] = vacation_seconds
        if sickness_seconds > 0:
            by_accounting[tr("status.sickness")] = sickness_seconds

        return {
            "matrix": matrix,
            "acc_tasks_map": acc_tasks_map,
            "dates": dates,
            "total_seconds": total_seconds,
            "by_accounting": by_accounting,
            "by_day": by_day,
            "prefs": prefs,
            "acc_columns": acc_columns,
            "vacation_dates": vacation_dates,
            "sickness_dates": sickness_dates,
        }

    def _create_data_sheet(self, workbook, worksheet, data, fmt_header, fmt_date, fmt_duration, fmt_number):
        """Create the Data table in matrix format (matching CSV output)"""
        prefs = data['prefs']
        acc_cols = data['acc_columns']
        dates = data['dates']
        matrix = data['matrix']
        acc_tasks_map = data['acc_tasks_map']
        vacation_dates = data['vacation_dates']
        sickness_dates = data['sickness_dates']

        # Calculate date column start position
        date_col_start = len(acc_cols) + 3  # Task + Profile + acc_cols + Total

        # Pre-calculate day types for coloring (matching history_window.py colors)
        weekend_days = set()
        holiday_days = set()
        for d in dates:
            if self.calendar_service.is_holiday(d):
                holiday_days.add(d)
            elif d.weekday() >= 5:
                weekend_days.add(d)

        # Formats - Colors matching history_window.py calendar
        # Vacation: #4CAF50 (green), Sickness: #c62828 (dark red), Holiday: #1976d2 (blue)
        # Weekend: light gray for non-working days

        # Header formats
        fmt_header_weekend = workbook.add_format({
            'bold': True, 'bg_color': '#E0E0E0', 'font_color': '#333333', 'border': 1
        })
        fmt_header_holiday = workbook.add_format({
            'bold': True, 'bg_color': '#1976d2', 'font_color': 'white', 'border': 1
        })

        # Info row formats
        fmt_info_header = workbook.add_format({
            'bold': True, 'bg_color': '#E2EFDA', 'border': 1
        })
        fmt_info = workbook.add_format({
            'bg_color': '#E2EFDA', 'border': 1, 'font_size': 9
        })
        fmt_info_weekend = workbook.add_format({
            'bg_color': '#F5F5F5', 'border': 1, 'font_size': 9
        })
        fmt_info_holiday = workbook.add_format({
            'bg_color': '#BBDEFB', 'border': 1, 'font_size': 9  # Light blue
        })
        fmt_info_vacation = workbook.add_format({
            'bg_color': '#C8E6C9', 'border': 1, 'font_size': 9  # Light green
        })
        fmt_info_sickness = workbook.add_format({
            'bg_color': '#FFCDD2', 'border': 1, 'font_size': 9  # Light red
        })

        # Total row formats
        fmt_total_header = workbook.add_format({
            'bold': True, 'bg_color': '#FFF2CC', 'border': 1
        })
        fmt_total = workbook.add_format({
            'bg_color': '#FFF2CC', 'border': 1, 'num_format': '0.0'
        })
        fmt_total_weekend = workbook.add_format({
            'bg_color': '#E0E0E0', 'border': 1, 'num_format': '0.0'
        })
        fmt_total_holiday = workbook.add_format({
            'bg_color': '#BBDEFB', 'border': 1, 'num_format': '0.0'
        })

        # Target row formats
        fmt_target = workbook.add_format({
            'bg_color': '#DDEBF7', 'border': 1, 'num_format': '0.0'
        })
        fmt_target_weekend = workbook.add_format({
            'bg_color': '#E0E0E0', 'border': 1, 'num_format': '0.0'
        })
        fmt_target_holiday = workbook.add_format({
            'bg_color': '#BBDEFB', 'border': 1, 'num_format': '0.0'
        })

        # Overtime row formats
        fmt_overtime = workbook.add_format({
            'bg_color': '#FCE4D6', 'border': 1, 'num_format': '0.0'
        })
        fmt_overtime_weekend = workbook.add_format({
            'bg_color': '#E0E0E0', 'border': 1, 'num_format': '0.0'
        })
        fmt_overtime_holiday = workbook.add_format({
            'bg_color': '#BBDEFB', 'border': 1, 'num_format': '0.0'
        })

        # Data cell formats
        fmt_hours = workbook.add_format({
            'border': 1, 'num_format': '0.0'
        })
        fmt_hours_weekend = workbook.add_format({
            'border': 1, 'num_format': '0.0', 'bg_color': '#F5F5F5'
        })
        fmt_hours_holiday = workbook.add_format({
            'border': 1, 'num_format': '0.0', 'bg_color': '#BBDEFB'
        })
        fmt_empty = workbook.add_format({'border': 1})
        fmt_empty_weekend = workbook.add_format({'border': 1, 'bg_color': '#F5F5F5'})
        fmt_empty_holiday = workbook.add_format({'border': 1, 'bg_color': '#BBDEFB'})

        # Headers: Task, Profile, [Acc Cols], Total, [Dates...]
        headers = [tr("report.col_task"), tr("report.col_profile")] + acc_cols + [tr("report.col_total")]
        headers.extend([self._format_date(d) for d in dates])

        row_idx = 0
        for col, header in enumerate(headers):
            # Use appropriate format for weekend/holiday date columns
            if col >= date_col_start:
                d = dates[col - date_col_start]
                if d in holiday_days:
                    fmt = fmt_header_holiday
                elif d in weekend_days:
                    fmt = fmt_header_weekend
                else:
                    fmt = fmt_header
            else:
                fmt = fmt_header
            worksheet.write(row_idx, col, header, fmt)

        # Day Info Row (Holiday, Vacation, Sickness)
        row_idx += 1
        worksheet.write(row_idx, 0, tr("report.row_info"), fmt_info_header)
        for col in range(1, len(acc_cols) + 3):  # Profile + acc_cols + Total
            worksheet.write(row_idx, col, "", fmt_info)

        for i, d in enumerate(dates):
            status = ""
            # Determine format based on day type
            if d in holiday_days:
                name = self.calendar_service.get_holiday_name(d)
                status = f"{tr('status.holiday')}: {name}" if name else tr("status.holiday")
                cell_fmt = fmt_info_holiday
            elif d in sickness_dates:
                status = tr("status.sickness")
                cell_fmt = fmt_info_sickness
            elif d in vacation_dates:
                status = tr("status.vacation")
                cell_fmt = fmt_info_vacation
            elif d in weekend_days:
                cell_fmt = fmt_info_weekend
            else:
                cell_fmt = fmt_info
            worksheet.write(row_idx, date_col_start + i, status, cell_fmt)

        # Separate assigned and unassigned rows
        assigned_rows = []
        unassigned_rows = []

        for key, row_data in matrix.items():
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

            if key is not None:
                assigned_rows.append(item)
            else:
                unassigned_rows.append(item)

        assigned_rows.sort(key=lambda x: x['acc_name'])
        unassigned_rows.sort(key=lambda x: x['task_names_str'])

        day_totals = {d: 0.0 for d in dates}

        # Write assigned rows
        for item in assigned_rows:
            row_data = item['row_data']
            rows_total_hours = sum(row_data.values())

            if rows_total_hours == 0:
                continue

            row_idx += 1
            col = 0
            worksheet.write(row_idx, col, item['task_names_str'], fmt_number)
            col += 1
            worksheet.write(row_idx, col, item['acc_name'], fmt_number)
            col += 1

            for acc_col in acc_cols:
                worksheet.write(row_idx, col, item['acc_attrs'].get(acc_col, ""), fmt_number)
                col += 1

            worksheet.write(row_idx, col, rows_total_hours, fmt_hours)
            col += 1

            for d in dates:
                val = row_data.get(d, 0.0)
                # Choose format based on day type
                if d in holiday_days:
                    cell_fmt = fmt_hours_holiday if val > 0 else fmt_empty_holiday
                elif d in weekend_days:
                    cell_fmt = fmt_hours_weekend if val > 0 else fmt_empty_weekend
                else:
                    cell_fmt = fmt_hours if val > 0 else fmt_empty

                if val > 0:
                    worksheet.write(row_idx, col, val, cell_fmt)
                    day_totals[d] += val
                else:
                    worksheet.write(row_idx, col, "", cell_fmt)
                col += 1

        # Footer rows
        padding_cols = 1 + len(acc_cols)  # Profile + acc_cols

        # Total Row
        row_idx += 2
        worksheet.write(row_idx, 0, tr("report.row_total"), fmt_total_header)
        for col in range(1, padding_cols + 1):
            worksheet.write(row_idx, col, "", fmt_total)

        grand_total = sum(day_totals.values())
        worksheet.write(row_idx, padding_cols + 1, grand_total, fmt_total)

        col = padding_cols + 2
        for d in dates:
            val = day_totals[d]
            # Choose format based on day type
            if d in holiday_days:
                cell_fmt = fmt_total_holiday
            elif d in weekend_days:
                cell_fmt = fmt_total_weekend
            else:
                cell_fmt = fmt_total

            if val > 0:
                worksheet.write(row_idx, col, val, cell_fmt)
            else:
                worksheet.write(row_idx, col, "", cell_fmt)
            col += 1

        # Target Row
        row_idx += 1
        worksheet.write(row_idx, 0, tr("report.row_target"), fmt_total_header)
        for col in range(1, padding_cols + 1):
            worksheet.write(row_idx, col, "", fmt_target)

        total_target = 0.0
        day_targets = {}
        for d in dates:
            is_weekday = d.weekday() < 5
            is_holiday = self.calendar_service.is_holiday(d)
            if is_weekday and not is_holiday:
                day_targets[d] = prefs.work_hours_per_day
                total_target += prefs.work_hours_per_day
            else:
                day_targets[d] = 0.0

        worksheet.write(row_idx, padding_cols + 1, total_target, fmt_target)

        col = padding_cols + 2
        for d in dates:
            # Choose format based on day type
            if d in holiday_days:
                cell_fmt = fmt_target_holiday
            elif d in weekend_days:
                cell_fmt = fmt_target_weekend
            else:
                cell_fmt = fmt_target
            worksheet.write(row_idx, col, day_targets[d], cell_fmt)
            col += 1

        # Overtime Row
        row_idx += 1
        worksheet.write(row_idx, 0, tr("report.row_overtime"), fmt_total_header)
        for col in range(1, padding_cols + 1):
            worksheet.write(row_idx, col, "", fmt_overtime)

        total_ot = grand_total - total_target
        worksheet.write(row_idx, padding_cols + 1, total_ot, fmt_overtime)

        col = padding_cols + 2
        for d in dates:
            actual = day_totals.get(d, 0.0)
            target = day_targets.get(d, 0.0)
            diff = actual - target
            # Choose format based on day type
            if d in holiday_days:
                cell_fmt = fmt_overtime_holiday
            elif d in weekend_days:
                cell_fmt = fmt_overtime_weekend
            else:
                cell_fmt = fmt_overtime
            worksheet.write(row_idx, col, diff, cell_fmt)
            col += 1

        # Unassigned Tasks Section
        if unassigned_rows:
            row_idx += 3
            worksheet.write(row_idx, 0, tr("report.unassigned_title"), fmt_header)

            row_idx += 1
            for col, header in enumerate(headers):
                if col >= date_col_start:
                    d = dates[col - date_col_start]
                    if d in holiday_days:
                        fmt = fmt_header_holiday
                    elif d in weekend_days:
                        fmt = fmt_header_weekend
                    else:
                        fmt = fmt_header
                else:
                    fmt = fmt_header
                worksheet.write(row_idx, col, header, fmt)

            for item in unassigned_rows:
                row_data = item['row_data']
                rows_total_hours = sum(row_data.values())

                if rows_total_hours == 0:
                    continue

                row_idx += 1
                col = 0
                worksheet.write(row_idx, col, item['task_names_str'], fmt_number)
                col += 1
                worksheet.write(row_idx, col, "", fmt_number)  # No accounting
                col += 1

                for _ in acc_cols:
                    worksheet.write(row_idx, col, "", fmt_number)
                    col += 1

                worksheet.write(row_idx, col, rows_total_hours, fmt_hours)
                col += 1

                for d in dates:
                    val = row_data.get(d, 0.0)
                    # Choose format based on day type
                    if d in holiday_days:
                        cell_fmt = fmt_hours_holiday if val > 0 else fmt_empty_holiday
                    elif d in weekend_days:
                        cell_fmt = fmt_hours_weekend if val > 0 else fmt_empty_weekend
                    else:
                        cell_fmt = fmt_hours if val > 0 else fmt_empty

                    if val > 0:
                        worksheet.write(row_idx, col, val, cell_fmt)
                    else:
                        worksheet.write(row_idx, col, "", cell_fmt)
                    col += 1

        # Set Column Widths
        worksheet.set_column(0, 0, 30)  # Task
        worksheet.set_column(1, 1, 20)  # Profile
        worksheet.set_column(2, 2 + len(acc_cols) - 1, 15)  # Acc cols
        worksheet.set_column(2 + len(acc_cols), 2 + len(acc_cols), 10)  # Total
        worksheet.set_column(date_col_start, date_col_start + len(dates) - 1, 12)  # Dates

    def _format_date(self, date_obj: datetime.date) -> str:
        """Format date for column header"""
        return date_obj.strftime("%a, %d. %b")

    def _create_dashboard_sheet(self, workbook, worksheet, data, period):
        """Create the Dashboard with KPI cards and Charts"""
        worksheet.hide_gridlines(2) # Hide gridlines

        color_work = '#4472C4'
        color_vacation = '#4CAF50'
        color_sickness = '#c62828'

        # Layout tuning
        worksheet.set_column('A:A', 2)
        worksheet.set_column('B:B', 16)
        worksheet.set_column('C:C', 16)
        worksheet.set_column('D:D', 4)
        worksheet.set_column('E:E', 16)
        worksheet.set_column('F:F', 16)
        worksheet.set_column('G:G', 4)
        worksheet.set_column('H:H', 20)
        worksheet.set_row(1, 28)
        worksheet.set_row(3, 22)
        worksheet.set_row(4, 28)

        # --- TITLE ---
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 20, 'font_color': '#203764'
        })
        worksheet.merge_range('B2:H2', tr("report.dashboard.title", period=period), title_fmt)

        # --- KPI CARDS ---
        # Card Format
        card_header_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_color': '#666666',
            'bg_color': '#F2F2F2', 'align': 'center', 'border': 1
        })
        card_value_fmt = workbook.add_format({
            'bold': True, 'font_size': 18, 'font_color': '#203764',
            'bg_color': 'white', 'align': 'center', 'border': 1, 'num_format': '#,##0.0'
        })

        total_hours = data['total_seconds'] / 3600.0

        # Card 1: Total Hours
        worksheet.merge_range('B4:C4', tr("report.dashboard.total_hours"), card_header_fmt)
        worksheet.merge_range('B5:C5', total_hours, card_value_fmt)

        # Card 2: Avg per Day (Simple Metric for now)
        # Using working days estimation could be better, but simplifing
        days_with_work = len([d for d, s in data['by_day'].items() if s > 0]) or 1
        avg_hours = total_hours / days_with_work

        worksheet.merge_range('E4:F4', tr("report.dashboard.avg_hours_day"), card_header_fmt)
        worksheet.merge_range('E5:F5', avg_hours, card_value_fmt)

        # --- CHARTS ---

        # Prepare hidden data for charts
        ws_hidden = workbook.add_worksheet("Hidden_Chart_Data")
        ws_hidden.hide()

        # 1. Donut Data (By Accounting)
        row = 0
        ws_hidden.write(row, 0, tr("report.dashboard.category"))
        ws_hidden.write(row, 1, tr("report.dashboard.hours"))
        categories = list(data['by_accounting'].items())
        for cat, seconds in categories:
            row += 1
            ws_hidden.write(row, 0, cat)
            ws_hidden.write(row, 1, seconds / 3600.0)
        donut_data_len = row

        # 2. Bar Data (By Day)
        row = 0
        ws_hidden.write(row, 3, tr("report.dashboard.day"))
        ws_hidden.write(row, 4, tr("report.dashboard.legend.work"))
        ws_hidden.write(row, 5, tr("report.dashboard.legend.vacation"))
        ws_hidden.write(row, 6, tr("report.dashboard.legend.sickness"))
        weekday_keys = [
            "weekday.short.mon",
            "weekday.short.tue",
            "weekday.short.wed",
            "weekday.short.thu",
            "weekday.short.fri",
            "weekday.short.sat",
            "weekday.short.sun",
        ]
        for date_obj in data['dates']:
            row += 1
            day_label = f"{tr(weekday_keys[date_obj.weekday()])}\n{date_obj.day}"
            seconds = data['by_day'].get(date_obj.day, 0)
            is_sick = date_obj in data['sickness_dates']
            is_vac = date_obj in data['vacation_dates']
            work_seconds = 0.0 if is_sick or is_vac else seconds
            vac_seconds = seconds if is_vac else 0.0
            sick_seconds = seconds if is_sick else 0.0
            ws_hidden.write(row, 3, day_label)
            ws_hidden.write(row, 4, work_seconds / 3600.0)
            ws_hidden.write(row, 5, vac_seconds / 3600.0)
            ws_hidden.write(row, 6, sick_seconds / 3600.0)
        bar_data_len = row

        # -- Donut Chart --
        chart_donut = workbook.add_chart({'type': 'doughnut'})
        if donut_data_len > 0:
            points = []
            for cat, _seconds in categories:
                if cat == tr("status.vacation"):
                    points.append({'fill': {'color': color_vacation}})
                elif cat == tr("status.sickness"):
                    points.append({'fill': {'color': color_sickness}})
                else:
                    points.append({})
            chart_donut.add_series({
                'name': tr("report.dashboard.hours_by_category"),
                'categories': ['Hidden_Chart_Data', 1, 0, donut_data_len, 0],
                'values':     ['Hidden_Chart_Data', 1, 1, donut_data_len, 1],
                'data_labels': {
                    'percentage': True,
                    'value': True,
                    'separator': '\n',
                    'num_format': '0.00',
                },
                'points': points,
            })
        chart_donut.set_title({'name': tr("report.dashboard.work_distribution")})
        chart_donut.set_style(10) # Modern style
        worksheet.insert_chart('B8', chart_donut, {'x_scale': 1.3, 'y_scale': 1.3})

        # -- Bar Chart --
        chart_bar = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
        if bar_data_len > 0:
            chart_bar.add_series({
                'name': tr("report.dashboard.legend.work"),
                'categories': ['Hidden_Chart_Data', 1, 3, bar_data_len, 3],
                'values':     ['Hidden_Chart_Data', 1, 4, bar_data_len, 4],
                'fill':       {'color': color_work},
            })
            chart_bar.add_series({
                'name': tr("report.dashboard.legend.vacation"),
                'categories': ['Hidden_Chart_Data', 1, 3, bar_data_len, 3],
                'values':     ['Hidden_Chart_Data', 1, 5, bar_data_len, 5],
                'fill':       {'color': color_vacation},
            })
            chart_bar.add_series({
                'name': tr("report.dashboard.legend.sickness"),
                'categories': ['Hidden_Chart_Data', 1, 3, bar_data_len, 3],
                'values':     ['Hidden_Chart_Data', 1, 6, bar_data_len, 6],
                'fill':       {'color': color_sickness},
                'data_labels': {'total': True, 'num_format': '0.00'},
            })
        chart_bar.set_title({'name': tr("report.dashboard.daily_trend")})
        chart_bar.set_legend({'position': 'bottom'})
        chart_bar.set_x_axis({'name': tr("report.dashboard.day_of_month")})
        chart_bar.set_y_axis({'name': tr("report.dashboard.hours")})
        chart_bar.set_style(10)

        worksheet.insert_chart('B28', chart_bar, {'x_scale': 2.4, 'y_scale': 1.4})

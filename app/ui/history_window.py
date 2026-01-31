import asyncio
import calendar
from datetime import datetime, timedelta
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QHeaderView, QMessageBox, QMenu,
    QAbstractItemView, QGroupBox, QCheckBox, QDoubleSpinBox, QSplitter, QToolTip
)
from PySide6.QtCore import Qt, QDate, Signal, QRect, QEvent, QLocale
from PySide6.QtGui import QColor, QAction, QPainter, QTextCharFormat, QKeySequence, QShortcut

from app.domain.models import Task, TimeEntry
from app.infra.repository import TaskRepository, TimeEntryRepository, UserRepository
from app.ui.dialogs import ManualEntryDialog
from app.ui.accounting_dialogs import AccountingManagementDialog
from app.ui.task_dialogs import TaskManagementDialog
from app.ui.report_window import ReportWindow
from app.infra.config import get_settings
from app.services.calendar_service import CalendarService
from app.i18n import tr, on_language_changed


class StatusCalendarWidget(QCalendarWidget):
    """
    Custom calendar widget that visualizes day status (Work, Vacation, Sickness, Holiday)
    with color coding and supports right-click cycling through states.
    Official German holidays are automatically marked based on the configured state.
    """

    STATE_WORK = "work"
    STATE_VACATION = "vacation"
    STATE_SICKNESS = "sickness"
    STATE_HOLIDAY = "holiday"

    # Colors will be set dynamically based on theme
    # These are placeholder defaults, actual colors set in _update_theme_colors()
    COLORS = {
        STATE_WORK: QColor("transparent"),
        STATE_VACATION: QColor("#4CAF50"),     # Match Generate Report button
        STATE_SICKNESS: QColor("#c62828"),     # Dark red
        STATE_HOLIDAY: QColor("#1976d2")       # Match Add Manual Entry button
    }

    dateContextRequested = Signal(QDate)  # Right-click signal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_data: Dict[QDate, str] = {}
        self.holiday_names: Dict[QDate, str] = {}  # Store holiday names for tooltips
        self._formatted_dates = set()
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        # Style calendar cells: border highlight on hover/selection instead of background change
        self.setStyleSheet("""
            QCalendarWidget QAbstractItemView {
                selection-background-color: transparent;
                selection-color: palette(text);
            }
            QCalendarWidget QAbstractItemView::item:selected {
                background-color: transparent;
                border: 2px solid #1976d2;
                color: palette(text);
            }
            QCalendarWidget QAbstractItemView::item:hover {
                background-color: transparent;
                border: 2px solid #90caf9;
                color: palette(text);
            }
        """)

        # Initialize theme-aware colors
        self._update_theme_colors()

        # Install event filter on the internal table view to catch right-clicks
        # QCalendarWidget uses an internal QTableView to display the calendar
        view = self.findChild(QAbstractItemView)
        if view:
            view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events to catch right-clicks and tooltips on calendar cells"""
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                view = self.findChild(QAbstractItemView)
                if view and obj == view.viewport():
                    index = view.indexAt(event.position().toPoint())
                    if index.isValid():
                        date = self._get_date_from_index(index)
                        if date.isValid():
                            self.dateContextRequested.emit(date)
                        return True  # Event handled

        # Handle tooltip events for holidays
        if event.type() == QEvent.ToolTip:
            view = self.findChild(QAbstractItemView)
            if view and obj == view.viewport():
                index = view.indexAt(event.pos())
                if index.isValid():
                    date = self._get_date_from_index(index)
                    if date.isValid() and date in self.holiday_names:
                        holiday_name = self.holiday_names[date]
                        QToolTip.showText(event.globalPos(), holiday_name, view)
                        return True
                QToolTip.hideText()
                return True

        return super().eventFilter(obj, event)

    def _get_date_from_index(self, index):
        """Calculate QDate from grid index"""
        # Row 0 is the header (Day names), so ignore it
        if index.row() < 1:
            return QDate()

        year = self.yearShown()
        month = self.monthShown()

        first_day_of_month = QDate(year, month, 1)

        # Get first day of week setting
        first_day_setting = self.firstDayOfWeek()
        if first_day_setting == 0:
            first_day_setting = QLocale.system().firstDayOfWeek()

        # Calculate offset to the first cell (0,0)
        # diff is how many days FIRST DAY OF MONTH is ahead of FIRST COL
        # Ensure we treat first_day_setting as int (Qt.DayOfWeek enum)
        diff = first_day_of_month.dayOfWeek() - first_day_setting.value
        if diff < 0:
            diff += 7

        # Start date of the grid (cell 0,0)
        start_date = first_day_of_month.addDays(-diff)

        # Target date
        # The internal QTableView of QCalendarWidget has a header row at row 0 (Day names)
        # So the actual dates start at row 1. We must subtract 1 from the row index.
        days_add = (index.row() - 1) * 7 + index.column()
        return start_date.addDays(days_add)

    def set_status_data(self, data: Dict[QDate, str]):
        """Update the status data and refresh the calendar display"""
        # Clear previous formatting
        clear_format = QTextCharFormat()
        for qdate in self._formatted_dates:
            self.setDateTextFormat(qdate, clear_format)
        self._formatted_dates.clear()

        self.status_data = data
        # Apply formatting for vacation/sickness
        for qdate, state in self.status_data.items():
            if state == self.STATE_WORK:
                continue
            fmt = QTextCharFormat()
            fmt.setBackground(self.COLORS.get(state, self.COLORS[self.STATE_WORK]))
            self.setDateTextFormat(qdate, fmt)
            self._formatted_dates.add(qdate)
        self.updateCells()
        # Force immediate repaint of the whole window to ensure visual update
        if self.window():
            self.window().repaint()

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        """Override to paint cell backgrounds based on day status"""
        state = self.status_data.get(date, self.STATE_WORK)

        # Paint background color for vacation/sickness/holiday
        if state != self.STATE_WORK:
            painter.save()
            color = self.COLORS.get(state, self.COLORS[self.STATE_WORK])
            painter.fillRect(rect, color)
            painter.restore()

        # Call parent to draw the date number
        super().paintCell(painter, rect, date)

        # Draw holiday flag icon if it's a holiday
        if state == self.STATE_HOLIDAY:
            painter.save()
            painter.setPen(QColor("#1565c0"))
            # Draw flag emoji in top-left corner to indicate official holiday
            painter.drawText(rect.adjusted(2, 2, 0, 0), Qt.AlignTop | Qt.AlignLeft, "🏳")
            painter.restore()

        # Draw violation warning icon if exists
        if hasattr(self, '_violations') and date in self._violations:
            painter.save()
            painter.setPen(QColor("#d32f2f"))
            # Draw warning triangle in top-right corner
            painter.drawText(rect.adjusted(rect.width()-18, 2, 0, 0), Qt.AlignTop | Qt.AlignRight, "⚠")
            painter.restore()

    def set_holiday_names(self, holiday_names: Dict[QDate, str]):
        """Set holiday names for tooltip display"""
        self.holiday_names = holiday_names

    def set_violations(self, violations: Dict[QDate, List[str]]):
        """Set violations data for display"""
        self._violations = violations
        self.updateCells()

    def _update_theme_colors(self):
        """Update colors based on current theme (dark or light mode)"""
        # Detect if dark mode is active by checking palette
        palette = self.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        is_dark = bg_color.lightness() < 128

        if is_dark:
            # Dark mode colors - slightly muted versions of button colors
            self.COLORS = {
                self.STATE_WORK: QColor("transparent"),
                self.STATE_VACATION: QColor("#388E3C"),     # Darker green (based on #4CAF50)
                self.STATE_SICKNESS: QColor("#c62828"),     # Dark red
                self.STATE_HOLIDAY: QColor("#1565c0")       # Darker blue (based on #1976d2)
            }
        else:
            # Light mode colors - match button colors with transparency
            self.COLORS = {
                self.STATE_WORK: QColor("transparent"),
                self.STATE_VACATION: QColor("#81C784"),     # Light green (based on #4CAF50)
                self.STATE_SICKNESS: QColor("#ef9a9a"),     # Light red/pink
                self.STATE_HOLIDAY: QColor("#64B5F6")       # Light blue (based on #1976d2)
            }

    def changeEvent(self, event):
        """Handle theme changes"""
        if event.type() == QEvent.PaletteChange:
            self._update_theme_colors()
            self.updateCells()
        super().changeEvent(event)


class HistoryWindow(QWidget):
    """
    Window to view daily time entries and add manual entries.
    """

    def __init__(self, loop=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("history.title"))
        self.resize(1100, 850)

        # Note: Global theme is managed by qdarktheme via SystemTrayApp
        # Only add minimal custom styling for specific elements that need it

        self.loop = loop or asyncio.get_event_loop()
        self.entry_repo = TimeEntryRepository()
        self.task_repo = TaskRepository()
        self.settings = get_settings()
        self.undo_stack = []

        # Initialize CalendarService for German holiday detection
        german_state = getattr(self.settings, 'german_state', 'BY')
        self.calendar_service = CalendarService(german_state=german_state)

        self.tasks: List[Task] = []
        self.current_entries: List[TimeEntry] = []
        self.month_violations: Dict[QDate, List[str]] = {}

        self._setup_ui()
        self._load_tasks()
        self._load_regulations()

        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self._undo_last_change)

        # Register for language changes
        on_language_changed(self._on_language_change)

    def _on_language_change(self, lang):
        self.retranslate_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)

        # Left Panel: Calendar and Work Regulations with Splitter
        left_layout = QVBoxLayout()

        #Create splitter for calendar and work regulations
        left_splitter = QSplitter(Qt.Vertical)

        # Top widget: Calendar and Legend
        calendar_widget = QWidget()
        calendar_layout = QVBoxLayout(calendar_widget)
        calendar_layout.setContentsMargins(0, 0, 0, 0)

        self.calendar = StatusCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._on_date_selected)
        self.calendar.currentPageChanged.connect(self._on_month_changed)
        self.calendar.dateContextRequested.connect(self._cycle_day_status)

        calendar_layout.addWidget(self.calendar)

        # Legend for day types
        legend_layout = QHBoxLayout()
        self.legend_label = QLabel(tr("history.legend"))
        self.legend_label.setStyleSheet("font-weight: bold; margin-right: 10px;")
        legend_layout.addWidget(self.legend_label)

        # Store legend labels for dynamic theme updates
        self.vacation_legend = QLabel(f"  {tr('status.vacation')}  ")
        legend_layout.addWidget(self.vacation_legend)

        self.sickness_legend = QLabel(f"  {tr('status.sickness')}  ")
        legend_layout.addWidget(self.sickness_legend)

        self.holiday_legend = QLabel(f"  🏳 {tr('status.holiday')}  ")
        self.holiday_legend.setToolTip("Official German holidays")
        legend_layout.addWidget(self.holiday_legend)

        self.hint_label = QLabel(tr("history.legend_hint"))
        legend_layout.addWidget(self.hint_label)

        # Apply initial theme-aware colors
        self._update_legend_colors()

        legend_layout.addStretch()
        calendar_layout.addLayout(legend_layout)

        # Add spacing below the calendar section
        calendar_layout.addSpacing(15)

        left_splitter.addWidget(calendar_widget)

        # Work Regulations Panel
        self.regulations_group = QGroupBox(tr("regulations.title"))
        self.regulations_group.setCheckable(False)
        # Use minimal styling that works with both themes
        self.regulations_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid palette(mid);
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        regulations_layout = QVBoxLayout(self.regulations_group)
        regulations_layout.setSpacing(8)

        # Daily Target
        target_layout = QHBoxLayout()
        self.label_daily_target = QLabel(tr("regulations.daily_target"))
        target_layout.addWidget(self.label_daily_target)
        self.spin_work_hours = QDoubleSpinBox()
        self.spin_work_hours.setRange(1.0, 24.0)
        self.spin_work_hours.setSingleStep(0.5)
        self.spin_work_hours.setSuffix(f" {tr('time.hours_short')}")
        self.spin_work_hours.setMinimumWidth(80)
        self.spin_work_hours.setValue(8.0)  # Default
        self.spin_work_hours.valueChanged.connect(self._save_regulations)
        target_layout.addWidget(self.spin_work_hours)
        target_layout.addStretch()
        regulations_layout.addLayout(target_layout)

        # Compliance Checks
        checkbox_style = """
            QCheckBox {
                spacing: 8px;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #999;
                border-radius: 3px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #1976d2;
                border-color: #1976d2;
            }
        """

        self.check_enable_compliance = QCheckBox(tr("regulations.enable_compliance"))
        self.check_enable_compliance.setToolTip("Warns when daily hours exceed 10 hours")
        self.check_enable_compliance.setStyleSheet(checkbox_style)
        self.check_enable_compliance.stateChanged.connect(self._save_regulations)
        regulations_layout.addWidget(self.check_enable_compliance)

        self.check_breaks = QCheckBox(tr("regulations.check_breaks"))
        self.check_breaks.setToolTip("Warn if >6h without 30m break")
        self.check_breaks.setStyleSheet(checkbox_style)
        self.check_breaks.stateChanged.connect(self._save_regulations)
        regulations_layout.addWidget(self.check_breaks)

        self.check_rest = QCheckBox(tr("regulations.check_rest"))
        self.check_rest.setToolTip("Warn if <11h between work days")
        self.check_rest.setStyleSheet(checkbox_style)
        self.check_rest.stateChanged.connect(self._save_regulations)
        regulations_layout.addWidget(self.check_rest)

        # Violations display
        self.violations_label = QLabel()
        self.violations_label.setStyleSheet("color: #d32f2f; font-weight: bold; padding: 5px;")
        self.violations_label.setWordWrap(True)
        self.violations_label.hide()
        regulations_layout.addWidget(self.violations_label)
        regulations_layout.addStretch()  # Push content to top

        left_splitter.addWidget(self.regulations_group)

        # Set initial splitter sizes
        left_splitter.setSizes([400, 300])
        left_splitter.setStretchFactor(0, 2)
        left_splitter.setStretchFactor(1, 1)

        left_layout.addWidget(left_splitter)

        # User repo for saving
        self.user_repo = UserRepository()

        layout.addLayout(left_layout, stretch=1)

        # Right Panel: Entries Table and Daily Summary with Splitter
        right_layout = QVBoxLayout()

        # Title for the table
        self.date_label = QLabel(QDate.currentDate().toString("dddd, MMMM d, yyyy"))
        self.date_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        right_layout.addWidget(self.date_label)

        # Create splitter for task table and daily summary
        splitter = QSplitter(Qt.Vertical)

        # Top widget: Task entries table
        task_table_widget = QWidget()
        task_table_layout = QVBoxLayout(task_table_widget)
        task_table_layout.setContentsMargins(0, 0, 0, 0)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            tr("history.task"), tr("history.start"), tr("history.end"), 
            tr("history.duration"), tr("history.notes")
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Context Menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Configure header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch) # Task name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Start
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # End
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Duration
        header.setSectionResizeMode(4, QHeaderView.Stretch) # Notes

        task_table_layout.addWidget(self.table)

        # Add Manual Entry Button (below task table)
        self.add_btn = QPushButton(f"+ {tr('history.add_entry')}")
        self.add_btn.clicked.connect(self._open_manual_entry)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                border: none;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)
        task_table_layout.addWidget(self.add_btn)

        splitter.addWidget(task_table_widget)

        # Bottom widget: Daily Summary
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)

        # Daily Summary Section
        self.summary_header = QLabel(tr("history.daily_summary"))
        self.summary_header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        summary_layout.addWidget(self.summary_header)

        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels([tr("history.task"), tr("history.duration")])
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setSelectionMode(QTableWidget.NoSelection)
        self.summary_table.setFocusPolicy(Qt.NoFocus)

        # Header setup
        summary_header = self.summary_table.horizontalHeader()
        summary_header.setSectionResizeMode(0, QHeaderView.Stretch)
        summary_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        summary_layout.addWidget(self.summary_table)
        splitter.addWidget(summary_widget)

        # Set initial splitter sizes (60% task table, 40% summary)
        splitter.setSizes([600, 400])
        splitter.setStretchFactor(0, 3)  # Task table gets more stretch priority
        splitter.setStretchFactor(1, 2)  # Summary gets less

        right_layout.addWidget(splitter)

        # Buttons
        btn_layout = QHBoxLayout()

        self.accounting_btn = QPushButton(tr("history.manage_accounting"))
        self.accounting_btn.clicked.connect(self._open_accounting)
        self.accounting_btn.setStyleSheet("""
            QPushButton {
                 background-color: #f5f5f5;
                 color: #333;
                 border: 1px solid #ccc;
                 border-radius: 6px;
                 padding: 10px 20px;
                 font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)



        self.tasks_btn = QPushButton(tr("history.manage_tasks"))
        self.tasks_btn.clicked.connect(self._open_tasks)
        self.tasks_btn.setStyleSheet("""
            QPushButton {
                 background-color: #f5f5f5;
                 color: #333;
                 border: 1px solid #ccc;
                 border-radius: 6px;
                 padding: 10px 20px;
                 font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)

        btn_layout.addWidget(self.accounting_btn)
        btn_layout.addWidget(self.tasks_btn)

        self.report_btn = QPushButton(f"📊 {tr('history.generate_report')}")
        self.report_btn.clicked.connect(self._generate_report)
        self.report_btn.setStyleSheet("""
            QPushButton {
                 background-color: #4CAF50;
                 color: white;
                 font-weight: bold;
                 border: none;
                 border-radius: 6px;
                 padding: 10px 20px;
                 font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        btn_layout.addWidget(self.report_btn)

        btn_layout.addStretch()

        right_layout.addLayout(btn_layout)
        layout.addLayout(right_layout, stretch=3) # Make right side wider

    def retranslate_ui(self):
        """Update UI strings on language change"""
        self.setWindowTitle(tr("history.title"))
        
        # Legend
        self.legend_label.setText(tr("history.legend"))
        self.vacation_legend.setText(f"  {tr('status.vacation')}  ")
        self.sickness_legend.setText(f"  {tr('status.sickness')}  ")
        self.holiday_legend.setText(f"  🏳 {tr('status.holiday')}  ")
        self.hint_label.setText(tr("history.legend_hint"))

        # Regulations
        self.regulations_group.setTitle(tr("regulations.title"))
        self.label_daily_target.setText(tr("regulations.daily_target"))
        self.spin_work_hours.setSuffix(f" {tr('time.hours_short')}")
        self.check_enable_compliance.setText(tr("regulations.enable_compliance"))
        self.check_breaks.setText(tr("regulations.check_breaks"))
        self.check_rest.setText(tr("regulations.check_rest"))

        # Tables
        self.table.setHorizontalHeaderLabels([
            tr("history.task"), tr("history.start"), tr("history.end"), 
            tr("history.duration"), tr("history.notes")
        ])
        
        self.summary_header.setText(tr("history.daily_summary"))
        self.summary_table.setHorizontalHeaderLabels([tr("history.task"), tr("history.duration")])

        # Buttons
        self.add_btn.setText(f"+ {tr('history.add_entry')}")
        self.accounting_btn.setText(tr("history.manage_accounting"))
        self.tasks_btn.setText(tr("history.manage_tasks"))
        self.report_btn.setText(f"📊 {tr('history.generate_report')}")

        # Update date label format
        if hasattr(self, 'calendar'):
             self._on_date_selected()

    def _is_dark_mode(self) -> bool:
        """Detect if dark mode is active based on palette"""
        palette = self.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        return bg_color.lightness() < 128

    def _update_legend_colors(self):
        """Update legend colors based on current theme"""
        is_dark = self._is_dark_mode()

        if is_dark:
            # Dark mode - use muted colors with light text
            vacation_style = (
                "background-color: #1b5e20; color: white; "
                "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
            )
            sickness_style = (
                "background-color: #b71c1c; color: white; "
                "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
            )
            holiday_style = (
                "background-color: #1565c0; color: white; "
                "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
            )
            hint_style = "color: #999; font-style: italic; font-size: 11px;"
        else:
            # Light mode - match button colors
            vacation_style = (
                "background-color: #81C784; color: #1b5e20; "
                "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
            )
            sickness_style = (
                "background-color: #ef9a9a; color: #b71c1c; "
                "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
            )
            holiday_style = (
                "background-color: #64B5F6; color: #0d47a1; "
                "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
            )
            hint_style = "color: #666; font-style: italic; font-size: 11px;"

        self.vacation_legend.setStyleSheet(vacation_style)
        self.sickness_legend.setStyleSheet(sickness_style)
        self.holiday_legend.setStyleSheet(holiday_style)
        self.hint_label.setStyleSheet(hint_style)

    def changeEvent(self, event):
        """Handle theme changes"""
        if event.type() == QEvent.PaletteChange:
            self.update_theme()
        super().changeEvent(event)

    def update_theme(self):
        """Update theme for all components when theme changes"""
        self._update_legend_colors()
        # Update calendar colors
        if hasattr(self, 'calendar'):
            self.calendar._update_theme_colors()
            self.calendar.updateCells()

    def _open_accounting(self):
        """Open accounting management dialog"""
        dialog = AccountingManagementDialog(self)
        dialog.exec()

    def _open_tasks(self):
        """Open task management dialog"""
        dialog = TaskManagementDialog(self)
        if dialog.exec():
            # Refresh tasks if needed (e.g. if names changed)
            self._load_tasks()

    def _generate_report(self):
        """Open the report generation wizard"""
        try:
            # Get current month/year from calendar
            current_date = self.calendar.selectedDate()

            # Create report window and set it to the current month
            self.report_window = ReportWindow()
            self.report_window._set_period(current_date.year(), current_date.month())
            self.report_window.show()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open report wizard:\n{e}")

    def _load_regulations(self):
        """Load work regulations from preferences"""
        try:
            prefs = self.loop.run_until_complete(self.user_repo.get_preferences())
            self.spin_work_hours.setValue(prefs.work_hours_per_day)
            self.check_enable_compliance.setChecked(prefs.enable_german_compliance)
            self.check_breaks.setChecked(prefs.check_breaks)
            self.check_rest.setChecked(prefs.check_rest_periods)
        except Exception as e:
            print(f"Failed to load regulations: {e}")

    def _save_regulations(self):
        """Save work regulations to preferences"""
        try:
            prefs = self.loop.run_until_complete(self.user_repo.get_preferences())
            prefs.work_hours_per_day = self.spin_work_hours.value()
            prefs.enable_german_compliance = self.check_enable_compliance.isChecked()
            prefs.check_breaks = self.check_breaks.isChecked()
            prefs.check_rest_periods = self.check_rest.isChecked()
            self.loop.run_until_complete(self.user_repo.update_preferences(prefs))
            self._check_violations()
        except Exception as e:
            print(f"Failed to save regulations: {e}")

    def _check_violations(self):
        """Check for work regulation violations on current date"""
        # Calculate total hours including active entries (same logic as _populate_tables)
        total_seconds = 0
        for entry in self.current_entries:
            if entry.end_time is None:
                # Active entry - calculate duration up to now
                duration = int((datetime.now() - entry.start_time).total_seconds())
            else:
                duration = entry.duration_seconds
            total_seconds += duration

        total_hours = total_seconds / 3600.0
        violations = []

        # Check 10h limit - will color Total row RED if exceeded
        limit_exceeded = False
        if self.check_enable_compliance.isChecked():
            if total_hours > 10.0:
                violations.append(f"⚠️ Exceeded 10h limit: {total_hours:.1f}h worked")
                limit_exceeded = True

        # Check daily target - will add Overtime row if exceeded
        target = self.spin_work_hours.value()
        overtime_seconds = 0
        if total_hours > target:
            over_hours = total_hours - target
            overtime_seconds = int((total_hours - target) * 3600)
            if over_hours > 2.0:  # Only warn if significantly over
                violations.append(f"📊 {over_hours:.1f}h over daily target ({target:.1f}h)")

        # Remove existing Overtime row FIRST (to prevent duplication)
        row_count = self.summary_table.rowCount()
        if row_count > 1:
            last_row_item = self.summary_table.item(row_count - 1, 0)
            if last_row_item and last_row_item.text() == "Overtime":
                self.summary_table.removeRow(row_count - 1)
                row_count -= 1  # Update count after removal

        # Color the Total row RED if 10h limit exceeded
        # Now row_count-1 is guaranteed to be Total row
        if row_count > 0:
            total_row = row_count - 1

            total_name_item = self.summary_table.item(total_row, 0)
            total_dur_item = self.summary_table.item(total_row, 1)

            if total_name_item and total_dur_item:
                if limit_exceeded:
                    # Mark Total RED for 10h limit violation
                    total_name_item.setForeground(QColor("#d32f2f"))
                    total_dur_item.setForeground(QColor("#d32f2f"))
                else:
                    # Normal blue color
                    total_name_item.setForeground(QColor("#1976d2"))
                    total_dur_item.setForeground(QColor("#1976d2"))

        # Add Overtime row if target exceeded (only info, not a violation warning)
        if overtime_seconds > 0:
            # Add an extra row for overtime
            current_rows = self.summary_table.rowCount()
            self.summary_table.setRowCount(current_rows + 1)

            overtime_row = current_rows
            overtime_name_item = QTableWidgetItem("Overtime")
            overtime_name_item.setForeground(QColor("#f57c00"))  # Orange color for info
            font = overtime_name_item.font()
            font.setItalic(True)
            overtime_name_item.setFont(font)
            self.summary_table.setItem(overtime_row, 0, overtime_name_item)

            hours, remainder = divmod(overtime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            overtime_dur_str = f"+{hours:02d}:{minutes:02d}"

            overtime_dur_item = QTableWidgetItem(overtime_dur_str)
            overtime_dur_item.setForeground(QColor("#f57c00"))
            overtime_dur_item.setFont(font)
            self.summary_table.setItem(overtime_row, 1, overtime_dur_item)

        # Update violations label
        if violations:
            self.violations_label.setText("\n".join(violations))
            self.violations_label.show()
        else:
            self.violations_label.hide()

        # Store violation for this date for calendar display
        selected_date = self.calendar.selectedDate()
        if not hasattr(self, 'month_violations'):
            self.month_violations = {}

        if violations:
            self.month_violations[selected_date] = violations
        elif selected_date in self.month_violations:
            del self.month_violations[selected_date]

        # Pass violations data to calendar
        self.calendar.set_violations(self.month_violations)


    def _show_context_menu(self, pos):
        """Show context menu for table"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        edit_action = QAction(tr("action.edit"), self)
        delete_action = QAction(tr("action.delete"), self)

        edit_action.triggered.connect(self._edit_current_entry)
        delete_action.triggered.connect(self._delete_current_entry)

        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(self.table.mapToGlobal(pos))

    def _edit_current_entry(self):
        """Edit the currently selected entry"""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_entries):
            return

        entry = self.current_entries[row]

        dialog = ManualEntryDialog(self.tasks, self)
        dialog.set_data(entry)

        if dialog.exec():
            data = dialog.get_data()
            try:
                self.loop.run_until_complete(self._update_entry(entry, data))
                self._on_date_selected() # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update entry: {e}")

    def _delete_current_entry(self):
        """Delete the currently selected entry"""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_entries):
            return

        reply = QMessageBox.question(
            self, tr("action.delete"),
            tr("history.delete_confirm"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        entry = self.current_entries[row]
        try:
            self.loop.run_until_complete(self.entry_repo.delete(entry.id))
            self._save_state_for_undo()
            self._on_date_selected()  # Refresh
        except Exception as e:
            QMessageBox.critical(self, tr("error"), f"{tr('history.delete_failed')}: {e}")

    def retranslate_ui(self):
        """Update strings when language changes"""
        self.setWindowTitle(tr("history.title"))
        self.legend_label.setText(tr("history.legend"))
        self.vacation_legend.setText(f"  {tr('status.vacation')}  ")
        self.sickness_legend.setText(f"  {tr('status.sickness')}  ")
        self.holiday_legend.setText(f"  🏳 {tr('status.holiday')}  ")
        self.hint_label.setText(tr("history.legend_hint"))

        self.regulations_group.setTitle(tr("regulations.title"))
        self.label_daily_target.setText(tr("regulations.daily_target"))
        self.check_enable_compliance.setText(tr("regulations.enable_compliance"))
        self.check_breaks.setText(tr("regulations.check_breaks"))
        self.check_rest.setText(tr("regulations.check_rest"))

        self.table.setHorizontalHeaderLabels([
            tr("history.task"), tr("history.start"), tr("history.end"),
            tr("history.duration"), tr("history.notes")
        ])
        self.add_btn.setText(f"+ {tr('history.add_entry')}")
        
        self.summary_header.setText(tr("history.daily_summary"))
        self.summary_table.setHorizontalHeaderLabels([tr("history.task"), tr("history.duration")])
        
        self.accounting_btn.setText(tr("history.manage_accounting"))
        self.tasks_btn.setText(tr("history.manage_tasks"))
        self.report_btn.setText(f"📊 {tr('history.generate_report')}")
        
        # Refresh current view to update date label and violations text if needed
        self._on_date_selected()



    def refresh_data(self):
        """Public method to refresh all data (called after backup restore)"""
        self._load_tasks()

    def _load_tasks(self):
        """Load tasks for sorting/displaying and for the manual entry dialog"""
        try:
            self.loop.run_until_complete(self._fetch_tasks())
            # After tasks are loaded, load entries for today
            self._on_date_selected()
            # Load month status for calendar coloring
            today = QDate.currentDate()
            self.loop.run_until_complete(self._refresh_month_status(today.year(), today.month()))
        except Exception as e:
            print(f"Error loading tasks: {e}")

    async def _fetch_tasks(self):
        self.tasks = await self.task_repo.get_all_active()

    def _on_month_changed(self, year, month):
        """Fetch status data when calendar page changes"""
        self.loop.run_until_complete(self._refresh_month_status(year, month))

    async def _refresh_month_status(self, year, month):
        """Load status (Work/Vacation/Sickness/Holiday) for the whole month"""
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)

        status_data = {}
        holiday_names = {}

        # First, mark all official German holidays for the month
        current_date = start_date.date()
        while current_date <= end_date.date():
            if self.calendar_service.is_holiday(current_date):
                qdate = QDate(current_date.year, current_date.month, current_date.day)
                status_data[qdate] = StatusCalendarWidget.STATE_HOLIDAY
                holiday_name = self.calendar_service.get_holiday_name(current_date)
                if holiday_name:
                    holiday_names[qdate] = holiday_name
            current_date += timedelta(days=1)

        # Fetch all entries for the month
        all_entries = []
        for task in self.tasks:
            entries = await self.entry_repo.get_overlapping(task.id, start_date, end_date)
            all_entries.extend(entries)

        # Process entries and determine day status
        # Priority: Sickness > Vacation > Holiday > Work
        for entry in all_entries:
            qdate = QDate(entry.start_time.year, entry.start_time.month, entry.start_time.day)

            # Get task name
            task_name = next((t.name for t in self.tasks if t.id == entry.task_id), "").lower()

            # Determine state based on task name
            new_state = StatusCalendarWidget.STATE_WORK
            if task_name == "vacation":
                new_state = StatusCalendarWidget.STATE_VACATION
            elif task_name == "sickness":
                new_state = StatusCalendarWidget.STATE_SICKNESS

            # Priority: Sickness > Vacation > Holiday > Work
            current = status_data.get(qdate, StatusCalendarWidget.STATE_WORK)
            if current == StatusCalendarWidget.STATE_SICKNESS:
                continue  # Keep Sickness (highest priority)
            if current == StatusCalendarWidget.STATE_VACATION and new_state != StatusCalendarWidget.STATE_SICKNESS:
                continue  # Keep Vacation unless new is Sickness
            if current == StatusCalendarWidget.STATE_HOLIDAY and new_state == StatusCalendarWidget.STATE_WORK:
                continue  # Keep Holiday unless user entry overrides

            status_data[qdate] = new_state

        self.calendar.set_holiday_names(holiday_names)
        self.calendar.set_status_data(status_data)

    def _cycle_day_status(self, qdate: QDate):
        """Cycle status: Work -> Vacation -> Sickness -> Work

        Note: Holidays and weekends cannot be cycled to vacation/sickness,
        but users can still manually add work entries for occasional weekend work.
        """
        # Convert QDate to Python date for checking
        py_date = qdate.toPython()

        # Check if this is a holiday or weekend - don't allow cycling
        is_holiday = self.calendar_service.is_holiday(py_date)
        is_weekend = self.calendar_service.is_weekend(py_date)

        if is_holiday or is_weekend:
            day_type = "a holiday" if is_holiday else "a weekend"
            holiday_name = self.calendar_service.get_holiday_name(py_date) if is_holiday else ""
            msg = f"This date is {day_type}"
            if holiday_name:
                msg += f" ({holiday_name})"
            msg += ".\n\nVacation/Sickness status cannot be set for holidays or weekends.\n"
            msg += "You can still add manual work entries if needed."
            QMessageBox.information(self, "Cannot Change Status", msg)
            return

        # Get current status
        current_status = self.calendar.status_data.get(qdate, StatusCalendarWidget.STATE_WORK)

        # Determine next state
        if current_status == StatusCalendarWidget.STATE_WORK:
            next_status = StatusCalendarWidget.STATE_VACATION
        elif current_status == StatusCalendarWidget.STATE_VACATION:
            next_status = StatusCalendarWidget.STATE_SICKNESS
        else:  # SICKNESS
            next_status = StatusCalendarWidget.STATE_WORK

        # Convert QDate to Python datetime
        date_start = datetime(qdate.year(), qdate.month(), qdate.day())
        date_end = datetime(qdate.year(), qdate.month(), qdate.day(), 23, 59, 59)

        # Apply the status cycle
        self.loop.run_until_complete(
            self._apply_status_cycle(date_start, date_end, current_status, next_status)
        )

    def _undo_last_change(self):
        """Undo last day status change (Ctrl+Z)."""
        if not self.undo_stack:
            return

        snapshot = self.undo_stack.pop()
        self.loop.run_until_complete(self._restore_entries(snapshot))

    async def _restore_entries(self, snapshot):
        """Restore entries from snapshot."""
        start = snapshot["start"]
        end = snapshot["end"]
        entries = snapshot["entries"]

        try:
            existing = []
            if hasattr(self.entry_repo, "get_all_in_range"):
                existing = await self.entry_repo.get_all_in_range(start, end)
            else:
                for task in self.tasks:
                    existing.extend(await self.entry_repo.get_overlapping(task.id, start, end))
            for entry in existing:
                await self.entry_repo.delete(entry.id)

            for entry in entries:
                new_entry = TimeEntry(
                    task_id=entry.task_id,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    duration_seconds=entry.duration_seconds,
                    notes=entry.notes
                )
                await self.entry_repo.create(new_entry)

            await self._refresh_month_status(start.year, start.month)
            await self._refresh_current_date_entries()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to undo change: {e}")

    async def _apply_status_cycle(self, start, end, current_status, next_status):
        """Apply the day status cycle with safety checks"""
        # Check existing entries for this day
        all_entries = []
        for task in self.tasks:
            entries = await self.entry_repo.get_overlapping(task.id, start, end)
            all_entries.extend(entries)

        has_entries = len(all_entries) > 0

        # Check if there are work entries (not vacation/sickness)
        has_work_entries = any(
            next((t.name for t in self.tasks if t.id == e.task_id), "").lower()
            not in ["vacation", "sickness"]
            for e in all_entries
        )

        # Safety confirmation dialogs
        if next_status == StatusCalendarWidget.STATE_VACATION:
            if has_work_entries:
                reply = QMessageBox.question(
                    self, "Confirm Overwrite",
                    f"Existing work entries found on {start.strftime('%Y-%m-%d')}. "
                    f"Replace with Vacation?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
        elif next_status == StatusCalendarWidget.STATE_WORK:
            # Clearing vacation/sickness
            if has_entries:
                reply = QMessageBox.question(
                    self, "Confirm Clear",
                    f"Clear {current_status.title()} status on {start.strftime('%Y-%m-%d')}?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        try:
            self.undo_stack.append({
                "start": start,
                "end": end,
                "entries": list(all_entries)
            })

            # Delete all existing entries for this day
            for entry in all_entries:
                await self.entry_repo.delete(entry.id)

            # Create new entry for Vacation or Sickness
            if next_status in [StatusCalendarWidget.STATE_VACATION, StatusCalendarWidget.STATE_SICKNESS]:
                task_name = "Vacation" if next_status == StatusCalendarWidget.STATE_VACATION else "Sickness"

                # Find or create the task
                task = next((t for t in self.tasks if t.name.lower() == task_name.lower()), None)
                if not task:
                    task = await self.task_repo.create(Task(name=task_name))
                    self.tasks.append(task)

                # Get default work hours from settings
                work_hours = self.settings.preferences.work_hours_per_day
                duration = int(work_hours * 3600)  # Convert to seconds

                # Create entry starting at 9:00 AM
                start_time = start.replace(hour=9, minute=0, second=0)
                end_time = start_time + timedelta(seconds=duration)

                new_entry = TimeEntry(
                    task_id=task.id,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    notes=f"Auto-generated {task_name}"
                )
                await self.entry_repo.create(new_entry)

            # Refresh calendar and current view
            await self._refresh_month_status(start.year, start.month)
            await self._refresh_current_date_entries()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update day status: {e}")

    def _on_date_selected(self):
        """Handle date selection from calendar"""
        qdate = self.calendar.selectedDate()
        self.date_label.setText(QLocale().toString(qdate, QLocale.LongFormat))

        # Fetch entries asynchronously
        self.loop.run_until_complete(self._refresh_current_date_entries())

    async def _refresh_current_date_entries(self):
        """Async method to refresh entries for the currently selected date"""
        qdate = self.calendar.selectedDate()

        # Convert QDate to Python date
        py_date = qdate.toPython()
        start_of_day = datetime.combine(py_date, datetime.min.time())
        end_of_day = datetime.combine(py_date, datetime.max.time())

        # Fetch entries
        try:
            entries = await self._fetch_entries(start_of_day, end_of_day)
            self.current_entries = entries
            self._populate_tables(entries)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load entries: {e}")

    async def _fetch_entries(self, start, end):
        all_entries = []
        for task in self.tasks:
            entries = await self.entry_repo.get_overlapping(task.id, start, end)
            all_entries.extend(entries)

        # Sort by start time
        all_entries.sort(key=lambda x: x.start_time)
        return all_entries

    def _populate_tables(self, entries: List[TimeEntry]):
        # 1. Populate Detailed Table
        self.table.setRowCount(len(entries))
        day_total_seconds = 0
        task_totals = {}

        for row, entry in enumerate(entries):
            # Task Name
            task_name = next((t.name for t in self.tasks if t.id == entry.task_id), "Unknown")
            self.table.setItem(row, 0, QTableWidgetItem(task_name))

            # Start
            self.table.setItem(row, 1, QTableWidgetItem(entry.start_time.strftime("%H:%M")))

            # End
            end_str = entry.end_time.strftime("%H:%M") if entry.end_time else "Active"
            self.table.setItem(row, 2, QTableWidgetItem(end_str))

            # Duration
            # If active, duration might be dynamic, but here we show whatever is in DB or calculated up to now
            # For active tasks, duration in DB might be 0 until stopped.
            # Ideally we should calculate it live or show "Running"
            if entry.end_time is None:
                # Calculate duration up to now
                duration = int((datetime.now() - entry.start_time).total_seconds())
            else:
                duration = entry.duration_seconds

            day_total_seconds += duration

            # Accumulate for summary
            task_totals[task_name] = task_totals.get(task_name, 0) + duration

            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            dur_str = f"{hours:02d}:{minutes:02d}"
            self.table.setItem(row, 3, QTableWidgetItem(dur_str))

            # Notes
            self.table.setItem(row, 4, QTableWidgetItem(entry.notes or ""))

        # 2. Populate Summary Table
        sorted_totals = sorted(task_totals.items(), key=lambda x: x[1], reverse=True)
        self.summary_table.setRowCount(len(sorted_totals))

        for row, (name, duration) in enumerate(sorted_totals):
            self.summary_table.setItem(row, 0, QTableWidgetItem(name))

            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            dur_str = f"{hours:02d}:{minutes:02d}"

            self.summary_table.setItem(row, 1, QTableWidgetItem(dur_str))

        # 3. Add Total as last row in summary table
        self.summary_table.setRowCount(len(sorted_totals) + 1)  # +1 for total row

        total_row = len(sorted_totals)
        total_name_item = QTableWidgetItem("Total")
        total_name_item.setForeground(QColor("#1976d2"))
        font = total_name_item.font()
        font.setBold(True)
        total_name_item.setFont(font)
        self.summary_table.setItem(total_row, 0, total_name_item)

        hours, remainder = divmod(day_total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        total_dur_str = f"{hours:02d}:{minutes:02d}"

        total_dur_item = QTableWidgetItem(total_dur_str)
        total_dur_item.setForeground(QColor("#1976d2"))
        total_dur_item.setFont(font)
        self.summary_table.setItem(total_row, 1, total_dur_item)

        self._check_violations()

    def _open_manual_entry(self):
        """Open the dialog to add a manual entry

        Note: Work entries are not allowed on holidays and Sundays.
        Saturday work is permitted for occasional overtime.
        """
        # Check if selected date is a holiday or Sunday
        selected_qdate = self.calendar.selectedDate()
        py_date = selected_qdate.toPython()

        is_holiday = self.calendar_service.is_holiday(py_date)
        is_sunday = py_date.weekday() == 6  # Sunday = 6

        if is_holiday or is_sunday:
            day_type = "a holiday" if is_holiday else "Sunday"
            holiday_name = self.calendar_service.get_holiday_name(py_date) if is_holiday else ""
            msg = f"This date is {day_type}"
            if holiday_name:
                msg += f" ({holiday_name})"
            msg += ".\n\nWork entries are not allowed on holidays and Sundays."
            QMessageBox.warning(self, "Cannot Add Entry", msg)
            return

        dialog = ManualEntryDialog(self.tasks, self)

        # Set date to currently selected date
        dialog.date_edit.setDate(self.calendar.selectedDate())

        if dialog.exec():
            data = dialog.get_data()
            try:
                self.loop.run_until_complete(self._create_manual_entry(data))
                self._on_date_selected() # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save entry: {e}")

    async def _create_manual_entry(self, data):
        task_id = data['task_id']

        # Validate date - no work on holidays or Sundays
        start = data['start_time']
        entry_date = start.date()
        is_holiday = self.calendar_service.is_holiday(entry_date)
        is_sunday = entry_date.weekday() == 6

        if is_holiday or is_sunday:
            day_type = "a holiday" if is_holiday else "Sunday"
            raise ValueError(f"Work entries are not allowed on {day_type}.")

        # If new task name (task_id is None), create task first
        if task_id is None:
            # Check if it actually exists by name to avoid duplicates
            existing = next((t for t in self.tasks if t.name.lower() == data['task_name'].lower()), None)
            if existing:
                task_id = existing.id
            else:
                new_task = Task(name=data['task_name'])
                created_task = await self.task_repo.create(new_task)
                self.tasks.append(created_task)
                task_id = created_task.id

        # Calculate duration
        start = data['start_time']
        end = data['end_time']

        # Check Overlap
        if await self.entry_repo.has_overlap(start, end):
            raise ValueError("Time entry overlaps with an existing entry.")

        duration = int((end - start).total_seconds())

        if duration < 0:
            duration = 0

        entry = TimeEntry(
            task_id=task_id,
            start_time=start,
            end_time=end,
            duration_seconds=duration,
            notes=data['notes']
        )

        await self.entry_repo.create(entry)

    async def _update_entry(self, entry: TimeEntry, data: dict):
        """Update existing entry with new data"""
        # Validate date - no work on holidays or Sundays
        start = data['start_time']
        entry_date = start.date()
        is_holiday = self.calendar_service.is_holiday(entry_date)
        is_sunday = entry_date.weekday() == 6

        if is_holiday or is_sunday:
            day_type = "a holiday" if is_holiday else "Sunday"
            raise ValueError(f"Work entries are not allowed on {day_type}.")

        task_id = data['task_id']

        # Handle new task creation if needed
        if task_id is None:
             existing = next((t for t in self.tasks if t.name.lower() == data['task_name'].lower()), None)
             if existing:
                 task_id = existing.id
             else:
                 new_task = Task(name=data['task_name'])
                 created_task = await self.task_repo.create(new_task)
                 self.tasks.append(created_task)
                 task_id = created_task.id

        start = data['start_time']
        end = data['end_time']

        # Check Overlap (Ignore current entry ID)
        if await self.entry_repo.has_overlap(start, end, ignore_id=entry.id):
            raise ValueError("Time entry overlaps with an existing entry.")

        duration = int((end - start).total_seconds())
        if duration < 0:
            duration = 0

        # Update fields
        entry.task_id = task_id
        entry.start_time = start
        entry.end_time = end
        entry.duration_seconds = duration
        entry.notes = data['notes']

        await self.entry_repo.update(entry)

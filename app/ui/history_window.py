import asyncio
import calendar
from datetime import datetime, timedelta
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QHeaderView, QMessageBox, QMenu,
    QAbstractItemView, QGroupBox, QCheckBox, QDoubleSpinBox, QSplitter
)
from PySide6.QtCore import Qt, QDate, Signal, QRect, QEvent
from PySide6.QtGui import QColor, QPalette, QAction, QPainter, QTextCharFormat, QKeySequence, QShortcut

from app.domain.models import Task, TimeEntry
from app.infra.repository import TaskRepository, TimeEntryRepository, UserRepository
from app.ui.dialogs import ManualEntryDialog
from app.ui.accounting_dialogs import AccountingManagementDialog
from app.ui.task_dialogs import TaskManagementDialog
from app.ui.report_window import ReportWindow
from app.infra.config import get_settings


class StatusCalendarWidget(QCalendarWidget):
    """
    Custom calendar widget that visualizes day status (Work, Vacation, Sickness)
    with color coding and supports right-click cycling through states.
    """

    STATE_WORK = "work"
    STATE_VACATION = "vacation"
    STATE_SICKNESS = "sickness"

    COLORS = {
        STATE_WORK: QColor("#ffffff"),         # White/Default
        STATE_VACATION: QColor("#90EE90"),     # Light Green
        STATE_SICKNESS: QColor("#FFB6C1")      # Light Pink
    }

    dateContextRequested = Signal(QDate)  # Right-click signal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_data: Dict[QDate, str] = {}
        self._formatted_dates = set()
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        # Install event filter on the internal table view to catch right-clicks
        # QCalendarWidget uses an internal QTableView to display the calendar
        view = self.findChild(QAbstractItemView)
        if view:
            view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events to catch right-clicks on calendar cells"""
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                # Get the date at the click position
                # First, let the calendar handle the click to select the date
                view = self.findChild(QAbstractItemView)
                if view and obj == view.viewport():
                    # Map the click position to find which date was clicked
                    # We'll use a simpler approach: just use the currently selected date
                    # But first, simulate a left click to select the date under cursor
                    from PySide6.QtGui import QMouseEvent
                    from PySide6.QtCore import QPoint

                    # Create a left-click event at the same position to select the date
                    left_click = QMouseEvent(
                        QEvent.MouseButtonPress,
                        event.position(),
                        Qt.LeftButton,
                        Qt.LeftButton,
                        Qt.NoModifier
                    )
                    # Send to the view to update selection
                    view.viewport().event(left_click)

                    # Small delay to let selection update, then emit signal
                    # Actually, emit immediately with selected date
                    target_date = self.selectedDate()
                    if target_date and target_date.isValid():
                        self.dateContextRequested.emit(target_date)
                    return True  # Event handled

        return super().eventFilter(obj, event)

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

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        """Override to paint cell backgrounds based on day status"""
        state = self.status_data.get(date, self.STATE_WORK)

        # Paint background color for vacation/sickness
        if state != self.STATE_WORK:
            painter.save()
            color = self.COLORS.get(state, self.COLORS[self.STATE_WORK])
            painter.fillRect(rect, color)
            painter.restore()

        # Call parent to draw the date number
        super().paintCell(painter, rect, date)
        
        # Draw violation warning icon if exists
        if hasattr(self, '_violations') and date in self._violations:
            painter.save()
            painter.setPen(QColor("#d32f2f"))
            # Draw warning triangle in top-right corner
            painter.drawText(rect.adjusted(rect.width()-18, 2, 0, 0), Qt.AlignTop | Qt.AlignRight, "⚠")
            painter.restore()

    def set_violations(self, violations: Dict[QDate, List[str]]):
        """Set violations data for display"""
        self._violations = violations
        self.updateCells()


class HistoryWindow(QWidget):
    """
    Window to view daily time entries and add manual entries.
    """

    def __init__(self, loop=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Monthly Overview")
        self.resize(1100, 850)

        # Apply Main Window-like styling (Light, Modern)
        self.setStyleSheet("""
            /* Global Reset for this Window */
            QWidget {
                background-color: #ffffff;
                color: #2c3e50;
            }

            /* Group Boxes */
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 24px;
                padding-top: 10px;
                font-weight: bold;
                color: #333;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                background-color: #ffffff;
            }

            /* Inputs & Combos */
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px;
                min-width: 80px;
                color: #333;
                background-color: #fff;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #fff;
                color: #333;
                selection-background-color: #e0e0e0;
                selection-color: #000;
            }

            /* Scroll Areas */
            QScrollArea, QScrollArea > QWidget > QWidget {
                background-color: #ffffff;
                border: none;
            }

            /* Labels */
            QLabel {
                color: #2c3e50;
                background-color: transparent;
            }

            /* Table */
            QTableWidget {
                background-color: #ffffff;
                color: #333;
                gridline-color: #e0e0e0;
                border: 1px solid #e0e0e0;
                selection-background-color: #e3f2fd;
                selection-color: #000;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333;
                padding: 5px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
            }
            QTableCornerButton::section {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
            }

            /* Calendar */
            QCalendarWidget QWidget {
                alternate-background-color: #f9f9f9;
            }
            QCalendarWidget QToolButton {
                color: #333;
                icon-size: 20px;
                background-color: transparent;
            }
            QCalendarWidget QMenu {
                background-color: #fff;
                color: #333;
            }
            QCalendarWidget QSpinBox {
                color: #333;
                background-color: #fff;
                selection-background-color: #1976d2;
                selection-color: #fff;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #333;
                background-color: #fff;
                selection-background-color: #ff9800; /* Vibrant Orange for Pop */
                selection-color: #fff;
                outline: 0;
            }
            QCalendarWidget QAbstractItemView::item:selected {
                background-color: #ff9800;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #f57c00;
            }
            QCalendarWidget QAbstractItemView::item:hover {
                background-color: #e0e0e0;
                color: #000;
            }
        """)

        # Force Light Palette
        light_palette = QPalette()
        light_palette.setColor(QPalette.Window, QColor(255, 255, 255))
        light_palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        light_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Text, QColor(0, 0, 0))
        light_palette.setColor(QPalette.Button, QColor(245, 245, 245))
        light_palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        light_palette.setColor(QPalette.Highlight, QColor(25, 118, 210))
        light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(light_palette)

        self.loop = loop or asyncio.get_event_loop()
        self.entry_repo = TimeEntryRepository()
        self.task_repo = TaskRepository()
        self.settings = get_settings()
        self.undo_stack = []

        self.tasks: List[Task] = []
        self.current_entries: List[TimeEntry] = []
        self.month_violations: Dict[QDate, List[str]] = {}

        self._setup_ui()
        self._load_tasks()
        self._load_regulations()

        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self._undo_last_change)

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
        legend_label = QLabel("Legend:")
        legend_label.setStyleSheet("font-weight: bold; margin-right: 10px;")
        legend_layout.addWidget(legend_label)

        vacation_legend = QLabel("  Vacation  ")
        vacation_legend.setStyleSheet(
            "background-color: #90EE90; border: 1px solid #ccc; "
            "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
        )
        legend_layout.addWidget(vacation_legend)

        sickness_legend = QLabel("  Sickness  ")
        sickness_legend.setStyleSheet(
            "background-color: #FFB6C1; border: 1px solid #ccc; "
            "padding: 4px 8px; border-radius: 4px; margin-right: 5px;"
        )
        legend_layout.addWidget(sickness_legend)

        hint_label = QLabel("(Right-click date to cycle)")
        hint_label.setStyleSheet("color: #777; font-style: italic; font-size: 11px;")
        legend_layout.addWidget(hint_label)

        legend_layout.addStretch()
        calendar_layout.addLayout(legend_layout)
        
        left_splitter.addWidget(calendar_widget)

        # Work Regulations Panel
        regulations_group = QGroupBox("Work Regulations")
        regulations_group.setCheckable(False)
        regulations_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ccc;
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
        regulations_layout = QVBoxLayout(regulations_group)
        regulations_layout.setSpacing(8)

        # Daily Target
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Daily Target:"))
        self.spin_work_hours = QDoubleSpinBox()
        self.spin_work_hours.setRange(1.0, 24.0) 
        self.spin_work_hours.setSingleStep(0.5)
        self.spin_work_hours.setSuffix(" h")
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
        
        self.check_enable_compliance = QCheckBox("Enable German Compliance (10h limit)")
        self.check_enable_compliance.setToolTip("Warns when daily hours exceed 10 hours")
        self.check_enable_compliance.setStyleSheet(checkbox_style)
        self.check_enable_compliance.stateChanged.connect(self._save_regulations)
        regulations_layout.addWidget(self.check_enable_compliance)

        self.check_breaks = QCheckBox("Check Mandatory Breaks")  
        self.check_breaks.setToolTip("Warn if >6h without 30m break")
        self.check_breaks.setStyleSheet(checkbox_style)
        self.check_breaks.stateChanged.connect(self._save_regulations)
        regulations_layout.addWidget(self.check_breaks)

        self.check_rest = QCheckBox("Check Rest Periods (11h)")
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

        left_splitter.addWidget(regulations_group)
        
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
        self.table.setHorizontalHeaderLabels(["Task", "Start", "End", "Duration", "Notes"])
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
        self.add_btn = QPushButton("+ Add Manual Entry")
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
        self.summary_header = QLabel("Daily Summary")
        self.summary_header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        summary_layout.addWidget(self.summary_header)

        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Task", "Duration"])
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

        self.accounting_btn = QPushButton("Manage Accounting")
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



        self.tasks_btn = QPushButton("Manage Tasks")
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
        
        self.report_btn = QPushButton("📊 Generate Report")
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
        edit_action = QAction("Edit", self)
        delete_action = QAction("Delete", self)

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

        entry = self.current_entries[row]

        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this entry?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.loop.run_until_complete(self.entry_repo.delete(entry.id))
                self._on_date_selected() # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete entry: {e}")

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
        """Load status (Work/Vacation/Sickness) for the whole month"""
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)

        status_data = {}

        # Fetch all entries for the month
        all_entries = []
        for task in self.tasks:
            entries = await self.entry_repo.get_overlapping(task.id, start_date, end_date)
            all_entries.extend(entries)

        # Process entries and determine day status
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

            # Priority: Sickness > Vacation > Work
            current = status_data.get(qdate, StatusCalendarWidget.STATE_WORK)
            if current == StatusCalendarWidget.STATE_SICKNESS:
                continue  # Keep Sickness (highest priority)
            if current == StatusCalendarWidget.STATE_VACATION and new_state != StatusCalendarWidget.STATE_SICKNESS:
                continue  # Keep Vacation unless new is Sickness

            status_data[qdate] = new_state

        self.calendar.set_status_data(status_data)

    def _cycle_day_status(self, qdate: QDate):
        """Cycle status: Work -> Vacation -> Sickness -> Work"""
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
        self.date_label.setText(qdate.toString("dddd, MMMM d, yyyy"))

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
        """Open the dialog to add a manual entry"""
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

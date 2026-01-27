"""
Report Generation Wizard.

A PySide6 dialog for configuring and generating Matrix Reports.
Features:
- Visual Calendar for managing Vacation/Sickness.
- Task exclusion selection.
- Configuration persistence.
"""

import sys
import datetime
import calendar
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Set
import yaml

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTabWidget, QWidget, QFileDialog, QComboBox, QScrollArea,
    QGridLayout, QCheckBox, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor, QPalette

from app.domain.models import Task
from app.infra.repository import TaskRepository
from app.services.matrix_report_service import (
    MatrixReportService, ReportConfiguration, TimeOffConfig
)
from app.infra.config import get_settings


class DayButton(QPushButton):
    """A button representing a day in the calendar."""
    
    # States
    STATE_WORK = "work"
    STATE_VACATION = "vacation"
    STATE_SICKNESS = "sickness"
    
    COLORS = {
        STATE_WORK: "#ffffff",      # White
        STATE_VACATION: "#a5d6a7",  # Green 200
        STATE_SICKNESS: "#ef9a9a",  # Red 200
    }
    
    LABELS = {
        STATE_WORK: "",
        STATE_VACATION: "V",
        STATE_SICKNESS: "S",
    }
    
    stateChanged = Signal(datetime.date, str)
    
    def __init__(self, date_obj: datetime.date, parent=None):
        super().__init__(parent)
        self.date_obj = date_obj
        self.current_state = self.STATE_WORK
        
        self.setFixedSize(40, 40)
        self.setText(str(date_obj.day))
        self.clicked.connect(self._cycle_state)
        self._update_style()
        
    def _cycle_state(self):
        """Cycle through states: Work -> Vacation -> Sickness -> Work"""
        # Prevent changing state on weekends
        if self.date_obj.weekday() >= 5: # 5=Sat, 6=Sun
            return
            
        if self.current_state == self.STATE_WORK:
            self.set_state(self.STATE_VACATION)
        elif self.current_state == self.STATE_VACATION:
            self.set_state(self.STATE_SICKNESS)
        else:
            self.set_state(self.STATE_WORK)
            
    def set_state(self, state: str):
        self.current_state = state
        self._update_style()
        self.stateChanged.emit(self.date_obj, self.current_state)
        
    def _update_style(self):
        # Determine color based on state and weekend status
        if self.date_obj.weekday() >= 5:
            color = "#eeeeee" # Light Gray for weekends
            text_color = "#999999"
            border_color = "#e0e0e0"
        else:
            color = self.COLORS.get(self.current_state, "#ffffff")
            text_color = "#000000"
            border_color = "#bdbdbd"
            
        suffix = self.LABELS.get(self.current_state, "")
        text = f"{self.date_obj.day}\n{suffix}" if suffix else str(self.date_obj.day)
        
        self.setText(text)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border: 2px solid #1976d2;
            }}
        """)


class ReportWindow(QDialog):
    """
    Main Wizard Window for generating reports.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Monthly Report")
        self.resize(600, 500)
        self.setModal(True)
        
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
            
            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: #fff;
            }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #555;
            }
            QTabBar::tab:selected {
                background: #fff;
                border-bottom-color: #fff;
                font-weight: bold;
                color: #1976d2;
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
            
            /* Checkboxes */
            QCheckBox {
                color: #2c3e50;
                background-color: transparent;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f5f5f5;
            }
            QCheckBox::indicator:checked {
                background-color: #1976d2;
                border-color: #1976d2;
                 /* Simple checkmark approximation or use an image if resources allowed. 
                    For pure CSS without images, we can use a border/background trick or just solid color.
                    Solid blue for checked is standard "flat" UI. 
                 */
                 image: url(none); /* remove any default */
            }
            QCheckBox::indicator:hover {
                border-color: #1976d2;
            }
        """)

        # Force Light Palette (helps with title bars on some Qt versions/platforms)
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
        light_palette.setColor(QPalette.Highlight, QColor(25, 118, 210)) # #1976d2
        light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(light_palette)

        self.loop = asyncio.get_event_loop()
        self.settings = get_settings()
        self.report_settings_path = self.settings.config_dir / "report_settings.yaml" if self.settings.config_dir else Path("report_settings.yaml")
        self.report_history = {} # Cache for history
        self.tasks: List[Task] = []
        
        # State
        self.selected_date = datetime.date.today().replace(day=1)
        self.day_buttons: Dict[datetime.date, DayButton] = {}
        self.excluded_tasks_checks: Dict[str, QCheckBox] = {}
        
        # UI Setup
        self._setup_ui()
        
        # Load Data
        # Run synchronously to ensure loading before window usage
        self.loop.run_until_complete(self._load_data())
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Header: Period Selection ---
        # --- Header: Period Selection ---
        header_grp = QGroupBox("Report Period")
        header_layout = QHBoxLayout()
        
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(30)
        self.btn_prev.clicked.connect(self._prev_month)
        
        self.month_combo = QComboBox()
        self.month_combo.addItems(calendar.month_name[1:])
        self.month_combo.setCurrentIndex(self.selected_date.month - 1)
        self.month_combo.currentIndexChanged.connect(self._on_period_changed)
        
        self.year_combo = QComboBox()
        current_year = self.selected_date.year
        self.year_combo.addItems([str(y) for y in range(current_year - 2, current_year + 3)])
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.currentIndexChanged.connect(self._on_period_changed)
        
        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(30)
        self.btn_next.clicked.connect(self._next_month)
        
        header_layout.addWidget(self.btn_prev)
        header_layout.addWidget(self.month_combo)
        header_layout.addWidget(self.year_combo)
        header_layout.addWidget(self.btn_next)
        header_layout.addStretch()
        
        header_grp.setLayout(header_layout)
        layout.addWidget(header_grp)
        
        # --- Tabs ---
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Configuration
        self.config_tab = QWidget()
        self._setup_config_tab()
        self.tabs.addTab(self.config_tab, "Configuration")
        
        # Tab 2: Time Off (Calendar)
        self.time_off_tab = QWidget()
        self._setup_time_off_tab()
        self.tabs.addTab(self.time_off_tab, "Time Off Manager")
        
        # Tab 3: Exclusions
        self.exclusions_tab = QWidget()
        self._setup_exclusions_tab()
        self.tabs.addTab(self.exclusions_tab, "Task Exclusions")
        
        # --- Footer ---
        footer_layout = QHBoxLayout()
        self.status_label = QLabel("")
        footer_layout.addWidget(self.status_label)
        
        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                font-weight: bold;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                color: #000;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #d5d5d5;
            }
        """)
        self.generate_btn.clicked.connect(self._generate_report)
        footer_layout.addWidget(self.generate_btn)
        
        layout.addLayout(footer_layout)
        
    def _setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        
        # Output File
        file_grp = QGroupBox("Output Settings")
        file_layout = QHBoxLayout()
        
        self.path_input = QLabel("No file selected")
        self.path_input.setStyleSheet("color: #666; font-style: italic;")
        
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_file)
        
        file_layout.addWidget(self.path_input)
        file_layout.addWidget(btn_browse)
        file_grp.setLayout(file_layout)
        
        layout.addWidget(file_grp)
        layout.addStretch()
        
    def _setup_time_off_tab(self):
        layout = QVBoxLayout(self.time_off_tab)
        
        # Legend
        legend_layout = QHBoxLayout()
        for state, label, color in [
            (DayButton.STATE_WORK, "Work (Click to cycle)", "white"),
            (DayButton.STATE_VACATION, "Vacation", "#a5d6a7"),
            (DayButton.STATE_SICKNESS, "Sickness", "#ef9a9a")
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"background-color: {color}; border: 1px solid #ccc; padding: 2px 6px; border-radius: 4px;")
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        layout.addLayout(legend_layout)
        
        # Calendar Grid
        self.calendar_area = QWidget()
        self.calendar_grid = QGridLayout(self.calendar_area)
        self.calendar_grid.setSpacing(5)
        
        layout.addWidget(self.calendar_area)
        layout.addStretch()
        
    def _setup_exclusions_tab(self):
        layout = QVBoxLayout(self.exclusions_tab)
        layout.addWidget(QLabel("Select tasks to exclude from 'Total Work' calculation (e.g. Pause, Lunch):"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.exclusions_content = QWidget()
        self.exclusions_layout = QVBoxLayout(self.exclusions_content)
        scroll.setWidget(self.exclusions_content)
        
        layout.addWidget(scroll)
        
    def _browse_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Report", 
            f"report_{self.selected_date.strftime('%m_%Y')}.csv",
            "CSV Files (*.csv)"
        )
        if filename:
            self.path_input.setText(filename)
            self.path_input.setStyleSheet("color: black;")

    def _on_period_changed(self):
        """Handle month/year change"""
        try:
            year = int(self.year_combo.currentText())
            month = self.month_combo.currentIndex() + 1
            self.selected_date = datetime.date(year, month, 1)
            self._render_calendar()
            
            # Update default filename if not manually set (simple check)
            if "report_" in self.path_input.text() or "No file" in self.path_input.text():
                 self.path_input.setText(f"report_{self.selected_date.strftime('%m_%Y')}.csv")
                 
        except ValueError:
            pass

    def _prev_month(self):
        """Go to previous month"""
        first = self.selected_date.replace(day=1)
        prev = first - datetime.timedelta(days=1)
        self._set_period(prev.year, prev.month)

    def _next_month(self):
        """Go to next month"""
        # Add 32 days to ensure we skip into next month, then find 1st
        first = self.selected_date.replace(day=1)
        next_month = (first + datetime.timedelta(days=32)).replace(day=1)
        self._set_period(next_month.year, next_month.month)
        
    def _set_period(self, year: int, month: int):
        """Update combos to set period"""
        # Block signals to prevent double triggering
        self.year_combo.blockSignals(True)
        self.month_combo.blockSignals(True)
        
        self.year_combo.setCurrentText(str(year))
        self.month_combo.setCurrentIndex(month - 1)
        self.selected_date = datetime.date(year, month, 1)
        
        self.year_combo.blockSignals(False)
        self.month_combo.blockSignals(False)
        
        self._render_calendar()
        self._apply_history_for_period() # Restore settings for this new period
        self._update_filename_if_default()

    def _update_filename_if_default(self):
        """Update filename if user hasn't typed a custom one"""
        current_text = self.path_input.text()
        # Heuristic: if it looks like a default filename or is empty
        if "report_" in current_text or "No file" in current_text:
            self.path_input.setText(f"report_{self.selected_date.strftime('%m_%Y')}.csv")
            self.path_input.setStyleSheet("color: black;") # Ensure visible

    def _render_calendar(self):
        """Render the grid of days for the selected month"""
        # Clear existing
        for i in reversed(range(self.calendar_grid.count())): 
            self.calendar_grid.itemAt(i).widget().setParent(None)
        self.day_buttons.clear()
        
        # Header
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, d in enumerate(days):
            self.calendar_grid.addWidget(QLabel(d, alignment=Qt.AlignCenter), 0, i)
        
        # Days
        month_range = calendar.monthrange(self.selected_date.year, self.selected_date.month)
        first_day_weekday = month_range[0] # 0=Mon
        num_days = month_range[1]
        
        row = 1
        col = first_day_weekday
        
        for day in range(1, num_days + 1):
            date_obj = datetime.date(self.selected_date.year, self.selected_date.month, day)
            btn = DayButton(date_obj)
            
            # Disable weekends by default visually? Or keep enabled for flexibility?
            # Let's keep enabled but maybe color differently?
            # For now standard.
            
            self.calendar_grid.addWidget(btn, row, col)
            self.day_buttons[date_obj] = btn
            
            col += 1
            if col > 6:
                col = 0
                row += 1

    async def _load_data(self):
        """Load tasks and configs asynchronously"""
        repo = TaskRepository()
        self.tasks = await repo.get_all_active()
        
        # Populate Exclusions
        for task in self.tasks:
            cb = QCheckBox(task.name)
            self.exclusions_layout.addWidget(cb)
            self.excluded_tasks_checks[task.name] = cb
            
        # Initial Render
        self._render_calendar()
        
        # Load persisted settings
        self._load_settings()

    def _load_settings(self):
        """Load settings from YAML"""
        if not self.report_settings_path.exists():
            return
            
        try:
            with open(self.report_settings_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                
            # 1. Load Defaults (Exclusions)
            defaults = data.get('defaults', {})
            excluded_names = defaults.get('excluded_tasks', [])
            for name, cb in self.excluded_tasks_checks.items():
                if name in excluded_names:
                    cb.setChecked(True)
            
            # 2. Load History for current period
            self.report_history = data.get('history', {})
            self._apply_history_for_period()
            
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def _apply_history_for_period(self):
        """Apply saved time off data for the selected period"""
        period_key = self.selected_date.strftime("%m.%Y")
        period_data = self.report_history.get(period_key, {})
        # Support fallback to old format for migration if needed, but let's stick to new
        if not period_data:
             period_data = self.report_history.get(self.selected_date.strftime("%Y-%m"), {})
        time_off_data = period_data.get('time_off', [])
        
        # Clear current calendar state first
        for btn in self.day_buttons.values():
            if btn.current_state != DayButton.STATE_WORK:
                btn.set_state(DayButton.STATE_WORK)
        
        # Apply saved states
        # Data structure: [{'task_name': 'Vacation', 'days': ['2026-01-01', ...]}, ...]
        for item in time_off_data:
            t_name = item.get('task_name')
            days = item.get('days', [])
            
            state = DayButton.STATE_WORK
            if t_name == "Vacation":
                state = DayButton.STATE_VACATION
            elif t_name == "Sickness":
                state = DayButton.STATE_SICKNESS
            
            if state != DayButton.STATE_WORK:
                for day_str in days:
                    try:
                        # Try German format first, then ISO
                        if "." in day_str:
                            d = datetime.datetime.strptime(day_str, "%d.%m.%Y").date()
                        else:
                            d = datetime.date.fromisoformat(day_str)
                            
                        if d in self.day_buttons:
                            self.day_buttons[d].set_state(state)
                    except ValueError:
                        pass
        
    def _save_settings(self):
        """Save current settings to YAML"""
        # 1. Gather Exclusions
        excluded = [name for name, cb in self.excluded_tasks_checks.items() if cb.isChecked()]
        
        # 2. Gather Time Off for current period
        vacation_days = []
        sickness_days = []
        for date_obj, btn in self.day_buttons.items():
            if btn.current_state == DayButton.STATE_VACATION:
                vacation_days.append(date_obj.strftime("%d.%m.%Y"))
            elif btn.current_state == DayButton.STATE_SICKNESS:
                sickness_days.append(date_obj.strftime("%d.%m.%Y"))
        
        current_time_off = []
        if vacation_days:
            current_time_off.append({'task_name': 'Vacation', 'days': vacation_days})
        if sickness_days:
            current_time_off.append({'task_name': 'Sickness', 'days': sickness_days})
            
        # 3. Update Data Structure
        period_key = self.selected_date.strftime("%m.%Y")
        self.report_history[period_key] = {'time_off': current_time_off}
        
        data = {
            'defaults': {
                'excluded_tasks': excluded
            },
            'history': self.report_history
        }
        
        # 4. Write to file
        try:
            self.report_settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.report_settings_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, sort_keys=False)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def _generate_report(self):
        """Gather config and run generation"""
        output_path = self.path_input.text()
        if "No file" in output_path:
            QMessageBox.warning(self, "Error", "Please select an output file.")
            return

        vacation_days = []
        sickness_days = []
        
        for date_obj, btn in self.day_buttons.items():
            if btn.current_state == DayButton.STATE_VACATION:
                vacation_days.append(date_obj)
            elif btn.current_state == DayButton.STATE_SICKNESS:
                sickness_days.append(date_obj)
        
        time_off_configs = []
        if vacation_days:
            time_off_configs.append(TimeOffConfig(
                task_name="Vacation",
                days=vacation_days
            ))
        if sickness_days:
            time_off_configs.append(TimeOffConfig(
                task_name="Sickness",
                days=sickness_days
            ))
            
        # 2. Gather Exclusions
        excluded = [name for name, cb in self.excluded_tasks_checks.items() if cb.isChecked()]
        
        # 3. Create Config
        config = ReportConfiguration(
            period=self.selected_date.strftime("%m.%Y"),
            output_path=output_path,
            time_off_configs=time_off_configs,
            excluded_tasks=excluded
        )
        
        # 4. Generate
        self.status_label.setText("Saving & Generating...")
        self.generate_btn.setEnabled(False)
        
        # Save settings for persistence
        self._save_settings()
        
        # Run async generation synchronously
        self.loop.run_until_complete(self._run_service(config))
        
    async def _run_service(self, config: ReportConfiguration):
        try:
            service = MatrixReportService()
            content = await service.generate_report(config)
            
            # Save file
            path = Path(config.output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.status_label.setText("Done!")
            QMessageBox.information(self, "Success", f"Report saved to:\n{path}")
            self.close()
            
        except Exception as e:
            self.status_label.setText("Error")
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{e}")
        finally:
            self.generate_btn.setEnabled(True)

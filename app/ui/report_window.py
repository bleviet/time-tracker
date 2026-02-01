"""
Report Generation Wizard.

A PySide6 dialog for configuring and generating Matrix Reports.
Features:
- Visual Calendar for managing Vacation/Sickness.
- Task exclusion selection.
- Configuration persistence.
"""

import datetime
import calendar
import asyncio
from pathlib import Path
from typing import List
import yaml

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTabWidget, QWidget, QFileDialog, QComboBox,
    QMessageBox, QGroupBox, QLabel
)

from app.domain.models import Task
from app.infra.repository import TaskRepository
from app.services.matrix_report_service import ReportConfiguration
from app.infra.config import get_settings
from app.i18n import tr


class ReportWindow(QDialog):
    """
    Main Wizard Window for generating reports.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("report.title"))
        self.resize(600, 500)
        self.setModal(True)

        # Note: Global theme is managed by qdarktheme via SystemTrayApp
        # Only add minimal custom styling for specific elements that need it

        self.loop = asyncio.get_event_loop()
        self.settings = get_settings()
        self.report_settings_path = self.settings.config_dir / "report_settings.yaml" if self.settings.config_dir else Path("report_settings.yaml")
        self.tasks: List[Task] = []

        # State
        self.selected_date = datetime.date.today().replace(day=1)
        self.report_history = {}


        # UI Setup
        self._setup_ui()

        # Load Data
        # Run synchronously to ensure loading before window usage
        self.loop.run_until_complete(self._load_data())

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Header: Period Selection ---
        # --- Header: Period Selection ---
        header_grp = QGroupBox(tr("report.period"))
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

        # --- Footer ---
        footer_layout = QHBoxLayout()
        self.status_label = QLabel("")
        footer_layout.addWidget(self.status_label)

        self.generate_btn = QPushButton(tr("report.generate"))
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.generate_btn.clicked.connect(self._generate_report)
        footer_layout.addWidget(self.generate_btn)

        layout.addLayout(footer_layout)

    def _setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)

        # Template Selection
        tmpl_grp = QGroupBox(tr("report.type"))
        tmpl_layout = QHBoxLayout()
        self.template_combo = QComboBox()
        self.template_combo.addItems(["Excel Report (.xlsx)", "CSV Report (.csv)"])
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        tmpl_layout.addWidget(QLabel(tr("report.template")))
        tmpl_layout.addWidget(self.template_combo)
        tmpl_grp.setLayout(tmpl_layout)
        layout.addWidget(tmpl_grp)

        # Output File
        file_grp = QGroupBox(tr("report.output"))
        file_layout = QHBoxLayout()

        self.path_input = QLabel(tr("report.no_file"))
        self.path_input.setStyleSheet("font-style: italic;")

        btn_browse = QPushButton(tr("report.browse"))
        btn_browse.clicked.connect(self._browse_file)

        file_layout.addWidget(self.path_input)
        file_layout.addWidget(btn_browse)
        file_grp.setLayout(file_layout)

        layout.addWidget(file_grp)
        layout.addStretch()

    def _on_template_changed(self, text):
        """Update filename extension when template type changes"""
        self._update_filename_if_default()

    def _browse_file(self):
        template_type = self.template_combo.currentText()
        is_excel = "Excel" in template_type
        ext = "xlsx" if is_excel else "csv"
        filter_str = "Excel Files (*.xlsx)" if is_excel else "CSV Files (*.csv)"

        filename, _ = QFileDialog.getSaveFileName(
            self, tr("report.save_title"),
            f"report_{self.selected_date.strftime('%m_%Y')}.{ext}",
            filter_str
        )
        if filename:
            self.path_input.setText(filename)
            self.path_input.setStyleSheet("")

    def _on_period_changed(self):
        """Handle month/year change"""
        try:
            year = int(self.year_combo.currentText())
            month = self.month_combo.currentIndex() + 1
            self.selected_date = datetime.date(year, month, 1)

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

        self._update_filename_if_default()

    def _update_filename_if_default(self):
        """Update filename if user hasn't typed a custom one"""
        current_text = self.path_input.text()
        template_type = self.template_combo.currentText()
        is_excel = "Excel" in template_type
        ext = "xlsx" if is_excel else "csv"

        # Heuristic: if it looks like a default filename or is empty
        if "report_" in current_text or "No file" in current_text or tr("report.no_file") in current_text:
            self.path_input.setText(f"report_{self.selected_date.strftime('%m_%Y')}.{ext}")
            self.path_input.setStyleSheet("")  # Reset to default palette color

    async def _load_data(self):
        """Load tasks and configs asynchronously"""
        repo = TaskRepository()
        self.tasks = await repo.get_all_active()

        # Load persisted settings
        self._load_settings()

    def _load_settings(self):
        """Load settings from YAML"""
        if not self.report_settings_path.exists():
            return

        try:
            with open(self.report_settings_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Load History for current period
            self.report_history = data.get('history', {})

        except Exception as e:
            print(f"Failed to load settings: {e}")

    def _save_settings(self):
        """Save current settings to YAML"""
        data = {
            'history': self.report_history
        }

        # Write to file
        try:
            self.report_settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.report_settings_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, sort_keys=False)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def _generate_report(self):
        """Gather config and run generation"""
        output_path = self.path_input.text()
        if "No file" in output_path or tr("report.no_file") in output_path:
            QMessageBox.warning(self, tr("error"), tr("report.select_file_error"))
            return

        # Create Config (no exclusions - handled automatically by service)
        config = ReportConfiguration(
            period=self.selected_date.strftime("%m.%Y"),
            output_path=output_path,
            time_off_configs=[],
            excluded_tasks=[]
        )

        # 4. Generate
        self.status_label.setText(tr("report.generating"))
        self.generate_btn.setEnabled(False)

        # Save settings for persistence
        self._save_settings()

        # Run async generation synchronously
        self.loop.run_until_complete(self._run_service(config))

    async def _run_service(self, config: ReportConfiguration):
        try:
            template_type = self.template_combo.currentText()
            is_excel = "Excel" in template_type

            # Get german_state from settings for holiday detection
            german_state = getattr(self.settings, 'german_state', 'BY')

            path = Path(config.output_path)

            if is_excel:
                from app.services.excel_report_service import ExcelReportService
                service = ExcelReportService(german_state=german_state)
                # Returns path string, writes file internally
                await service.generate_report(config)
            else:
                 # Default to CSV
                 from app.services.accounting_matrix_service import AccountingMatrixService
                 service = AccountingMatrixService(german_state=german_state)
                 content = await service.generate_report(config)

                 # CSV service returns content, needs writing
                 path.parent.mkdir(parents=True, exist_ok=True)
                 with open(path, 'w', encoding='utf-8-sig') as f:
                    f.write(content)

            self.status_label.setText(tr("report.done"))
            QMessageBox.information(self, tr("report.success"), tr("report.saved_to", path=path))
            self.close()

        except Exception as e:
            self.status_label.setText(tr("error"))
            QMessageBox.critical(self, tr("error"), tr("report.failed", error=e))
        finally:
            self.generate_btn.setEnabled(True)

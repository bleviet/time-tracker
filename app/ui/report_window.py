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
        self.tasks: List[Task] = []

        # State
        self.selected_date = datetime.date.today().replace(day=1)


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

        # Template Selection
        tmpl_grp = QGroupBox(tr("report.type"))
        tmpl_layout = QHBoxLayout()
        self.template_combo = QComboBox()
        self.template_combo.addItems(["Monthly Report"])
        tmpl_layout.addWidget(QLabel(tr("report.template")))
        tmpl_layout.addWidget(self.template_combo)
        tmpl_grp.setLayout(tmpl_layout)
        layout.addWidget(tmpl_grp)

        # Output File
        file_grp = QGroupBox(tr("report.output"))
        file_layout = QHBoxLayout()

        self.path_input = QLabel(tr("report.no_file"))
        self.path_input.setStyleSheet("color: #666; font-style: italic;")

        btn_browse = QPushButton(tr("report.browse"))
        btn_browse.clicked.connect(self._browse_file)

        file_layout.addWidget(self.path_input)
        file_layout.addWidget(btn_browse)
        file_grp.setLayout(file_layout)

        layout.addWidget(file_grp)
        layout.addStretch()

    def _browse_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, tr("report.save_title"),
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
        # Heuristic: if it looks like a default filename or is empty
        if "report_" in current_text or "No file" in current_text:
            self.path_input.setText(f"report_{self.selected_date.strftime('%m_%Y')}.csv")
            self.path_input.setStyleSheet("color: black;") # Ensure visible

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

            # Get german_state from settings for holiday detection
            german_state = getattr(self.settings, 'german_state', 'BY')

            # Simplified logic: Always use (or Default to) Accounting Matrix Service for "Monthly Report"
            # as requested by user to replace "Detailed CSV" and remove "Matrix Report"
            if template_type == "Monthly Report":
                from app.services.accounting_matrix_service import AccountingMatrixService
                service = AccountingMatrixService(german_state=german_state)
                content = await service.generate_report(config)
            else:
                # Fallback purely for safety if somehow old value persists, but simpler to just default
                 from app.services.accounting_matrix_service import AccountingMatrixService
                 service = AccountingMatrixService(german_state=german_state)
                 content = await service.generate_report(config)

            path = Path(config.output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.status_label.setText(tr("report.done"))
            QMessageBox.information(self, tr("report.success"), tr("report.saved_to", path=path))
            self.close()

        except Exception as e:
            self.status_label.setText(tr("error"))
            QMessageBox.critical(self, tr("error"), tr("report.failed", error=e))
        finally:
            self.generate_btn.setEnabled(True)

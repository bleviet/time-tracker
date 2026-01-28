
import asyncio
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QCheckBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QMessageBox,
    QLabel, QGroupBox
)
from PySide6.QtCore import Qt

from app.domain.models import UserPreferences
from app.infra.repository import UserRepository

class SettingsDialog(QDialog):
    """
    Application-wide settings dialog.
    Tabs: General, Work Regulations
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 400)
        
        self.loop = asyncio.get_event_loop()
        self.repo = UserRepository()
        self.prefs = UserPreferences() # Default
        
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        # Tab 1: General
        self.general_tab = QWidget()
        self._setup_general_tab()
        self.tabs.addTab(self.general_tab, "General")
        
        # Tab 2: Work Regulations
        self.regulations_tab = QWidget()
        self._setup_regulations_tab()
        self.tabs.addTab(self.regulations_tab, "Work Regulations")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _setup_general_tab(self):
        layout = QFormLayout(self.general_tab)
        
        self.check_auto_pause = QCheckBox("Auto-pause when screen locks")
        self.check_ask_unlock = QCheckBox("Ask about time away on unlock")
        
        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(0, 60)
        self.spin_threshold.setSuffix(" min")
        
        layout.addRow(self.check_auto_pause)
        layout.addRow(self.check_ask_unlock)
        layout.addRow("Auto-pause threshold:", self.spin_threshold)
        
        # Tray settings
        self.check_show_seconds = QCheckBox("Show seconds in tray icon")
        self.check_minimize_tray = QCheckBox("Minimize to try instead of closing")
        
        layout.addRow(self.check_show_seconds)
        layout.addRow(self.check_minimize_tray)

    def _setup_regulations_tab(self):
        layout = QVBoxLayout(self.regulations_tab)
        
        # Target
        target_group = QGroupBox("Daily Target")
        target_form = QFormLayout(target_group)
        
        self.spin_work_hours = QDoubleSpinBox()
        self.spin_work_hours.setRange(1.0, 24.0)
        self.spin_work_hours.setSingleStep(0.5)
        self.spin_work_hours.setSuffix(" hours")
        
        target_form.addRow("Target Hours per Day:", self.spin_work_hours)
        layout.addWidget(target_group)
        
        # Compliance
        comp_group = QGroupBox("Compliance Warnings")
        comp_layout = QVBoxLayout(comp_group)
        
        self.check_enable_compliance = QCheckBox("Enable German Compliance Checks")
        self.check_enable_compliance.setToolTip("Warns about exceeding 10 hours daily limit")
        
        # Optional Checks
        self.check_breaks = QCheckBox("Check for Mandatory Breaks")
        self.check_breaks.setToolTip("Warn if >6h without 30m break, or >9h without 45m break")
        
        self.check_rest = QCheckBox("Check for Rest Periods (11h)")
        self.check_rest.setToolTip("Warn if less than 11h between end of work and start of next day")
        
        comp_layout.addWidget(self.check_enable_compliance)
        comp_layout.addWidget(self.check_breaks)
        comp_layout.addWidget(self.check_rest)
        
        # Max Hours (Warning only)
        # We hardcode 10h as warning trigger as per ArbZG, but user can change "Warning Level" in theory
        # or we update description.
        self.lbl_max_info = QLabel("<i>Note: You will always be warned if you exceed 10 hours.</i>")
        self.lbl_max_info.setStyleSheet("color: gray")
        comp_layout.addWidget(self.lbl_max_info)
        
        layout.addWidget(comp_group)
        layout.addStretch()

    def _load_data(self):
        try:
            self.prefs = self.loop.run_until_complete(self.repo.get_preferences())
            
            # General
            self.check_auto_pause.setChecked(self.prefs.auto_pause_on_lock)
            self.check_ask_unlock.setChecked(self.prefs.ask_on_unlock)
            self.spin_threshold.setValue(self.prefs.auto_pause_threshold_minutes)
            self.check_show_seconds.setChecked(self.prefs.show_seconds_in_tray)
            self.check_minimize_tray.setChecked(self.prefs.minimize_to_tray)
            
            # Regulations
            self.spin_work_hours.setValue(self.prefs.work_hours_per_day)
            self.check_enable_compliance.setChecked(self.prefs.enable_german_compliance)
            self.check_breaks.setChecked(self.prefs.check_breaks)
            self.check_rest.setChecked(self.prefs.check_rest_periods)
            
            # Update optional state
            self._update_compliance_state()
            self.check_enable_compliance.stateChanged.connect(self._update_compliance_state)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load settings: {e}")

    def _update_compliance_state(self):
        enabled = self.check_enable_compliance.isChecked()
        # Dependent checkboxes
        # Actually user said Breaks are optional/disabled by default.
        # So they can be enabled independently? Or only if "Compliance" is permitted?
        # Let's keep them independent but maybe grouped visually under Compliance.
        # But for logic: if Compliance=False, do we check breaks?
        # Let's say: Compliance Toggle = Master Switch for "Strict German Rules".
        # But "Check Breaks" might be useful even for non-strict.
        # Let's keep them active.
        pass

    def _save(self):
        try:
            # Update Prefs Object
            self.prefs.auto_pause_on_lock = self.check_auto_pause.isChecked()
            self.prefs.ask_on_unlock = self.check_ask_unlock.isChecked()
            self.prefs.auto_pause_threshold_minutes = self.spin_threshold.value()
            self.prefs.show_seconds_in_tray = self.check_show_seconds.isChecked()
            self.prefs.minimize_to_tray = self.check_minimize_tray.isChecked()
            
            self.prefs.work_hours_per_day = self.spin_work_hours.value()
            self.prefs.enable_german_compliance = self.check_enable_compliance.isChecked()
            self.prefs.check_breaks = self.check_breaks.isChecked()
            self.prefs.check_rest_periods = self.check_rest.isChecked()
            
            # Check 10h logic: if compliance enabled, maybe enforce 10h in logic, but here we just save.
            
            self.loop.run_until_complete(self.repo.update_preferences(self.prefs))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

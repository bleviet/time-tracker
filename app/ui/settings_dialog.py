
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



    def _load_data(self):
        try:
            self.prefs = self.loop.run_until_complete(self.repo.get_preferences())
            
            # General
            self.check_auto_pause.setChecked(self.prefs.auto_pause_on_lock)
            self.check_ask_unlock.setChecked(self.prefs.ask_on_unlock)
            self.spin_threshold.setValue(self.prefs.auto_pause_threshold_minutes)
            self.check_show_seconds.setChecked(self.prefs.show_seconds_in_tray)
            self.check_minimize_tray.setChecked(self.prefs.minimize_to_tray)

            

            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load settings: {e}")



    def _save(self):
        try:
            # Update Prefs Object
            self.prefs.auto_pause_on_lock = self.check_auto_pause.isChecked()
            self.prefs.ask_on_unlock = self.check_ask_unlock.isChecked()
            self.prefs.auto_pause_threshold_minutes = self.spin_threshold.value()
            self.prefs.show_seconds_in_tray = self.check_show_seconds.isChecked()
            self.prefs.minimize_to_tray = self.check_minimize_tray.isChecked()

            
            # Check 10h logic: if compliance enabled, maybe enforce 10h in logic, but here we just save.
            
            self.loop.run_until_complete(self.repo.update_preferences(self.prefs))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

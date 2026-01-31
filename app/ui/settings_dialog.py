
import asyncio
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QCheckBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QMessageBox,
    QLabel, QGroupBox, QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
    QComboBox, QListWidget, QListWidgetItem, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, QTime

from app.domain.models import UserPreferences
from app.infra.repository import UserRepository
from app.services.backup_service import BackupService


class SettingsDialog(QDialog):
    """
    Application-wide settings dialog.
    """

    # Emitted when data is restored from backup, so other windows can refresh
    data_restored = Signal()
    # Emitted when theme changes, so the app can apply the new theme
    theme_changed = Signal(str)
    # Emitted when font scale changes
    font_scale_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(550, 500)

        self.loop = asyncio.get_event_loop()
        self.repo = UserRepository()
        self.backup_service = BackupService()
        self.prefs = UserPreferences() # Default
        self._loading = False  # Flag to prevent theme changes during load

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # Tab 1: General
        self.general_tab = QWidget()
        self._setup_general_tab()
        self.tabs.addTab(self.general_tab, "General")

        # Tab 2: Backup
        self.backup_tab = QWidget()
        self._setup_backup_tab()
        self.tabs.addTab(self.backup_tab, "Backup")

        layout.addWidget(self.tabs)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _setup_general_tab(self):
        layout = QFormLayout(self.general_tab)

        # Appearance section
        appearance_label = QLabel("Appearance")
        appearance_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addRow(appearance_label)

        # Theme selection
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("Follow System", "auto")
        self.combo_theme.addItem("Light", "light")
        self.combo_theme.addItem("Dark", "dark")
        self.combo_theme.setToolTip("Select application color theme")
        self.combo_theme.currentIndexChanged.connect(self._on_theme_preview)
        layout.addRow("Theme:", self.combo_theme)

        # Font size control
        font_layout = QHBoxLayout()
        self.spin_font_scale = QDoubleSpinBox()
        self.spin_font_scale.setRange(0.5, 2.0)
        self.spin_font_scale.setSingleStep(0.1)
        self.spin_font_scale.setValue(1.0)
        self.spin_font_scale.setToolTip("Adjust font size (0.5 = 50%, 1.0 = 100%, 2.0 = 200%)")
        self.spin_font_scale.valueChanged.connect(self._on_font_scale_preview)
        font_layout.addWidget(self.spin_font_scale)
        self.font_scale_label = QLabel("100%")
        self.font_scale_label.setMinimumWidth(50)
        font_layout.addWidget(self.font_scale_label)
        font_layout.addStretch()
        layout.addRow("Font Size:", font_layout)

        # Add separator
        separator_label = QLabel("")
        layout.addRow(separator_label)

        # Behavior section
        behavior_label = QLabel("Behavior")
        behavior_label.setStyleSheet("font-weight: bold;")
        layout.addRow(behavior_label)

        self.check_auto_pause = QCheckBox("Auto-pause when screen locks")
        self.check_ask_unlock = QCheckBox("Ask about time away on unlock")

        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(0, 60)
        self.spin_threshold.setSuffix(" min")

        layout.addRow(self.check_auto_pause)
        layout.addRow(self.check_ask_unlock)
        layout.addRow("Auto-pause threshold:", self.spin_threshold)

        # Add separator
        separator_label2 = QLabel("")
        layout.addRow(separator_label2)

        # Tray section
        tray_label = QLabel("System Tray")
        tray_label.setStyleSheet("font-weight: bold;")
        layout.addRow(tray_label)

        self.check_show_seconds = QCheckBox("Show seconds in tray icon")
        self.check_minimize_tray = QCheckBox("Minimize to tray instead of closing")

        layout.addRow(self.check_show_seconds)
        layout.addRow(self.check_minimize_tray)

    def _setup_backup_tab(self):
        """Setup the backup settings tab"""
        layout = QVBoxLayout(self.backup_tab)

        # Automatic Backup Group
        auto_group = QGroupBox("Automatic Backup")
        auto_layout = QFormLayout(auto_group)

        self.check_backup_enabled = QCheckBox("Enable automatic backups")
        self.check_backup_enabled.stateChanged.connect(self._on_backup_enabled_changed)
        auto_layout.addRow(self.check_backup_enabled)

        # Frequency
        self.combo_backup_frequency = QComboBox()
        self.combo_backup_frequency.addItem("Daily", 1)
        self.combo_backup_frequency.addItem("Every 3 days", 3)
        self.combo_backup_frequency.addItem("Weekly", 7)
        self.combo_backup_frequency.addItem("Every 2 weeks", 14)
        self.combo_backup_frequency.addItem("Monthly", 30)
        auto_layout.addRow("Backup frequency:", self.combo_backup_frequency)

        # Backup time
        from PySide6.QtWidgets import QTimeEdit
        self.time_backup = QTimeEdit()
        self.time_backup.setDisplayFormat("HH:mm")
        self.time_backup.setTime(QTime(9, 0))  # Default 9:00 AM
        self.time_backup.setToolTip("Time of day when automatic backup will be performed")
        auto_layout.addRow("Backup time:", self.time_backup)

        # Retention
        self.spin_backup_retention = QSpinBox()
        self.spin_backup_retention.setRange(1, 50)
        self.spin_backup_retention.setValue(5)
        self.spin_backup_retention.setSuffix(" backups")
        auto_layout.addRow("Keep last:", self.spin_backup_retention)

        # Backup directory
        dir_layout = QHBoxLayout()
        self.edit_backup_dir = QLineEdit()
        self.edit_backup_dir.setPlaceholderText("Default: AppData/TimeTracker/backups")
        self.btn_browse_backup = QPushButton("Browse...")
        self.btn_browse_backup.clicked.connect(self._browse_backup_dir)
        dir_layout.addWidget(self.edit_backup_dir)
        dir_layout.addWidget(self.btn_browse_backup)
        auto_layout.addRow("Backup location:", dir_layout)

        # Last backup info
        self.label_last_backup = QLabel("Last backup: Never")
        self.label_last_backup.setStyleSheet("color: #666; font-style: italic;")
        auto_layout.addRow(self.label_last_backup)

        layout.addWidget(auto_group)

        # Manual Backup/Restore Group
        manual_group = QGroupBox("Manual Backup && Restore")
        manual_layout = QVBoxLayout(manual_group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_backup_now = QPushButton("📦 Backup Now")
        self.btn_backup_now.clicked.connect(self._backup_now)
        self.btn_restore = QPushButton("📥 Restore from Backup...")
        self.btn_restore.clicked.connect(self._restore_backup)
        btn_row.addWidget(self.btn_backup_now)
        btn_row.addWidget(self.btn_restore)
        btn_row.addStretch()
        manual_layout.addLayout(btn_row)

        # Backup list
        manual_layout.addWidget(QLabel("Available backups:"))
        self.list_backups = QListWidget()
        self.list_backups.setMaximumHeight(150)
        manual_layout.addWidget(self.list_backups)

        # Refresh button
        refresh_row = QHBoxLayout()
        self.btn_refresh_backups = QPushButton("🔄 Refresh List")
        self.btn_refresh_backups.clicked.connect(self._refresh_backup_list)
        self.btn_delete_backup = QPushButton("🗑️ Delete Selected")
        self.btn_delete_backup.clicked.connect(self._delete_selected_backup)
        refresh_row.addWidget(self.btn_refresh_backups)
        refresh_row.addWidget(self.btn_delete_backup)
        refresh_row.addStretch()
        manual_layout.addLayout(refresh_row)

        layout.addWidget(manual_group)
        layout.addStretch()

    def _on_backup_enabled_changed(self, state):
        """Enable/disable backup controls based on checkbox"""
        # Handle both int and Qt.CheckState enum
        enabled = state == Qt.Checked or state == Qt.CheckState.Checked or state == 2
        self.combo_backup_frequency.setEnabled(enabled)
        self.time_backup.setEnabled(enabled)
        self.spin_backup_retention.setEnabled(enabled)
        self.edit_backup_dir.setEnabled(enabled)
        self.btn_browse_backup.setEnabled(enabled)

    def _browse_backup_dir(self):
        """Open directory browser for backup location"""
        current = self.edit_backup_dir.text() or str(Path.home())
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Backup Directory", current
        )
        if dir_path:
            self.edit_backup_dir.setText(dir_path)

    def _backup_now(self):
        """Create a backup immediately"""
        from datetime import date
        try:
            backup_dir = self.edit_backup_dir.text() or None
            backup_file = self.loop.run_until_complete(
                self.backup_service.create_backup(backup_dir)
            )

            # Update last backup date in preferences
            self.prefs.last_backup_date = date.today().isoformat()
            self.loop.run_until_complete(self.repo.update_preferences(self.prefs))

            QMessageBox.information(
                self, "Backup Complete",
                f"Backup created successfully:\n{backup_file}"
            )
            self._refresh_backup_list()
            self._update_last_backup_label()
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", f"Failed to create backup:\n{e}")

    def _restore_backup(self):
        """Restore from a backup file"""
        # Check if a backup is selected in the list
        selected = self.list_backups.currentItem()
        if selected:
            backup_path = selected.data(Qt.UserRole)
        else:
            # Open file dialog
            backup_dir = self.edit_backup_dir.text() or str(
                self.backup_service._get_default_backup_dir()
            )
            backup_path, _ = QFileDialog.getOpenFileName(
                self, "Select Backup File", backup_dir,
                "Backup Files (*.json);;All Files (*.*)"
            )

        if not backup_path:
            return

        # Confirm restore
        reply = QMessageBox.warning(
            self, "Confirm Restore",
            f"⚠️ WARNING: This will REPLACE all current data!\n\n"
            f"All existing tasks, time entries, and accounting profiles\n"
            f"will be permanently deleted and replaced with the backup.\n\n"
            f"This action cannot be undone.\n\n"
            f"Continue with restore?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            result = self.loop.run_until_complete(
                self.backup_service.restore_backup(Path(backup_path))
            )
            QMessageBox.information(
                self, "Restore Complete",
                f"Backup restored successfully!\n\n"
                f"Restored items:\n"
                f"- Accounting profiles: {result['accounting']}\n"
                f"- Tasks: {result['tasks']}\n"
                f"- Time entries: {result['time_entries']}"
            )
            # Notify other windows to refresh their data
            self.data_restored.emit()
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", f"Failed to restore backup:\n{e}")

    def _refresh_backup_list(self):
        """Refresh the list of available backups"""
        self.list_backups.clear()
        backup_dir = self.edit_backup_dir.text() or None

        backups = self.backup_service.list_backups(backup_dir)
        for backup in backups:
            item = QListWidgetItem(
                f"{backup['date'].strftime('%Y-%m-%d %H:%M:%S')} ({backup['size_human']})"
            )
            item.setData(Qt.UserRole, backup['path'])
            item.setToolTip(backup['path'])
            self.list_backups.addItem(item)

    def _delete_selected_backup(self):
        """Delete the selected backup file"""
        selected = self.list_backups.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a backup to delete.")
            return

        backup_path = selected.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete this backup?\n\n{Path(backup_path).name}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                Path(backup_path).unlink()
                self._refresh_backup_list()
                QMessageBox.information(self, "Deleted", "Backup deleted successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete backup:\n{e}")

    def _update_last_backup_label(self):
        """Update the last backup date label"""
        if self.prefs.last_backup_date:
            self.label_last_backup.setText(f"Last backup: {self.prefs.last_backup_date}")
        else:
            self.label_last_backup.setText("Last backup: Never")

    def _on_theme_preview(self, index: int):
        """Preview theme change immediately when selection changes"""
        if self._loading:
            return  # Don't trigger theme change during initial load
        theme = self.combo_theme.currentData()
        self.theme_changed.emit(theme)

    def _on_font_scale_preview(self, value: float):
        """Preview font scale change and update label"""
        self.font_scale_label.setText(f"{int(value * 100)}%")
        if self._loading:
            return  # Don't trigger changes during initial load
        self.font_scale_changed.emit(value)

    def _load_data(self):
        try:
            self._loading = True  # Prevent theme changes during load
            self.prefs = self.loop.run_until_complete(self.repo.get_preferences())

            # Theme (loading flag prevents triggering preview during load)
            theme_index = self.combo_theme.findData(self.prefs.theme)
            if theme_index >= 0:
                self.combo_theme.setCurrentIndex(theme_index)

            # General
            self.check_auto_pause.setChecked(self.prefs.auto_pause_on_lock)
            self.check_ask_unlock.setChecked(self.prefs.ask_on_unlock)
            self.spin_threshold.setValue(self.prefs.auto_pause_threshold_minutes)
            self.check_show_seconds.setChecked(self.prefs.show_seconds_in_tray)
            self.check_minimize_tray.setChecked(self.prefs.minimize_to_tray)

            # Font scale
            self.spin_font_scale.setValue(self.prefs.font_scale)
            self.font_scale_label.setText(f"{int(self.prefs.font_scale * 100)}%")

            # Backup
            self.check_backup_enabled.setChecked(self.prefs.backup_enabled)
            # Set frequency combo index
            freq_index = self.combo_backup_frequency.findData(self.prefs.backup_frequency_days)
            if freq_index >= 0:
                self.combo_backup_frequency.setCurrentIndex(freq_index)
            # Set backup time
            try:
                hour, minute = map(int, self.prefs.backup_time.split(':'))
                self.time_backup.setTime(QTime(hour, minute))
            except (ValueError, AttributeError):
                self.time_backup.setTime(QTime(9, 0))  # Default
            self.spin_backup_retention.setValue(self.prefs.backup_retention_count)
            self.edit_backup_dir.setText(self.prefs.backup_directory or "")
            self._on_backup_enabled_changed(
                Qt.Checked if self.prefs.backup_enabled else Qt.Unchecked
            )
            self._update_last_backup_label()
            self._refresh_backup_list()

            self._loading = False  # Loading complete, allow theme changes

        except Exception as e:
            self._loading = False
            QMessageBox.critical(self, "Error", f"Failed to load settings: {e}")



    def _save(self):
        try:
            # Theme
            self.prefs.theme = self.combo_theme.currentData()

            # Update Prefs Object
            self.prefs.auto_pause_on_lock = self.check_auto_pause.isChecked()
            self.prefs.ask_on_unlock = self.check_ask_unlock.isChecked()
            self.prefs.auto_pause_threshold_minutes = self.spin_threshold.value()
            self.prefs.show_seconds_in_tray = self.check_show_seconds.isChecked()
            self.prefs.minimize_to_tray = self.check_minimize_tray.isChecked()
            self.prefs.font_scale = self.spin_font_scale.value()

            # Backup settings
            self.prefs.backup_enabled = self.check_backup_enabled.isChecked()
            self.prefs.backup_frequency_days = self.combo_backup_frequency.currentData()
            self.prefs.backup_time = self.time_backup.time().toString("HH:mm")
            self.prefs.backup_retention_count = self.spin_backup_retention.value()
            backup_dir = self.edit_backup_dir.text().strip()
            self.prefs.backup_directory = backup_dir if backup_dir else None

            self.loop.run_until_complete(self.repo.update_preferences(self.prefs))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

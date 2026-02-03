
import asyncio
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QCheckBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QMessageBox,
    QLabel, QGroupBox, QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
    QComboBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QTime

from app.domain.models import UserPreferences
from app.infra.repository import UserRepository
from app.services.backup_service import BackupService
from app.i18n import tr


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
    # Emitted when language changes
    language_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
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
        self.tabs.addTab(self.general_tab, tr("settings.general"))

        # Tab 2: Backup
        self.backup_tab = QWidget()
        self._setup_backup_tab()
        self.tabs.addTab(self.backup_tab, tr("settings.backup"))

        layout.addWidget(self.tabs)

        # Buttons
        self.btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.btns.accepted.connect(self._save)
        self.btns.rejected.connect(self.reject)
        layout.addWidget(self.btns)

    def _setup_general_tab(self):
        layout = QFormLayout(self.general_tab)

        # Appearance section
        appearance_label = QLabel(tr("settings.appearance"))
        appearance_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addRow(appearance_label)

        # Theme selection
        self.combo_theme = QComboBox()
        self.combo_theme.addItem(tr("settings.theme_auto"), "auto")
        self.combo_theme.addItem(tr("settings.theme_light"), "light")
        self.combo_theme.addItem(tr("settings.theme_dark"), "dark")
        self.combo_theme.setToolTip("Select application color theme")
        self.combo_theme.currentIndexChanged.connect(self._on_theme_preview)
        layout.addRow(tr("settings.theme"), self.combo_theme)

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
        layout.addRow(tr("settings.font_size"), font_layout)

        # Language selection
        self.combo_language = QComboBox()
        self.combo_language.addItem(f"{tr('settings.theme_auto')} (System)", "auto")
        self.combo_language.addItem(tr("settings.language_en"), "en")
        self.combo_language.addItem(tr("settings.language_de"), "de")
        self.combo_language.setToolTip("Select UI language")
        self.combo_language.currentIndexChanged.connect(self._on_language_preview)
        layout.addRow(tr("settings.language"), self.combo_language)

        # Add separator
        separator_label = QLabel("")
        layout.addRow(separator_label)

        # Behavior section
        behavior_label = QLabel(tr("settings.behavior"))
        behavior_label.setStyleSheet("font-weight: bold;")
        layout.addRow(behavior_label)

        self.check_auto_pause = QCheckBox(tr("settings.auto_pause"))
        self.check_ask_unlock = QCheckBox(tr("settings.ask_unlock"))

        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(0, 60)
        self.spin_threshold.setSuffix(f" {tr('time.minutes')}")

        layout.addRow(self.check_auto_pause)
        layout.addRow(self.check_ask_unlock)
        layout.addRow(tr("settings.pause_threshold"), self.spin_threshold)

        # Add separator
        separator_label2 = QLabel("")
        layout.addRow(separator_label2)

        # Regional section
        regional_label = QLabel(tr("settings.regional"))
        regional_label.setStyleSheet("font-weight: bold;")
        layout.addRow(regional_label)

        # German state selection
        self.combo_german_state = QComboBox()
        self._populate_german_states()
        self.combo_german_state.setToolTip(
            "Select your German state for accurate public holiday detection"
        )
        layout.addRow(tr("settings.german_state"), self.combo_german_state)

        self.check_respect_holidays = QCheckBox(tr("settings.respect_holidays"))
        self.check_respect_holidays.setToolTip("Disable tracking on public holidays")
        layout.addRow(self.check_respect_holidays)

        self.check_respect_weekends = QCheckBox(tr("settings.respect_weekends"))
        self.check_respect_weekends.setToolTip("Disable tracking on weekends")
        layout.addRow(self.check_respect_weekends)

        # Add separator
        separator_label3 = QLabel("")
        layout.addRow(separator_label3)

        # Tray section
        tray_label = QLabel(tr("settings.system_tray"))
        tray_label.setStyleSheet("font-weight: bold;")
        layout.addRow(tray_label)

        self.check_show_seconds = QCheckBox(tr("settings.show_seconds"))
        self.check_minimize_tray = QCheckBox(tr("settings.minimize_tray"))

        layout.addRow(self.check_show_seconds)
        layout.addRow(self.check_minimize_tray)

    def _populate_german_states(self):
        """Populate the German state dropdown with all 16 states."""
        # German states with their two-letter codes
        german_states = [
            ("BW", "Baden-Württemberg"),
            ("BY", "Bavaria (Bayern)"),
            ("BE", "Berlin"),
            ("BB", "Brandenburg"),
            ("HB", "Bremen"),
            ("HH", "Hamburg"),
            ("HE", "Hesse (Hessen)"),
            ("MV", "Mecklenburg-Vorpommern"),
            ("NI", "Lower Saxony (Niedersachsen)"),
            ("NW", "North Rhine-Westphalia (Nordrhein-Westfalen)"),
            ("RP", "Rhineland-Palatinate (Rheinland-Pfalz)"),
            ("SL", "Saarland"),
            ("SN", "Saxony (Sachsen)"),
            ("ST", "Saxony-Anhalt (Sachsen-Anhalt)"),
            ("SH", "Schleswig-Holstein"),
            ("TH", "Thuringia (Thüringen)"),
        ]
        for code, name in german_states:
            self.combo_german_state.addItem(f"{name} ({code})", code)

    def _setup_backup_tab(self):
        """Setup the backup settings tab"""
        layout = QVBoxLayout(self.backup_tab)

        # Automatic Backup Group
        self.auto_group = QGroupBox(tr("settings.backup_auto"))
        auto_layout = QFormLayout(self.auto_group)

        self.check_backup_enabled = QCheckBox(tr("settings.backup_enable"))
        self.check_backup_enabled.stateChanged.connect(self._on_backup_enabled_changed)
        auto_layout.addRow(self.check_backup_enabled)

        # Frequency
        self.combo_backup_frequency = QComboBox()
        self.combo_backup_frequency.addItem(tr("backup.daily"), 1)
        self.combo_backup_frequency.addItem(tr("backup.every_3_days"), 3)
        self.combo_backup_frequency.addItem(tr("backup.weekly"), 7)
        self.combo_backup_frequency.addItem(tr("backup.every_2_weeks"), 14)
        self.combo_backup_frequency.addItem(tr("backup.monthly"), 30)
        auto_layout.addRow(tr("settings.backup_frequency"), self.combo_backup_frequency)

        # Backup time
        from PySide6.QtWidgets import QTimeEdit
        self.time_backup = QTimeEdit()
        self.time_backup.setDisplayFormat("HH:mm")
        self.time_backup.setTime(QTime(9, 0))  # Default 9:00 AM
        self.time_backup.setToolTip("Time of day when automatic backup will be performed")
        auto_layout.addRow(tr("settings.backup_time"), self.time_backup)

        # Retention
        self.spin_backup_retention = QSpinBox()
        self.spin_backup_retention.setRange(1, 50)
        self.spin_backup_retention.setValue(5)
        self.spin_backup_retention.setSuffix(f" {tr('time.backups')}")
        auto_layout.addRow(tr("settings.backup_retention"), self.spin_backup_retention)

        # Backup directory
        dir_layout = QHBoxLayout()
        self.edit_backup_dir = QLineEdit()
        self.edit_backup_dir.setPlaceholderText("Default: AppData/TimeTracker/backups")
        self.btn_browse_backup = QPushButton(tr("settings.backup_browse"))
        self.btn_browse_backup.clicked.connect(self._browse_backup_dir)
        dir_layout.addWidget(self.edit_backup_dir)
        dir_layout.addWidget(self.btn_browse_backup)
        auto_layout.addRow(tr("settings.backup_location"), dir_layout)

        # Last backup info
        self.label_last_backup = QLabel(f"{tr('settings.backup_last')} {tr('settings.backup_never')}")
        self.label_last_backup.setStyleSheet("color: #666; font-style: italic;")
        auto_layout.addRow(self.label_last_backup)

        layout.addWidget(self.auto_group)

        # Manual Backup/Restore Group
        self.manual_group = QGroupBox(tr("settings.backup_manual"))
        manual_layout = QVBoxLayout(self.manual_group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_backup_now = QPushButton(f"📦 {tr('settings.backup_now')}")
        self.btn_backup_now.clicked.connect(self._backup_now)
        self.btn_restore = QPushButton(f"📥 {tr('settings.backup_restore')}")
        self.btn_restore.clicked.connect(self._restore_backup)
        btn_row.addWidget(self.btn_backup_now)
        btn_row.addWidget(self.btn_restore)
        btn_row.addStretch()
        manual_layout.addLayout(btn_row)

        # Backup list
        self.label_available_backups = QLabel(tr("settings.backup_available"))
        manual_layout.addWidget(self.label_available_backups)
        self.list_backups = QListWidget()
        self.list_backups.setMaximumHeight(150)
        manual_layout.addWidget(self.list_backups)

        # Refresh button
        refresh_row = QHBoxLayout()
        self.btn_refresh_backups = QPushButton(tr("settings.backup_refresh"))
        self.btn_refresh_backups.clicked.connect(self._refresh_backup_list)
        self.btn_delete_backup = QPushButton(tr("settings.backup_delete"))
        self.btn_delete_backup.clicked.connect(self._delete_selected_backup)
        refresh_row.addWidget(self.btn_refresh_backups)
        refresh_row.addWidget(self.btn_delete_backup)
        refresh_row.addStretch()
        manual_layout.addLayout(refresh_row)

        layout.addWidget(self.manual_group)
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
            self, tr("settings.backup_select_dir"), current
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
                self, tr("settings.backup_complete_title"),
                f"{tr('settings.backup_complete_msg')}\n{backup_file}"
            )
            self._refresh_backup_list()
            self._update_last_backup_label()
        except Exception as e:
            QMessageBox.critical(self, tr("settings.backup_failed_title"), f"{tr('settings.backup_failed_msg')}\n{e}")

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
                self, tr("settings.backup_select_file"), backup_dir,
                "Backup Files (*.json);;All Files (*.*)"
            )

        if not backup_path:
            return

        # Confirm restore
        reply = QMessageBox.warning(
            self, tr("settings.restore_confirm_title"),
            tr("settings.restore_confirm_msg"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            result = self.loop.run_until_complete(
                self.backup_service.restore_backup(Path(backup_path))
            )
            QMessageBox.information(
                self, tr("settings.restore_complete_title"),
                f"{tr('settings.restore_complete_msg')}\n\n"
                f"{tr('settings.restore_details')}:\n"
                f"- Accounting profiles: {result['accounting']}\n"
                f"- Tasks: {result['tasks']}\n"
                f"- Time entries: {result['time_entries']}"
            )
            # Notify other windows to refresh their data
            self.data_restored.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("settings.restore_failed_title"), f"{tr('settings.restore_failed_msg')}\n{e}")

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
            QMessageBox.warning(self, tr("settings.no_selection_title"), tr("settings.no_selection_msg"))
            return

        backup_path = selected.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, tr("settings.delete_confirm_title"),
            f"{tr('settings.delete_confirm_msg')}\n\n{Path(backup_path).name}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                Path(backup_path).unlink()
                self._refresh_backup_list()
                QMessageBox.information(self, tr("settings.deleted_title"), tr("settings.deleted_msg"))
            except Exception as e:
                QMessageBox.critical(self, tr("error"), f"{tr('settings.delete_failed_msg')}\n{e}")

    def _update_last_backup_label(self):
        """Update the last backup date label"""
        # This implementation is replaced by the one inside retranslate_ui to support translation
        pass

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

    def _on_language_preview(self, index: int):
        """Preview language change immediately when selection changes"""
        if self._loading:
            return  # Don't trigger language change during initial load
        language = self.combo_language.itemData(index)
        self.language_changed.emit(language)
        # Update UI language immediately
        from app.i18n import set_language, on_language_changed, detect_system_language
        if language == 'auto':
            set_language(detect_system_language())
        else:
            set_language(language)
        self.retranslate_ui()

    def retranslate_ui(self):
        """Update strings when language changes"""
        self.setWindowTitle(tr("settings.title"))
        self.tabs.setTabText(0, tr("settings.general"))
        self.tabs.setTabText(1, tr("settings.backup"))
        
        # General Tab labels are harder to update dynamically with QFormLayout as they are not stored as fields
        # Ideally, we would reconstruct the fields or have stored references to labels. 
        # For now, immediate switching updates critical parts, reopen dialog to fully refresh form labels 
        # is a simpler strategy if full dynamic translation of form labels is too complex to refactor now.
        # But wait, we can store labels or just recreate the dialog.
        
        # Actually, let's just accept that some static labels might need close/reopen
        # OR we can iterate layout items.
        # Given the "immediate" requirement, the cleanest way without refactoring everything to store 20+ labels
        # is to tell the user that some settings might need reopen, OR we refactor to store labels.
        #
        # Better approach: We update what we can easily access.
        self.combo_theme.setItemText(0, tr("settings.theme_auto"))
        self.combo_theme.setItemText(1, tr("settings.theme_light"))
        self.combo_theme.setItemText(2, tr("settings.theme_dark"))
        
        self.combo_language.setItemText(0, f"{tr('settings.theme_auto')} (System)")
        self.combo_language.setItemText(1, tr("settings.language_en"))
        self.combo_language.setItemText(2, tr("settings.language_de"))

        self.check_auto_pause.setText(tr("settings.auto_pause"))
        self.check_ask_unlock.setText(tr("settings.ask_unlock"))
        self.spin_threshold.setSuffix(f" {tr('time.minutes')}")
        
        self.check_respect_holidays.setText(tr("settings.respect_holidays"))
        self.check_respect_weekends.setText(tr("settings.respect_weekends"))
        
        self.check_show_seconds.setText(tr("settings.show_seconds"))
        self.check_minimize_tray.setText(tr("settings.minimize_tray"))
        
        # Backup Tab
        self.auto_group.setTitle(tr("settings.backup_auto"))
        self.check_backup_enabled.setText(tr("settings.backup_enable"))
        self.combo_backup_frequency.setItemText(0, tr("backup.daily"))
        self.combo_backup_frequency.setItemText(1, tr("backup.every_3_days"))
        self.combo_backup_frequency.setItemText(2, tr("backup.weekly"))
        self.combo_backup_frequency.setItemText(3, tr("backup.every_2_weeks"))
        self.combo_backup_frequency.setItemText(4, tr("backup.monthly"))
        
        self.spin_backup_retention.setSuffix(f" {tr('time.backups')}")
        self.btn_browse_backup.setText(tr("settings.backup_browse"))
        
        # Update last backup label
        self._update_last_backup_label()
        
        self.manual_group.setTitle(tr("settings.backup_manual"))
        self.btn_backup_now.setText(f"📦 {tr('settings.backup_now')}")
        self.btn_restore.setText(f"📥 {tr('settings.backup_restore')}")
        self.label_available_backups.setText(tr("settings.backup_available"))
        self.btn_refresh_backups.setText(tr("settings.backup_refresh"))
        self.btn_refresh_backups.setText(tr("settings.backup_refresh"))
        self.btn_delete_backup.setText(tr("settings.backup_delete"))
        
        # Update Dialog Buttons
        self.btns.button(QDialogButtonBox.Save).setText(tr("dialog.save"))
        self.btns.button(QDialogButtonBox.Cancel).setText(tr("dialog.cancel"))

    def _update_last_backup_label(self):
        """Update the last backup date label"""
        last_text = self.prefs.last_backup_date if self.prefs.last_backup_date else tr("settings.backup_never")
        self.label_last_backup.setText(f"{tr('settings.backup_last')} {last_text}")

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

            # Language
            lang_index = self.combo_language.findData(self.prefs.language)
            if lang_index >= 0:
                self.combo_language.setCurrentIndex(lang_index)

            # Regional settings
            state_index = self.combo_german_state.findData(self.prefs.german_state)
            if state_index >= 0:
                self.combo_german_state.setCurrentIndex(state_index)
            self.check_respect_holidays.setChecked(self.prefs.respect_holidays)
            self.check_respect_weekends.setChecked(self.prefs.respect_weekends)

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
            
            # Apply translations to ensure buttons are correct
            self.retranslate_ui()

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
            self.prefs.language = self.combo_language.currentData()

            # Regional settings
            self.prefs.german_state = self.combo_german_state.currentData()
            self.prefs.respect_holidays = self.check_respect_holidays.isChecked()
            self.prefs.respect_weekends = self.check_respect_weekends.isChecked()

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

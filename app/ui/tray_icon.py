"""
System Tray Application - Main UI entry point.

Architecture Decision: Presentation Layer
This layer only handles UI logic. Business logic is delegated to Services.
"""

import sys
import os
import asyncio
import datetime
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon, QPixmap, QColor, QAction, QKeySequence, QShortcut, QFont
from PySide6.QtCore import QTimer, Qt
import qdarktheme

from app.services import CalendarService, TimerService, ReportService
from app.services.backup_service import BackupService
from app.infra.config import get_settings
from app.infra.os_hooks import create_system_monitor
from app.infra.db import init_db
from app.infra.repository import TaskRepository
from app.domain.models import Task
from app.i18n import tr, set_language, detect_system_language, on_language_changed
from .dialogs import InterruptionDialog
from .main_window import MainWindow
from .history_window import HistoryWindow
from .settings_dialog import SettingsDialog
from .splash_screen import SplashScreen
from app.utils import get_resource_path


class SystemTrayApp:
    """
    Main application class managing the system tray icon and coordination.

    Follows Clean Architecture: UI delegates to Services, Services use Repositories.
    """

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running when windows close

        # Show splash screen immediately for perceived responsiveness
        self.splash = SplashScreen()
        self.splash.show()
        self.app.processEvents()

        # Set application icon (for taskbar, etc.)
        app_icon = self._create_icon()
        self.app.setWindowIcon(app_icon)

        # Settings
        self.settings = get_settings()

        # Event loop for async operations (needed early for loading preferences)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Load user preferences from repository (same source as settings dialog)
        self.splash.update_status("Loading preferences...")
        from app.infra.repository import UserRepository
        self.user_repo = UserRepository()
        self.user_prefs = self.loop.run_until_complete(self.user_repo.get_preferences())

        # Apply theme based on user preference from repository
        self.splash.update_status("Applying theme...")
        self._apply_theme(self.user_prefs.theme)

        # Apply font scale
        self._apply_font_scale(self.user_prefs.font_scale)

        # Apply language
        self._apply_language(self.user_prefs.language)

        # Register for language change notifications
        on_language_changed(self._on_language_changed)

        # Services
        self.calendar = CalendarService(
            german_state=self.settings.preferences.german_state,
            respect_holidays=self.settings.preferences.respect_holidays,
            respect_weekends=self.settings.preferences.respect_weekends
        )
        self.timer = TimerService()
        self.report_service = ReportService()

        # System Monitor
        self.system_monitor = create_system_monitor()
        self.lock_time: Optional[datetime.datetime] = None

        # Tasks cache (initialize early)
        self.tasks = []

        # Windows
        self.main_window = None
        self.history_window = None
        self.settings_window = None

        # Connect signals
        self._connect_signals()

        # Background tasks
        self.recovery_task = None


        # Setup UI
        self.tray_icon = QSystemTrayIcon(self._create_icon(), self.app)
        self.tray_icon.setToolTip("Time Tracker Ready")
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.setup_menu()
        self.tray_icon.show()

        # Initialize on startup
        QTimer.singleShot(0, self._async_init)

    def _create_icon(self):
        """Create the tray icon from assets"""
        # Load icon from correct path (works in dev and frozen)
        # Prefer .ico for Windows as it contains multiple sizes
        icon_path = get_resource_path("app/assets/icon.ico")
        if icon_path.exists():
            return QIcon(str(icon_path))

        # Fallback to PNG
        icon_path = get_resource_path("app/assets/clock_icon.png")

        if icon_path.exists():
            return QIcon(str(icon_path))

        # Fallback if icon not found
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("green"))
        return QIcon(pixmap)

    def _apply_theme(self, theme: str):
        """Apply the specified theme using qdarktheme.

        Args:
            theme: 'light', 'dark', or 'auto' (follows system)
        """
        if theme == "auto":
            qdarktheme.setup_theme("auto")
        elif theme == "dark":
            qdarktheme.setup_theme("dark")
        else:
            qdarktheme.setup_theme("light")

    def change_theme(self, theme: str):
        """Change the application theme at runtime.

        Args:
            theme: 'light', 'dark', or 'auto' (follows system)
        """
        self._apply_theme(theme)
        # Update all open windows to reflect the new theme
        if self.main_window:
            self.main_window.update_theme(theme)
        if self.history_window:
            self.history_window.update_theme()
        # Settings dialog uses standard Qt widgets that auto-update with palette

    def _apply_font_scale(self, scale: float):
        """Apply font scale to the application.

        Args:
            scale: Font scale factor (1.0 = 100%, 0.5 = 50%, 2.0 = 200%)
        """
        font = self.app.font()
        # Get the default system font size (typically 9-10 pt)
        default_size = QFont().pointSize()
        if default_size <= 0:
            default_size = 9  # Fallback default
        font.setPointSizeF(default_size * scale)
        self.app.setFont(font)

    def change_font_scale(self, scale: float):
        """Change the application font scale at runtime.

        Args:
            scale: Font scale factor (1.0 = 100%, 0.5 = 50%, 2.0 = 200%)
        """
        self._apply_font_scale(scale)

    def _apply_language(self, language: str):
        """Apply the specified language.

        Args:
            language: 'en', 'de', or 'auto' (detect from system)
        """
        if language == 'auto':
            language = detect_system_language()
        set_language(language)

    def change_language(self, language: str):
        """Change the application language at runtime.

        Args:
            language: 'en', 'de', or 'auto' (detect from system)
        """
        self._apply_language(language)

    def _on_language_changed(self, language: str):
        """Handle language change notification - update all UI elements."""
        # Update tray menu
        self.setup_menu()
        # Update tooltip
        self.tray_icon.setToolTip(tr("app.ready"))
        # Update main window if open
        if self.main_window:
            self.main_window.retranslate_ui()
        # Update history window if open
        if self.history_window:
            self.history_window.retranslate_ui()

    def _connect_signals(self):
        """Connect service signals to UI handlers"""
        # Timer signals
        self.timer.tick.connect(self.update_tooltip)
        self.timer.task_started.connect(lambda tid: None)  # Could show notification
        self.timer.task_stopped.connect(lambda tid, secs: None)

        # Notification signals
        self.timer.target_reached.connect(self._on_target_reached)
        self.timer.limit_reached.connect(self._on_limit_reached)

        # System monitor signals
        self.system_monitor.system_locked.connect(self._on_system_locked)
        self.system_monitor.system_unlocked.connect(self._on_system_unlocked)

    def _on_target_reached(self, hours: float):
        """Show notification when daily target is reached"""
        self.tray_icon.showMessage(
            "Target Reached!",
            f"Congratulations! You have reached your daily target of {hours} hours.",
            QSystemTrayIcon.Information,
            10000
        )

    def _on_limit_reached(self, hours: float):
        """Show warning when daily limit is reached"""
        self.tray_icon.showMessage(
            "Maximum Limit Reached!",
            f"Warning: You have reached the maximum daily limit of {hours} hours.\nPlease stop working.",
            QSystemTrayIcon.Warning,
            15000
        )

    def _async_init(self):
        """Async initialization tasks"""
        try:
            # Initialize database
            self.splash.update_status("Initializing database...")
            self.loop.run_until_complete(init_db())

            # Load tasks
            self.splash.update_status("Loading tasks...")
            self.loop.run_until_complete(self._load_tasks())

            # Rebuild menu with loaded tasks
            self.setup_menu()

            # Create and show main window
            self.splash.update_status("Starting application...")
            self.main_window = MainWindow(self.timer, self.tasks)
            self.main_window.update_theme(self.user_prefs.theme)  # Apply saved theme
            self.main_window.closed.connect(self._on_main_window_closed)
            self.main_window.show_history.connect(self._show_history_window)
            self.main_window.show()

            # Close splash screen now that main window is ready
            self.splash.finish(self.main_window)

            # Setup global shortcut to show window (Ctrl+Shift+T)
            self.show_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self.main_window)
            self.show_shortcut.activated.connect(self._show_main_window)
            self.show_shortcut.setContext(Qt.ApplicationShortcut)

            # Check for holidays
            self.check_today()

            # Start system monitoring
            self.system_monitor.start_monitoring()

            # Perform scheduled backup if needed
            self._check_scheduled_backup()

            # Setup periodic backup check (every 30 minutes)
            self.backup_timer = QTimer()
            self.backup_timer.timeout.connect(self._check_scheduled_backup)
            self.backup_timer.start(30 * 60 * 1000)  # 30 minutes in milliseconds

            # Check for orphaned entries (crash recovery)
            self._check_orphaned_entries()

        except Exception as e:
            QMessageBox.critical(None, "Initialization Error",
                               f"Failed to initialize application:\n{e}")

    def _check_orphaned_entries(self):
        """Check for and recover orphaned entries from previous sessions"""
        self.recovery_task = self.loop.create_task(self._process_orphaned_entries())

    async def _process_orphaned_entries(self):
        """Process orphaned entries async"""
        try:
            repo = self.timer.entry_repo
            orphans = await repo.get_orphaned_entries()

            if not orphans:
                return

            recovered_count = 0
            for entry in orphans:
                # Calculate likely end time based on recorded duration
                # duration_seconds is updated periodically, so this is the "last known active time"
                inferred_end_time = entry.start_time + datetime.timedelta(seconds=entry.duration_seconds)

                # Check for plausibility - if duration is 0, maybe it just started and crashed?
                # If duration is 0, set end_time to start_time (0 duration)

                entry.end_time = inferred_end_time
                entry.notes = (entry.notes or "") + " [Recovered: Auto-closed after unclean shutdown]"

                await repo.update(entry)
                recovered_count += 1

            if recovered_count > 0:
                self.tray_icon.showMessage(
                    "Session Recovery",
                    f"Recovered {recovered_count} unfinished task(s) from previous session.",
                    QSystemTrayIcon.Information,
                    5000
                )

        except Exception as e:
            print(f"Failed to recover orphaned entries: {e}")

    async def _load_tasks(self):
        """Load tasks from database"""
        task_repo = TaskRepository()
        self.tasks = await task_repo.get_all_active()

        # If no tasks exist, create default ones
        if not self.tasks:
            defaults = [
                Task(name="General Admin", description="Administrative work"),
                Task(name="Software Development", description="Coding and development"),
                Task(name="Meetings", description="Meetings and calls"),
            ]
            for task in defaults:
                created = await task_repo.create(task)
                self.tasks.append(created)

    def setup_menu(self):
        """Setup the system tray context menu"""
        menu = QMenu()

        # Show Main Window
        show_action = QAction(tr("tray.show_window"), self.app)
        show_action.triggered.connect(self._show_main_window)
        menu.addAction(show_action)

        menu.addSeparator()

        # Quit Action
        quit_action = QAction(tr("tray.quit"), self.app)
        quit_action.triggered.connect(self._quit_application)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)

    def _show_settings(self):
        """Show settings dialog"""
        if not self.settings_window:
            self.settings_window = SettingsDialog()
            self.settings_window.data_restored.connect(self._on_data_restored)
            self.settings_window.theme_changed.connect(self.change_theme)
            self.settings_window.font_scale_changed.connect(self.change_font_scale)
            self.settings_window.language_changed.connect(self.change_language)
        self.settings_window.show()
        self.settings_window.activateWindow()

    def _on_data_restored(self):
        """Handle data restoration - refresh all windows"""
        # Reload tasks
        self.loop.run_until_complete(self._load_tasks())
        # Refresh history window if open
        if self.history_window:
            self.history_window.refresh_data()

    def _check_scheduled_backup(self):
        """Check if a scheduled backup is due and perform it"""
        try:
            backup_service = BackupService()
            backup_result = self.loop.run_until_complete(
                backup_service.perform_scheduled_backup()
            )
            if backup_result:
                self.tray_icon.showMessage(
                    "Backup Complete",
                    f"Automatic backup created successfully.",
                    QSystemTrayIcon.Information,
                    3000
                )
        except Exception as e:
            self.tray_icon.showMessage(
                "Backup Failed",
                f"Failed to create scheduled backup: {e}",
                QSystemTrayIcon.Warning,
                5000
            )

    def _show_history_window(self):
        """Show the history window"""
        if not self.history_window:
            self.history_window = HistoryWindow(self.loop)
        self.history_window.show()
        self.history_window.activateWindow()

    def _start_task_sync(self, task_id: int):
        """Synchronous wrapper for starting a task"""
        try:
            self.loop.run_until_complete(self.timer.start_task(task_id))
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Failed to start task:\n{e}")

    def _stop_task_sync(self):
        """Synchronous wrapper for stopping a task"""
        try:
            self.loop.run_until_complete(self.timer.stop_task())
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Failed to stop task:\n{e}")



    def update_tooltip(self, text: str, seconds: int):
        """Update the tray icon tooltip with current time"""
        self.tray_icon.setToolTip(text)

    def check_today(self):
        """Check if today is a holiday or weekend"""
        today = datetime.date.today()

        if not self.calendar.is_working_day(today):
            holiday_name = self.calendar.get_holiday_name(today)
            if holiday_name:
                message = f"Today is {holiday_name}. Enjoy your day!"
            else:
                message = "It's the weekend. Time to relax!"

            self.tray_icon.showMessage(
                "Holiday Notice",
                message,
                QSystemTrayIcon.Information,
                5000  # 5 seconds
            )

    def _on_system_locked(self):
        """Handle system lock event"""
        if not self.settings.preferences.auto_pause_on_lock:
            return

        self.lock_time = datetime.datetime.now()
        self.timer.pause_task()

        self.tray_icon.showMessage(
            "Paused",
            "Tracking paused (screen locked)",
            QSystemTrayIcon.Information,
            2000
        )

    def _on_system_unlocked(self):
        """Handle system unlock event"""
        if not self.lock_time:
            return

        # Calculate time away
        now = datetime.datetime.now()
        elapsed_seconds = (now - self.lock_time).total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        # Only ask if away longer than threshold
        if elapsed_minutes < self.settings.preferences.auto_pause_threshold_minutes:
            self.timer.resume_task()
            self.lock_time = None
            return

        # Ask user what to do with the time
        if self.settings.preferences.ask_on_unlock and self.timer.active_task:
            dialog = InterruptionDialog(elapsed_minutes)
            dialog.exec()

            was_work = dialog.choice == "track"

            # Handle the interruption
            try:
                self.loop.run_until_complete(
                    self.timer.mark_interruption(was_work, int(elapsed_seconds))
                )

                if was_work:
                    self.tray_icon.showMessage(
                        "Time Added",
                        f"Added {elapsed_minutes:.1f} minutes to task",
                        QSystemTrayIcon.Information,
                        3000
                    )
            except Exception as e:
                print(f"Error handling interruption: {e}")

        # Resume tracking
        self.timer.resume_task()
        self.lock_time = None

    def _show_main_window(self):
        """Show the main window"""
        if self.main_window:
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.raise_()

    def _on_main_window_closed(self):
        """Handle main window close (minimize to tray)"""
        self.tray_icon.showMessage(
            "Time Tracker",
            "Application minimized to tray. Click icon to restore.",
            QSystemTrayIcon.Information,
            2000
        )

    def _on_tray_icon_activated(self, reason):
        """Handle tray icon click"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_main_window()

    def _quit_application(self):
        """Quit the application"""
        # Stop tracking
        if self.timer.is_tracking():
            self.loop.run_until_complete(self.timer.stop_task())

        # Stop monitoring
        self.system_monitor.stop_monitoring()

        # Close main window if open
        if self.main_window:
            # Disconnect closed signal to prevent "minimized to tray" notification
            try:
                self.main_window.closed.disconnect(self._on_main_window_closed)
            except (RuntimeError, TypeError):
                pass
            self.main_window.close()

        # Cancel background tasks
        if self.recovery_task and not self.recovery_task.done():
            self.recovery_task.cancel()
            try:
                # brief run to process cancellation
                self.loop.run_until_complete(asyncio.sleep(0))
            except Exception:
                pass

        # Close event loop
        self.loop.close()

        # Quit Qt application
        self.app.quit()

    def run(self):
        """Run the application"""
        return sys.exit(self.app.exec())

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
from PySide6.QtGui import QIcon, QPixmap, QColor, QAction, QKeySequence, QShortcut
from PySide6.QtCore import QTimer, Qt

from app.services import CalendarService, TimerService, ReportService
from app.infra.config import get_settings
from app.infra.os_hooks import create_system_monitor
from app.infra.db import init_db
from app.infra.repository import TaskRepository
from app.domain.models import Task
from .dialogs import InterruptionDialog
from .main_window import MainWindow
from .history_window import HistoryWindow
from .settings_dialog import SettingsDialog
from app.utils import get_resource_path


class SystemTrayApp:
    """
    Main application class managing the system tray icon and coordination.
    
    Follows Clean Architecture: UI delegates to Services, Services use Repositories.
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # Set application icon (for taskbar, etc.)
        app_icon = self._create_icon()
        self.app.setWindowIcon(app_icon)
        
        # Settings
        self.settings = get_settings()
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.minimize_to_tray = self.settings.preferences.minimize_to_tray and self.tray_available
        self.app.setQuitOnLastWindowClosed(not self.minimize_to_tray)
        
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
        
        # Setup UI
        self.tray_icon = None
        if self.tray_available:
            self.tray_icon = QSystemTrayIcon(self._create_icon(), self.app)
            self.tray_icon.setToolTip("Time Tracker Ready")
            self.tray_icon.activated.connect(self._on_tray_icon_activated)
            self.setup_menu()
            self.tray_icon.show()
        
        # Event loop for async operations
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
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
        self._show_tray_message(
            "Target Reached!",
            f"Congratulations! You have reached your daily target of {hours} hours.",
            QSystemTrayIcon.Information,
            10000
        )
        
    def _on_limit_reached(self, hours: float):
        """Show warning when daily limit is reached"""
        self._show_tray_message(
            "Maximum Limit Reached!",
            f"Warning: You have reached the maximum daily limit of {hours} hours.\nPlease stop working.",
            QSystemTrayIcon.Warning,
            15000
        )
    
    def _async_init(self):
        """Async initialization tasks"""
        try:
            # Initialize database
            self.loop.run_until_complete(init_db())
            
            # Load tasks
            self.loop.run_until_complete(self._load_tasks())
            
            # Rebuild menu with loaded tasks
            self.setup_menu()
            
            # Create and show main window
            self.main_window = MainWindow(self.timer, self.tasks, minimize_to_tray=self.minimize_to_tray)
            if self.minimize_to_tray:
                self.main_window.closed.connect(self._on_main_window_closed)
            self.main_window.show_history.connect(self._show_history_window)
            self.main_window.show()
            
            # Setup global shortcut to show window (Ctrl+Shift+T)
            self.show_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self.main_window)
            self.show_shortcut.activated.connect(self._show_main_window)
            self.show_shortcut.setContext(Qt.ApplicationShortcut)
            
            # Check for holidays
            self.check_today()

            if not self.tray_available:
                QMessageBox.information(
                    self.main_window,
                    "System Tray Unavailable",
                    "No system tray was detected. On GNOME Shell, install the "
                    "'AppIndicator and KStatusNotifierItem Support' extension "
                    "to enable tray icons."
                )
            
            # Start system monitoring
            self.system_monitor.start_monitoring()
            
        except Exception as e:
            QMessageBox.critical(None, "Initialization Error", 
                               f"Failed to initialize application:\n{e}")
    
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
        if not self.tray_icon:
            return
        menu = QMenu()
        
        # Show Main Window
        show_action = QAction("Show Main Window", self.app)
        show_action.triggered.connect(self._show_main_window)
        menu.addAction(show_action)
        

        
        menu.addSeparator()

        # View History
        history_action = QAction("Monthly Overview...", self.app)
        history_action.triggered.connect(self._show_history_window)
        menu.addAction(history_action)
        

        
        menu.addSeparator()
        
        # Settings
        settings_action = QAction("Settings...", self.app)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)
        
        menu.addSeparator()
        
        # Quit Action
        quit_action = QAction("Quit", self.app)
        quit_action.triggered.connect(self._quit_application)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
    
    def _show_settings(self):
        """Show settings dialog"""
        if not self.settings_window:
            self.settings_window = SettingsDialog()
        self.settings_window.show()
        self.settings_window.activateWindow()
    
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
        if self.tray_icon:
            self.tray_icon.setToolTip(text)

    def _show_tray_message(self, title: str, message: str, icon, duration: int):
        """Show a tray notification if available"""
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, icon, duration)
    
    def check_today(self):
        """Check if today is a holiday or weekend"""
        today = datetime.date.today()
        
        if not self.calendar.is_working_day(today):
            holiday_name = self.calendar.get_holiday_name(today)
            if holiday_name:
                message = f"Today is {holiday_name}. Enjoy your day!"
            else:
                message = "It's the weekend. Time to relax!"
            
            self._show_tray_message(
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
        
        self._show_tray_message(
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
                    self._show_tray_message(
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
        self._show_tray_message(
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
            self.main_window.close()
        
        # Close event loop
        self.loop.close()
        
        # Quit Qt application
        self.app.quit()
    
    def run(self):
        """Run the application"""
        return sys.exit(self.app.exec())

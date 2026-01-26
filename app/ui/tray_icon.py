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
from .report_window import ReportWindow
from app.utils import get_resource_path


class SystemTrayApp:
    """
    Main application class managing the system tray icon and coordination.
    
    Follows Clean Architecture: UI delegates to Services, Services use Repositories.
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running when windows close
        
        # Set application icon (for taskbar, etc.)
        app_icon = self._create_icon()
        self.app.setWindowIcon(app_icon)
        
        # Settings
        self.settings = get_settings()
        
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
        
        # Main Window (will be shown after initialization)
        self.main_window = None
        
        # Connect signals
        self._connect_signals()
        
        # Setup UI
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
        
        # System monitor signals
        self.system_monitor.system_locked.connect(self._on_system_locked)
        self.system_monitor.system_unlocked.connect(self._on_system_unlocked)
    
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
            self.main_window = MainWindow(self.timer, self.tasks)
            self.main_window.closed.connect(self._on_main_window_closed)
            self.main_window.show()
            
            # Setup global shortcut to show window (Ctrl+Shift+T)
            self.show_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self.main_window)
            self.show_shortcut.activated.connect(self._show_main_window)
            self.show_shortcut.setContext(Qt.ApplicationShortcut)
            
            # Check for holidays
            self.check_today()
            
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
        menu = QMenu()
        
        # Show Main Window
        show_action = QAction("Show Main Window", self.app)
        show_action.triggered.connect(self._show_main_window)
        menu.addAction(show_action)
        
        menu.addSeparator()
        
        # Task Selection Submenu (quick access)
        if self.tasks:
            task_menu = menu.addMenu("Quick Start Task")
            for task in self.tasks[:5]:  # Show top 5 tasks
                action = QAction(task.name, self.app)
                action.triggered.connect(
                    lambda checked, t=task: self._start_task_sync(t.id)
                )
                task_menu.addAction(action)
        
        # Stop Action
        stop_action = QAction("Stop Tracking", self.app)
        stop_action.triggered.connect(self._stop_task_sync)
        menu.addAction(stop_action)
        
        menu.addSeparator()
        
        # Generate Report
        report_action = QAction("Generate Report...", self.app)
        report_action.triggered.connect(self._generate_report_sync)
        menu.addAction(report_action)
        
        menu.addSeparator()
        
        # Quit Action
        quit_action = QAction("Quit", self.app)
        quit_action.triggered.connect(self._quit_application)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
    
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
    
    def _generate_report_sync(self):
        """Open the report generation wizard"""
        try:
            self.report_window = ReportWindow()
            self.report_window.show()
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Failed to open report wizard:\n{e}")
    
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
            self.main_window.close()
        
        # Close event loop
        self.loop.close()
        
        # Quit Qt application
        self.app.quit()
    
    def run(self):
        """Run the application"""
        return sys.exit(self.app.exec())

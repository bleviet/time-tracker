"""
Main Window - Minimal always-on-top task tracker widget.

Architecture Decision: Simplicity first
Minimal UI with just task input and timer display, always visible on screen.
"""

import asyncio
from typing import List, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QLineEdit,
    QLabel, QCompleter, QMessageBox, QApplication, QPushButton
)
from PySide6.QtCore import Qt, Signal, QStringListModel
from PySide6.QtGui import QFont, QScreen, QShortcut, QKeySequence

from app.domain.models import Task
from app.services import TimerService
from app.infra.repository import TaskRepository


class MainWindow(QMainWindow):
    """
    Minimal always-on-top widget showing only task name and timer.
    
    Features:
    - Task input field with autocomplete (always editable for instant switching)
    - Large timer display
    - Always on top, transparent background
    - Positioned at bottom right
    """
    
    # Signals
    closed = Signal()  # Emitted when window is closed
    show_history = Signal() # Request to show history window
    
    def __init__(self, timer_service: TimerService, tasks: List[Task], parent=None, minimize_to_tray: bool = True):
        super().__init__(parent)
        self.timer_service = timer_service
        self.tasks = tasks
        self.minimize_to_tray = minimize_to_tray
        self.loop = asyncio.get_event_loop()
        
        # Window settings for minimal always-on-top widget
        self.setWindowTitle("Time Tracker")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
        self._update_completer()
        self._setup_shortcuts()
        
        # Position at bottom right after UI is set up
        QApplication.processEvents()  # Ensure size is calculated
        self._position_bottom_right()
        
    def _setup_ui(self):
        """Setup the minimal UI - just task input and timer"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Add modern rounded border styling to entire widget
        central_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 240);
                border-radius: 15px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)
        
        # Horizontal layout for task name and timer side by side
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)
        
        # Task input with autocomplete
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Task name...")
        self.task_input.returnPressed.connect(self._on_task_entered)
        
        # Modern styling for task input
        task_font = QFont()
        task_font.setPointSize(11)
        self.task_input.setFont(task_font)
        self.task_input.setMinimumHeight(30)
        self.task_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                padding: 5px;
                color: #2c3e50;
            }
            QLineEdit:focus {
                color: #1976d2;
            }
        """)
        
        # Setup autocomplete
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.task_input.setCompleter(self.completer)
        
        layout.addWidget(self.task_input, stretch=3)
        
        # Play/Pause Button
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.clicked.connect(self._toggle_tracking)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #4CAF50;  /* Green for Play */
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.1);
            }
        """)
        self.toggle_btn.setToolTip("Start Tracking")
        layout.addWidget(self.toggle_btn)
        
        # Separator line
        separator = QLabel("|")
        separator.setStyleSheet("color: rgba(0, 0, 0, 0.2); font-size: 14px;")
        separator.setAlignment(Qt.AlignCenter)
        layout.addWidget(separator)
        
        # Timer display
        self.timer_display = QLabel("00:00:00")
        self.timer_display.setAlignment(Qt.AlignCenter)
        timer_font = QFont()
        timer_font.setPointSize(11)
        timer_font.setBold(True)
        self.timer_display.setFont(timer_font)
        self.timer_display.setMinimumHeight(30)
        self.timer_display.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #1976d2;
                padding: 5px;
            }
        """)
        
        layout.addWidget(self.timer_display, stretch=2)
        # Minimize button
        self.minimize_button = QPushButton("▼")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.clicked.connect(self.hide)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: rgba(0, 0, 0, 0.5);
                font-size: 20px;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
                color: rgba(0, 0, 0, 0.8);
            }
        """)
        self.minimize_button.setToolTip("Hide to tray (Esc)")
        layout.addWidget(self.minimize_button)
        
        # Make window compact with rounded appearance
        self.setFixedHeight(50)
        self.setMinimumWidth(450)
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Escape to minimize/hide
        hide_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        hide_shortcut.activated.connect(self.hide)
        
        # Note: Global shortcut to show window is handled in tray_icon.py
        # because global shortcuts need to work even when window is hidden
        self.setMinimumWidth(400)
    
    def _position_bottom_right(self):
        """Position window at bottom right of screen"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            
            # Wait for window to have correct size
            self.adjustSize()
            window_geometry = self.frameGeometry()
            
            # Position at bottom right with margin
            x = screen_geometry.width() - window_geometry.width() - 20
            y = screen_geometry.height() - window_geometry.height() - 20
            
            self.move(x, y)
        
    def _connect_signals(self):
        """Connect timer service signals to UI updates"""
        self.timer_service.tick.connect(self._on_timer_tick)
        self.timer_service.task_started.connect(self._on_task_started)
        self.timer_service.task_stopped.connect(self._on_task_stopped)
    
    def _update_completer(self):
        """Update the autocomplete with current task names"""
        task_names = [task.name for task in self.tasks]
        model = QStringListModel(task_names)
        self.completer.setModel(model)
    
    def _toggle_tracking(self):
        """Toggle between Play and Pause"""
        if self.timer_service.is_tracking():
            self._stop_current_task()
        else:
            # If stopped, try to start task from input
            self._on_task_entered()

    def _on_task_entered(self):
        """Handle Enter key press in task input"""
        task_name = self.task_input.text().strip()
        
        if not task_name:
            return
        
        # Find or create task
        try:
            self.loop.run_until_complete(self._start_task_by_name(task_name))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to start task:\n{e}")
    
    async def _start_task_by_name(self, task_name: str):
        """Find or create task and start tracking"""
        # Check if task exists
        existing_task = None
        for task in self.tasks:
            if task.name.lower() == task_name.lower():
                existing_task = task
                break
        
        # Create new task if it doesn't exist
        if not existing_task:
            task_repo = TaskRepository()
            new_task = Task(name=task_name)
            created_task = await task_repo.create(new_task)
            self.tasks.append(created_task)
            self._update_completer()
            existing_task = created_task
        
        # Start tracking
        await self.timer_service.start_task(existing_task.id)
    
    def _on_timer_tick(self, formatted_time: str, seconds: int):
        """Update timer display on each tick"""
        # Extract just the time portion (HH:MM:SS)
        if ": " in formatted_time:
            time_only = formatted_time.split(": ")[1]
        else:
            time_only = formatted_time
        self.timer_display.setText(time_only)
    
    def _on_task_started(self, task_id: int):
        """Update UI when task starts"""
        # Find task name and set it in the input field
        task_name = "Unknown Task"
        for task in self.tasks:
            if task.id == task_id:
                task_name = task.name
                break
        
        # Keep input editable for instant task switching
        self.task_input.setText(task_name)
        self.task_input.selectAll()  # Select all text for easy overwriting
        
        # Update styling for Pause state
        self.toggle_btn.setText("⏸")
        self.toggle_btn.setToolTip("Pause Tracking")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #FF9800;  /* Orange for Pause */
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(255, 152, 0, 0.1);
            }
        """)
    
    def _on_task_stopped(self, task_id: int, total_seconds: int):
        """Update UI when task stops"""
        self.task_input.clear()
        self.task_input.setPlaceholderText("Task name...")
        self.timer_display.setText("00:00:00")
        
        # Update styling for Play state
        self.toggle_btn.setText("▶")
        self.toggle_btn.setToolTip("Start Tracking")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #4CAF50;  /* Green for Play */
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.1);
            }
        """)
    
    def refresh_tasks(self, tasks: List[Task]):
        """Refresh the task list (called when tasks are reloaded)"""
        self.tasks = tasks
        self._update_completer()
    
    def mousePressEvent(self, event):
        """Allow dragging the window"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def contextMenuEvent(self, event):
        """Right-click shows option to stop or close"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self)
        
        if self.timer_service.is_tracking():
            stop_action = QAction("Stop Tracking", self)
            stop_action.triggered.connect(self._stop_current_task)
            menu.addAction(stop_action)
            
            menu.addSeparator()
            
        history_action = QAction("View History", self)
        history_action.triggered.connect(self.show_history.emit)
        menu.addAction(history_action)

        menu.addSeparator()
        
        hide_action = QAction("Hide to Tray", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        
        menu.exec(event.globalPos())
    
    def _stop_current_task(self):
        """Stop the current task"""
        try:
            self.loop.run_until_complete(self.timer_service.stop_task())
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to stop task:\n{e}")
    
    def _quit(self):
        """Close the window and emit closed signal"""
        self.close()
    
    def closeEvent(self, event):
        """Override close event to minimize to tray instead of quitting"""
        if self.minimize_to_tray:
            event.ignore()
            self.hide()
            self.closed.emit()
        else:
            event.accept()

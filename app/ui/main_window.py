"""
Main Window - Minimal always-on-top task tracker widget.

Architecture Decision: Simplicity first
Minimal UI with just task input and timer display, always visible on screen.
"""

import asyncio
from typing import List
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QLineEdit,
    QLabel, QCompleter, QMessageBox, QApplication, QPushButton,
    QDialog, QVBoxLayout, QSlider
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QEvent, QUrl
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QPalette

from app.domain.models import Task
from app.services import TimerService
from app.infra.repository import TaskRepository
from app.i18n import tr
from app.utils import get_resource_path


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

    def __init__(self, timer_service: TimerService, tasks: List[Task], parent=None):
        super().__init__(parent)
        self.timer_service = timer_service
        self.tasks = tasks
        self.loop = asyncio.get_event_loop()
        self._current_theme: str = "auto"  # Track explicit theme setting

        # Window settings for minimal always-on-top widget
        self.setWindowTitle(tr("main.title"))
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

    def _is_dark_mode(self) -> bool:
        """Detect if the application is using dark mode based on current theme setting"""
        if self._current_theme == "dark":
            return True
        elif self._current_theme == "light":
            return False
        else:
            # Auto mode: detect from palette
            palette = QApplication.palette()
            window_color = palette.color(QPalette.ColorRole.Window)
            # If window background is darker than mid-gray, we're in dark mode
            return window_color.lightness() < 128

    def _get_theme_colors(self) -> dict:
        """Get theme-appropriate colors for the floating widget"""
        if self._is_dark_mode():
            return {
                'bg': 'rgba(45, 45, 45, 240)',
                'border': 'rgba(255, 255, 255, 0.1)',
                'text': '#e0e0e0',
                'text_focus': '#90caf9',
                'separator': 'rgba(255, 255, 255, 0.2)',
                'timer': '#90caf9',
                'icon': 'rgba(255, 255, 255, 0.6)',
                'icon_hover': 'rgba(255, 255, 255, 0.8)',
                'hover_bg': 'rgba(255, 255, 255, 0.1)',
                'tooltip_bg': '#424242',
                'tooltip_border': '#666666',
            }
        else:
            return {
                'bg': 'rgba(255, 255, 255, 240)',
                'border': 'rgba(0, 0, 0, 0.1)',
                'text': '#2c3e50',
                'text_focus': '#1976d2',
                'separator': 'rgba(0, 0, 0, 0.2)',
                'timer': '#1976d2',
                'icon': 'rgba(0, 0, 0, 0.6)',
                'icon_hover': 'rgba(0, 0, 0, 0.8)',
                'hover_bg': 'rgba(0, 0, 0, 0.1)',
                'tooltip_bg': '#333333',
                'tooltip_border': '#555555',
            }

    def _setup_ui(self):
        """Setup the minimal UI - just task input and timer"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.central_widget = central_widget  # Store reference for theme updates

        # Apply theme-aware styling
        self._apply_widget_theme()

        # Horizontal layout for task name and timer side by side
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)

        # Task input with autocomplete
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText(tr("main.task_placeholder"))
        self.task_input.returnPressed.connect(self._on_task_entered)

        # Modern styling for task input
        task_font = QFont()
        task_font.setPointSize(11)
        self.task_input.setFont(task_font)
        self.task_input.setMinimumHeight(30)

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
        self.toggle_btn.setToolTip(tr("main.start"))
        layout.addWidget(self.toggle_btn)

        # Separator line
        self.separator = QLabel("|")
        self.separator.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.separator)

        # Timer display
        self.timer_display = QLabel("00:00:00")
        self.timer_display.setAlignment(Qt.AlignCenter)
        timer_font = QFont()
        timer_font.setPointSize(11)
        timer_font.setBold(True)
        self.timer_display.setFont(timer_font)
        self.timer_display.setMinimumHeight(30)

        layout.addWidget(self.timer_display, stretch=2)

        # Monthly Overview button
        self.report_btn = QPushButton("📊")
        self.report_btn.setFixedSize(30, 30)
        self.report_btn.clicked.connect(self.show_history.emit)
        self.report_btn.setCursor(Qt.PointingHandCursor)
        self.report_btn.setToolTip(tr("main.history"))
        layout.addWidget(self.report_btn)

        # Settings button
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.clicked.connect(self._open_settings)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setToolTip(tr("main.settings"))
        layout.addWidget(self.settings_btn)

        # Video tutorial button (Help)
        self.video_btn = QPushButton("?")
        self.video_btn.setFixedSize(30, 30)
        self.video_btn.clicked.connect(self._show_video_tutorial)
        self.video_btn.setCursor(Qt.PointingHandCursor)
        self.video_btn.setToolTip(tr("main.video_tutorial"))
        layout.addWidget(self.video_btn)

        # Minimize button
        self.minimize_button = QPushButton("▼")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.clicked.connect(self.hide)
        self.minimize_button.setToolTip(tr("tray.show_window"))  # Reuse 'Show Window' or add 'Minimize' key if needed
        layout.addWidget(self.minimize_button)

        # Make window compact with rounded appearance
        self.setFixedHeight(50)
        self.setMinimumWidth(450)

        # Apply element-specific styles
        self._apply_element_styles()

    def _apply_widget_theme(self):
        """Apply theme to the central widget"""
        colors = self._get_theme_colors()
        self.central_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {colors['bg']};
                border-radius: 15px;
                border: 1px solid {colors['border']};
            }}
            QToolTip {{
                background-color: {colors['tooltip_bg']};
                color: white;
                border: 1px solid {colors['tooltip_border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)

    def _apply_element_styles(self):
        """Apply theme-aware styles to individual elements"""
        colors = self._get_theme_colors()

        # Task input
        self.task_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: transparent;
                border: none;
                padding: 5px;
                color: {colors['text']};
            }}
            QLineEdit:focus {{
                color: {colors['text_focus']};
            }}
        """)

        # Play button (green for play)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #4CAF50;
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: rgba(76, 175, 80, 0.1);
            }}
        """)

        # Separator
        self.separator.setStyleSheet(f"color: {colors['separator']}; font-size: 14px;")

        # Timer display
        self.timer_display.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: {colors['timer']};
                padding: 5px;
            }}
        """)

        # Report button
        self.report_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                font-size: 16px;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: {colors['hover_bg']};
            }}
        """)

        # Settings button
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {colors['icon']};
                font-size: 18px;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: {colors['hover_bg']};
                color: {colors['icon_hover']};
            }}
        """)

        # Video tutorial button
        self.video_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {colors['icon']};
                font-size: 16px;
                font-weight: bold;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: {colors['hover_bg']};
                color: {colors['icon_hover']};
            }}
        """)

        # Minimize button
        self.minimize_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {colors['icon']};
                font-size: 20px;
                font-weight: bold;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: {colors['hover_bg']};
                color: {colors['icon_hover']};
            }}
        """)

    def update_theme(self, theme: str = None):
        """Update the widget theme (call when application theme changes)

        Args:
            theme: The theme to apply ('auto', 'dark', 'light'). If None, uses current theme.
        """
        if theme is not None:
            self._current_theme = theme
        self._apply_widget_theme()
        self._apply_element_styles()
        # Re-apply toggle button style based on current state
        if self.timer_service.is_tracking():
            self._apply_pause_button_style()
        else:
            self._apply_play_button_style()

    def _apply_play_button_style(self):
        """Apply play button style (green)"""
        colors = self._get_theme_colors()
        self.toggle_btn.setText("▶")
        self.toggle_btn.setToolTip(tr("main.start"))
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: #4CAF50;
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: rgba(76, 175, 80, 0.1);
            }}
        """)

    def _apply_pause_button_style(self):
        """Apply pause button style (orange)"""
        self.toggle_btn.setText("⏸")
        self.toggle_btn.setToolTip(tr("main.stop"))
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #FF9800;
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(255, 152, 0, 0.1);
            }
        """)

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

    def _show_video_tutorial(self) -> None:
        """Open the video tutorial in an internal player dialog with controls."""
        video_path = get_resource_path("docs/tutorial/video/TimeTracker_VideoTutorial.mp4")
        if not video_path.exists():
            QMessageBox.warning(
                self,
                tr("error"),
                tr("main.video_missing").format(path=video_path),
            )
            return

        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtMultimediaWidgets import QVideoWidget
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("error"),
                tr("main.video_unavailable").format(error=e),
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("main.video_title"))
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        layout = QVBoxLayout(dialog)

        # Video display widget
        video_widget = QVideoWidget(dialog)
        layout.addWidget(video_widget, stretch=1)

        # Controls layout
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 5, 10, 10)

        # Play/Pause button
        play_pause_btn = QPushButton("⏸")
        play_pause_btn.setFixedSize(40, 30)
        play_pause_btn.setCursor(Qt.PointingHandCursor)
        play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #666;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(100, 100, 100, 0.3);
            }
        """)
        controls_layout.addWidget(play_pause_btn)

        # Timeline slider
        timeline_slider = QSlider(Qt.Horizontal)
        timeline_slider.setRange(0, 0)
        timeline_slider.setCursor(Qt.PointingHandCursor)
        timeline_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #444;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -4px 0;
                background: #1976d2;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #2196f3;
            }
            QSlider::sub-page:horizontal {
                background: #1976d2;
                border-radius: 3px;
            }
        """)
        controls_layout.addWidget(timeline_slider, stretch=1)

        # Time label (current / total)
        time_label = QLabel("00:00 / 00:00")
        time_label.setStyleSheet("font-size: 12px; color: #888; margin-left: 10px;")
        controls_layout.addWidget(time_label)

        layout.addLayout(controls_layout)

        # Media player setup
        player = QMediaPlayer(dialog)
        audio_output = QAudioOutput(dialog)
        player.setAudioOutput(audio_output)
        player.setVideoOutput(video_widget)
        player.setSource(QUrl.fromLocalFile(str(video_path)))

        # State tracking for slider dragging
        is_slider_pressed = [False]

        def _format_time(ms: int) -> str:
            """Format milliseconds to MM:SS."""
            total_seconds = ms // 1000
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"

        def _on_duration_changed(duration: int) -> None:
            timeline_slider.setRange(0, duration)
            time_label.setText(f"00:00 / {_format_time(duration)}")

        def _on_position_changed(position: int) -> None:
            if not is_slider_pressed[0]:
                timeline_slider.setValue(position)
            duration = player.duration()
            time_label.setText(f"{_format_time(position)} / {_format_time(duration)}")

        def _on_slider_pressed() -> None:
            is_slider_pressed[0] = True

        def _on_slider_released() -> None:
            is_slider_pressed[0] = False
            player.setPosition(timeline_slider.value())

        def _on_slider_moved(position: int) -> None:
            duration = player.duration()
            time_label.setText(f"{_format_time(position)} / {_format_time(duration)}")

        def _toggle_play_pause() -> None:
            if player.playbackState() == QMediaPlayer.PlayingState:
                player.pause()
                play_pause_btn.setText("▶")
            else:
                player.play()
                play_pause_btn.setText("⏸")

        def _on_playback_state_changed(state) -> None:
            if state == QMediaPlayer.PlayingState:
                play_pause_btn.setText("⏸")
            else:
                play_pause_btn.setText("▶")

        def _handle_video_error(*_args) -> None:
            QMessageBox.warning(self, tr("error"), tr("main.video_playback_error"))

        # Connect signals
        player.durationChanged.connect(_on_duration_changed)
        player.positionChanged.connect(_on_position_changed)
        player.playbackStateChanged.connect(_on_playback_state_changed)
        player.errorOccurred.connect(_handle_video_error)

        timeline_slider.sliderPressed.connect(_on_slider_pressed)
        timeline_slider.sliderReleased.connect(_on_slider_released)
        timeline_slider.sliderMoved.connect(_on_slider_moved)

        play_pause_btn.clicked.connect(_toggle_play_pause)

        dialog.finished.connect(player.stop)

        dialog.resize(900, 560)
        player.play()
        dialog.exec()

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

    task_created = Signal(Task)  # Signal emitted when a new task is created

    async def _start_task_by_name(self, task_name: str):
        """Find or create task and start tracking"""
        # Search for existing active task
        task = next((t for t in self.tasks if t.name.lower() == task_name.lower()), None)
        
        if task:
            await self.timer_service.start_task(task.id)
        else:
            # Check for archived task or create new
            try:
                task_repo = TaskRepository()
                # Check DB for task (including archived)
                existing = await task_repo.get_by_name(task_name, include_archived=True)
                
                created_task = None
                
                if existing and not existing.is_active:
                    # Found archived task -> Ask to restore
                    reply = QMessageBox.question(
                        self, 
                        tr("task.restore_title"),
                        tr("task.restore_message").format(name=existing.name), 
                        QMessageBox.Yes | QMessageBox.No, 
                        QMessageBox.Yes
                    )
                    
                    if reply == QMessageBox.Yes:
                        await task_repo.unarchive(existing.id)
                        existing.is_active = True
                        existing.archived_at = None
                        created_task = existing
                    else:
                        # User cancelled restoration
                        return
                        
                elif existing:
                    # Found active task that wasn't in local list (rare sync issue?)
                    created_task = existing
                else:
                    # Create entirely new task
                    new_task = Task(name=task_name)
                    created_task = await task_repo.create(new_task)
                
                # Add to local list and start
                if created_task:
                    # Avoid duplicates in local list
                    if not any(t.id == created_task.id for t in self.tasks):
                        self.tasks.append(created_task)
                        self._update_completer()
                        self.task_created.emit(created_task)
                    
                    await self.timer_service.start_task(created_task.id)
                    
            except Exception as e:
                print(f"Error creating/restoring task: {e}")
                # Re-raise to show generic error if needed, but logging is safer for UI not to crash loop
                QMessageBox.warning(self, tr("error"), f"Failed to start task: {e}")

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
        self._apply_pause_button_style()

    def _on_task_stopped(self, task_id: int, total_seconds: int):
        """Update UI when task stops"""
        self.task_input.clear()
        self.task_input.setPlaceholderText(tr("main.task_placeholder"))
        self.timer_display.setText("00:00:00")

        # Update styling for Play state
        self._apply_play_button_style()

    def refresh_tasks(self, tasks: List[Task]):
        """Refresh the task list (called when tasks are reloaded)"""
        self.tasks = tasks
        self._update_completer()

    def _open_settings(self):
        """Open the Settings dialog"""
        from app.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        # Connect theme change signal to update this window and apply theme globally
        dialog.theme_changed.connect(self._on_theme_changed)
        dialog.exec()

    def _on_theme_changed(self, theme: str):
        """Handle theme change from settings dialog"""
        import qdarktheme
        # Apply the theme globally
        if theme == "auto":
            qdarktheme.setup_theme("auto")
        elif theme == "dark":
            qdarktheme.setup_theme("dark")
        else:
            qdarktheme.setup_theme("light")
        # Update this window's custom styling with the explicit theme
        self.update_theme(theme)

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
            stop_action = QAction(tr("main.stop"), self)
            stop_action.triggered.connect(self._stop_current_task)
            menu.addAction(stop_action)

            menu.addSeparator()

        history_action = QAction(tr("main.history"), self)
        history_action.triggered.connect(self.show_history.emit)
        menu.addAction(history_action)

        menu.addSeparator()

        hide_action = QAction(tr("tray.show_window"), self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)

        quit_action = QAction(tr("tray.quit"), self)
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
        event.ignore()
        self.hide()
        self.closed.emit()

    def changeEvent(self, event):
        """Handle theme/palette changes"""
        if event.type() == QEvent.PaletteChange:
            self.update_theme()
        super().changeEvent(event)

    def retranslate_ui(self):
        """Update strings when language changes"""
        self.setWindowTitle(tr("main.title"))
        self.task_input.setPlaceholderText(tr("main.task_placeholder"))

        if self.timer_service.is_tracking():
            self.toggle_btn.setToolTip(tr("main.stop"))
        else:
            self.toggle_btn.setToolTip(tr("main.start"))

        self.report_btn.setToolTip(tr("main.history"))
        self.settings_btn.setToolTip(tr("main.settings"))
        self.video_btn.setToolTip(tr("main.video_tutorial"))
        self.minimize_button.setToolTip(tr("tray.show_window"))

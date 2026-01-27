import asyncio
from datetime import datetime, timedelta
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, QTableWidget, 
    QTableWidgetItem, QPushButton, QLabel, QHeaderView, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QPalette, QAction

from app.domain.models import Task, TimeEntry
from app.infra.repository import TaskRepository, TimeEntryRepository
from app.ui.dialogs import ManualEntryDialog


class HistoryWindow(QWidget):
    """
    Window to view daily time entries and add manual entries.
    """
    
    def __init__(self, loop=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History & Daily Log")
        self.resize(800, 600)
        
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

            /* Table */
            QTableWidget {
                background-color: #ffffff;
                color: #333;
                gridline-color: #e0e0e0;
                border: 1px solid #e0e0e0;
                selection-background-color: #e3f2fd;
                selection-color: #000;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333;
                padding: 5px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
            }
            QTableCornerButton::section {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
            }
            
            /* Calendar */
            QCalendarWidget QWidget { 
                alternate-background-color: #f9f9f9; 
            }
            QCalendarWidget QToolButton {
                color: #333;
                icon-size: 20px;
                background-color: transparent;
            }
            QCalendarWidget QMenu {
                background-color: #fff;
                color: #333;
            }
            QCalendarWidget QSpinBox {
                color: #333;
                background-color: #fff;
                selection-background-color: #1976d2;
                selection-color: #fff;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #333;
                background-color: #fff;
                selection-background-color: #ff9800; /* Vibrant Orange for Pop */
                selection-color: #fff;
                outline: 0;
            }
            QCalendarWidget QAbstractItemView::item:selected {
                background-color: #ff9800;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #f57c00;
            }
            QCalendarWidget QAbstractItemView::item:hover {
                background-color: #e0e0e0;
                color: #000;
            }
        """)

        # Force Light Palette
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
        light_palette.setColor(QPalette.Highlight, QColor(25, 118, 210))
        light_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(light_palette)
        
        self.loop = loop or asyncio.get_event_loop()
        self.entry_repo = TimeEntryRepository()
        self.task_repo = TaskRepository()
        
        self.tasks: List[Task] = []
        self.current_entries: List[TimeEntry] = []
        
        self._setup_ui()
        self._load_tasks()
        
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left Panel: Calendar
        left_layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._on_date_selected)
        left_layout.addWidget(self.calendar)
        
        # Summary for selected day
        self.summary_header = QLabel("Daily Summary")
        self.summary_header.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;")
        left_layout.addWidget(self.summary_header)
        
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Task", "Duration"])
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setSelectionMode(QTableWidget.NoSelection)
        self.summary_table.setFocusPolicy(Qt.NoFocus)
        
        # Header setup
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        left_layout.addWidget(self.summary_table)
        
        # Total Label
        self.total_label = QLabel("Total: 00:00")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px; color: #1976d2;")
        self.total_label.setAlignment(Qt.AlignRight)
        left_layout.addWidget(self.total_label)
        
        # left_layout.addStretch() # Removed stretch to let table expand, or keep it if table is small?
        # Better to have table take available space or fixed? 
        # Let's simple use weight.
        
        layout.addLayout(left_layout, stretch=1)
        
        # Right Panel: Entries Table
        right_layout = QVBoxLayout()
        
        # Title for the table
        self.date_label = QLabel(QDate.currentDate().toString("dddd, MMMM d, yyyy"))
        self.date_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        right_layout.addWidget(self.date_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Task", "Start", "End", "Duration", "Notes"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Configure header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch) # Task name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Start
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # End
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Duration
        header.setSectionResizeMode(4, QHeaderView.Stretch) # Notes
        
        right_layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Manual Entry")
        self.add_btn.clicked.connect(self._open_manual_entry)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)
        
        right_layout.addLayout(btn_layout)
        layout.addLayout(right_layout, stretch=3) # Make right side wider
        
    def _show_context_menu(self, pos):
        """Show context menu for table"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
            
        menu = QMenu(self)
        edit_action = QAction("Edit", self)
        delete_action = QAction("Delete", self)
        
        edit_action.triggered.connect(self._edit_current_entry)
        delete_action.triggered.connect(self._delete_current_entry)
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(self.table.mapToGlobal(pos))
        
    def _edit_current_entry(self):
        """Edit the currently selected entry"""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_entries):
            return
            
        entry = self.current_entries[row]
        
        dialog = ManualEntryDialog(self.tasks, self)
        dialog.set_data(entry)
        
        if dialog.exec():
            data = dialog.get_data()
            try:
                self.loop.run_until_complete(self._update_entry(entry, data))
                self._on_date_selected() # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update entry: {e}")

    def _delete_current_entry(self):
        """Delete the currently selected entry"""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.current_entries):
            return
            
        entry = self.current_entries[row]
        
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this entry?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.loop.run_until_complete(self.entry_repo.delete(entry.id))
                self._on_date_selected() # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete entry: {e}")

    def _load_tasks(self):
        """Load tasks for sorting/displaying and for the manual entry dialog"""
        try:
            self.loop.run_until_complete(self._fetch_tasks())
            # After tasks are loaded, load entries for today
            self._on_date_selected()
        except Exception as e:
            print(f"Error loading tasks: {e}")
            
    async def _fetch_tasks(self):
        self.tasks = await self.task_repo.get_all_active()
        
    def _on_date_selected(self):
        """Handle date selection from calendar"""
        qdate = self.calendar.selectedDate()
        self.date_label.setText(qdate.toString("dddd, MMMM d, yyyy"))
        
        # Convert QDate to Python date
        py_date = qdate.toPython()
        start_of_day = datetime.combine(py_date, datetime.min.time())
        end_of_day = datetime.combine(py_date, datetime.max.time())
        
        # Fetch entries
        try:
            entries = self.loop.run_until_complete(self._fetch_entries(start_of_day, end_of_day))
            self.current_entries = entries
            self._populate_tables(entries)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load entries: {e}")
            
    async def _fetch_entries(self, start, end):
        all_entries = []
        for task in self.tasks:
            entries = await self.entry_repo.get_overlapping(task.id, start, end)
            all_entries.extend(entries)
            
        # Sort by start time
        all_entries.sort(key=lambda x: x.start_time)
        return all_entries

    def _populate_tables(self, entries: List[TimeEntry]):
        # 1. Populate Detailed Table
        self.table.setRowCount(len(entries))
        day_total_seconds = 0
        task_totals = {}
        
        for row, entry in enumerate(entries):
            # Task Name
            task_name = next((t.name for t in self.tasks if t.id == entry.task_id), "Unknown")
            self.table.setItem(row, 0, QTableWidgetItem(task_name))
            
            # Start
            self.table.setItem(row, 1, QTableWidgetItem(entry.start_time.strftime("%H:%M")))
            
            # End
            end_str = entry.end_time.strftime("%H:%M") if entry.end_time else "Active"
            self.table.setItem(row, 2, QTableWidgetItem(end_str))
            
            # Duration
            # If active, duration might be dynamic, but here we show whatever is in DB or calculated up to now
            # For active tasks, duration in DB might be 0 until stopped.
            # Ideally we should calculate it live or show "Running"
            if entry.end_time is None:
                # Calculate duration up to now
                duration = int((datetime.now() - entry.start_time).total_seconds())
            else:
                duration = entry.duration_seconds
                
            day_total_seconds += duration
            
            # Accumulate for summary
            task_totals[task_name] = task_totals.get(task_name, 0) + duration
            
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            dur_str = f"{hours:02d}:{minutes:02d}"
            self.table.setItem(row, 3, QTableWidgetItem(dur_str))
            
            # Notes
            self.table.setItem(row, 4, QTableWidgetItem(entry.notes or ""))
            
        # 2. Populate Summary Table
        sorted_totals = sorted(task_totals.items(), key=lambda x: x[1], reverse=True)
        self.summary_table.setRowCount(len(sorted_totals))
        
        for row, (name, duration) in enumerate(sorted_totals):
            self.summary_table.setItem(row, 0, QTableWidgetItem(name))
            
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            dur_str = f"{hours:02d}:{minutes:02d}"
            
            self.summary_table.setItem(row, 1, QTableWidgetItem(dur_str))
            
        # 3. Update Total Label
        hours, remainder = divmod(day_total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.total_label.setText(f"Total: {hours:02d}:{minutes:02d}")
        
    def _open_manual_entry(self):
        """Open the dialog to add a manual entry"""
        dialog = ManualEntryDialog(self.tasks, self)
        
        # Set date to currently selected date
        dialog.date_edit.setDate(self.calendar.selectedDate())
        
        if dialog.exec():
            data = dialog.get_data()
            try:
                self.loop.run_until_complete(self._create_manual_entry(data))
                self._on_date_selected() # Refresh
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save entry: {e}")
                
    async def _create_manual_entry(self, data):
        task_id = data['task_id']
        
        # If new task name (task_id is None), create task first
        if task_id is None:
            # Check if it actually exists by name to avoid duplicates
            existing = next((t for t in self.tasks if t.name.lower() == data['task_name'].lower()), None)
            if existing:
                task_id = existing.id
            else:
                new_task = Task(name=data['task_name'])
                created_task = await self.task_repo.create(new_task)
                self.tasks.append(created_task)
                task_id = created_task.id
        
        # Calculate duration
        start = data['start_time']
        end = data['end_time']
        
        # Check Overlap
        if await self.entry_repo.has_overlap(start, end):
            raise ValueError("Time entry overlaps with an existing entry.")
            
        duration = int((end - start).total_seconds())
        
        if duration < 0:
            duration = 0
            
        entry = TimeEntry(
            task_id=task_id,
            start_time=start,
            end_time=end,
            duration_seconds=duration,
            notes=data['notes']
        )
        
        await self.entry_repo.create(entry)

    async def _update_entry(self, entry: TimeEntry, data: dict):
        """Update existing entry with new data"""
        task_id = data['task_id']
        
        # Handle new task creation if needed
        if task_id is None:
             existing = next((t for t in self.tasks if t.name.lower() == data['task_name'].lower()), None)
             if existing:
                 task_id = existing.id
             else:
                 new_task = Task(name=data['task_name'])
                 created_task = await self.task_repo.create(new_task)
                 self.tasks.append(created_task)
                 task_id = created_task.id
        
        start = data['start_time']
        end = data['end_time']
        
        # Check Overlap (Ignore current entry ID)
        if await self.entry_repo.has_overlap(start, end, ignore_id=entry.id):
            raise ValueError("Time entry overlaps with an existing entry.")
            
        duration = int((end - start).total_seconds())
        if duration < 0:
            duration = 0
            
        # Update fields
        entry.task_id = task_id
        entry.start_time = start
        entry.end_time = end
        entry.duration_seconds = duration
        entry.notes = data['notes']
        
        await self.entry_repo.update(entry)

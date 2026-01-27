"""
Dialogs for handling interruptions and manual entry.
"""

from typing import List, Optional
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
    QComboBox, QDateEdit, QTimeEdit, QTextEdit, QFormLayout, 
    QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt, QDate, QTime

from app.domain.models import Task


class InterruptionDialog(QDialog):
    """
    The popup asking the user what to do with time elapsed while away.
    """
    
    def __init__(self, elapsed_minutes: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome Back")
        self.choice = "ignore"  # default
        self.setModal(True)
        
        # Setup UI
        layout = QVBoxLayout()
        
        # Message
        message_label = QLabel(f"You were away for {elapsed_minutes:.1f} minutes.")
        message_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(message_label)
        
        question_label = QLabel("How should we handle this time?")
        layout.addWidget(question_label)
        
        layout.addSpacing(20)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_break = QPushButton("It was a Break\n(Ignore time)")
        btn_break.setMinimumHeight(60)
        btn_break.clicked.connect(lambda: self.set_choice("ignore"))
        
        btn_work = QPushButton("I was working\n(Add to current task)")
        btn_work.setMinimumHeight(60)
        btn_work.clicked.connect(lambda: self.set_choice("track"))
        
        btn_layout.addWidget(btn_break)
        btn_layout.addWidget(btn_work)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.setMinimumWidth(400)
    
    def set_choice(self, choice: str):
        """Set the user's choice and close dialog"""
        self.choice = choice
        self.accept()


class ManualEntryDialog(QDialog):
    """
    Dialog for manually adding a past time entry.
    """
    
    def __init__(self, tasks: List[Task], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Manual Entry")
        self.tasks = tasks
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Task Selection
        self.task_combo = QComboBox()
        self.task_combo.setEditable(True)  # Allow creating new tasks
        for task in self.tasks:
            self.task_combo.addItem(task.name, task.id)
        form_layout.addRow("Task:", self.task_combo)
        
        # Date
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        form_layout.addRow("Date:", self.date_edit)
        
        # Start Time
        self.start_time = QTimeEdit(QTime.currentTime().addSecs(-3600)) # Default 1 hr ago
        form_layout.addRow("Start Time:", self.start_time)
        
        # End Time
        self.end_time = QTimeEdit(QTime.currentTime())
        form_layout.addRow("End Time:", self.end_time)
        
        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes...")
        self.notes_edit.setMaximumHeight(80)
        form_layout.addRow("Notes:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _validate_and_accept(self):
        """Validate input before accepting"""
        start = self.start_time.time()
        end = self.end_time.time()
        
        if start >= end:
            QMessageBox.warning(self, "Invalid Time", "End time must be after start time.")
            return
            
        self.accept()
    
    def get_data(self):
        """Return the entered data"""
        task_name = self.task_combo.currentText()
        # Check if ID is in user data, otherwise it's a new task (None)
        task_id = self.task_combo.currentData() 
        
        date = self.date_edit.date().toPython()
        start_time = self.start_time.time().toPython()
        end_time = self.end_time.time().toPython()
        
        start_dt = datetime.combine(date, start_time)
        end_dt = datetime.combine(date, end_time)
        
        return {
            "task_name": task_name,
            "task_id": task_id,
            "start_time": start_dt,
            "end_time": end_dt,
            "notes": self.notes_edit.toPlainText()
        }

"""
Dialog for handling interruptions (lock/unlock events).

Asks the user if time during absence should be tracked or ignored.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt


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

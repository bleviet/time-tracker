from typing import List
import asyncio
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QHBoxLayout, QMessageBox, QHeaderView
)
from app.domain.models import Task
from app.infra.repository import TaskRepository, AccountingRepository
from app.ui.dialogs import TaskEditDialog

class TaskManagementDialog(QDialog):
    """
    Manage Tasks (List, Edit, Archive).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tasks")
        self.resize(600, 400)
        
        self.loop = asyncio.get_event_loop()
        self.repo = TaskRepository()
        self.acc_repo = AccountingRepository()
        
        self.tasks: List[Task] = []
        
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Accounting", "Active"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit Task")
        edit_btn.clicked.connect(self._edit_task)
        
        # archive_btn = QPushButton("Archive Task")
        # archive_btn.clicked.connect(self._archive_task)
        
        btn_layout.addWidget(edit_btn)
        # btn_layout.addWidget(archive_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def _load_data(self):
        try:
            self.tasks = self.loop.run_until_complete(self.repo.get_all_active())
            # We also need accounting names
            accs = self.loop.run_until_complete(self.acc_repo.get_all_active())
            self.acc_map = {a.id: a.name for a in accs}
            
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tasks: {e}")
            
    def _refresh_table(self):
        self.table.setRowCount(len(self.tasks))
        for row, task in enumerate(self.tasks):
            self.table.setItem(row, 0, QTableWidgetItem(task.name))
            
            acc_name = self.acc_map.get(task.accounting_id, "-") if task.accounting_id else "-"
            self.table.setItem(row, 1, QTableWidgetItem(acc_name))
            
            status = "Active" if task.is_active else "Archived"
            self.table.setItem(row, 2, QTableWidgetItem(status))
            
    def _edit_task(self):
        row = self.table.currentRow()
        if row < 0:
            return
            
        task = self.tasks[row]
        dlg = TaskEditDialog(task, self)
        if dlg.exec():
            updated_task = dlg.get_data()
            try:
                self.loop.run_until_complete(self.repo.update(updated_task))
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update task: {e}")

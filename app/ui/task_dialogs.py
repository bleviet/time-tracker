import asyncio
from typing import List
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QHBoxLayout, QMessageBox, QHeaderView,
    QMenu, QComboBox, QWidget
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from app.domain.models import Task, Accounting
from app.infra.repository import TaskRepository, AccountingRepository
from app.i18n import tr

class TaskManagementDialog(QDialog):
    """
    Manage Tasks (List, Inline Edit, Archive).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("task_mgmt.title"))
        self.resize(800, 500)
        
        self.loop = asyncio.get_event_loop()
        self.repo = TaskRepository()
        self.acc_repo = AccountingRepository()
        
        self.tasks: List[Task] = []
        self.accounting_profiles: List[Accounting] = []
        
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            tr("task_mgmt.header_name"), 
            tr("task_mgmt.header_accounting"), 
            tr("task_mgmt.header_active")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Connect Name edit
        self.table.itemChanged.connect(self._on_item_changed)
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton(tr("action.add"))
        add_btn.clicked.connect(self._add_task)
        
        # edit_btn = QPushButton(tr("task_mgmt.btn_edit"))
        # edit_btn.clicked.connect(self._edit_task)
        
        btn_layout.addWidget(add_btn)
        # btn_layout.addWidget(edit_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def _load_data(self):
        try:
            # Load Accounting Profiles
            self.accounting_profiles = self.loop.run_until_complete(self.acc_repo.get_all_active())
            
            # Load Tasks
            self.tasks = self.loop.run_until_complete(self.repo.get_all_active())
            
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, tr("error"), tr("task_mgmt.load_error").format(error=e))
            
    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.tasks))
        
        for row, task in enumerate(self.tasks):
            # Name (Editable Item)
            name_item = QTableWidgetItem(task.name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            
            # Accounting (ComboBox)
            acc_combo = QComboBox()
            acc_combo.addItem(tr("task_edit.none"), None)
            current_idx = 0
            for i, acc in enumerate(self.accounting_profiles):
                acc_combo.addItem(acc.name, acc.id)
                if task.accounting_id == acc.id:
                    current_idx = i + 1
            acc_combo.setCurrentIndex(current_idx)
            
            # Connect signal using closure to capture row (careful with loop variable)
            acc_combo.currentIndexChanged.connect(lambda idx, r=row: self._on_accounting_changed(r))
            self.table.setCellWidget(row, 1, acc_combo)
            
            # Active (ComboBox)
            status_combo = QComboBox()
            # Items: "Active" (True), "Archived" (False)
            status_combo.addItem(tr("task_mgmt.active"), True)
            status_combo.addItem(tr("task_mgmt.archived"), False)
            status_combo.setCurrentIndex(0 if task.is_active else 1)
            
            status_combo.currentIndexChanged.connect(lambda idx, r=row: self._on_status_changed(r))
            self.table.setCellWidget(row, 2, status_combo)
            
        self.table.blockSignals(False)
            
    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle Name changes"""
        row = item.row()
        if row < 0 or row >= len(self.tasks):
            return
            
        # Only column 0 is item-based
        if item.column() != 0:
            return
            
        task = self.tasks[row]
        new_name = item.text().strip()
        
        if not new_name:
            # Don't save empty names
            return
            
        task.name = new_name
        self._update_task(task)

    def _on_accounting_changed(self, row: int):
        if row < 0 or row >= len(self.tasks):
            return
            
        combo: QComboBox = self.table.cellWidget(row, 1)
        if not combo:
            return
            
        task = self.tasks[row]
        new_acc_id = combo.currentData()
        
        if task.accounting_id != new_acc_id:
            task.accounting_id = new_acc_id
            self._update_task(task)
            
    def _on_status_changed(self, row: int):
        if row < 0 or row >= len(self.tasks):
            return
            
        combo: QComboBox = self.table.cellWidget(row, 2)
        if not combo:
            return
            
        task = self.tasks[row]
        is_active = combo.currentData()
        
        if task.is_active != is_active:
            task.is_active = is_active
            if not is_active:
                task.archived_at = datetime.now()
            else:
                task.archived_at = None
                
            self._update_task(task)

    def _update_task(self, task: Task):
        try:
            self.loop.run_until_complete(self.repo.update(task))
        except Exception as e:
            self.table.blockSignals(True)
            QMessageBox.critical(self, tr("error"), tr("task_mgmt.update_error").format(error=e))
            self.table.blockSignals(False)
            
    def _add_task(self):
        new_task = Task(name="New Task")
        try:
            created = self.loop.run_until_complete(self.repo.create(new_task))
            self.tasks.append(created)
            
            # Refresh to show new row
            self._refresh_table()
            
            # Select and edit
            new_row = len(self.tasks) - 1
            self.table.selectRow(new_row)
            self.table.editItem(self.table.item(new_row, 0))
            
        except Exception as e:
            QMessageBox.critical(self, tr("error"), "Failed to create task: {error}".format(error=e))

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        
        archive_action = QAction(tr("action.archive"), self)
        archive_action.triggered.connect(self._archive_task)
        menu.addAction(archive_action)
        
        menu.exec(self.table.mapToGlobal(pos))
            
    def _archive_task(self):
        row = self.table.currentRow()
        if row < 0:
            return
            
        task = self.tasks[row]
        reply = QMessageBox.question(
            self, tr("task_mgmt.confirm_archive_title"),
            tr("task_mgmt.confirm_archive_msg").format(name=task.name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Just set status to archive and update UI, reuse change logic
            task.is_active = False
            task.archived_at = datetime.now()
            self._update_task(task)
            self._refresh_table() # To update dropdown state

import asyncio
from typing import List, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QInputDialog, QFormLayout, 
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QLineEdit
)
from PySide6.QtCore import Qt

from app.domain.models import Accounting, UserPreferences
from app.infra.repository import AccountingRepository, UserRepository

class AccountingSettingsDialog(QDialog):
    """
    Dialog to configure dynamic accounting columns.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Accounting Settings")
        self.resize(400, 300)
        self.repo = UserRepository()
        self.preferences = None
        self.columns = []
        
        # Load current prefs safely (run in loop? or just init generic)
        # For simplicity, we assume we might need asyncio loop handling
        self.loop = asyncio.get_event_loop()
        
        self._setup_ui()
        self._load_columns()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Define the columns for your accounting structure (e.g. 'Cost Center', 'Project ID')."))
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Column")
        self.add_btn.clicked.connect(self._add_column)
        
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._remove_column)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)
        
        save_btn = QPushButton("Save && Close")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)
        
    def _load_columns(self):
        try:
            self.preferences = self.loop.run_until_complete(self.repo.get_preferences())
            self.columns = list(self.preferences.accounting_columns)
            self._refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load settings: {e}")
            
    def _refresh_list(self):
        self.list_widget.clear()
        for col in self.columns:
            self.list_widget.addItem(col)
            
    def _add_column(self):
        text, ok = QInputDialog.getText(self, "New Column", "Column Name:")
        if ok and text:
            if text in self.columns:
                QMessageBox.warning(self, "Error", "Column already exists.")
                return
            self.columns.append(text)
            self._refresh_list()
            
    def _remove_column(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            del self.columns[row]
            self._refresh_list()
            
    def _save(self):
        if self.preferences:
            self.preferences.accounting_columns = self.columns
            try:
                self.loop.run_until_complete(self.repo.update_preferences(self.preferences))
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")


class AccountingEditDialog(QDialog):
    """
    Dynamic form to Create/Edit an Accounting Profile.
    """
    def __init__(self, columns: List[str], accounting: Accounting = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Accounting Profile" if accounting else "New Accounting Profile")
        self.columns = columns
        self.accounting = accounting
        self.inputs = {}
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Name
        self.name_input = QLineEdit()
        if self.accounting:
            self.name_input.setText(self.accounting.name)
        form.addRow("Name (Primary ID):", self.name_input)
        
        # Dynamic Columns
        current_attrs = self.accounting.attributes if self.accounting else {}
        
        for col in self.columns:
            inp = QLineEdit()
            inp.setText(current_attrs.get(col, ""))
            self.inputs[col] = inp
            form.addRow(f"{col}:", inp)
            
        layout.addLayout(form)
        
        # Buttons
        btns = QHBoxLayout()
        ok_btn = QPushButton("Save")
        ok_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required.")
            return
            
        attributes = {col: inp.text().strip() for col, inp in self.inputs.items()}
        
        if self.accounting:
            self.accounting.name = name
            self.accounting.attributes = attributes
        else:
            self.accounting = Accounting(name=name, attributes=attributes)
            
        self.accept()
        
    def get_data(self) -> Accounting:
        return self.accounting


class AccountingManagementDialog(QDialog):
    """
    Manage Accounting Profiles (List, Add, Edit, Delete).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Accounting")
        self.resize(600, 400)
        
        self.loop = asyncio.get_event_loop()
        self.repo = AccountingRepository()
        self.user_repo = UserRepository()
        
        self.profiles: List[Accounting] = []
        self.columns: List[str] = []
        
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Profile")
        add_btn.clicked.connect(self._add_profile)
        
        edit_btn = QPushButton("Edit Profile")
        edit_btn.clicked.connect(self._edit_profile)
        
        del_btn = QPushButton("Delete Profile")
        del_btn.clicked.connect(self._delete_profile)
        
        settings_btn = QPushButton("Column Settings")
        settings_btn.clicked.connect(self._open_settings)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(settings_btn)
        
        layout.addLayout(btn_layout)
        
    def _load_data(self):
        try:
            # Load Columns
            prefs = self.loop.run_until_complete(self.user_repo.get_preferences())
            self.columns = prefs.accounting_columns
            
            # Load Profiles
            self.profiles = self.loop.run_until_complete(self.repo.get_all_active())
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {e}")
            
    def _refresh_table(self):
        self.table.clear()
        
        headers = ["Name"] + self.columns
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.profiles))
        
        for row, profile in enumerate(self.profiles):
            self.table.setItem(row, 0, QTableWidgetItem(profile.name))
            for col_idx, col_name in enumerate(self.columns):
                val = profile.attributes.get(col_name, "")
                self.table.setItem(row, col_idx + 1, QTableWidgetItem(val))
                
    def _open_settings(self):
        dlg = AccountingSettingsDialog(self)
        if dlg.exec():
            self._load_data() # Refresh columns and table
            
    def _add_profile(self):
        dlg = AccountingEditDialog(self.columns, parent=self)
        if dlg.exec():
            profile = dlg.get_data()
            try:
                self.loop.run_until_complete(self.repo.create(profile))
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create profile: {e}")
                
    def _edit_profile(self):
        row = self.table.currentRow()
        if row < 0:
            return
        
        profile = self.profiles[row]
        dlg = AccountingEditDialog(self.columns, accounting=profile, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            try:
                self.loop.run_until_complete(self.repo.update(updated))
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update profile: {e}")
                
    def _delete_profile(self):
        row = self.table.currentRow()
        if row < 0:
            return
            
        profile = self.profiles[row]
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            f"Delete profile '{profile.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.loop.run_until_complete(self.repo.delete(profile.id))
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete profile: {e}")

import asyncio
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QInputDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from app.domain.models import Accounting
from app.infra.repository import AccountingRepository, UserRepository
from app.i18n import tr

class AccountingManagementDialog(QDialog):
    """
    Manage Accounting Profiles (List, Add, Edit, Delete).
    Supports inline editing and property management.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("acc_mgmt.title"))
        self.resize(800, 500)
        
        self.loop = asyncio.get_event_loop()
        self.repo = AccountingRepository()
        self.user_repo = UserRepository()
        
        self.profiles: List[Accounting] = []
        self.columns: List[str] = []
        
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Enable item changed signal for inline editing
        self.table.itemChanged.connect(self._on_item_changed)
        
        # Enable header context menu for removing properties
        self.table.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._show_header_context_menu)
        
        # Context Menu for Rows (Delete Profile)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton(tr("acc_mgmt.btn_add_profile"))
        add_btn.clicked.connect(self._add_profile)
        
        del_btn = QPushButton(tr("acc_mgmt.btn_del_profile"))
        del_btn.clicked.connect(self._delete_profile)
        
        add_prop_btn = QPushButton(tr("acc_mgmt.btn_add_property"))
        add_prop_btn.clicked.connect(self._add_property)

        remove_prop_btn = QPushButton(tr("acc_mgmt.btn_remove_property"))
        remove_prop_btn.clicked.connect(self._remove_property)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(add_prop_btn)
        btn_layout.addWidget(remove_prop_btn)
        
        layout.addLayout(btn_layout)
        
    def _load_data(self):
        try:
            # Load Columns
            prefs = self.loop.run_until_complete(self.user_repo.get_preferences())
            self.columns = list(prefs.accounting_columns)
            
            # Load Profiles
            self.profiles = self.loop.run_until_complete(self.repo.get_all_active())
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, tr("error"), tr("acc_mgmt.load_error").format(error=e))
            
    def _refresh_table(self):
        self.table.blockSignals(True) # Prevent saving while loading
        self.table.clear()
        
        headers = [tr("acc_mgmt.header_name")] + self.columns
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.profiles))
        
        for row, profile in enumerate(self.profiles):
            # Name Column (0)
            name_item = QTableWidgetItem(profile.name)
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            
            # Attribute Columns
            for col_idx, col_name in enumerate(self.columns):
                val = profile.attributes.get(col_name, "")
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, col_idx + 1, item)
                
        self.table.blockSignals(False)
    
    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle inline edits"""
        row = item.row()
        col = item.column()
        
        if row < 0 or row >= len(self.profiles):
            return
            
        profile = self.profiles[row]
        new_value = item.text().strip()
        
        # Determine what changed
        if col == 0:
            # Name changed
            if not new_value:
                return 
            profile.name = new_value
        else:
            # Attribute changed
            # Columns are at col-1 in attributes list
            if col - 1 < len(self.columns):
                col_name = self.columns[col - 1]
                profile.attributes[col_name] = new_value
                
        # Save to DB
        try:
            self.loop.run_until_complete(self.repo.update(profile))
        except Exception as e:
            self.table.blockSignals(True)
            QMessageBox.critical(self, tr("error"), tr("acc_mgmt.update_error").format(error=e))
            self.table.blockSignals(False)

    def _show_context_menu(self, pos):
        """Context menu for rows (Delete Profile)"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
            
        menu = QMenu(self)
        
        del_action = QAction(tr("action.delete"), self)
        del_action.triggered.connect(self._delete_profile)
        menu.addAction(del_action)
        
        menu.exec(self.table.mapToGlobal(pos))
        
    def _show_header_context_menu(self, pos):
        """Context menu for headers (Delete Property)"""
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        
        # Column 0 is Name, cannot delete
        if col <= 0:
            return
            
        # Check if it corresponds to a dynamic property
        if col - 1 < len(self.columns):
            col_name = self.columns[col - 1]
            
            menu = QMenu(self)
            # "Delete Property 'X'"
            del_action = QAction(f"{tr('action.delete')} '{col_name}'", self)
            del_action.triggered.connect(lambda: self._delete_property(col_name))
            menu.addAction(del_action)
            
            menu.exec(self.table.mapToGlobal(pos))

    def _add_profile(self):
        # Create a default profile immediately
        new_profile = Accounting(
            name="New Profile", # Default name, user should rename
            attributes={}
        )
        try:
            created = self.loop.run_until_complete(self.repo.create(new_profile))
            self.profiles.append(created)
            
            # Refresh table to show new row
            self._refresh_table()
            
            # Select and edit the new row's name
            new_row = len(self.profiles) - 1
            self.table.selectRow(new_row)
            self.table.editItem(self.table.item(new_row, 0))
            
        except Exception as e:
            QMessageBox.critical(self, tr("error"), tr("acc_mgmt.create_error").format(error=e))
            
    def _add_property(self):
        """Add a new accounting property (column)"""
        text, ok = QInputDialog.getText(self, tr("acc_settings.new_col_title"), tr("acc_settings.new_col_msg"))
        if ok and text:
            text = text.strip()
            if not text:
                return
                
            if text in self.columns:
                QMessageBox.warning(self, tr("error"), tr("acc_settings.error_exists"))
                return
            
            # Update Preferences
            try:
                prefs = self.loop.run_until_complete(self.user_repo.get_preferences())
                current_cols = list(prefs.accounting_columns)
                current_cols.append(text)
                
                prefs.accounting_columns = current_cols
                self.loop.run_until_complete(self.user_repo.update_preferences(prefs))
                
                # Reload UI
                self._load_data()
                
            except Exception as e:
                QMessageBox.critical(self, tr("error"), tr("acc_settings.save_error").format(error=e))

    def _remove_property(self):
        """Remove an accounting property (column)"""
        if not self.columns:
            QMessageBox.information(self, tr("acc_mgmt.remove_property_title"), tr("acc_mgmt.no_properties"))
            return

        col_name, ok = QInputDialog.getItem(
            self,
            tr("acc_mgmt.remove_property_title"),
            tr("acc_mgmt.remove_property_msg"),
            self.columns,
            0,
            False,
        )
        if ok and col_name:
            self._delete_property(col_name)
                
    def _delete_property(self, col_name: str):
        """Delete an accounting property (column)"""
        reply = QMessageBox.question(
            self, tr("acc_mgmt.confirm_del_title"),
            f"{tr('action.delete')} '{col_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                prefs = self.loop.run_until_complete(self.user_repo.get_preferences())
                current_cols = list(prefs.accounting_columns)
                if col_name in current_cols:
                    current_cols.remove(col_name)
                    
                prefs.accounting_columns = current_cols
                self.loop.run_until_complete(self.user_repo.update_preferences(prefs))
                
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, tr("error"), tr("acc_settings.save_error").format(error=e))
                
    def _delete_profile(self):
        row = self.table.currentRow()
        if row < 0:
            return
            
        profile = self.profiles[row]
        reply = QMessageBox.question(
            self, tr("acc_mgmt.confirm_del_title"), 
            tr("acc_mgmt.confirm_del_msg").format(name=profile.name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.loop.run_until_complete(self.repo.delete(profile.id))
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, tr("error"), tr("acc_mgmt.delete_error").format(error=e))

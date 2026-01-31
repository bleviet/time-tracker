"""
Backup Service - Handles database export and import functionality.

Architecture Decision: Why JSON for backups?
- Human-readable format for easy inspection and manual edits
- Cross-platform compatible
- Can be version-controlled if needed
- Easy to restore partial data
"""

import json
import shutil
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from app.infra.repository import TaskRepository, TimeEntryRepository, AccountingRepository, UserRepository
from app.domain.models import Task, TimeEntry, Accounting, UserPreferences

logger = logging.getLogger(__name__)


class BackupService:
    """
    Handles database backup (export) and restore (import) operations.

    Backup naming convention: timetracker_backup_YYYY-MM-DD_HHMMSS.json
    """

    BACKUP_PREFIX = "timetracker_backup_"
    BACKUP_EXTENSION = ".json"

    def __init__(self):
        self.task_repo = TaskRepository()
        self.entry_repo = TimeEntryRepository()
        self.acc_repo = AccountingRepository()
        self.user_repo = UserRepository()

    def _get_default_backup_dir(self) -> Path:
        """Get the default backup directory based on OS"""
        if os.name == 'nt':  # Windows
            base = Path(os.getenv('APPDATA')) / 'TimeTracker'
        else:  # Linux/Mac
            base = Path.home() / '.local' / 'share' / 'timetracker'

        backup_dir = base / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    def _get_backup_dir(self, custom_dir: Optional[str] = None) -> Path:
        """Get the backup directory, using custom or default"""
        if custom_dir and custom_dir.strip():
            backup_dir = Path(custom_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)
            return backup_dir
        return self._get_default_backup_dir()

    def _generate_backup_filename(self) -> str:
        """Generate a timestamped backup filename"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return f"{self.BACKUP_PREFIX}{timestamp}{self.BACKUP_EXTENSION}"

    def _parse_backup_date(self, filename: str) -> Optional[datetime]:
        """Extract datetime from backup filename"""
        try:
            # Remove prefix and extension
            date_part = filename.replace(self.BACKUP_PREFIX, "").replace(self.BACKUP_EXTENSION, "")
            return datetime.strptime(date_part, "%Y-%m-%d_%H%M%S")
        except ValueError:
            return None

    async def create_backup(self, backup_dir: Optional[str] = None) -> Path:
        """
        Create a full backup of the database.

        Args:
            backup_dir: Optional custom backup directory

        Returns:
            Path to the created backup file
        """
        backup_path = self._get_backup_dir(backup_dir)
        filename = self._generate_backup_filename()
        backup_file = backup_path / filename

        # Collect all data
        backup_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "app_name": "TimeTracker",
            "data": {
                "accounting": [],
                "tasks": [],
                "time_entries": [],
                "preferences": None
            }
        }

        # Export accounting profiles
        accounting_profiles = await self.acc_repo.get_all_active()
        for acc in accounting_profiles:
            backup_data["data"]["accounting"].append({
                "id": acc.id,
                "name": acc.name,
                "attributes": acc.attributes,
                "is_active": acc.is_active
            })

        # Export tasks
        tasks = await self.task_repo.get_all_active()
        for task in tasks:
            backup_data["data"]["tasks"].append({
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "is_active": task.is_active,
                "accounting_id": task.accounting_id
            })

        # Export time entries (all entries)
        for task in tasks:
            entries = await self.entry_repo.get_overlapping(
                task.id,
                datetime(2000, 1, 1),  # Far past
                datetime(2100, 12, 31)  # Far future
            )
            for entry in entries:
                backup_data["data"]["time_entries"].append({
                    "id": entry.id,
                    "task_id": entry.task_id,
                    "start_time": entry.start_time.isoformat(),
                    "end_time": entry.end_time.isoformat() if entry.end_time else None,
                    "duration_seconds": entry.duration_seconds,
                    "notes": entry.notes
                })

        # Export preferences
        prefs = await self.user_repo.get_preferences()
        backup_data["data"]["preferences"] = prefs.model_dump()

        # Write to file
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Backup created: {backup_file}")
        return backup_file

    async def restore_backup(self, backup_file: Path) -> Dict[str, int]:
        """
        Restore data from a backup file.

        This performs a full rollback: all existing data is wiped and replaced
        with the backup data. This ensures no duplicates and a clean restore.

        Args:
            backup_file: Path to the backup file

        Returns:
            Dictionary with counts of restored items
        """
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)

        # Validate backup format
        if "version" not in backup_data or "data" not in backup_data:
            raise ValueError("Invalid backup file format")

        # Wipe existing data (order matters due to foreign keys)
        # Delete time entries first, then tasks, then accounting
        await self.entry_repo.delete_all()
        await self.task_repo.delete_all()
        await self.acc_repo.delete_all()

        logger.info("Existing data cleared for restore")

        restored = {
            "accounting": 0,
            "tasks": 0,
            "time_entries": 0
        }

        data = backup_data["data"]

        # Map old IDs to new IDs for foreign key references
        accounting_id_map = {}  # old_id -> new_id
        task_id_map = {}  # old_id -> new_id

        # Restore accounting profiles
        for acc_data in data.get("accounting", []):
            try:
                old_id = acc_data.get("id")
                acc = Accounting(
                    name=acc_data["name"],
                    attributes=acc_data.get("attributes", {}),
                    is_active=acc_data.get("is_active", True)
                )
                created = await self.acc_repo.create(acc)
                if old_id and created.id:
                    accounting_id_map[old_id] = created.id
                restored["accounting"] += 1
            except Exception as e:
                logger.warning(f"Failed to restore accounting: {acc_data.get('name')}: {e}")

        # Restore tasks
        for task_data in data.get("tasks", []):
            try:
                old_id = task_data.get("id")
                old_acc_id = task_data.get("accounting_id")
                new_acc_id = accounting_id_map.get(old_acc_id) if old_acc_id else None
                task = Task(
                    name=task_data["name"],
                    description=task_data.get("description"),
                    is_active=task_data.get("is_active", True),
                    accounting_id=new_acc_id
                )
                created = await self.task_repo.create(task)
                if old_id and created.id:
                    task_id_map[old_id] = created.id
                restored["tasks"] += 1
            except Exception as e:
                logger.warning(f"Failed to restore task: {task_data.get('name')}: {e}")

        # Restore time entries
        for entry_data in data.get("time_entries", []):
            try:
                old_task_id = entry_data["task_id"]
                new_task_id = task_id_map.get(old_task_id)
                if not new_task_id:
                    logger.warning(f"Skipping time entry: task_id {old_task_id} not found in map")
                    continue
                entry = TimeEntry(
                    task_id=new_task_id,
                    start_time=datetime.fromisoformat(entry_data["start_time"]),
                    end_time=datetime.fromisoformat(entry_data["end_time"]) if entry_data.get("end_time") else None,
                    duration_seconds=entry_data.get("duration_seconds", 0),
                    notes=entry_data.get("notes")
                )
                await self.entry_repo.create(entry)
                restored["time_entries"] += 1
            except Exception as e:
                logger.warning(f"Failed to restore time entry: {e}")

        # Restore preferences if available
        if data.get("preferences"):
            try:
                prefs = UserPreferences(**data["preferences"])
                await self.user_repo.update_preferences(prefs)
            except Exception as e:
                logger.warning(f"Failed to restore preferences: {e}")

        logger.info(f"Backup restored: {restored}")
        return restored

    def list_backups(self, backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available backups in the backup directory.

        Returns:
            List of backup info dictionaries sorted by date (newest first)
        """
        backup_path = self._get_backup_dir(backup_dir)
        backups = []

        for file in backup_path.glob(f"{self.BACKUP_PREFIX}*{self.BACKUP_EXTENSION}"):
            backup_date = self._parse_backup_date(file.name)
            if backup_date:
                file_size = file.stat().st_size
                backups.append({
                    "filename": file.name,
                    "path": str(file),
                    "date": backup_date,
                    "size_bytes": file_size,
                    "size_human": self._format_size(file_size)
                })

        # Sort by date, newest first
        backups.sort(key=lambda x: x["date"], reverse=True)
        return backups

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def cleanup_old_backups(self, backup_dir: Optional[str] = None, keep_count: int = 5):
        """
        Remove old backups, keeping only the most recent ones.

        Args:
            backup_dir: Backup directory
            keep_count: Number of backups to keep
        """
        backups = self.list_backups(backup_dir)

        if len(backups) <= keep_count:
            return

        # Remove oldest backups
        for backup in backups[keep_count:]:
            try:
                Path(backup["path"]).unlink()
                logger.info(f"Removed old backup: {backup['filename']}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {backup['filename']}: {e}")

    def should_backup(self, prefs: UserPreferences) -> bool:
        """
        Check if a backup is due based on preferences.

        Args:
            prefs: User preferences with backup settings

        Returns:
            True if backup should be performed
        """
        if not prefs.backup_enabled:
            return False

        now = datetime.now()

        # Parse scheduled backup time
        try:
            backup_hour, backup_minute = map(int, prefs.backup_time.split(':'))
        except (ValueError, AttributeError):
            backup_hour, backup_minute = 9, 0  # Default to 9:00 AM

        # Check if we're past the scheduled time today
        scheduled_time_today = now.replace(hour=backup_hour, minute=backup_minute, second=0, microsecond=0)
        if now < scheduled_time_today:
            # Haven't reached backup time yet today
            return False

        if not prefs.last_backup_date:
            return True

        try:
            last_backup = date.fromisoformat(prefs.last_backup_date)
            days_since = (date.today() - last_backup).days
            return days_since >= prefs.backup_frequency_days
        except ValueError:
            return True

    async def perform_scheduled_backup(self, prefs: UserPreferences = None) -> Optional[Path]:
        """
        Perform a scheduled backup if due.

        Args:
            prefs: User preferences (fetched from DB if not provided)

        Returns:
            Path to backup file if created, None otherwise
        """
        # Fetch preferences if not provided
        if prefs is None:
            prefs = await self.user_repo.get_preferences()

        if not self.should_backup(prefs):
            return None

        # Create backup
        backup_file = await self.create_backup(prefs.backup_directory)

        # Cleanup old backups
        self.cleanup_old_backups(prefs.backup_directory, prefs.backup_retention_count)

        # Update last backup date
        prefs.last_backup_date = date.today().isoformat()
        await self.user_repo.update_preferences(prefs)

        return backup_file

    def copy_database(self, destination: Path) -> Path:
        """
        Create a raw copy of the SQLite database file.

        Args:
            destination: Destination directory

        Returns:
            Path to the copied database file
        """
        # Get source database path
        if os.name == 'nt':
            source_db = Path(os.getenv('APPDATA')) / 'TimeTracker' / 'timetracker.db'
        else:
            source_db = Path.home() / '.local' / 'share' / 'timetracker' / 'timetracker.db'

        if not source_db.exists():
            raise FileNotFoundError(f"Database not found: {source_db}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        dest_file = destination / f"timetracker_db_backup_{timestamp}.db"

        shutil.copy2(source_db, dest_file)
        logger.info(f"Database copied to: {dest_file}")
        return dest_file

"""
Configuration management using Pydantic Settings.

Architecture Decision: Why pydantic-settings?
- Type-safe configuration with validation
- Supports multiple sources (YAML, env vars, defaults)
- Easy to test with different configurations
"""

import os
from pathlib import Path
from typing import Optional
import yaml

from pydantic_settings import BaseSettings, SettingsConfigDict
from app.domain.models import UserPreferences


class Settings(BaseSettings):
    """
    Application settings with multiple sources:
    1. Default values (hardcoded)
    2. YAML config file
    3. Environment variables (highest priority)
    """
    model_config = SettingsConfigDict(
        env_prefix='TIMETRACKER_',
        env_file='.env',
        env_file_encoding='utf-8'
    )
    
    # Application paths
    app_name: str = "TimeTracker"
    config_dir: Optional[Path] = None
    data_dir: Optional[Path] = None
    
    # Database
    database_url: Optional[str] = None
    
    # User preferences
    preferences: UserPreferences = UserPreferences()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_paths()
        self._load_yaml_config()
    
    def _init_paths(self):
        """Initialize default paths based on OS"""
        if self.config_dir is None:
            if os.name == 'nt':  # Windows
                base = Path(os.getenv('APPDATA'))
            else:  # Linux/Mac
                base = Path.home() / '.config'
            self.config_dir = base / self.app_name.lower()
        
        if self.data_dir is None:
            if os.name == 'nt':  # Windows
                base = Path(os.getenv('APPDATA'))
            else:  # Linux/Mac
                base = Path.home() / '.local' / 'share'
            self.data_dir = base / self.app_name.lower()
        
        # Create directories if they don't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_yaml_config(self):
        """Load configuration from YAML file"""
        # First check in workspace config folder
        config_file = Path("config/settings.yaml")
        if not config_file.exists():
            # Then check in user's config directory
            config_file = self.config_dir / "settings.yaml"
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                if config_data:
                    # Update preferences with YAML data
                    self.preferences = UserPreferences(**config_data)
    
    def save_preferences(self):
        """Save current preferences to YAML file"""
        config_file = self.config_dir / "settings.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.preferences.model_dump(), f, default_flow_style=False)
    
    def get_db_url(self) -> str:
        """Get database URL, creating default if not set"""
        if self.database_url:
            return self.database_url
        
        db_path = self.data_dir / 'timetracker.db'
        return f"sqlite+aiosqlite:///{db_path}"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings():
    """Reload settings from file"""
    global _settings
    _settings = Settings()
    return _settings

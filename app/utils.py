import sys
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    
    Args:
        relative_path: Relative path from project root (e.g., "templates" or "app/assets")
        
    Returns:
        Absolute Path object
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # Standard python execution
        # This file is in app/utils.py, so project root is up two levels
        base_path = Path(__file__).parent.parent.absolute()

    return base_path / relative_path

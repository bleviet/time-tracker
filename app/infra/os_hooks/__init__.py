"""OS-specific system event monitors"""

from .base import SystemMonitor
from .factory import create_system_monitor

__all__ = ["SystemMonitor", "create_system_monitor"]

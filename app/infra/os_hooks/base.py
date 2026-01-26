"""
Base class for system event monitoring.

Architecture Decision: Observer Pattern + Factory Pattern
Defines abstract interface that platform-specific implementations must follow.
"""

from abc import ABCMeta
from PySide6.QtCore import QObject, Signal


class QABCMeta(type(QObject), ABCMeta):
    """Combined metaclass for QObject and ABC"""
    pass


class SystemMonitor(QObject, metaclass=QABCMeta):
    """
    Abstract base class for monitoring system events (lock/unlock).
    
    Platform-specific implementations inherit from this class.
    """
    
    # Signals
    system_locked = Signal()
    system_unlocked = Signal()
    system_sleep = Signal()
    system_wake = Signal()
    
    def __init__(self):
        super().__init__()
    
    def start_monitoring(self):
        """Start monitoring system events"""
        raise NotImplementedError("Subclasses must implement start_monitoring")
    
    def stop_monitoring(self):
        """Stop monitoring system events"""
        raise NotImplementedError("Subclasses must implement stop_monitoring")

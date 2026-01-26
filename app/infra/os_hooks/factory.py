"""
Factory for creating platform-specific system monitors.

Architecture Decision: Factory Pattern
Instantiates the correct monitor based on the current OS.
"""

import platform
import sys


def create_system_monitor():
    """
    Create the appropriate system monitor for the current platform.
    
    Returns:
        SystemMonitor instance for the current platform
    """
    system = platform.system()
    
    if system == "Windows":
        from .windows_monitor import WindowsMonitor
        return WindowsMonitor()
    elif system == "Linux":
        from .linux_monitor import LinuxMonitor
        return LinuxMonitor()
    elif system == "Darwin":  # macOS
        from .macos_monitor import MacOSMonitor
        return MacOSMonitor()
    else:
        # Fallback to a dummy monitor for unsupported platforms
        from .base import SystemMonitor
        
        class DummyMonitor(SystemMonitor):
            def start_monitoring(self):
                print(f"Warning: System monitoring not supported on {system}")
            
            def stop_monitoring(self):
                pass
        
        return DummyMonitor()

"""
macOS system monitor using pyobjc.

Listens for NSWorkspace notifications.
"""

from .base import SystemMonitor

try:
    from Foundation import NSObject, NSNotificationCenter, NSWorkspace
    from AppKit import (
        NSWorkspaceScreensDidSleepNotification,
        NSWorkspaceScreensDidWakeNotification,
        NSWorkspaceSessionDidResignActiveNotification,
        NSWorkspaceSessionDidBecomeActiveNotification
    )
    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False


class MacOSMonitor(SystemMonitor):
    """
    Monitors macOS session events via NSWorkspace notifications.
    """
    
    def __init__(self):
        super().__init__()
        self._monitoring = False
        self.observer = None
        
        if not HAS_PYOBJC:
            print("Warning: pyobjc not installed. Install with: pip install pyobjc-framework-Cocoa")
    
    def start_monitoring(self):
        """Start monitoring macOS notifications"""
        if not HAS_PYOBJC:
            return
        
        if self._monitoring:
            return
        
        try:
            # Create observer object
            if HAS_PYOBJC:
                self.observer = _MacOSObserver.alloc().initWithMonitor_(self)
                
                center = NSWorkspace.sharedWorkspace().notificationCenter()
                
                # Register for screen lock/unlock
                center.addObserver_selector_name_object_(
                    self.observer,
                    "onScreenLocked:",
                    NSWorkspaceScreensDidSleepNotification,
                    None
                )
                
                center.addObserver_selector_name_object_(
                    self.observer,
                    "onScreenUnlocked:",
                    NSWorkspaceScreensDidWakeNotification,
                    None
                )
                
                # Register for session changes
                center.addObserver_selector_name_object_(
                    self.observer,
                    "onSessionInactive:",
                    NSWorkspaceSessionDidResignActiveNotification,
                    None
                )
                
                center.addObserver_selector_name_object_(
                    self.observer,
                    "onSessionActive:",
                    NSWorkspaceSessionDidBecomeActiveNotification,
                    None
                )
            
            self._monitoring = True
            
        except Exception as e:
            print(f"Error starting macOS monitor: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        if not HAS_PYOBJC or not self._monitoring:
            return
        
        if self.observer:
            center = NSWorkspace.sharedWorkspace().notificationCenter()
            center.removeObserver_(self.observer)
        
        self._monitoring = False


if HAS_PYOBJC:
    class _MacOSObserver(NSObject):
        """Helper class to receive macOS notifications"""
        
        def initWithMonitor_(self, monitor):
            self = super(_MacOSObserver, self).init()
            if self:
                self.monitor = monitor
            return self
        
        def onScreenLocked_(self, notification):
            self.monitor.system_locked.emit()
        
        def onScreenUnlocked_(self, notification):
            self.monitor.system_unlocked.emit()
        
        def onSessionInactive_(self, notification):
            self.monitor.system_sleep.emit()
        
        def onSessionActive_(self, notification):
            self.monitor.system_wake.emit()

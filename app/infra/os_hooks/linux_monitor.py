"""
Linux system monitor using DBus.

Listens for org.freedesktop.login1 signals.
"""

from .base import SystemMonitor

try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False


class LinuxMonitor(SystemMonitor):
    """
    Monitors Linux session events via DBus.
    
    Listens to systemd-logind (login1) for lock/unlock signals.
    """
    
    def __init__(self):
        super().__init__()
        self._monitoring = False
        
        if not HAS_DBUS:
            print("Warning: dbus-python not installed. Install with: pip install dbus-python")
    
    def start_monitoring(self):
        """Start monitoring Linux DBus signals"""
        if not HAS_DBUS:
            return
        
        if self._monitoring:
            return
        
        try:
            # Setup DBus main loop
            DBusGMainLoop(set_as_default=True)
            
            # Connect to system bus
            bus = dbus.SystemBus()
            
            # Listen for Lock/Unlock signals
            bus.add_signal_receiver(
                self._on_lock,
                dbus_interface='org.freedesktop.login1.Session',
                signal_name='Lock'
            )
            
            bus.add_signal_receiver(
                self._on_unlock,
                dbus_interface='org.freedesktop.login1.Session',
                signal_name='Unlock'
            )
            
            # Listen for PrepareForSleep signal (suspend/resume)
            bus.add_signal_receiver(
                self._on_prepare_for_sleep,
                dbus_interface='org.freedesktop.login1.Manager',
                signal_name='PrepareForSleep'
            )
            
            self._monitoring = True
            
        except Exception as e:
            print(f"Error starting Linux monitor: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self._monitoring = False
        # DBus cleanup happens automatically
    
    def _on_lock(self):
        """Called when session is locked"""
        self.system_locked.emit()
    
    def _on_unlock(self):
        """Called when session is unlocked"""
        self.system_unlocked.emit()
    
    def _on_prepare_for_sleep(self, sleep):
        """Called before sleep/after wake"""
        if sleep:
            self.system_sleep.emit()
        else:
            self.system_wake.emit()

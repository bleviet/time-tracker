"""
Windows system monitor using pywin32.

Listens for WTS (Windows Terminal Services) session change notifications.
"""

import sys
from .base import SystemMonitor

try:
    import win32api
    import win32con
    import win32gui
    import win32ts
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Constants not always in win32con
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
PBT_APMSUSPEND = 0x4
PBT_APMRESUMESUSPEND = 0x7


class WindowsMonitor(SystemMonitor):
    """
    Monitors Windows session events (lock, unlock, sleep, wake).
    
    Uses hidden window to receive WM_WTSSESSION_CHANGE messages.
    """
    
    def __init__(self):
        super().__init__()
        self.hwnd = None
        self._monitoring = False
        
        if not HAS_WIN32:
            print("Warning: pywin32 not installed. Install with: pip install pywin32")
    
    def start_monitoring(self):
        """Start monitoring Windows session events"""
        if not HAS_WIN32:
            return
        
        if self._monitoring:
            return
        
        # Create hidden window to receive messages
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "TimeTrackerMonitor"
        wc.hInstance = win32api.GetModuleHandle(None)
        
        try:
            class_atom = win32gui.RegisterClass(wc)
            self.hwnd = win32gui.CreateWindow(
                class_atom,
                "TimeTrackerMonitor",
                0, 0, 0, 0, 0, 0, 0,
                wc.hInstance,
                None
            )
            
            # Register for session notifications
            win32ts.WTSRegisterSessionNotification(self.hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
            self._monitoring = True
            
        except Exception as e:
            print(f"Error starting Windows monitor: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        if not HAS_WIN32 or not self._monitoring:
            return
        
        if self.hwnd:
            try:
                win32ts.WTSUnRegisterSessionNotification(self.hwnd)
                win32gui.DestroyWindow(self.hwnd)
            except Exception as e:
                print(f"Error stopping Windows monitor: {e}")
        
        self._monitoring = False
        self.hwnd = None
    
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure to handle messages"""
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:  # Session locked
                self.system_locked.emit()
            elif wparam == WTS_SESSION_UNLOCK:  # Session unlocked
                self.system_unlocked.emit()
        
        elif msg == win32con.WM_POWERBROADCAST:
            if wparam == PBT_APMSUSPEND:  # System suspending
                self.system_sleep.emit()
            elif wparam == PBT_APMRESUMESUSPEND:  # System resuming
                self.system_wake.emit()
        
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

"""
Splash Screen - Shows loading indicator during application startup.

Architecture Decision: Perceived Performance
A splash screen improves perceived startup time by showing feedback immediately
while heavy initialization (DB, services, theme) happens in the background.
"""

from PySide6.QtWidgets import QSplashScreen, QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt

from app.utils import get_resource_path
from app.i18n import tr, detect_system_language, set_language


class SplashScreen(QSplashScreen):
    """
    Simple splash screen shown during application startup.

    Features:
    - Shows app icon and name
    - Displays loading status messages
    - Automatically closes when main window is ready
    """

    def __init__(self):
        # Initialize language for splash screen based on system
        # (Preferences will be loaded later, but this gives a good first guess)
        set_language(detect_system_language())
        
        # Create splash pixmap
        pixmap = self._create_splash_pixmap()
        super().__init__(pixmap)

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

    def _create_splash_pixmap(self) -> QPixmap:
        """Create the splash screen image"""
        width, height = 300, 150

        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#2d2d2d"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw border
        painter.setPen(QColor("#555555"))
        painter.drawRect(0, 0, width - 1, height - 1)

        # Try to load and draw the app icon
        icon_path = get_resource_path("app/assets/clock_icon.png")
        if icon_path.exists():
            icon_pixmap = QPixmap(str(icon_path))
            if not icon_pixmap.isNull():
                scaled_icon = icon_pixmap.scaled(
                    48, 48,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                icon_x = (width - scaled_icon.width()) // 2
                painter.drawPixmap(icon_x, 25, scaled_icon)

        # Draw app name
        painter.setPen(QColor("#e0e0e0"))
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(0, 85, width, 30, Qt.AlignCenter, tr("app.name"))

        # Draw loading text area (will be updated with showMessage)
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#90caf9"))
        painter.drawText(0, 115, width, 25, Qt.AlignCenter, tr("splash.starting"))

        painter.end()
        return pixmap

    def update_status(self, message: str):
        """Update the loading status message"""
        self.showMessage(
            message,
            Qt.AlignBottom | Qt.AlignHCenter,
            QColor("#90caf9")
        )
        QApplication.processEvents()

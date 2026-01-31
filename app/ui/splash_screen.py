import sys
from PySide6.QtWidgets import (QSplashScreen, QApplication, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QProgressBar, QFrame, QGraphicsDropShadowEffect)
from PySide6.QtGui import QPixmap, QColor, QFont, QPalette
from PySide6.QtCore import Qt, QTimer

from app.utils import get_resource_path
from app.i18n import tr, detect_system_language, set_language


class SplashScreen(QSplashScreen):
    """
    Modern 'Floating Card' splash screen.
    
    Architecture Decision: Widget-based Composition
    Instead of manual QPainter drawing (old school), we use standard Qt Widgets
    (QFrame, QLabel, Layouts) with QGraphicsDropShadowEffect and TranslucentBackground.
    This allows for easy styling, gradients, and proper layout management.
    """

    def __init__(self):
        # 1. Setup Window (Translucent & Frameless)
        # We pass a dummy pixmap to super because QSplashScreen expects it, 
        # but we relying on our internal widgets for rendering.
        super().__init__(QPixmap(1, 1)) 
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Initialize language
        set_language(detect_system_language())

        # 2. Main Layout (The "Canvas")
        # We need distinct margins to allow space for the Drop Shadow
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 3. The "Card" (The actual visible area)
        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF; /* Light mode default */
                border-radius: 16px;
            }
        """)
        
        # Determine theme (simple check for now, can be improved)
        # For splash, we might stick to light or dark. User asked for White or Charcoal.
        # Let's Default to White for "Clean" look unless system detection? 
        # We can stick to White for now as per "Clean white" spec.
        
        # 4. Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 80)) # Subtle dark shadow
        self.card.setGraphicsEffect(shadow)
        
        self.main_layout.addWidget(self.card)
        
        # 5. Content Layout (Horizontal Split: Icon | Text)
        self.card_layout = QHBoxLayout(self.card)
        self.card_layout.setContentsMargins(40, 40, 40, 40)
        self.card_layout.setSpacing(30)
        
        # 6. Left: Large Icon
        self.icon_label = QLabel()
        # Prefer master_icon.png (High Res)
        icon_path = get_resource_path("app/assets/master_icon.png")
        if not icon_path.exists():
             icon_path = get_resource_path("app/assets/clock_icon.png")
             
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            # Scale to reasonable size for splash (e.g. 128x128)
            pix = pix.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pix)
        
        self.card_layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        
        # 7. Right: Info Column
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(5)
        
        # App Name
        self.title_label = QLabel(tr("app.name"))
        font = QFont("Segoe UI", 28, QFont.Bold) # Modern font
        font.setStyleStrategy(QFont.PreferAntialias)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("color: #2c3e50;") # Dark Slate
        self.info_layout.addWidget(self.title_label)
        
        # Spacer
        self.info_layout.addStretch()
        
        # Status Text
        self.status_label = QLabel(tr("splash.starting"))
        # Using a monospaced font or smaller UI font might act nicely
        status_font = QFont("Segoe UI", 10)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("color: #7f8c8d;") # Gray
        self.info_layout.addWidget(self.status_label)
        
        # Progress Bar (Thin & Modern)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #ecf0f1;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #3498db, stop:1 #8e44ad);
                border-radius: 2px;
            }
        """)
        self.progress.setRange(0, 0) # Indeterminate mode by default
        self.info_layout.addWidget(self.progress)
        
        # Version
        self.version_label = QLabel("v1.0.0")
        version_font = QFont("Segoe UI", 8)
        self.version_label.setFont(version_font)
        self.version_label.setStyleSheet("color: #bdc3c7;") # Light Gray
        self.version_label.setAlignment(Qt.AlignRight)
        self.info_layout.addWidget(self.version_label)
        
        self.card_layout.addLayout(self.info_layout)
        
        # Set Fixed Size for the whole splash window (600x350 specified)
        self.setFixedSize(600, 350)
        
        # Center on screen
        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def update_status(self, message: str):
        """Update the loading status message"""
        self.status_label.setText(message)
        QApplication.processEvents()

    def set_progress(self, value: int):
        """Update progress bar (0-100)"""
        self.progress.setRange(0, 100)
        self.progress.setValue(value)
        QApplication.processEvents()
        
    def finish(self, window):
        """Close splash when main window is ready"""
        # We can implement a fade out here if we wanted to be fancy,
        # but for now standard finish behavior is fine.
        super().finish(window)

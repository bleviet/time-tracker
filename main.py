#!/usr/bin/env python

"""
Time Tracker Application - Main Entry Point

A cross-platform time tracking application with German holiday support,
automatic pause/resume on lock/unlock, and customizable report generation.

Usage:
    python main.py

Requirements:
    - Python 3.12+
    - See requirements.txt for dependencies
"""

import sys
import os
from pathlib import Path

# Suppress verbose Qt Multimedia/FFmpeg logging
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.info=false"

# Use native Windows Media Foundation backend on Windows to avoid FFmpeg log spam
if os.name == 'nt':
    os.environ["QT_MEDIA_BACKEND"] = "windows"

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ui import SystemTrayApp


def main():
    """Main entry point"""
    app = SystemTrayApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())

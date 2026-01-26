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
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ui import SystemTrayApp


def main():
    """Main entry point"""
    app = SystemTrayApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())

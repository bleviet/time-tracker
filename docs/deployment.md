# Deployment Guide

This guide explains how to build and distribute the Time Tracker application.

## Prerequisites

- Python 3.12+
- `uv` (recommended) or `pip`

## Building the Application

We use `PyInstaller` to create a standalone executable.

1.  **Install Dependencies**
    Ensure all project requirements are installed:
    uv sync
    ```


2.  **Run Build Script**
    A helper script `build.py` is provided to automate the process:
    ```powershell
    uv run python build.py
    ```

    This will:
    - Clean previous builds.
    - Run PyInstaller with the correct configuration.
    - Include necessary assets (`app/assets`, `templates`).

3.  **Locate Output**
    The packaged application will be in the `dist/TimeTracker` folder.

## Distribution

To ship to customers:

1.  Navigate to the `dist` directory.
2.  Zip the `TimeTracker` folder (or just `TimeTracker.exe` if using `--onefile` mode, but directory mode is faster to start).
    - *Note: The current build configuration uses directory mode (onedir) for better compatibility.*
3.  Send the Zip file to the customer.

### Customer Instructions
- Unzip the archive.
- Run `TimeTracker.exe`.
- The application will appear in the system tray.

import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    """Build the application using PyInstaller"""
    project_root = Path(__file__).parent

    # Configuration
    app_name = "TimeTracker"
    entry_point = "main.py"

    # Assets to include: (source, destination) relative to project root
    # Windows uses ";" as separator, Linux ":"
    sep = ";" if os.name == "nt" else ":"

    add_data = [
        ("app/assets", "app/assets"),
        ("app/resources/templates", "app/resources/templates"),
        ("docs/tutorial/video", "docs/tutorial/video"),
    ]

    # Construct PyInstaller arguments
    # Use "PyInstaller" as module name
    args = [
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # No console window
        f"--name={app_name}",
        f"--icon={str(Path('app/assets/icon.ico').absolute())}", # Use absolute path
    ]

    # Add data arguments
    for src, dst in add_data:
        args.append(f"--add-data={src}{sep}{dst}")

    # Add hidden imports (only what is actually needed)
    args.append("--hidden-import=aiosqlite")

    # Exclude unused database drivers and platform-specific modules to reduce warnings
    args.append("--exclude-module=MySQLdb")
    args.append("--exclude-module=psycopg2")
    args.append("--exclude-module=pysqlite2")

    if os.name == 'nt':
        args.append("--exclude-module=AppKit")
        args.append("--exclude-module=Cocoa")
        args.append("--exclude-module=Foundation")

    # Collect all holidays submodules (fixes dynamic import issue)
    args.append("--collect-all=holidays")

    # Entry point
    args.append(entry_point)

    print("=" * 50)
    print(f"Building {app_name}...")
    print(f"Command: {' '.join(args)}")
    print("=" * 50)

    try:
        # Check if pyinstaller is installed
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=True, capture_output=True)

        # Run build
        subprocess.run([sys.executable, "-m"] + args, check=True)

        print("\nBuild successful!")
        print(f"Executable is located at: {project_root / 'dist' / app_name / (app_name + '.exe')}")

    except subprocess.CalledProcessError as e:
        print(f"\nError: Build failed with exit code {e.returncode}")
        print("Ensure 'pyinstaller' is installed: uv add --dev pyinstaller")
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: PyInstaller not found.")
        print("Please install it: uv add --dev pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    main()

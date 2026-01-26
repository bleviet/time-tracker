import shutil
import os
from pathlib import Path

def cleanup():
    """Clean up build artifacts and temporary files."""
    root_dir = Path(__file__).parent.parent
    
    dirs_to_remove = [
        root_dir / "build",
        root_dir / "dist",
        root_dir / "__pycache__",
        root_dir / "app" / "__pycache__",
        root_dir / "app" / "domain" / "__pycache__",
        root_dir / "app" / "services" / "__pycache__",
        root_dir / "app" / "ui" / "__pycache__",
        root_dir / "app" / "infra" / "__pycache__",
    ]
    
    files_to_remove = [
        root_dir / "TimeTracker.spec",
        root_dir / "timetracker.db",  # Starting fresh
    ]
    
    # Remove directories
    for d in dirs_to_remove:
        if d.exists():
            print(f"Removing directory: {d}")
            try:
                shutil.rmtree(d)
            except Exception as e:
                print(f"Error removing {d}: {e}")
                
    # Remove specific files
    for f in files_to_remove:
        if f.exists():
            print(f"Removing file: {f}")
            try:
                os.remove(f)
            except Exception as e:
                print(f"Error removing {f}: {e}")

    # Clean reports but keep directory
    reports_dir = root_dir / "reports"
    if reports_dir.exists():
        print(f"Cleaning reports in: {reports_dir}")
        for f in reports_dir.glob("*"):
            if f.name != ".gitkeep":
                try:
                    os.remove(f)
                except Exception as e:
                     print(f"Error removing {f}: {e}")
    else:
        reports_dir.mkdir()
        
    # Create .gitkeep in reports
    (reports_dir / ".gitkeep").touch()
    
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup()

# Time Tracker

A cross-platform time tracking application with German holiday support and automatic pause/resume functionality.

## Features

- ✅ **System Tray Integration** - Runs in background, always accessible
- ✅ **Multi-Task Tracking** - Track time across multiple projects/tasks
- ✅ **German Holiday Support** - Automatically detects German holidays (configurable by state)
- ✅ **Auto-Pause on Lock** - Pauses tracking when you lock your screen
- ✅ **Smart Resume** - Asks if time during absence was work or break
- ✅ **Report Generation** - Generate customizable time reports using Jinja2 templates
- ✅ **Clean Architecture** - Modular design with separation of concerns
- ✅ **Cross-Platform** - Works on Windows, Linux, and macOS

## Architecture

See [Architecture Documentation](docs/architecture/overview.md) for details.


## Installation

### Prerequisites

- Python 3.12 or higher
- pip (Python package manager)

### Steps

1. Clone or download this repository

2. Install dependencies:
```bash
uv sync
```

3. (Windows only) If you want lock/unlock detection, ensure pywin32 is installed (should be handled by uv sync if on Windows).


4. Run the application:
```bash
uv run main.py
```

## Configuration

Edit `config/settings.yaml` to customize behavior:

```yaml
# German state (BY=Bavaria, NW=North Rhine-Westphalia, etc.)
german_state: BY

# Auto-pause settings
auto_pause_on_lock: true
ask_on_unlock: true
auto_pause_threshold_minutes: 5

# Report settings
default_report_template: monthly_report.txt
```

## Usage

### Minimal Widget Interface

The application displays a **modern, unified widget** at the **bottom right** of your screen:

**Appearance:** Single rounded rectangle with semi-transparent background containing:

1. **Task Name Field** (Left) - Always editable
   - Type to start/switch tasks instantly
   - Autocomplete suggests existing tasks
   - Press Enter to start/switch

2. **Timer Display** (Right) - Shows HH:MM:SS
   - Cumulative time across all sessions
   - Bold blue numbers
   - Updates every second

**Widget Features:**
- Modern rounded design with subtle transparency
- Always stays on top of other windows
- Bottom right position (unobtrusive)
- Drag anywhere to reposition
- Right-click for options (Stop, Hide, Quit)
- Minimizes to system tray

### Starting & Switching Tasks

**Just type and press Enter - no buttons needed:**

1. Type task name (e.g., "Development")
2. Autocomplete suggests matches
3. Press Enter
4. Timer begins/continues from cumulative time

**To switch to another task:**
1. Type new task name (overwrites current)
2. Press Enter
3. Previous task auto-stops, new task starts with its cumulative time

**Example:**
- Type "Development" + Enter → Timer: **00:00:00** → Tracks to **00:30:00**
- Type "Meeting" + Enter → Development stops, Meeting timer shows **00:00:00**
- Type "Development" + Enter → Timer immediately shows **00:30:00** and continues

**The task field is always editable** - you can switch tasks anytime by typing a new name.

### Stopping Time Tracking

**Only needed when completely done:**
1. Right-click widget → "Stop Tracking", OR
2. Right-click tray icon → "Stop Tracking"

### Widget Management

- **Hide Widget**: 
  - Click minimize button (−) on widget, OR
  - Press **Esc**, OR
  - Right-click → "Hide to Tray"
- **Show Widget**: 
  - Press **Ctrl+Shift+T** (global shortcut), OR
  - Double-click tray icon, OR
  - Right-click tray icon → "Show Main Window"
- **Move Widget**: Click and drag anywhere on the widget
- **Quit**: Right-click → "Quit"

### Keyboard Shortcuts

- **Esc** - Hide widget to tray
- **Ctrl+Shift+T** - Show widget (works globally, even when hidden)
- **Enter** - Start/switch task (when focused on task input)

### Generating Reports

1. Right-click the system tray icon
2. Select "Generate Report..."
3. Report is generated for the current month

### Customizing Reports

Edit templates in the `templates/` directory. Example template:

```jinja2
Time Tracking Report
====================
Period: {{ start_date }} to {{ end_date }}

Total Time: {{ total_seconds | format_duration }}

{% for task_data in tasks %}
Task: {{ task_data.task.name }}
  Total: {{ task_data.total_seconds | format_duration }}
{% endfor %}
```

## Database

Data is stored in SQLite at:
- **Windows**: `%APPDATA%\TimeTracker\timetracker.db`
- **Linux/Mac**: `~/.local/share/timetracker/timetracker.db`

## Development



### Project Structure

- **Domain Layer**: Pure business logic, no dependencies on frameworks
- **Service Layer**: Application logic, coordinates between domain and infrastructure
- **Infrastructure Layer**: Database, OS integration, external dependencies
- **Presentation Layer**: UI, system tray, user interaction

### Adding New Features

1. Add domain models to `app/domain/models.py`
2. Add business logic to `app/services/`
3. Add infrastructure code to `app/infra/`
4. Update UI in `app/ui/`

## Troubleshooting

### System tray icon doesn't show
- On Linux, ensure you have a system tray (like `gnome-shell-extension-appindicator`)
- Try restarting the application

### Lock/unlock detection doesn't work
- **Windows**: Ensure `pywin32` is installed
- **Linux**: Ensure `dbus-python` is installed
- **macOS**: Ensure `pyobjc-framework-Cocoa` is installed

### Database errors
- Delete the database file (see Database section above)
- Restart the application to create a fresh database

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or pull request.

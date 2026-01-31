# Time Tracker

A cross-platform time tracking application with German holiday support and automatic pause/resume functionality.

## Features

- ✅ **System Tray Integration** - Runs in background, always accessible
- ✅ **Multi-Task Tracking** - Track time across multiple projects/tasks
- ✅ **German Holiday Support** - Automatically detects German holidays (configurable by state)
- ✅ **Auto-Pause on Lock** - Pauses tracking when you lock your screen
- ✅ **Smart Resume** - Asks if time during absence was work or break
- ✅ **Work Regulations** - Configurable daily targets and German ArbZG compliance
- ✅ **Overtime Tracking** - Automatic daily/total overtime calculation in reports
- ✅ **Auto-Save** - Periodic background saves every 60 seconds for data safety
- ✅ **Advanced Reporting** - Monthly reports, Accounting exports, and Sick/Vacation leave management
- ✅ **Theme Support** - Light, Dark, or Auto (follows system) theme selection
- ✅ **Font Scaling** - Adjustable font size (50% - 200%) for high-DPI displays
- ✅ **Scheduled Backups** - Automatic backups with configurable time and frequency
- ✅ **Splash Screen** - Immediate visual feedback during startup
- ✅ **Clean Architecture** - Modular design with separation of concerns
- ✅ **Internationalization** - Fully localized in English and German
- ✅ **Cross-Platform** - Works on Windows, Linux, and macOS

## Architecture

See [Architecture Documentation](docs/architecture/overview.md) for details.


## Installation

### Prerequisites

- Python 3.10 or higher
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

1.  **Task Name Field** (Left) - Always editable
    -   Type to start/switch tasks instantly
    -   Autocomplete suggests existing tasks
    -   Press Enter to start/switch

2.  **Play/Pause Button** (Middle)
    -   **Play (▶)**: Green, starts tracking current task
    -   **Pause (⏸)**: Orange, stops tracking

3.  **Timer Display** (Right) - Shows HH:MM:SS
    -   Cumulative time across all sessions
    -   Bold blue numbers
    -   Updates every second

4.  **Minimize Button** (Far Right)
    -   Arrow Down (▼) icon
    -   Hides widget to system tray

**Widget Features:**
- Modern rounded design with subtle transparency
- Always stays on top of other windows
- Bottom right position (unobtrusive)
- Drag anywhere to reposition
- Right-click for options (Stop, Hide, Quit)
- Minimizes to system tray (Restore with Ctrl+Shift+T)

### Starting & Switching Tasks

**Just type and press Enter - no buttons needed:**

1.  Type task name (e.g., "Development")
2.  Autocomplete suggests matches
3.  Press Enter
4.  Timer begins/continues from cumulative time

**To switch to another task:**
1.  Type new task name (overwrites current)
2.  Press Enter
3.  Previous task auto-stops, new task starts with its cumulative time

**Example:**
- Type "Development" + Enter → Timer: **00:00:00** → Tracks to **00:30:00**
- Type "Meeting" + Enter → Development stops, Meeting timer shows **00:00:00**
- Type "Development" + Enter → Timer immediately shows **00:30:00** and continues

**The task field is always editable** - you can switch tasks anytime by typing a new name.

### Stopping Time Tracking

**Two ways to stop:**
1.  Click the **Pause (⏸)** button on the widget
2.  Right-click widget → "Stop Tracking"

### Widget Management

- **Hide Widget**: 
  - Click minimize button (▼) on widget, OR
  - Press **Esc**, OR
  - Right-click → "Hide to Tray"
- **Show Widget**: 
  - Press **Ctrl+Shift+T** (global shortcut), OR
  - Double-click tray icon, OR
  - Right-click → "Show Main Window"
- **Move Widget**: Click and drag anywhere on the widget
- **Quit**: Right-click → "Quit"

### Task Management (Archiving)

You can manage your tasks via the **Manage Tasks** dialog (accessible from the History window or Settings).

**Archiving vs Deleting:**
- **Archiving** "retires" a completed task. It hides it from your daily selection lists but **preserves all history** for valid reports.
- **Deleting** creates data inconsistencies and is generally discouraged.

**To Archive a Task:**
1. Open **Manage Tasks**.
2. Find the task in the list.
3. Change its status from **Active** to **Archived** in the dropdown.
4. The task will no longer appear in autocomplete but its history remains safe.

### Keyboard Shortcuts

- **Esc** - Hide widget to tray
- **Ctrl+Shift+T** - Show widget (works globally, even when hidden)
- **Enter** - Start/switch task (when focused on task input)

### Managing Time Entries (History)

1. Right-click the system tray icon → "Show History & Log"
2. **View Entries**: Select a date in the calendar to view that day's log.
3. **Daily Summary**: See cumulative totals per task and Work Regulations status.
   - **Resizable Layout**: Drag splitters to resize Calendar, Regulations, Task List, and Daily Summary.
   - **Work Regulations**: View daily target progress and compliance warnings (10h limit, rest periods).
4. **Edit/Delete**: Right-click any entry in the table to **Edit** or **Delete** it.
   - *Note: Deleting an entry permanently removes it and recalculates the daily total.*
5. **Manual Entry**: Click "+ Add Manual Entry" to record offline work.

### Generating Reports

1. Right-click the system tray icon → "Generate Report..."
2. **The Report Wizard** opens:
   - **Configuration**: Select Report Type (Monthly Report) and Month/Year.
   - **Time Off Manager**: Click days in the calendar to mark them as **Vacation** (Green) or **Sickness** (Red).
   - **Exclusions**: Uncheck tasks (like "Lunch" or "Break") to exclude them from the "Total Work" calculation.
3. Click **Generate Report**. Your settings for Time Off and Exclusions are **automatically saved** for next time.

### Internationalization

The application supports **English** and **German**.

1. Go to **Settings** (Right-click tray icon → Settings).
2. In the **General** tab, select your preferred language.
3. The interface updates **immediately** without restarting.
4. **Auto-detection**: By default, the app matches your system language.

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

# Architecture Overview

The Time Tracker application is built using a **Clean Architecture** approach, separating concerns into distinct layers. This ensures that business logic is decoupled from the UI and infrastructure, making the system testable and maintainable.

## 1. High-Level Layers

The application is structured into four main layers (inside the `app/` directory):

| Layer | Directory | Responsibility | Dependencies |
|-------|-----------|----------------|--------------|
| **Domain** | `app/domain` | Operations-agnostic entities (Pydantic models). Contains the core data structures (`Task`, `TimeEntry`). | None |
| **Services** | `app/services` | Pure business logic. Orchestrates operations, manages state (e.g., `TimerService`), and handles calculations. | Domain, Repository Interfaces |
| **Infrastructure** | `app/infra` | External concerns: Database, File System, OS Hooks, Configuration. Implements repository interfaces. | Domain |
| **Presentation (UI)** | `app/ui` | User Interface logic using PySide6 (Qt). Handles user input and visualizes state. | Services, Domain |

## 2. Directory Structure

```text
app/
├── domain/             # Pydantic models (Schema definitions)
│   └── models.py       # Task, TimeEntry, UserPreferences models
├── services/           # Application Business Logic
│   ├── timer_service.py    # Core state machine (Start/Stop/Pause)
│   ├── calendar_service.py # Holiday & Weekend calculations
│   └── report_service.py   # Report generation orchestration
├── infra/              # Infrastructure Implementations
│   ├── db.py               # SQLAlchemy Async Engine setup
│   ├── repository.py       # Database access objects
│   └── os_hooks/           # OS-specific monitoring (Idle detection)
├── ui/                 # Presentation Layer
│   ├── tray_icon.py        # Main Application Controller (SystemTrayApp)
│   ├── main_window.py      # Floating Timer Widget
│   ├── history_window.py   # Complex Management UI (Calendar/Tables)
│   └── report_window.py    # Report Configuration Wizard
└── i18n/               # Internationalization
    └── translations.py     # Translation strings (EN/DE)
```

## 3. Core Components

### SystemTrayApp (`app.ui.tray_icon`)
The root controller of the application. It does not just manage the tray icon but orchestrates the entire application lifecycle:
- Initializes the Async event loop.
- Sets up the `TimerService` and `SystemMonitor`.
- Manages window visibility (`MainWindow`, `HistoryWindow`).
- Handles Global Shortcuts and System Events (Quit, Minimize).

### TimerService (`app.services.timer_service`)
The heart of the application. It acts as the "source of truth" for the tracking state.
- **Pattern**: Observer (via Qt Signals).
- **Responsibility**: Tracks current entry, notifies UI of ticks (every second), handles Pause/Resume logic.
- **Persistence**: Periodically auto-saves active entries to prevent data loss.

### Repositories (`app.infra.repository`)
Abstraction layer over the database.
- Uses **SQLAlchemy 2.0 (AsyncIO)** with `aiosqlite`.
- Provides async methods for CRUD operations (`get_overlapping`, `create`, `update`).
- Handles "Orphaned Entry" recovery (detecting entries left open after a crash).

### SystemMonitor (`app.infra.os_hooks`)
Monitors User Activity to handle "Auto-Pause".
- Detects Screen Lock/Unlock events.
- **Windows**: Uses Win32 APIs (`pywin32`) to detect lock session.
- **macOS**: Uses `pyobjc` to listen for `NSWorkspace` notifications.

## 4. Key Design Patterns

### Asynchronous UI
The application integrates Python's `asyncio` event loop with Qt's Event Loop (`QEventLoop`).
- **Startup**: `SystemTrayApp` sets up the `asyncio` loop running on the main thread (cooperatively via `QTimer` or `qasync` style integration).
- **Operations**: Database calls are `await`ed, ensuring the UI never freezes during heavy queries or report generation.

### Observer Pattern (Signals & Slots)
The UI is decoupled from the Service layer.
- **TimerService** emits signals: `task_started`, `tick`, `task_stopped`.
- **UI Components** connect to these signals to update their views.
- The Service does *not* know about the UI classes.

## 5. Technology Stack

- **Language**: Python 3.12+
- **GUI Framework**: PySide6 (Qt 6.8+)
- **Database**: SQLite (via `aiosqlite` + `SQLAlchemy`)
- **Validation**: Pydantic v2
- **Reporting**: `XlsxWriter` (Excel), `Jinja2` (HTML/PDF prep)
- **Time/Date**: Native `datetime` + `holidays` library

# Architecture Overview

This application follows **Clean Architecture** principles:

```
├── app/
│   ├── domain/          # Business entities (Pydantic models)
│   ├── services/        # Business logic (Timer, Calendar, Reports)
│   ├── infra/           # Infrastructure (Database, OS hooks, Config)
│   └── ui/              # Presentation layer (PySide6)
├── templates/           # Jinja2 report templates
├── config/              # User configuration
└── main.py              # Entry point
```

For detailed design concepts and technology choices, please see:
- [Concept](concept.md)
- [Internationalization](internationalization.md)

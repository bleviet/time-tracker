# Internationalization (i18n)

The application supports multiple languages with immediate UI updates and system locale detection.

## Architecture

The internationalization system is built as a standalone module `app.i18n` to decouple translation logic from the UI.

### Key Components

1.  **`app.i18n.translations`**: Contains the dictionary of all translatable strings.
    -   Structure: `{'en': {'key': 'value'}, 'de': {'key': 'wert'}}`
    -   Keys are hierarchical (e.g., `settings.general`, `main.title`).

2.  **`app.i18n` Module**:
    -   `tr(key, **kwargs)`: The core translation function. Returns the translated string for the current language. Supports Python-style string formatting.
    -   `set_language(lang)`: Sets the current language and updates `QLocale`.
    -   `detect_system_language()`: Detects the OS language (defaults to 'en' if not supported).
    -   `on_language_changed(callback)`: Registry for observers.

3.  **Observer Pattern**:
    -   UI components (Windows, Dialogs, Tray) subscribe to language changes via `on_language_changed`.
    -   When language changes, they call their own `retranslate_ui()` method to update texts immediately.

### Dynamic Updates

Unlike standard Qt applications that often require a restart or `.qm` file reloading, this application uses a lightweight dictionary-based approach.

1.  User selects language in **Settings**.
2.  `SettingsDialog` calls `set_language()`.
3.  `set_language` updates `QLocale` (for dates/numbers) and notifies all subscribers.
4.  Subscribers (e.g., `MainWindow`, `HistoryWindow`) execute `retranslate_ui()`.
5.  All labels, buttons, and titles are updated instantly.

## Adding a New Language

1.  Open `app/i18n/translations.py`.
2.  Add a new key to the `TRANSLATIONS` dictionary (e.g., `"fr"` for French).
3.  Copy structure from `"en"` and translate values.
4.  Update `SUPPORTED_LANGUAGES` in `app/i18n/__init__.py`.
5.  Add the language to `get_available_languages()`.

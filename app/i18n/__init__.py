# -*- coding: utf-8 -*-
"""
Internationalization (i18n) module for Time Tracker.

This module provides translation functions and language management.
Supports English and German with automatic system locale detection.
"""

import locale
from typing import Callable, List
from PySide6.QtCore import QLocale

from app.i18n.translations import TRANSLATIONS

# Supported languages
SUPPORTED_LANGUAGES = ["en", "de"]

# Current language (default to English)
_current_language = "en"

# Callbacks to notify when language changes
_language_changed_callbacks: List[Callable[[str], None]] = []


def detect_system_language() -> str:
    """
    Detect the system language and return a supported language code.

    Returns:
        'de' if German is detected, 'en' otherwise.
    """
    try:
        # Get system locale
        system_locale = locale.getdefaultlocale()[0]
        if system_locale:
            # Check if German
            if system_locale.startswith('de'):
                return 'de'
    except Exception:
        pass
    return 'en'


def get_language() -> str:
    """Get the current language code."""
    return _current_language


def set_language(lang: str) -> None:
    """
    Set the current UI language.

    Args:
        lang: Language code ('en' or 'de')
    """
    global _current_language
    if lang not in SUPPORTED_LANGUAGES:
        lang = 'en'
    _current_language = lang

    # Update Qt Locale for dates and standard widgets
    if lang == 'de':
        QLocale.setDefault(QLocale(QLocale.German))
    else:
        QLocale.setDefault(QLocale(QLocale.English))

    # Notify all registered callbacks
    for callback in _language_changed_callbacks:
        try:
            callback(lang)
        except Exception:
            pass


def tr(key: str, **kwargs) -> str:
    """
    Get the translated string for the given key.

    Args:
        key: Translation key (e.g., 'settings.title')
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string, or the key itself if not found.
    """
    translations = TRANSLATIONS.get(_current_language, TRANSLATIONS.get('en', {}))
    text = translations.get(key, key)

    # Apply format arguments if provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text


def on_language_changed(callback: Callable[[str], None]) -> None:
    """
    Register a callback to be notified when language changes.

    Args:
        callback: Function that takes the new language code as argument.
    """
    if callback not in _language_changed_callbacks:
        _language_changed_callbacks.append(callback)


def remove_language_callback(callback: Callable[[str], None]) -> None:
    """
    Remove a previously registered language change callback.

    Args:
        callback: The callback function to remove.
    """
    if callback in _language_changed_callbacks:
        _language_changed_callbacks.remove(callback)


def get_available_languages() -> List[tuple]:
    """
    Get list of available languages for UI display.

    Returns:
        List of (code, display_name) tuples.
    """
    return [
        ('en', 'English'),
        ('de', 'Deutsch'),
    ]

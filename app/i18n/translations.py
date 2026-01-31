# -*- coding: utf-8 -*-
"""
Translation dictionaries for German and English.

This module contains all translatable strings for the Time Tracker application.
"""

TRANSLATIONS = {
    "en": {
        # Application
        "app.name": "Time Tracker",
        "app.ready": "Time Tracker Ready",

        # Splash screen
        "splash.loading_preferences": "Loading preferences...",
        "splash.applying_theme": "Applying theme...",
        "splash.initializing_db": "Initializing database...",
        "splash.loading_tasks": "Loading tasks...",
        "splash.starting": "Starting application...",

        # Tray menu
        "tray.show_window": "Show Window",
        "tray.quit": "Quit",

        # Main window
        "main.title": "Time Tracker",
        "main.task_placeholder": "Enter task name...",
        "main.start": "Start",
        "main.stop": "Stop",
        "main.history": "History",
        "main.settings": "Settings",

        # History window
        "history.title": "Monthly Overview",
        "history.add_entry": "+ Add Manual Entry",
        "history.manage_accounting": "Manage Accounting",
        "history.manage_tasks": "Manage Tasks",
        "history.generate_report": "Generate Report",
        "history.task": "Task",
        "history.start": "Start",
        "history.end": "End",
        "history.duration": "Duration",
        "history.notes": "Notes",
        "history.total": "Total",
        "history.daily_summary": "Daily Summary",

        # Calendar/Legend
        "calendar.legend": "Legend:",
        "calendar.vacation": "Vacation",
        "calendar.sickness": "Sickness",
        "calendar.holiday": "Holiday",
        "calendar.hint": "(Right-click date to cycle)",

        # Work regulations
        "regulations.title": "Work Regulations",
        "regulations.daily_target": "Daily Target:",
        "regulations.german_compliance": "Enable German Compliance (10h limit)",
        "regulations.check_breaks": "Check Mandatory Breaks",
        "regulations.check_rest": "Check Rest Periods (11h)",

        # Settings dialog
        "settings.title": "Settings",
        "settings.general": "General",
        "settings.backup": "Backup",

        # Settings - Appearance
        "settings.appearance": "Appearance",
        "settings.theme": "Theme:",
        "settings.theme_auto": "Follow System",
        "settings.theme_light": "Light",
        "settings.theme_dark": "Dark",
        "settings.font_size": "Font Size:",
        "settings.language": "Language:",
        "settings.language_en": "English",
        "settings.language_de": "Deutsch",

        # Settings - Behavior
        "settings.behavior": "Behavior",
        "settings.auto_pause": "Auto-pause when screen locks",
        "settings.ask_unlock": "Ask about time away on unlock",
        "settings.pause_threshold": "Auto-pause threshold:",

        # Settings - Regional
        "settings.regional": "Regional",
        "settings.german_state": "German State:",
        "settings.respect_holidays": "Respect public holidays",
        "settings.respect_weekends": "Respect weekends",

        # Settings - System Tray
        "settings.system_tray": "System Tray",
        "settings.show_seconds": "Show seconds in tray icon",
        "settings.minimize_tray": "Minimize to tray instead of closing",

        # Settings - Backup
        "settings.backup_auto": "Automatic Backup",
        "settings.backup_enable": "Enable automatic backups",
        "settings.backup_frequency": "Backup frequency:",
        "settings.backup_time": "Backup time:",
        "settings.backup_retention": "Keep last:",
        "settings.backup_location": "Backup location:",
        "settings.backup_browse": "Browse...",
        "settings.backup_last": "Last backup:",
        "settings.backup_never": "Never",

        "settings.backup_manual": "Manual Backup & Restore",
        "settings.backup_now": "Backup Now",
        "settings.backup_restore": "Restore from Backup",
        "settings.backup_available": "Available Backups:",
        "settings.backup_refresh": "🔄 Refresh List",
        "settings.backup_delete": "🗑️ Delete Selected",

        # Backup frequencies
        "backup.daily": "Daily",
        "backup.every_3_days": "Every 3 days",
        "backup.weekly": "Weekly",
        "backup.every_2_weeks": "Every 2 weeks",
        "backup.monthly": "Monthly",

        # Dialogs
        "dialog.save": "Save",
        "dialog.cancel": "Cancel",
        "dialog.ok": "OK",
        "dialog.yes": "Yes",
        "dialog.no": "No",
        "dialog.error": "Error",
        "dialog.warning": "Warning",
        "dialog.info": "Information",
        "dialog.confirm": "Confirm",

        # Dialogs - Interruption
        "interruption.title": "Welcome Back",
        "interruption.message": "You were away for {minutes:.1f} minutes.",
        "interruption.question": "How should we handle this time?",
        "interruption.btn_break": "It was a Break\\n(Ignore time)",
        "interruption.btn_work": "I was working\\n(Add to current task)",

        # Dialogs - Task Edit
        "task_edit.title": "Edit Task",
        "task_edit.name": "Name:",
        "task_edit.accounting": "Accounting:",
        "task_edit.none": "None",

        # Dialogs - Manual Entry
        "manual_entry.title_add": "Add Manual Entry",
        "manual_entry.title_edit": "Edit Entry",
        "manual_entry.task": "Task:",
        "manual_entry.date": "Date:",
        "manual_entry.start_time": "Start Time:",
        "manual_entry.end_time": "End Time:",
        "manual_entry.notes": "Notes:",
        "manual_entry.notes_placeholder": "Optional notes...",
        "manual_entry.invalid_time_title": "Invalid Time",
        "manual_entry.invalid_time_msg_order": "End time must be after start time.",
        "manual_entry.invalid_time_msg_future": "Cannot add entries in the future.",

        # Report
        "report.title": "Generate Monthly Report",
        "report.period": "Report Period",
        "report.type": "Report Type",
        "report.template": "Template:",
        "report.output": "Output Settings",
        "report.no_file": "No file selected",
        "report.browse": "Browse...",
        "report.generate": "Generate Report",
        "report.save_title": "Save Report",
        "report.select_file_error": "Please select an output file.",
        "report.success": "Success",
        "report.saved_to": "Report saved to:\\n{path}",
        "report.failed": "Failed to generate report:\\n{error}",
        "report.generating": "Saving & Generating...",
        "report.done": "Done!",
        
        # Report Content
        "report.col_task": "Task name",
        "report.col_profile": "Accounting Profile",
        "report.col_total": "Total hours",
        "report.row_total": "Total Work",
        "report.row_target": "Daily Target",
        "report.row_overtime": "Overtime",
        "report.row_compliance": "Compliance Notes",
        "report.row_info": "Day Info",
        "report.unassigned_title": "Tasks without Accounting (not included in totals above)",

        # Notifications
        "notify.backup_complete": "Backup Complete",
        "notify.backup_success": "Automatic backup created successfully.",
        "notify.backup_failed": "Backup Failed",
        "notify.target_reached": "Target Reached!",
        "notify.target_message": "Congratulations! You have reached your daily target of {hours} hours.",
        "notify.limit_reached": "Maximum Limit Reached!",
        "notify.limit_message": "Warning: You have reached the maximum daily limit of {hours} hours.\nPlease stop working.",

        # Time formats
        "time.hours": "h",
        "time.minutes": "min",
        "time.backups": "backups",

        # Actions
        "action.edit": "Edit",
        "action.delete": "Delete",
        "error": "Error",

        # Missing History & Status
        "history.legend": "Legend:",
        "history.legend_hint": "(Right-click date to cycle)",
        "status.vacation": "Vacation",
        "status.sickness": "Sickness",
        "status.holiday": "Holiday",
        "time.hours_short": "h",
        "regulations.enable_compliance": "Enable German Compliance (10h limit)",
        "history.delete_confirm": "Are you sure you want to delete this entry?",
        "history.delete_failed": "Failed to delete entry",

        # Settings Messages
        "settings.backup_select_dir": "Select Backup Directory",
        "settings.backup_select_file": "Select Backup File",
        "settings.backup_complete_title": "Backup Complete",
        "settings.backup_complete_msg": "Backup created successfully:",
        "settings.backup_failed_title": "Backup Failed",
        "settings.backup_failed_msg": "Failed to create backup:",
        "settings.restore_confirm_title": "Confirm Restore",
        "settings.restore_confirm_msg": "⚠️ WARNING: This will REPLACE all current data!\\n\\nAll existing tasks, time entries, and accounting profiles\\nwill be permanently deleted and replaced with the backup.\\n\\nThis action cannot be undone.\\n\\nContinue with restore?",
        "settings.restore_complete_title": "Restore Complete",
        "settings.restore_complete_msg": "Backup restored successfully!",
        "settings.restore_details": "Restored items",
        "settings.restore_failed_title": "Restore Failed",
        "settings.restore_failed_msg": "Failed to restore backup:",
        "settings.no_selection_title": "No Selection",
        "settings.no_selection_msg": "Please select a backup to delete.",
        "settings.delete_confirm_title": "Confirm Delete",
        "settings.delete_confirm_msg": "Delete this backup?",
        "settings.deleted_title": "Deleted",
        "settings.deleted_msg": "Backup deleted successfully.",
        "settings.delete_failed_msg": "Failed to delete backup:",
    },

    "de": {
        # Application
        "app.name": "Zeiterfassung",
        "app.ready": "Zeiterfassung bereit",

        # Splash screen
        "splash.loading_preferences": "Einstellungen laden...",
        "splash.applying_theme": "Design anwenden...",
        "splash.initializing_db": "Datenbank initialisieren...",
        "splash.loading_tasks": "Aufgaben laden...",
        "splash.starting": "Anwendung starten...",

        # Tray menu
        "tray.show_window": "Fenster anzeigen",
        "tray.quit": "Beenden",

        # Main window
        "main.title": "Zeiterfassung",
        "main.task_placeholder": "Aufgabenname eingeben...",
        "main.start": "Start",
        "main.stop": "Stopp",
        "main.history": "Verlauf",
        "main.settings": "Einstellungen",

        # History window
        "history.title": "Monatsübersicht",
        "history.add_entry": "+ Manueller Eintrag",
        "history.manage_accounting": "Kostenstellen verwalten",
        "history.manage_tasks": "Aufgaben verwalten",
        "history.generate_report": "Bericht erstellen",
        "history.task": "Aufgabe",
        "history.start": "Start",
        "history.end": "Ende",
        "history.duration": "Dauer",
        "history.notes": "Notizen",
        "history.total": "Gesamt",
        "history.daily_summary": "Tageszusammenfassung",

        # Calendar/Legend
        "calendar.legend": "Legende:",
        "calendar.vacation": "Urlaub",
        "calendar.sickness": "Krankheit",
        "calendar.holiday": "Feiertag",
        "calendar.hint": "(Rechtsklick zum Wechseln)",

        # Work regulations
        "regulations.title": "Arbeitszeitregelung",
        "regulations.daily_target": "Tagesziel:",
        "regulations.german_compliance": "Deutsche Arbeitszeitregelung (10h Limit)",
        "regulations.check_breaks": "Pausenzeiten prüfen",
        "regulations.check_rest": "Ruhezeiten prüfen (11h)",

        # Settings dialog
        "settings.title": "Einstellungen",
        "settings.general": "Allgemein",
        "settings.backup": "Sicherung",

        # Settings - Appearance
        "settings.appearance": "Darstellung",
        "settings.theme": "Design:",
        "settings.theme_auto": "Systemeinstellung",
        "settings.theme_light": "Hell",
        "settings.theme_dark": "Dunkel",
        "settings.font_size": "Schriftgröße:",
        "settings.language": "Sprache:",
        "settings.language_en": "English",
        "settings.language_de": "Deutsch",

        # Settings - Behavior
        "settings.behavior": "Verhalten",
        "settings.auto_pause": "Automatisch pausieren bei Bildschirmsperre",
        "settings.ask_unlock": "Bei Entsperrung nach Abwesenheit fragen",
        "settings.pause_threshold": "Pausenschwelle:",

        # Settings - Regional
        "settings.regional": "Regional",
        "settings.german_state": "Bundesland:",
        "settings.respect_holidays": "Feiertage beachten",
        "settings.respect_weekends": "Wochenenden beachten",

        # Settings - System Tray
        "settings.system_tray": "Infobereich",
        "settings.show_seconds": "Sekunden im Symbol anzeigen",
        "settings.minimize_tray": "In den Infobereich minimieren",

        # Settings - Backup
        "settings.backup_auto": "Automatische Sicherung",
        "settings.backup_enable": "Automatische Sicherung aktivieren",
        "settings.backup_frequency": "Sicherungshäufigkeit:",
        "settings.backup_time": "Sicherungszeit:",
        "settings.backup_retention": "Behalten:",
        "settings.backup_location": "Speicherort:",
        "settings.backup_browse": "Durchsuchen...",
        "settings.backup_last": "Letzte Sicherung:",
        "settings.backup_never": "Nie",

        "settings.backup_manual": "Manuelle Sicherung & Wiederherstellung",
        "settings.backup_now": "Jetzt sichern",
        "settings.backup_restore": "Aus Sicherung wiederherstellen",
        "settings.backup_available": "Verfügbare Sicherungen:",
        "settings.backup_refresh": "🔄 Liste aktualisieren",
        "settings.backup_delete": "🗑️ Ausgewählte löschen",

        # Backup frequencies
        "backup.daily": "Täglich",
        "backup.every_3_days": "Alle 3 Tage",
        "backup.weekly": "Wöchentlich",
        "backup.every_2_weeks": "Alle 2 Wochen",
        "backup.monthly": "Monatlich",

        # Dialogs
        "dialog.save": "Speichern",
        "dialog.cancel": "Abbrechen",
        "dialog.ok": "OK",
        "dialog.yes": "Ja",
        "dialog.no": "Nein",
        "dialog.error": "Fehler",
        "dialog.warning": "Warnung",
        "dialog.info": "Information",
        "dialog.confirm": "Bestätigen",

        # Dialogs - Interruption
        "interruption.title": "Willkommen zurück",
        "interruption.message": "Sie waren für {minutes:.1f} Minuten abwesend.",
        "interruption.question": "Wie soll diese Zeit behandelt werden?",
        "interruption.btn_break": "Es war eine Pause\\n(Zeit ignorieren)",
        "interruption.btn_work": "Ich habe gearbeitet\\n(Zur Aufgabe hinzufügen)",

        # Dialogs - Task Edit
        "task_edit.title": "Aufgabe bearbeiten",
        "task_edit.name": "Name:",
        "task_edit.accounting": "Kostenstelle:",
        "task_edit.none": "Keine",

        # Dialogs - Manual Entry
        "manual_entry.title_add": "Manuellen Eintrag erstellen",
        "manual_entry.title_edit": "Eintrag bearbeiten",
        "manual_entry.task": "Aufgabe:",
        "manual_entry.date": "Datum:",
        "manual_entry.start_time": "Startzeit:",
        "manual_entry.end_time": "Endzeit:",
        "manual_entry.notes": "Notizen:",
        "manual_entry.notes_placeholder": "Optionale Notizen...",
        "manual_entry.invalid_time_title": "Ungültige Zeit",
        "manual_entry.invalid_time_msg_order": "Endzeit muss nach der Startzeit liegen.",
        "manual_entry.invalid_time_msg_future": "Einträge in der Zukunft sind nicht möglich.",

        # Report
        "report.title": "Monatsbericht erstellen",
        "report.period": "Berichtszeitraum",
        "report.type": "Berichtstyp",
        "report.template": "Vorlage:",
        "report.output": "Ausgabeeinstellungen",
        "report.no_file": "Keine Datei ausgewählt",
        "report.browse": "Durchsuchen...",
        "report.generate": "Bericht erstellen",
        "report.save_title": "Bericht speichern",
        "report.select_file_error": "Bitte wählen Sie eine Ausgabedatei.",
        "report.success": "Erfolg",
        "report.saved_to": "Bericht gespeichert unter:\\n{path}",
        "report.failed": "Berichtserstellung fehlgeschlagen:\\n{error}",
        "report.generating": "Speichern & Generieren...",
        "report.done": "Fertig!",

        # Report Content
        "report.col_task": "Aufgabenname",
        "report.col_profile": "Kostenstelle",
        "report.col_total": "Gesamtstunden",
        "report.row_total": "Gesamtarbeit",
        "report.row_target": "Tagesziel",
        "report.row_overtime": "Überstunden",
        "report.row_compliance": "Regelverstöße",
        "report.row_info": "Tagesinfo",
        "report.unassigned_title": "Aufgaben ohne Kostenstelle (nicht in Gesamtsumme enthalten)",

        # Notifications
        "notify.backup_complete": "Sicherung abgeschlossen",
        "notify.backup_success": "Automatische Sicherung erfolgreich erstellt.",
        "notify.backup_failed": "Sicherung fehlgeschlagen",
        "notify.target_reached": "Tagesziel erreicht!",
        "notify.target_message": "Herzlichen Glückwunsch! Sie haben Ihr Tagesziel von {hours} Stunden erreicht.",
        "notify.limit_reached": "Höchstarbeitszeit erreicht!",
        "notify.limit_message": "Warnung: Sie haben die maximale Tagesarbeitszeit von {hours} Stunden erreicht.\nBitte beenden Sie die Arbeit.",

        # Time formats
        "time.hours": "Std",
        "time.minutes": "Min",
        "time.backups": "Sicherungen",

        # Actions
        "action.edit": "Bearbeiten",
        "action.delete": "Löschen",
        "error": "Fehler",

        # Missing History & Status
        "history.legend": "Legende:",
        "history.legend_hint": "(Rechtsklick zum Wechseln)",
        "status.vacation": "Urlaub",
        "status.sickness": "Krankheit",
        "status.holiday": "Feiertag",
        "time.hours_short": "Std",
        "regulations.enable_compliance": "Deutsche Arbeitszeitregelung aktivieren (10h Limit)",
        "history.delete_confirm": "Möchten Sie diesen Eintrag wirklich löschen?",
        "history.delete_failed": "Eintrag konnte nicht gelöscht werden",

        # Settings Messages
        "settings.backup_select_dir": "Sicherungsverzeichnis auswählen",
        "settings.backup_select_file": "Sicherungsdatei auswählen",
        "settings.backup_complete_title": "Sicherung abgeschlossen",
        "settings.backup_complete_msg": "Sicherung erfolgreich erstellt:",
        "settings.backup_failed_title": "Sicherung fehlgeschlagen",
        "settings.backup_failed_msg": "Sicherung konnte nicht erstellt werden:",
        "settings.restore_confirm_title": "Wiederherstellung bestätigen",
        "settings.restore_confirm_msg": "⚠️ WARNUNG: Dies wird ALLE aktuellen Daten ERSETZEN!\\n\\nAlle vorhandenen Aufgaben, Zeiteinträge und Kostenstellen\\nwerden dauerhaft gelöscht und durch die Sicherung ersetzt.\\n\\nDiese Aktion kann nicht rückgängig gemacht werden.\\n\\nMit der Wiederherstellung fortfahren?",
        "settings.restore_complete_title": "Wiederherstellung abgeschlossen",
        "settings.restore_complete_msg": "Sicherung erfolgreich wiederhergestellt!",
        "settings.restore_details": "Wiederhergestellte Elemente",
        "settings.restore_failed_title": "Wiederherstellung fehlgeschlagen",
        "settings.restore_failed_msg": "Sicherung konnte nicht wiederhergestellt werden:",
        "settings.no_selection_title": "Keine Auswahl",
        "settings.no_selection_msg": "Bitte wählen Sie eine Sicherung zum Löschen aus.",
        "settings.delete_confirm_title": "Löschen bestätigen",
        "settings.delete_confirm_msg": "Diese Sicherung löschen?",
        "settings.deleted_title": "Gelöscht",
        "settings.deleted_msg": "Sicherung erfolgreich gelöscht.",
        "settings.delete_failed_msg": "Sicherung konnte nicht gelöscht werden:",
    }
}

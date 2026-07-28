import sys

from PySide6.QtWidgets import QApplication

from core.database.upgrade_guard import (
    MigrationGuardError,
    prepare_database_for_startup,
)
from core.dialogs.message_box import (
    configure_application_for_dialogs,
    install_unified_message_boxes,
    show_critical,
)
from core.widgets.no_wheel_guards import install_form_wheel_guards
from core.services.app_runtime_service import mark_application_started
from core.settings.settings_manager import settings
from core.theme import theme
from core.theme.app_style import apply_app_style
from core.resources.app_icon import load_app_icon
from core.version import APP_VERSION
from core.windows.main_window import MainWindow


def _show_startup_error(title: str, message: str) -> None:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationVersion(APP_VERSION)
        configure_application_for_dialogs(app)
        install_unified_message_boxes(app)
        install_form_wheel_guards(app)
    show_critical(None, title, message)


def main():
    # MIGRATION-0: předmigrační záloha (je-li třeba) před jakýmkoli zápisem schématu.
    try:
        prepare_database_for_startup()
    except MigrationGuardError as exc:
        _show_startup_error("Nelze spustit upgrade databáze", str(exc))
        sys.exit(1)

    mark_application_started()
    settings.load()
    theme.load(settings.get("theme", "default"))

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationVersion(APP_VERSION)
    # UX-DIALOG-1: prázdný display name + technický applicationName
    # → WM nepřidává „ — Manažer BOZP“ do dialogů.
    # Titulek hlavního okna zůstává app_display_name() přes setWindowTitle.
    configure_application_for_dialogs(app)
    install_unified_message_boxes(app)
    # UX-FORMS-1: kolečko myši nemění hodnoty combo/spin při rolování formuláře.
    install_form_wheel_guards(app)
    apply_app_style(app)

    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # BACKUP-2c: upozornění na nedokončenou obnovu (marker) před otevřením okna.
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        instance_backup_workflow_service,
    )

    instance_backup_workflow_service.check_recovery_markers_at_startup(None)

    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    if settings.get("window_maximized", True):
        window.showMaximized()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

import sys

from PySide6.QtWidgets import QApplication

from core.database.database_initializer import initialize_database
from core.services.app_runtime_service import mark_application_started
from core.settings.settings_manager import settings
from core.theme import theme
from core.theme.app_style import apply_app_style
from core.resources.app_icon import load_app_icon
from core.windows.main_window import MainWindow


def main():
    initialize_database()
    mark_application_started()
    settings.load()
    theme.load(settings.get("theme", "default"))

    app = QApplication(sys.argv)
    apply_app_style(app)

    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

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

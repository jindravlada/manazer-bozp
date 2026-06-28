import sys

from PySide6.QtWidgets import QApplication

from core.database.database_initializer import initialize_database
from core.settings.settings_manager import settings
from core.theme import theme
from core.theme.app_style import apply_app_style
from core.windows.main_window import MainWindow


def main():
    initialize_database()
    settings.load()
    theme.load(settings.get("theme", "default"))

    app = QApplication(sys.argv)
    apply_app_style(app)

    window = MainWindow()
    if settings.get("window_maximized", True):
        window.showMaximized()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

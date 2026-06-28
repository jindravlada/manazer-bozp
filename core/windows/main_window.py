from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.modules.module_manager import ModuleManager
from core.search.global_search_service import global_search_service


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manažer BOZP 3.0")
        self.resize(1280, 800)

        self.module_manager = ModuleManager()
        self._pages = {}
        self._page_widgets = {}
        self._search_results = {}

        self._create_toolbar()

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self._load_modules()

        layout.addWidget(self._sidebar())
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        status_bar = QStatusBar()
        status_bar.showMessage("Připraveno")
        self.setStatusBar(status_bar)

        self._show("dashboard")

    def _create_toolbar(self):
        toolbar = QToolBar("Hlavní")
        toolbar.setMovable(False)

        toolbar.addWidget(QLabel("Hledat: "))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Globální vyhledávání...")
        self.search_edit.setMaximumWidth(420)

        self.search_model = QStringListModel()
        self.search_completer = QCompleter(self.search_model, self)
        self.search_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_completer.setFilterMode(Qt.MatchContains)
        self.search_completer.setMaxVisibleItems(12)

        self.search_edit.setCompleter(self.search_completer)
        self.search_edit.textChanged.connect(self._update_global_search)
        self.search_completer.activated[str].connect(self._open_search_result)

        toolbar.addWidget(self.search_edit)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Uživatel: -"))
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Notifikace: 0"))

        self.addToolBar(toolbar)

    def _load_modules(self):
        for module in self.module_manager.get_modules():
            page = self._create_page(module)
            self._page_widgets[module.key] = page
            self._pages[module.key] = self.stack.addWidget(page)

    def _create_page(self, module):
        if module.key == "dashboard":
            from moduly.dashboard.ui.dashboard_page import DashboardPage
            return DashboardPage(open_tasks_callback=lambda: self._show("ukoly"))

        return module.page_factory()

    def _sidebar(self):
        frame = QFrame()
        frame.setObjectName("Sidebar")
        frame.setFixedWidth(250)

        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel("<b>Manažer BOZP 3.0</b>"))
        layout.addSpacing(10)

        self._add_sidebar_button(layout, "🏠 Pracovní plocha", "dashboard")
        layout.addSpacing(6)

        preferred_order = [
            "ukoly",
            "kniha_urazu",
            "kontroly",
            "audity",
            "proverky",
            "dokumentace",
            "statistiky",
        ]

        modules = {module.key: module for module in self.module_manager.get_modules()}

        for key in preferred_order:
            module = modules.get(key)
            if module is None:
                continue
            self._add_sidebar_button(layout, module.name, module.key, module.enabled)

        layout.addStretch()
        layout.addSpacing(8)
        self._add_separator(layout)

        settings_module = modules.get("nastaveni")
        if settings_module is not None:
            self._add_sidebar_button(
                layout,
                f"⚙️ {settings_module.name}",
                settings_module.key,
                settings_module.enabled,
            )

        return frame

    def _add_sidebar_button(self, layout, text: str, key: str, enabled: bool = True):
        button = QPushButton(text)
        button.setMinimumHeight(34)

        if enabled:
            button.clicked.connect(lambda _, module_key=key: self._show(module_key))
        else:
            button.setEnabled(False)

        layout.addWidget(button)

    def _add_separator(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

    def _show(self, key):
        if key in self._pages:
            widget = self._page_widgets.get(key)
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()

            self.stack.setCurrentIndex(self._pages[key])
            self.statusBar().showMessage(f"Otevřen modul: {key}")

    def _update_global_search(self, text: str):
        results = global_search_service.search(text)
        self._search_results = {result.display: result for result in results}
        self.search_model.setStringList(list(self._search_results.keys()))

        if len(text.strip()) >= 2 and results:
            self.search_completer.complete()

    def _open_search_result(self, display_text: str):
        result = self._search_results.get(display_text)

        if result is None:
            return

        self._show(result.module_key)
        self.search_edit.clear()
        self.statusBar().showMessage(f"Vyhledáno: {result.display}")

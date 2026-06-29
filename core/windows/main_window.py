from datetime import date

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.modules.module_manager import ModuleManager
from core.search.global_search_service import global_search_service


class MainWindow(QMainWindow):
    _COMPLETER_ROW_SEP = "\u2063"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manažer BOZP 3.0")
        self.resize(1280, 800)

        self.module_manager = ModuleManager()
        self._pages = {}
        self._page_widgets = {}
        self._search_results = []

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

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        toolbar.addWidget(QLabel(self._format_today_cs()))

        self.addToolBar(toolbar)

    def _format_today_cs(self) -> str:
        days = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"]
        today = date.today()
        return f"{days[today.weekday()]} {today.strftime('%d.%m.%Y')}"

    def _load_modules(self):
        for module in self.module_manager.get_modules():
            page = self._create_page(module)
            self._page_widgets[module.key] = page
            self._pages[module.key] = self.stack.addWidget(page)

    def _create_page(self, module):
        if module.key == "dashboard":
            from moduly.dashboard.ui.dashboard_page import DashboardPage
            return DashboardPage(
                open_tasks_callback=self._open_new_task,
                open_accidents_callback=self._open_new_accident,
                open_search_callback=self._focus_search,
                open_kontroly_callback=self._open_kontroly,
                open_kniha_urazu_callback=self._open_kniha_urazu,
            )

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

    def _open_new_task(self):
        self._show("ukoly")
        page = self._page_widgets.get("ukoly")
        if page is not None:
            page.new_task()

    def _open_new_accident(self):
        self._show("kniha_urazu")
        page = self._page_widgets.get("kniha_urazu")
        if page is not None:
            page.new_accident()

    def _open_kontroly(self):
        self._show("kontroly")

    def _open_kniha_urazu(self):
        self._show("kniha_urazu")

    def _focus_search(self):
        self.search_edit.setFocus()
        if self.search_edit.text():
            self.search_edit.selectAll()

    def _update_global_search(self, text: str):
        if self._completer_row_from_text(text) is not None:
            if len(text.strip()) >= 2 and self._search_results:
                self.search_completer.complete()
            return

        results = global_search_service.search(text)
        self._search_results = results
        self.search_model.setStringList([
            f"{result.display}{self._COMPLETER_ROW_SEP}{index}"
            for index, result in enumerate(results)
        ])

        if len(text.strip()) >= 2 and results:
            self.search_completer.complete()

    def _completer_row_from_text(self, text: str) -> int | None:
        if self._COMPLETER_ROW_SEP not in text:
            return None

        try:
            row = int(text.rsplit(self._COMPLETER_ROW_SEP, 1)[1])
        except ValueError:
            return None

        if row < 0 or row >= len(self._search_results):
            return None

        return row

    def _open_search_result(self, display_text: str):
        row = self._completer_row_from_text(display_text)
        if row is None:
            completion_model = self.search_completer.completionModel()
            index = self.search_completer.popup().currentIndex()
            if not index.isValid():
                index = self.search_completer.currentIndex()
            if not index.isValid():
                return

            source_index = completion_model.mapToSource(index)
            row = source_index.row()

        if row < 0 or row >= len(self._search_results):
            return

        result = self._search_results[row]

        self._show(result.module_key)
        if result.record_type == "task" and result.record_id is not None:
            page = self._page_widgets.get("ukoly")
            if page is not None:
                page.open_task(result.record_id)
        elif result.record_type == "accident" and result.record_id is not None:
            page = self._page_widgets.get("kniha_urazu")
            if page is not None:
                page.open_accident(result.record_id)
        elif result.record_type == "worker" and result.record_id is not None:
            page = self._page_widgets.get("nastaveni")
            if page is not None:
                page.open_worker(result.record_id)
        self.search_edit.clear()
        self.statusBar().showMessage(f"Vyhledáno: {result.display}")

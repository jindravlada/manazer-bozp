from datetime import date

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.modules.module_manager import ModuleManager
from core.navigation.source_navigator import source_navigator
from core.version import app_brand_label, app_display_name
from core.windows.about_dialog import AboutDialog
from core.search import global_search_service
from core.search.global_search_result import GlobalSearchResult
from core.search.ui.global_search_dialog import GlobalSearchDialog


class MainWindow(QMainWindow):
    _COMPLETER_ROW_SEP = "\u2063"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(app_display_name())
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

        source_navigator.configure(self)

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
        self.search_edit.returnPressed.connect(self._open_global_search_from_field)
        self.search_completer.activated[str].connect(self._open_search_result)

        toolbar.addWidget(self.search_edit)

        self.global_search_button = QPushButton("Globální vyhledávání")
        self.global_search_button.setToolTip("Globální vyhledávání (Ctrl+K)")
        self.global_search_button.clicked.connect(self._open_global_search_dialog)
        toolbar.addWidget(self.global_search_button)

        self._global_search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._global_search_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._global_search_shortcut.activated.connect(self._open_global_search_dialog)

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
                open_task_by_id_callback=self._open_task_by_id,
                open_attention_callback=self._open_attention_item,
                open_accidents_callback=self._open_new_accident,
                open_kontroly_callback=self._open_kontroly,
                open_kniha_urazu_callback=self._open_kniha_urazu,
                open_sprava_dat_callback=self._open_sprava_dat,
                refresh_sprava_dat_callback=self._refresh_sprava_dat_status,
            )

        if module.key == "kniha_urazu":
            from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage
            return KnihaUrazuPage(open_mu_investigation_callback=self._open_mu_from_accident)

        return module.page_factory()

    def _sidebar(self):
        frame = QFrame()
        frame.setObjectName("Sidebar")
        frame.setFixedWidth(250)

        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel(app_brand_label()))
        layout.addSpacing(10)

        self._add_sidebar_button(layout, "🏠 Pracovní plocha", "dashboard")
        layout.addSpacing(6)

        preferred_order = [
            "ukoly",
            "kniha_urazu",
            "vysetrovani_mu",
            "kontroly",
            "audity",
            "proverky",
            "pravni_pozadavky",
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

        sprava_dat_module = modules.get("sprava_dat")
        if sprava_dat_module is not None:
            self._add_sidebar_button(
                layout,
                sprava_dat_module.name,
                sprava_dat_module.key,
                sprava_dat_module.enabled,
            )

        settings_module = modules.get("nastaveni")
        if settings_module is not None:
            self._add_sidebar_button(
                layout,
                f"⚙️ {settings_module.name}",
                settings_module.key,
                settings_module.enabled,
            )

        about_button = QPushButton("O programu")
        about_button.setMinimumHeight(34)
        about_button.clicked.connect(self._show_about_dialog)
        layout.addWidget(about_button)

        return frame

    def _show_about_dialog(self) -> None:
        AboutDialog(self).exec()

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

    def _open_task_by_id(self, task_id: int) -> None:
        from moduly.ukoly.sluzby.task_service import task_service
        from moduly.ukoly.ui.task_dialog import TaskDialog

        task = task_service.get_task_by_id(task_id)
        dashboard = self._page_widgets.get("dashboard")

        if task is None:
            QMessageBox.warning(self, "Úkoly", "Opatření nebylo nalezeno.")
            if dashboard is not None and hasattr(dashboard, "refresh"):
                dashboard.refresh()
            return

        parent = dashboard if dashboard is not None else self
        dialog = TaskDialog(parent, task=task)
        if dialog.exec():
            data = dialog.get_data()
            if data["title"]:
                task_service.update_task(task_id=task_id, **data)

        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _open_attention_item(self, item) -> None:
        from core.dashboard.attention_item import (
            ITEM_TYPE_AUDIT,
            ITEM_TYPE_BOZP_INSPECTION,
            ITEM_TYPE_TASK,
        )

        item_type = getattr(item, "item_type", None)
        entity_id = getattr(item, "entity_id", None)
        if item_type == ITEM_TYPE_TASK and entity_id is not None:
            self._open_task_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_AUDIT and entity_id is not None:
            self._open_audit_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_BOZP_INSPECTION and entity_id is not None:
            self._open_inspection_by_id(entity_id)

    def _open_audit_by_id(self, audit_id: int) -> None:
        self._show("audity")
        page = self._page_widgets.get("audity")
        if page is not None and hasattr(page, "open_audit"):
            page.open_audit(audit_id)

        dashboard = self._page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _open_inspection_by_id(self, inspection_id: int) -> None:
        self._show("proverky")
        page = self._page_widgets.get("proverky")
        if page is not None and hasattr(page, "open_inspection"):
            page.open_inspection(inspection_id)

        dashboard = self._page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _open_new_accident(self):
        self._show("kniha_urazu")
        page = self._page_widgets.get("kniha_urazu")
        if page is not None:
            page.new_accident()

    def _open_kontroly(self):
        self._show("kontroly")

    def _open_kniha_urazu(self):
        self._show("kniha_urazu")

    def _open_sprava_dat(self, tab_key: str | None = None) -> None:
        self._show("sprava_dat")
        page = self._page_widgets.get("sprava_dat")
        if page is not None and tab_key:
            page.navigate_to_tab(tab_key)

    def _refresh_sprava_dat_status(self) -> None:
        page = self._page_widgets.get("sprava_dat")
        if page is not None and hasattr(page, "refresh_backup_status"):
            page.refresh_backup_status()

    def _open_mu_from_accident(self, accident_id: int):
        self._show("vysetrovani_mu")
        page = self._page_widgets.get("vysetrovani_mu")
        if page is not None:
            page.open_from_accident(accident_id)

    def _open_global_search_from_field(self) -> None:
        if not self.search_edit.text().strip():
            return
        self._open_global_search_dialog()

    def _open_global_search_dialog(self) -> None:
        dialog = GlobalSearchDialog(
            parent=self,
            search_service=global_search_service,
            initial_query=self.search_edit.text().strip(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.selected_result
            if result is not None:
                self._open_global_search_result(result)

    def _open_global_search_result(self, result: GlobalSearchResult) -> None:
        if global_search_service.open_result(result, self):
            self.statusBar().showMessage("Globální vyhledávání: výsledek otevřen")
        else:
            self.statusBar().showMessage("Globální vyhledávání: výsledek nelze otevřít")

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

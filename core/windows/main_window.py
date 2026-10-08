from datetime import date

from PySide6.QtCore import QSize, QStringListModel, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
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
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

# Strop minimální velikosti okna – musí jít zúžit pod šířku 1600×900.
_MAX_WINDOW_MIN_WIDTH = 1100
_MAX_WINDOW_MIN_HEIGHT = 650

from core.modules.module_manager import ModuleManager
from core.navigation.source_navigator import source_navigator
from core.version import app_brand_label, app_display_name
from core.windows.about_dialog import AboutDialog
from core.search import global_search_service
from core.search.global_search_result import GlobalSearchResult
from core.search.ui.global_search_dialog import GlobalSearchDialog


class MainWindow(QMainWindow):
    _COMPLETER_ROW_SEP = "\u2063"
    _SIDEBAR_ACTIVE_STYLE = (
        "QPushButton { background-color: #E3F2FD; border: 2px solid #93c5fd; }"
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle(app_display_name())
        self.resize(1280, 800)

        self.module_manager = ModuleManager()
        self._pages = {}
        self._page_widgets = {}
        self._sidebar_buttons: dict[str, QPushButton] = {}
        self._search_results = []
        self._electronic_exam_locked = False

        self._create_toolbar()

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._load_modules()

        self._workspace = QWidget()
        layout = QHBoxLayout(self._workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._sidebar_panel = self._sidebar()
        layout.addWidget(self._sidebar_panel)
        layout.addWidget(self.stack, 1)

        self._exam_cover = QLabel("Probíhá elektronický test.")
        self._exam_cover.setObjectName("electronic-exam-cover")
        self._exam_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exam_cover.setStyleSheet("font-size: 22px;")

        self._workspace_stack = QStackedWidget()
        self._workspace_stack.addWidget(self._workspace)
        self._workspace_stack.addWidget(self._exam_cover)
        outer.addWidget(self._workspace_stack)

        self.setCentralWidget(central)

        status_bar = QStatusBar()
        status_bar.showMessage("Připraveno")
        self.setStatusBar(status_bar)

        source_navigator.configure(self)

        # Explicitní strop: layout/modul nesmí vynutit min. šířku nad obrazovku.
        self.setMinimumSize(0, 0)

        self._show("dashboard")

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(
            min(max(hint.width(), 0), _MAX_WINDOW_MIN_WIDTH),
            min(max(hint.height(), 0), _MAX_WINDOW_MIN_HEIGHT),
        )

    def _create_toolbar(self):
        toolbar = QToolBar("Hlavní")
        toolbar.setMovable(False)
        self._main_toolbar = toolbar

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
            self._pages[module.key] = self.stack.addWidget(
                self._host_module_page(module.key, page)
            )

    def _host_module_page(self, key: str, page: QWidget) -> QWidget:
        """Vlož stránku do stacku bez propagace její minimální velikosti do okna.

        QStackedWidget bere maximum minimumSizeHint všech stránek a všechny
        se načítají při startu. Široké toolbary (Prověrky, Audity, …) by jinak
        držely hlavní okno nad šířkou menších displejů (např. 1600×900).
        Dashboard už má vlastní QScrollArea; ostatní stránky obalíme scroll area.
        """
        if key == "dashboard":
            return page

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        scroll.setWidget(page)
        return scroll

    def _create_page(self, module):
        if module.key == "dashboard":
            from moduly.dashboard.ui.dashboard_page import DashboardPage
            return DashboardPage(
                open_tasks_callback=self._open_new_task,
                open_new_meeting_callback=self._open_new_meeting,
                open_task_by_id_callback=self._open_task_by_id,
                open_attention_callback=self._open_attention_item,
                open_accidents_callback=self._open_new_accident,
                open_kontroly_callback=self._open_kontroly,
                open_kniha_urazu_callback=self._open_kniha_urazu,
                open_agenda_callback=self._open_agenda_from_dashboard,
                open_sprava_dat_callback=self._open_sprava_dat,
                refresh_sprava_dat_callback=self._refresh_sprava_dat_status,
                open_exam_validity_callback=self._open_exam_validity_from_dashboard,
            )

        if module.key == "kniha_urazu":
            from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage
            return KnihaUrazuPage(open_mu_investigation_callback=self._open_mu_from_accident)

        if module.key == "schuzky":
            from moduly.schuzky.ui.schuzky_page import SchuzkyPage

            page = SchuzkyPage()
            page.set_dashboard_refresh_callback(self._refresh_dashboard_and_agenda)
            return page

        if module.key == "agenda":
            from moduly.agenda.ui.agenda_page import AgendaPage

            page = AgendaPage(open_attention_callback=self._open_attention_item)
            page.set_dashboard_refresh_callback(self._refresh_dashboard_and_agenda)
            return page

        if module.key == "smlouvy_ozo":
            from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage

            page = SmlouvyOzoPage()
            page.set_dashboard_refresh_callback(self._refresh_dashboard_and_agenda)
            return page

        return module.page_factory()

    def _refresh_dashboard_page(self) -> None:
        dashboard = self._page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _refresh_dashboard_and_agenda(self) -> None:
        self._refresh_dashboard_page()
        agenda = self._page_widgets.get("agenda")
        if agenda is not None and hasattr(agenda, "refresh"):
            agenda.refresh()

    def _open_agenda_from_dashboard(self) -> None:
        page = self._page_widgets.get("agenda")
        if page is not None and hasattr(page, "apply_workspace_filters"):
            page.apply_workspace_filters()
        self._show("agenda")

    def _open_exam_validity_from_dashboard(self) -> None:
        module = next(
            (item for item in self.module_manager.get_modules() if item.key == "testy"),
            None,
        )
        if module is None or not module.enabled:
            return
        self._show("testy")
        page = self._page_widgets.get("testy")
        show_validity = getattr(page, "show_validity_tab", None)
        if callable(show_validity):
            show_validity()

    def _sidebar(self):
        frame = QFrame()
        frame.setObjectName("Sidebar")
        frame.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )

        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel(app_brand_label()))
        layout.addSpacing(10)

        self._add_sidebar_button(layout, "🏠 Pracovní plocha", "dashboard")
        layout.addSpacing(6)

        preferred_order = [
            "agenda",
            "kniha_urazu",
            "vysetrovani_mu",
            "kontroly",
            "audity",
            "proverky",
            "rizeni_rizik",
            "koordinace_bozp",
            "pravni_pozadavky",
            "testy",
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

        smlouvy_ozo_module = modules.get("smlouvy_ozo")
        if smlouvy_ozo_module is not None:
            self._add_sidebar_button(
                layout,
                smlouvy_ozo_module.name,
                smlouvy_ozo_module.key,
                smlouvy_ozo_module.enabled,
            )

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

        # Scroll při nižší výšce okna – součet tlačítek nesmí držet min. výšku MainWindow.
        scroll = QScrollArea()
        scroll.setObjectName("SidebarScroll")
        scroll.setFixedWidth(250)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Ignored,
        )
        scroll.setWidget(frame)
        return scroll

    def _show_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def _add_sidebar_button(self, layout, text: str, key: str, enabled: bool = True):
        button = QPushButton(text)
        button.setMinimumHeight(34)

        if enabled:
            button.clicked.connect(lambda _, module_key=key: self._show(module_key))
        else:
            button.setEnabled(False)

        self._sidebar_buttons[key] = button
        layout.addWidget(button)

    def _add_separator(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

    def _update_sidebar_active(self, active_key: str) -> None:
        for key, button in self._sidebar_buttons.items():
            if key == active_key:
                button.setStyleSheet(self._SIDEBAR_ACTIVE_STYLE)
            else:
                button.setStyleSheet("")
            style = button.style()
            style.unpolish(button)
            style.polish(button)
            button.update()

    def _confirm_unsaved_employer_edit(self) -> bool:
        """Neuložené údaje zaměstnavatele chrání přechod modulu i zavření okna."""
        page = self._page_widgets.get("nastaveni")
        confirm = getattr(page, "confirm_leave_employer_edit", None)
        if not callable(confirm):
            return True
        return bool(confirm())

    def set_electronic_exam_lock(self, locked: bool) -> None:
        """Schová navigaci Manažera po dobu elektronického testu.

        Neblokuje klávesy operačního systému. Návrat do administrace
        není součástí tohoto kroku.
        """
        self._electronic_exam_locked = bool(locked)
        self._sidebar_panel.setVisible(not locked)
        self._main_toolbar.setVisible(not locked)
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.setVisible(not locked)
        self._global_search_shortcut.setEnabled(not locked)
        if locked:
            self._workspace_stack.setCurrentWidget(self._exam_cover)
        else:
            self._workspace_stack.setCurrentWidget(self._workspace)

    def restore_after_written_exam(self, exam_id: int) -> None:
        """Po předání počítače vrátí Manažer na záložku Zkoušky."""
        self.set_electronic_exam_lock(False)
        self._show("testy")
        page = self.current_page_widget()
        focus = getattr(page, "show_exams_tab", None)
        if callable(focus):
            focus(int(exam_id))
        self.show()
        self.raise_()
        self.activateWindow()

    def _show(self, key):
        if self._electronic_exam_locked:
            return
        if key not in self._pages:
            return
        if not self._confirm_unsaved_employer_edit():
            return

        widget = self._page_widgets.get(key)
        if widget is not None and hasattr(widget, "refresh"):
            widget.refresh()

        self.stack.setCurrentIndex(self._pages[key])
        self._update_sidebar_active(key)
        self.statusBar().showMessage(f"Otevřen modul: {key}")

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._electronic_exam_locked and event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._electronic_exam_locked:
            event.ignore()
            return
        if not self._confirm_unsaved_employer_edit():
            event.ignore()
            return
        super().closeEvent(event)

    def current_page_widget(self) -> QWidget | None:
        """Aktuální stránka modulu (bez případného QScrollArea wrapperu ve stacku)."""
        current = self.stack.currentWidget()
        if isinstance(current, QScrollArea):
            return current.widget()
        return current

    def open_hazard_library_template(self, template_id: int) -> None:
        self._show("rizeni_rizik")
        page = self._page_widgets.get("rizeni_rizik")
        if page is not None and hasattr(page, "open_library_template_editor"):
            page.open_library_template_editor(template_id)

    def _open_new_task(self):
        from moduly.ukoly.ui.task_dialog import TaskDialog

        dashboard = self._page_widgets.get("dashboard")
        parent = dashboard if dashboard is not None else self
        dialog = TaskDialog(parent)
        dialog.exec()
        self._refresh_dashboard_and_agenda()

    def _open_new_meeting(self) -> None:
        from core.widgets.dialog_utils import exec_maximized
        from moduly.schuzky.sluzby.meeting_agenda_item_service import (
            meeting_agenda_item_service,
        )
        from moduly.schuzky.sluzby.meeting_service import (
            MeetingValidationError,
            meeting_service,
        )
        from moduly.schuzky.ui.meeting_dialog import MeetingDialog

        dashboard = self._page_widgets.get("dashboard")
        parent = dashboard if dashboard is not None else self
        dialog = MeetingDialog(parent)
        if not exec_maximized(dialog):
            return
        try:
            meeting = meeting_service.create_meeting(**dialog.get_data())
            meeting_agenda_item_service.save_items(meeting.id, dialog.get_agenda_items())
        except MeetingValidationError as error:
            QMessageBox.warning(self, "Události", str(error))
            return
        self._refresh_dashboard_and_agenda()

    def _open_task_by_id(self, task_id: int) -> None:
        from moduly.ukoly.sluzby.task_service import task_service
        from moduly.ukoly.ui.task_dialog import TaskDialog

        task = task_service.get_task_by_id(task_id)
        dashboard = self._page_widgets.get("dashboard")

        if task is None:
            QMessageBox.warning(self, "Úkoly", "Opatření nebylo nalezeno.")
            self._refresh_dashboard_and_agenda()
            return

        parent = dashboard if dashboard is not None else self
        dialog = TaskDialog(parent, task=task)
        dialog.exec()
        self._refresh_dashboard_and_agenda()

    def _open_attention_item(self, item) -> None:
        from core.dashboard.attention_item import (
            ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE,
            ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
            ITEM_TYPE_ACCIDENT_SIGNED_RECORD,
            ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION,
            ITEM_TYPE_AUDIT,
            ITEM_TYPE_EXTERNAL_AUDIT,
            ITEM_TYPE_EXTERNAL_AUDIT_NC,
            ITEM_TYPE_EXTERNAL_AUDIT_PKZ,
            ITEM_TYPE_INSPECTION,
            ITEM_TYPE_MEETING,
            ITEM_TYPE_OZO_CONTRACT,
            ITEM_TYPE_OZO_PERSON_CERTIFICATE,
            ITEM_TYPE_PERIODIC,
            ITEM_TYPE_QUALIFICATION_CERTIFICATE,
            ITEM_TYPE_STATE_SUPERVISION,
            ITEM_TYPE_TASK,
            ITEM_TYPE_YEARLY_PLAN_MONTH,
        )

        item_type = getattr(item, "item_type", None) or getattr(item, "source_type", None)
        entity_id = getattr(item, "source_id", None)
        if entity_id is None:
            entity_id = getattr(item, "entity_id", None)
        if item_type == ITEM_TYPE_TASK and entity_id is not None:
            self._open_task_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_EXTERNAL_AUDIT and entity_id is not None:
            metadata = getattr(item, "open_metadata", None) or {}
            self._open_external_audit_by_id(
                int(entity_id),
                focus_tab=metadata.get("focus_tab") or "spis",
                focus_visit_date=metadata.get("visit_date"),
            )
            return
        if item_type in {
            ITEM_TYPE_EXTERNAL_AUDIT_NC,
            ITEM_TYPE_EXTERNAL_AUDIT_PKZ,
        } and entity_id is not None:
            metadata = getattr(item, "open_metadata", None) or {}
            audit_id = metadata.get("audit_id")
            if audit_id is None:
                QMessageBox.information(
                    self,
                    "Externí audity",
                    "Zjištění už není dostupné. Seznam bude obnoven.",
                )
                self._refresh_dashboard_and_agenda()
                return
            self._open_external_audit_by_id(
                int(audit_id),
                focus_tab="findings",
                focus_finding_id=int(entity_id),
                focus_finding_type=metadata.get("finding_type"),
            )
            return
        if item_type == ITEM_TYPE_AUDIT and entity_id is not None:
            self._open_audit_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_INSPECTION and entity_id is not None:
            self._open_inspection_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_MEETING and entity_id is not None:
            self._open_meeting_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_PERIODIC and entity_id is not None:
            self._open_periodic_activity_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_OZO_CONTRACT and entity_id is not None:
            self._open_ozo_contract_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_OZO_PERSON_CERTIFICATE:
            self._open_ozo_person()
            return
        if item_type == ITEM_TYPE_QUALIFICATION_CERTIFICATE and entity_id is not None:
            self._open_qualification_certificate_by_id(entity_id)
            return
        if item_type == ITEM_TYPE_YEARLY_PLAN_MONTH:
            metadata = getattr(item, "open_metadata", None) or {}
            year = metadata.get("year")
            month = metadata.get("month")
            if year is None or month is None:
                today = date.today()
                year = today.year
                month = today.month
            self._open_yearly_plan_month(int(year), int(month))
            return
        if item_type == ITEM_TYPE_STATE_SUPERVISION and entity_id is not None:
            metadata = getattr(item, "open_metadata", None) or {}
            supervision_id = metadata.get("supervision_id", entity_id)
            self._open_state_supervision_by_id(
                int(supervision_id),
                target_tab=metadata.get("target_tab"),
                focus_kind=metadata.get("kind"),
                focus_child_id=metadata.get("child_id"),
            )
            return
        if item_type == ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION and entity_id is not None:
            metadata = getattr(item, "open_metadata", None) or {}
            self._open_accident_reporting_by_id(
                int(entity_id),
                focus_obligation_key=metadata.get("obligation_key"),
            )
            return
        if item_type in {
            ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE,
            ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
            ITEM_TYPE_ACCIDENT_SIGNED_RECORD,
        } and entity_id is not None:
            metadata = getattr(item, "open_metadata", None) or {}
            self._open_accident_by_id(
                int(entity_id),
                focus_tab=metadata.get("focus_tab"),
            )

    def _open_external_audit_by_id(
        self,
        audit_id: int,
        *,
        focus_tab: str | None = None,
        focus_visit_date=None,
        focus_finding_id: int | None = None,
        focus_finding_type: str | None = None,
    ) -> None:
        from core.widgets.dialog_utils import exec_maximized
        from moduly.externi_audity.sluzby.external_audit_service import (
            ExternalAuditError,
            external_audit_service,
        )
        from moduly.externi_audity.ui.external_audit_editor_dialog import (
            ExternalAuditEditorDialog,
        )

        try:
            external_audit_service.get_by_id(int(audit_id))
        except ExternalAuditError:
            QMessageBox.information(
                self,
                "Externí audity",
                "Externí audit už není dostupný. Seznam bude obnoven.",
            )
            self._refresh_dashboard_and_agenda()
            return

        dashboard = self._page_widgets.get("dashboard")
        parent = dashboard if dashboard is not None else self
        dialog = ExternalAuditEditorDialog(
            parent,
            audit_id=int(audit_id),
            focus_tab=focus_tab,
            focus_visit_date=focus_visit_date,
            focus_finding_id=focus_finding_id,
            focus_finding_type=focus_finding_type,
        )
        exec_maximized(dialog)
        self._refresh_dashboard_and_agenda()

    def _open_audit_by_id(self, audit_id: int) -> None:
        from moduly.audity.sluzby.audit_service import audit_service

        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, "Audity", "Audit nebyl nalezen.")
            dashboard = self._page_widgets.get("dashboard")
            if dashboard is not None and hasattr(dashboard, "refresh"):
                dashboard.refresh()
            return

        self._show("audity")
        page = self._page_widgets.get("audity")
        if page is not None and hasattr(page, "open_audit"):
            page.open_audit(audit_id)

        dashboard = self._page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _open_inspection_by_id(self, inspection_id: int) -> None:
        from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service

        inspection = bozp_inspection_service.get_by_id(inspection_id)
        if inspection is None:
            QMessageBox.warning(self, "Prověrky", "Prověrka nebyla nalezena.")
            dashboard = self._page_widgets.get("dashboard")
            if dashboard is not None and hasattr(dashboard, "refresh"):
                dashboard.refresh()
            return

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

    def _open_accident_reporting_by_id(
        self,
        accident_id: int,
        *,
        focus_obligation_key: str | None = None,
    ) -> None:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Kniha úrazů", "Úraz nebyl nalezen.")
            dashboard = self._page_widgets.get("dashboard")
            if dashboard is not None and hasattr(dashboard, "refresh"):
                dashboard.refresh()
            return

        self._show("kniha_urazu")
        page = self._page_widgets.get("kniha_urazu")
        if page is not None and hasattr(page, "open_investigation"):
            page.open_investigation(
                accident_id,
                focus_obligation_key=focus_obligation_key,
            )

        dashboard = self._page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _open_accident_by_id(self, accident_id: int, *, focus_tab: str | None = None) -> None:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Kniha úrazů", "Úraz nebyl nalezen.")
            dashboard = self._page_widgets.get("dashboard")
            if dashboard is not None and hasattr(dashboard, "refresh"):
                dashboard.refresh()
            return

        self._show("kniha_urazu")
        page = self._page_widgets.get("kniha_urazu")
        if page is not None and hasattr(page, "open_accident"):
            page.open_accident(accident_id, focus_tab=focus_tab)

        dashboard = self._page_widgets.get("dashboard")
        if dashboard is not None and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _open_kontroly(self):
        self._show("kontroly")

    def _open_meeting_by_id(self, meeting_id: int) -> None:
        from moduly.schuzky.sluzby.meeting_agenda_item_service import (
            meeting_agenda_item_service,
        )
        from moduly.schuzky.sluzby.meeting_service import (
            MeetingValidationError,
            meeting_service,
        )
        from moduly.schuzky.ui.meeting_dialog import MeetingDialog

        meeting = meeting_service.get_by_id(meeting_id)
        dashboard = self._page_widgets.get("dashboard")

        if meeting is None:
            QMessageBox.warning(self, "Události", "Událost nebyla nalezena.")
            self._refresh_dashboard_and_agenda()
            return

        parent = dashboard if dashboard is not None else self
        dialog = MeetingDialog(parent, meeting=meeting)
        from core.widgets.dialog_utils import exec_maximized

        if exec_maximized(dialog):
            try:
                meeting_service.update_meeting(meeting_id, **dialog.get_data())
                meeting_agenda_item_service.save_items(
                    meeting_id,
                    dialog.get_agenda_items(),
                )
            except MeetingValidationError as error:
                QMessageBox.warning(self, "Události", str(error))

        self._refresh_dashboard_and_agenda()

    def _open_periodic_activity_by_id(self, activity_id: int) -> None:
        from moduly.periodicke_cinnosti.constants import TAB_PERIODIC
        from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
            periodic_activity_service,
        )

        activity = periodic_activity_service.get_by_id(activity_id)
        if activity is None:
            QMessageBox.warning(self, TAB_PERIODIC, "Periodická činnost nebyla nalezena.")
            self._refresh_dashboard_and_agenda()
            return

        self._show("agenda")
        page = self._page_widgets.get("agenda")
        if page is not None and hasattr(page, "open_periodic_activity"):
            page.open_periodic_activity(activity_id)

        self._refresh_dashboard_and_agenda()

    def _open_yearly_plan_month(self, year: int, month: int) -> None:
        self._show("agenda")
        page = self._page_widgets.get("agenda")
        if page is not None and hasattr(page, "open_yearly_plan"):
            page.open_yearly_plan(year, month)
        self._refresh_dashboard_and_agenda()

    def _open_state_supervision_by_id(
        self,
        supervision_id: int,
        *,
        target_tab: str | None = None,
        focus_kind: str | None = None,
        focus_child_id: int | None = None,
    ) -> None:
        from moduly.statni_dozor.constants import ITEM_NOT_FOUND_MESSAGE, MODULE_NAME
        from moduly.statni_dozor.sluzby.state_supervision_service import (
            state_supervision_service,
        )

        record = state_supervision_service.get_supervision(supervision_id)
        if record is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self._refresh_dashboard_and_agenda()
            return

        self._show("agenda")
        page = self._page_widgets.get("agenda")
        if page is not None and hasattr(page, "open_supervision"):
            page.open_supervision(
                supervision_id,
                target_tab=target_tab,
                focus_kind=focus_kind,
                focus_child_id=focus_child_id,
            )
        self._refresh_dashboard_and_agenda()

    def _open_ozo_contract_by_id(self, contract_id: int) -> None:
        from moduly.smlouvy_ozo.constants import MODULE_NAME, ITEM_NOT_FOUND_MESSAGE
        from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service

        contract = ozo_contract_service.get_by_id(contract_id)
        if contract is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self._refresh_dashboard_and_agenda()
            return

        self._show("smlouvy_ozo")
        page = self._page_widgets.get("smlouvy_ozo")
        if page is not None and hasattr(page, "open_contract"):
            page.open_contract(contract_id)
        self._refresh_dashboard_and_agenda()

    def _open_ozo_person(self) -> None:
        self._show("smlouvy_ozo")
        page = self._page_widgets.get("smlouvy_ozo")
        if page is not None and hasattr(page, "edit_ozo_person"):
            page.edit_ozo_person()
        self._refresh_dashboard_and_agenda()

    def _open_qualification_certificate_by_id(self, certificate_id: int) -> None:
        self._show("smlouvy_ozo")
        page = self._page_widgets.get("smlouvy_ozo")
        if page is not None and hasattr(page, "open_qualification_certificate"):
            page.open_qualification_certificate(certificate_id)
        self._refresh_dashboard_and_agenda()

    def _open_schuzky(self):
        self._show("schuzky")

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

        if result.record_type == "task" and result.record_id is not None:
            self._show("agenda")
            page = self._page_widgets.get("agenda")
            if page is not None:
                page.open_task(result.record_id)
        elif result.record_type == "accident" and result.record_id is not None:
            self._show(result.module_key)
            page = self._page_widgets.get("kniha_urazu")
            if page is not None:
                page.open_accident(result.record_id)
        elif result.record_type == "worker" and result.record_id is not None:
            self._show(result.module_key)
            page = self._page_widgets.get("nastaveni")
            if page is not None:
                page.open_worker(result.record_id)
        else:
            self._show(result.module_key)
        self.search_edit.clear()
        self.statusBar().showMessage(f"Vyhledáno: {result.display}")

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.services.backup_service import (
    BACKUP_TYPE_CATALOGS_TEMPLATES,
    BACKUP_TYPE_DATABASE,
    BACKUP_TYPE_FULL,
    BACKUP_TYPE_LABELS,
    BACKUP_TYPE_RESTORE_LABELS,
    backup_service,
)

from core.dashboard import (
    AccidentsWidget,
    CalendarPlaceholderWidget,
    ControlsWidget,
    DaysWithoutAccidentWidget,
    RecentActivityWidget,
    StatisticsPlaceholderWidget,
    SummaryWidget,
    TodayWidget,
    UpcomingTasksWidget,
)


class DashboardPage(QWidget):
    """
    Pracovní plocha Manažer BOZP 3.0.
    Dashboard je složený z menších widgetů.
    """

    def __init__(
        self,
        open_tasks_callback=None,
        open_accidents_callback=None,
        open_search_callback=None,
        open_kontroly_callback=None,
        open_kniha_urazu_callback=None,
    ) -> None:
        super().__init__()
        self.open_tasks_callback = open_tasks_callback
        self.open_accidents_callback = open_accidents_callback
        self.open_search_callback = open_search_callback
        self.open_kontroly_callback = open_kontroly_callback
        self.open_kniha_urazu_callback = open_kniha_urazu_callback

        self.setStyleSheet("""
            QFrame#HeaderCard,
            QFrame#DashboardPanel,
            QFrame#DashboardCard {
                border: 1px solid #d6dce5;
                border-radius: 10px;
                background: #ffffff;
            }

            QLabel#PageTitle {
                font-size: 28px;
                font-weight: 700;
                color: #174a8b;
            }

            QLabel#InfoText {
                color: #555;
            }

            QLabel#DashboardCardTitle,
            QLabel#DashboardPanelTitle {
                font-weight: 700;
                color: #174a8b;
            }

            QLabel#DashboardCardValue {
                font-size: 28px;
                font-weight: 800;
            }

            QLabel#DashboardCardSubtitle {
                color: #666;
            }

            QPushButton#QuickButton {
                min-height: 34px;
                font-weight: 600;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        root_layout.addWidget(self.scroll_area)

        content = QWidget()
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        self.days_without_accident = DaysWithoutAccidentWidget(compact=True)
        top_row.addWidget(self._create_header(), 0)
        top_row.addWidget(self._create_vertical_separator())
        top_row.addWidget(self.days_without_accident, 1)
        top_row.addWidget(self._create_quick_actions(), 0)
        layout.addLayout(top_row)

        self.summary = SummaryWidget()
        layout.addWidget(self.summary)

        grid = QGridLayout()
        grid.setSpacing(14)

        self.today = TodayWidget()
        self.upcoming = UpcomingTasksWidget(open_tasks_callback=self.open_tasks_callback)
        self.calendar = CalendarPlaceholderWidget()
        self.activity = RecentActivityWidget()
        self.stats = StatisticsPlaceholderWidget()
        self.controls = ControlsWidget(open_kontroly_callback=self.open_kontroly_callback)
        self.accidents = AccidentsWidget(open_kniha_urazu_callback=self.open_kniha_urazu_callback)

        # Pevné výšky u panelů, které nemají roztahovat celou pracovní plochu.
        self.today.setFixedHeight(170)
        self.calendar.setFixedHeight(280)
        self.stats.setFixedHeight(130)
        self.controls.setFixedHeight(170)
        self.accidents.setFixedHeight(170)
        self.upcoming.setMinimumHeight(260)
        self.activity.setMinimumHeight(220)

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)
        right_layout.addWidget(self.calendar)
        right_layout.addWidget(self.stats)
        right_layout.addWidget(self.controls)
        right_layout.addWidget(self.accidents)
        right_layout.addStretch(1)

        grid.addWidget(self.today, 0, 0)
        grid.addWidget(right_column, 0, 1, 3, 1)
        grid.addWidget(self.upcoming, 1, 0)
        grid.addWidget(self.activity, 2, 0)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 0)
        grid.setRowStretch(2, 0)

        layout.addLayout(grid)
        layout.addStretch(1)

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderCard")
        header.setFixedHeight(92)
        header.setMinimumWidth(280)

        layout = QVBoxLayout(header)
        layout.setContentsMargins(18, 14, 18, 14)

        title = QLabel("Pracovní plocha")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Dobrý den. Co dnes budeme řešit?")
        subtitle.setObjectName("InfoText")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return header

    def _create_vertical_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(72)
        return line

    def _create_quick_actions(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DashboardPanel")
        panel.setFixedHeight(92)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        buttons = [
            ("+ Úraz", True),
            ("✓ Úkol", True),
            ("📋 Kontrola", True),
            ("🔎 Hledat", True),
            ("💾 Záloha", True),
            ("♻ Obnova", True),
        ]

        for text, enabled in buttons:
            button = QPushButton(text)
            button.setObjectName("QuickButton")
            button.setEnabled(enabled)

            if text == "+ Úraz" and self.open_accidents_callback:
                button.clicked.connect(self.open_accidents_callback)
            elif text == "✓ Úkol" and self.open_tasks_callback:
                button.clicked.connect(self.open_tasks_callback)
            elif text == "🔎 Hledat" and self.open_search_callback:
                button.clicked.connect(self.open_search_callback)
            elif text == "📋 Kontrola" and self.open_kontroly_callback:
                button.clicked.connect(self.open_kontroly_callback)
            elif text == "📋 Kontrola":
                button.clicked.connect(self.show_kontroly_info)
            elif text == "💾 Záloha":
                self._setup_backup_menu(button)
            elif text == "♻ Obnova":
                self._setup_restore_menu(button)

            layout.addWidget(button)

        layout.addStretch()
        return panel

    def show_kontroly_info(self):
        QMessageBox.information(self, "Kontroly", "Modul Kontroly zatím není aktivní.")

    def _setup_backup_menu(self, button: QPushButton) -> None:
        menu = QMenu(button)
        for backup_type in (BACKUP_TYPE_FULL, BACKUP_TYPE_DATABASE, BACKUP_TYPE_CATALOGS_TEMPLATES):
            action = menu.addAction(BACKUP_TYPE_LABELS[backup_type])
            action.triggered.connect(
                lambda _checked=False, t=backup_type: self.create_backup(t)
            )
        button.setMenu(menu)

    def _setup_restore_menu(self, button: QPushButton) -> None:
        menu = QMenu(button)
        for restore_type in (BACKUP_TYPE_FULL, BACKUP_TYPE_DATABASE, BACKUP_TYPE_CATALOGS_TEMPLATES):
            action = menu.addAction(BACKUP_TYPE_RESTORE_LABELS[restore_type])
            action.triggered.connect(
                lambda _checked=False, t=restore_type: self.restore_backup(t)
            )
        button.setMenu(menu)

    def create_backup(self, backup_type: str = BACKUP_TYPE_FULL):
        label = BACKUP_TYPE_LABELS[backup_type]
        default_path = str(backup_service.default_backup_path(backup_type))
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Uložit – {label}",
            default_path,
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".zip"):
            file_path += ".zip"

        try:
            result = backup_service.create_backup(file_path, backup_type=backup_type)
        except Exception as exc:
            QMessageBox.critical(self, label, f"Zálohu se nepodařilo vytvořit.\n\n{exc}")
            return

        QMessageBox.information(self, label, f"Záloha byla vytvořena:\n{result}")

    def _restore_confirmation_text(self, restore_type: str) -> str:
        safety = "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu.\n\n"
        if restore_type == BACKUP_TYPE_FULL:
            return (
                "Obnova přepíše celé pracovní prostředí: databázi, přílohy, exporty, "
                "šablony a editovatelné číselníky.\n"
                f"{safety}Pokračovat?"
            )
        if restore_type == BACKUP_TYPE_DATABASE:
            return (
                "Obnova přepíše pouze databázi. Číselníky a šablony zůstanou beze změny.\n"
                f"{safety}Pokračovat?"
            )
        return (
            "Obnova přepíše editovatelné číselníky a uživatelské šablony. "
            "Databáze zůstane beze změny.\n"
            f"{safety}Pokračovat?"
        )

    def restore_backup(self, restore_type: str = BACKUP_TYPE_FULL):
        label = BACKUP_TYPE_RESTORE_LABELS[restore_type]
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Vybrat – {label}",
            str(backup_service.default_backup_path().parent),
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return

        answer = QMessageBox.question(
            self,
            label,
            self._restore_confirmation_text(restore_type),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            backup_service.restore_backup(file_path, restore_type=restore_type)
        except Exception as exc:
            QMessageBox.critical(self, label, f"Obnovu se nepodařilo dokončit.\n\n{exc}")
            return

        if backup_service.requires_restart_after_restore(restore_type):
            QMessageBox.information(
                self,
                label,
                "Data byla obnovena. Aplikace se nyní ukončí. "
                "Po novém spuštění se načtou obnovená data.",
            )
            QApplication.quit()
            return

        QMessageBox.information(
            self,
            label,
            "Číselníky a šablony byly obnoveny. Databáze zůstala beze změny.",
        )

    def _placeholder_panel(self, title: str, text: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DashboardPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)

        title_label = QLabel(title)
        title_label.setObjectName("DashboardPanelTitle")

        text_label = QLabel(text)
        text_label.setObjectName("InfoText")
        text_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(text_label)
        return panel

    def refresh(self):
        for widget in [
            self.summary,
            self.today,
            self.upcoming,
            self.calendar,
            self.activity,
            self.stats,
            self.controls,
            self.accidents,
            self.days_without_accident,
        ]:
            if hasattr(widget, "refresh"):
                widget.refresh()

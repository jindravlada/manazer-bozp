from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QApplication,
    QVBoxLayout,
    QWidget,
)

from core.services.backup_service import backup_service

from core.dashboard import (
    CalendarPlaceholderWidget,
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

    def __init__(self, open_tasks_callback=None) -> None:
        super().__init__()
        self.open_tasks_callback = open_tasks_callback

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
        top_row.addWidget(self._create_header(), 1)
        top_row.addWidget(self._create_quick_actions(), 0)
        top_row.addStretch(1)
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
        self.days_without_accident = self._placeholder_panel("Dny bez pracovního úrazu", "Aktivuje se po dokončení Knihy úrazů.")

        # Pevné výšky u panelů, které nemají roztahovat celou pracovní plochu.
        self.today.setFixedHeight(170)
        self.calendar.setFixedHeight(310)
        self.stats.setFixedHeight(130)
        self.upcoming.setMinimumHeight(260)
        self.activity.setMinimumHeight(220)

        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)
        right_layout.addWidget(self.calendar)
        right_layout.addWidget(self.stats)
        right_layout.addStretch(1)

        grid.addWidget(self.today, 0, 0)
        grid.addWidget(right_column, 0, 1, 3, 1)
        grid.addWidget(self.upcoming, 1, 0)
        grid.addWidget(self.activity, 2, 0)
        grid.addWidget(self.days_without_accident, 3, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 0)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 0)

        layout.addLayout(grid)
        layout.addStretch(1)

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderCard")
        header.setFixedSize(520, 92)

        layout = QVBoxLayout(header)
        layout.setContentsMargins(18, 14, 18, 14)

        title = QLabel("Pracovní plocha")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Dobrý den. Co dnes budeme řešit?")
        subtitle.setObjectName("InfoText")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return header

    def _create_quick_actions(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DashboardPanel")
        panel.setFixedHeight(92)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        buttons = [
            ("+ Úraz", False),
            ("✓ Úkol", True),
            ("📋 Kontrola", False),
            ("🔎 Hledat", False),
            ("💾 Záloha", True),
            ("♻ Obnova", True),
        ]

        for text, enabled in buttons:
            button = QPushButton(text)
            button.setObjectName("QuickButton")
            button.setEnabled(enabled)

            if text == "✓ Úkol" and self.open_tasks_callback:
                button.clicked.connect(self.open_tasks_callback)
            elif text == "💾 Záloha":
                button.clicked.connect(self.create_backup)
            elif text == "♻ Obnova":
                button.clicked.connect(self.restore_backup)

            layout.addWidget(button)

        layout.addStretch()
        return panel

    def create_backup(self):
        default_path = str(backup_service.default_backup_path())
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit zálohu programu",
            default_path,
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".zip"):
            file_path += ".zip"

        try:
            result = backup_service.create_backup(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Záloha", f"Zálohu se nepodařilo vytvořit.\n\n{exc}")
            return

        QMessageBox.information(self, "Záloha", f"Záloha byla vytvořena:\n{result}")

    def restore_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat zálohu programu",
            str(backup_service.default_backup_path().parent),
            "ZIP záloha (*.zip)",
        )
        if not file_path:
            return

        answer = QMessageBox.question(
            self,
            "Obnova dat",
            "Obnova přepíše aktuální databázi, přílohy, exporty a šablony.\n"
            "Před obnovou bude automaticky vytvořena bezpečnostní záloha aktuálního stavu.\n\n"
            "Pokračovat?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            backup_service.restore_backup(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Obnova dat", f"Obnovu se nepodařilo dokončit.\n\n{exc}")
            return

        QMessageBox.information(
            self,
            "Obnova dat",
            "Data byla obnovena. Aplikace se nyní ukončí. Po novém spuštění se načtou obnovená data.",
        )
        QApplication.quit()

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
            self.activity,
            self.stats,
        ]:
            if hasattr(widget, "refresh"):
                widget.refresh()

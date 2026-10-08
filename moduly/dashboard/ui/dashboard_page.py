from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.resources.app_icon import load_app_icon
from moduly.dashboard.ui.complete_backup_dialog import (
    ACTION_CANCEL,
    ACTION_GO_TO_SPRAVA_DAT,
    ACTION_PROCEED,
    CompleteBackupConfirmDialog,
    CompleteRestoreConfirmDialog,
)
from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
    instance_backup_workflow_service,
)
from moduly.sprava_dat.ui.tab_constants import TAB_BACKUP

from core.dashboard import (
    AccidentsWidget,
    CalendarPlaceholderWidget,
    ControlsWidget,
    DaysWithoutAccidentWidget,
    ExamRetrainingWidget,
    RecentActivityWidget,
    StatisticsPlaceholderWidget,
    SummaryWidget,
    TodayWidget,
    UpcomingTasksWidget,
)


class DashboardPage(QWidget):
    """Pracovní plocha Manažer BOZP – dashboard složený z menších widgetů."""

    def __init__(
        self,
        open_tasks_callback=None,
        open_new_meeting_callback=None,
        open_task_by_id_callback=None,
        open_attention_callback=None,
        open_accidents_callback=None,
        open_kontroly_callback=None,
        open_kniha_urazu_callback=None,
        open_agenda_callback=None,
        open_sprava_dat_callback=None,
        refresh_sprava_dat_callback=None,
        open_exam_validity_callback=None,
    ) -> None:
        super().__init__()
        self.open_tasks_callback = open_tasks_callback
        self.open_new_meeting_callback = open_new_meeting_callback
        self.open_task_by_id_callback = open_task_by_id_callback
        self.open_attention_callback = open_attention_callback
        self.open_accidents_callback = open_accidents_callback
        self.open_kontroly_callback = open_kontroly_callback
        self.open_kniha_urazu_callback = open_kniha_urazu_callback
        self.open_agenda_callback = open_agenda_callback
        self.open_sprava_dat_callback = open_sprava_dat_callback
        self.refresh_sprava_dat_callback = refresh_sprava_dat_callback
        self.open_exam_validity_callback = open_exam_validity_callback

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

            QLabel#DashboardCardTitle {
                font-size: 11px;
            }

            QLabel#DashboardCardValue {
                font-size: 28px;
                font-weight: 800;
            }

            QLabel#DashboardCardSubtitle {
                color: #666;
                font-size: 11px;
            }

            QFrame#IndicatorSeparator {
                background: #d6dce5;
                border: none;
                border-radius: 0px;
            }

            QPushButton#QuickButton {
                min-height: 34px;
                font-weight: 600;
            }

            QFrame#HeaderIconSection {
                border-right: 1px solid #e8ecf1;
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
        self.exam_separator = self._create_indicator_separator()
        self.exam_retraining = ExamRetrainingWidget(
            open_callback=self.open_exam_validity_callback,
        )
        indicators = QHBoxLayout()
        indicators.setContentsMargins(0, 0, 0, 0)
        indicators.setSpacing(14)
        indicators.addWidget(self.summary, 1)
        indicators.addWidget(self.exam_separator, 0)
        indicators.addWidget(self.exam_retraining, 1)
        layout.addLayout(indicators)
        self._sync_indicator_halves()

        grid = QGridLayout()
        grid.setSpacing(14)

        self.today = TodayWidget(
            open_task_callback=self.open_task_by_id_callback,
            open_attention_callback=self.open_attention_callback,
        )
        self.upcoming = UpcomingTasksWidget(
            open_task_callback=self.open_task_by_id_callback,
            open_attention_callback=self.open_attention_callback,
            open_agenda_callback=self.open_agenda_callback,
        )
        self.calendar = CalendarPlaceholderWidget()
        self.activity = RecentActivityWidget()
        self.stats = StatisticsPlaceholderWidget()
        self.controls = ControlsWidget(open_kontroly_callback=self.open_kontroly_callback)
        self.accidents = AccidentsWidget(open_kniha_urazu_callback=self.open_kniha_urazu_callback)

        # Pevné výšky u panelů, které nemají roztahovat celou pracovní plochu.
        self.today.setFixedHeight(170)
        self.stats.setFixedHeight(130)
        self.controls.setMinimumHeight(220)
        self.accidents.setFixedHeight(170)
        # 97a: vyšší panel pozornosti (~+30 %), nižší Poslední aktivita (~3 položky).
        self.upcoming.setMinimumHeight(340)
        self.activity.setMinimumHeight(140)
        self.activity.setMaximumHeight(160)

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
        header_icon_size = 60

        header = QFrame()
        header.setObjectName("HeaderCard")
        header.setFixedHeight(100)
        header.setMinimumWidth(360)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 16, 20, 16)
        layout.setSpacing(0)

        icon_section = QFrame()
        icon_section.setObjectName("HeaderIconSection")
        icon_layout = QHBoxLayout(icon_section)
        icon_layout.setContentsMargins(0, 0, 18, 0)
        icon_layout.setSpacing(0)

        app_icon = load_app_icon()
        if not app_icon.isNull():
            icon_pixmap = app_icon.pixmap(
                header_icon_size,
                header_icon_size,
                QIcon.Mode.Normal,
                QIcon.State.Off,
            )
            if not icon_pixmap.isNull():
                icon_label = QLabel()
                icon_label.setPixmap(icon_pixmap)
                icon_label.setFixedSize(header_icon_size, header_icon_size)
                icon_label.setScaledContents(False)
                icon_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_section = QWidget()
        text_layout = QVBoxLayout(text_section)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        title = QLabel("Pracovní plocha")
        title.setObjectName("PageTitle")

        subtitle = QLabel("Dobrý den. Co dnes budeme řešit?")
        subtitle.setObjectName("InfoText")

        text_layout.addWidget(title, 0, Qt.AlignmentFlag.AlignTop)
        text_layout.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignTop)
        text_layout.addStretch(1)

        if icon_layout.count() > 0:
            layout.addWidget(icon_section, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(text_section, 1, Qt.AlignmentFlag.AlignTop)

        return header

    def _create_indicator_separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("IndicatorSeparator")
        line.setFixedWidth(1)
        line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        return line

    def _sync_indicator_halves(self) -> None:
        tests_visible = not self.exam_retraining.isHidden()
        self.exam_separator.setVisible(tests_visible)

    def _create_vertical_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setFixedHeight(80)
        return line

    def _create_quick_actions(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DashboardPanel")
        panel.setFixedHeight(100)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        buttons = [
            ("+ Úraz", True),
            ("Nový úkol", True),
            ("Nová událost", True),
            ("💾 Záloha", True),
            ("♻ Obnova", True),
        ]

        for text, enabled in buttons:
            button = QPushButton(text)
            button.setObjectName("QuickButton")
            button.setEnabled(enabled)

            if text == "+ Úraz" and self.open_accidents_callback:
                button.clicked.connect(self.open_accidents_callback)
            elif text == "Nový úkol" and self.open_tasks_callback:
                button.clicked.connect(self.open_tasks_callback)
            elif text == "Nová událost" and self.open_new_meeting_callback:
                button.clicked.connect(self.open_new_meeting_callback)
            elif text == "💾 Záloha":
                button.clicked.connect(self._show_backup_dialog)
            elif text == "♻ Obnova":
                button.clicked.connect(self._show_restore_dialog)

            layout.addWidget(button)

        layout.addStretch()
        return panel

    def _show_backup_dialog(self) -> None:
        dialog = CompleteBackupConfirmDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.action == ACTION_CANCEL:
            return
        if dialog.action == ACTION_GO_TO_SPRAVA_DAT:
            self._open_sprava_dat(TAB_BACKUP)
            return
        if dialog.action == ACTION_PROCEED:
            if instance_backup_workflow_service.create_instance_backup_ui(self):
                self._refresh_sprava_dat_status()

    def _show_restore_dialog(self) -> None:
        dialog = CompleteRestoreConfirmDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.action == ACTION_CANCEL:
            return
        if dialog.action == ACTION_GO_TO_SPRAVA_DAT:
            self._open_sprava_dat(TAB_BACKUP)
            return
        if dialog.action == ACTION_PROCEED:
            if instance_backup_workflow_service.restore_instance_backup_ui(self):
                self._refresh_sprava_dat_status()

    def _open_sprava_dat(self, tab_key: str) -> None:
        if callable(self.open_sprava_dat_callback):
            self.open_sprava_dat_callback(tab_key)

    def _refresh_sprava_dat_status(self) -> None:
        if callable(self.refresh_sprava_dat_callback):
            self.refresh_sprava_dat_callback()

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
            self.exam_retraining,
        ]:
            if hasattr(widget, "refresh"):
                widget.refresh()
        self._sync_indicator_halves()

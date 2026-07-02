"""Mini dashboard Manažera auditů na hlavní stránce modulu Audity."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import (
    AUDIT_PROGRAM_MANAGER_BANNER_ACTIVE_PROGRAM,
    AUDIT_PROGRAM_MANAGER_BANNER_NEAREST_VISIT,
    AUDIT_PROGRAM_MANAGER_BANNER_OPEN_FINDINGS,
    AUDIT_PROGRAM_MANAGER_BANNER_OPEN_TASKS,
    AUDIT_PROGRAM_MANAGER_BANNER_TITLE,
    AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT,
)
from moduly.audity.sluzby.audit_program_dashboard_service import (
    audit_program_dashboard_service,
)
from moduly.audity.sluzby.audit_program_service import (
    AuditProgramBannerInfo,
    audit_program_service,
)


@dataclass(frozen=True)
class AuditProgramManagerBannerView:
    has_program: bool
    program_name: str
    completion_percent: float | None
    nearest_visit_term: str | None
    nearest_visit_workplace: str | None
    open_findings_count: int | None
    open_tasks_count: int | None


def load_audit_program_manager_banner_view() -> AuditProgramManagerBannerView:
    info = audit_program_service.get_banner_info()
    if not info.has_program or info.program_id is None:
        return AuditProgramManagerBannerView(
            has_program=False,
            program_name="",
            completion_percent=None,
            nearest_visit_term=None,
            nearest_visit_workplace=None,
            open_findings_count=None,
            open_tasks_count=None,
        )

    summary = audit_program_dashboard_service.get_program_summary(info.program_id)
    return AuditProgramManagerBannerView(
        has_program=True,
        program_name=info.program_name,
        completion_percent=info.completion_percent,
        nearest_visit_term=info.nearest_visit_term,
        nearest_visit_workplace=info.nearest_visit_workplace,
        open_findings_count=summary.findings_open,
        open_tasks_count=summary.tasks_open,
    )


class AuditProgramManagerBannerWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AuditProgramManagerBanner")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(20)

        self._program_column = self._build_program_column()
        self._visit_column = self._build_visit_column()
        self._stats_column = self._build_stats_column()
        self._empty_label = QLabel(AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT)
        self._empty_label.setObjectName("InfoText")
        self._empty_label.setWordWrap(True)
        self._empty_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self._visit_separator = self._vertical_separator()
        self._stats_separator = self._vertical_separator()

        root.addWidget(self._program_column, 3)
        root.addWidget(self._visit_separator)
        root.addWidget(self._visit_column, 2)
        root.addWidget(self._stats_separator)
        root.addWidget(self._stats_column, 2)
        root.addWidget(self._empty_label, 1)

        self._set_dashboard_visible(False)

    @staticmethod
    def _vertical_separator() -> QFrame:
        line = QFrame()
        line.setObjectName("AuditProgramManagerBannerSeparator")
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        return line

    def _build_program_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel(AUDIT_PROGRAM_MANAGER_BANNER_TITLE)
        title.setObjectName("AuditProgramManagerBannerTitle")
        layout.addWidget(title)

        active_label = QLabel(AUDIT_PROGRAM_MANAGER_BANNER_ACTIVE_PROGRAM)
        active_label.setObjectName("MutedText")
        layout.addWidget(active_label)

        self._program_name_label = QLabel()
        self._program_name_label.setObjectName("AuditProgramManagerBannerProgramName")
        self._program_name_label.setWordWrap(True)
        layout.addWidget(self._program_name_label)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 4, 0, 0)
        progress_row.setSpacing(8)
        self._completion_bar = QProgressBar()
        self._completion_bar.setObjectName("AuditProgramManagerBannerProgress")
        self._completion_bar.setTextVisible(False)
        self._completion_bar.setFixedHeight(10)
        self._completion_percent_label = QLabel()
        self._completion_percent_label.setObjectName("MutedText")
        progress_row.addWidget(self._completion_bar, 1)
        progress_row.addWidget(self._completion_percent_label, 0)
        layout.addLayout(progress_row)

        return column

    def _build_visit_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._visit_title_label = QLabel(
            f"📅 {AUDIT_PROGRAM_MANAGER_BANNER_NEAREST_VISIT}"
        )
        self._visit_title_label.setObjectName("AuditProgramManagerBannerSectionTitle")
        layout.addWidget(self._visit_title_label)

        self._visit_term_label = QLabel()
        self._visit_term_label.setObjectName("AuditProgramManagerBannerHighlight")
        layout.addWidget(self._visit_term_label)

        self._visit_workplace_label = QLabel()
        self._visit_workplace_label.setObjectName("InfoText")
        self._visit_workplace_label.setWordWrap(True)
        layout.addWidget(self._visit_workplace_label)
        layout.addStretch(1)

        return column

    def _build_stats_column(self) -> QWidget:
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._findings_label = QLabel()
        self._findings_label.setObjectName("InfoText")
        self._findings_label.setWordWrap(True)
        layout.addWidget(self._findings_label)

        self._tasks_label = QLabel()
        self._tasks_label.setObjectName("InfoText")
        self._tasks_label.setWordWrap(True)
        layout.addWidget(self._tasks_label)
        layout.addStretch(1)

        return column

    def refresh(self) -> None:
        self.load_view(load_audit_program_manager_banner_view())

    def load_info(self, info: AuditProgramBannerInfo) -> None:
        if not info.has_program or info.program_id is None:
            self.load_view(
                AuditProgramManagerBannerView(
                    has_program=False,
                    program_name="",
                    completion_percent=None,
                    nearest_visit_term=None,
                    nearest_visit_workplace=None,
                    open_findings_count=None,
                    open_tasks_count=None,
                )
            )
            return

        summary = audit_program_dashboard_service.get_program_summary(info.program_id)
        self.load_view(
            AuditProgramManagerBannerView(
                has_program=True,
                program_name=info.program_name,
                completion_percent=info.completion_percent,
                nearest_visit_term=info.nearest_visit_term,
                nearest_visit_workplace=info.nearest_visit_workplace,
                open_findings_count=summary.findings_open,
                open_tasks_count=summary.tasks_open,
            )
        )

    def load_view(self, view: AuditProgramManagerBannerView) -> None:
        if not view.has_program:
            self._set_dashboard_visible(False)
            self._empty_label.setText(AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT)
            return

        self._set_dashboard_visible(True)
        self._program_name_label.setText(view.program_name or "—")

        completion = view.completion_percent
        if completion is None:
            self._completion_bar.setValue(0)
            self._completion_percent_label.setText("—")
        else:
            self._completion_bar.setValue(max(0, min(100, int(round(completion)))))
            self._completion_percent_label.setText(f"{completion:.0f} %")

        self._visit_term_label.setText(view.nearest_visit_term or "—")
        self._visit_workplace_label.setText(view.nearest_visit_workplace or "—")

        findings_count = view.open_findings_count
        tasks_count = view.open_tasks_count
        self._findings_label.setText(
            f"⚠ {AUDIT_PROGRAM_MANAGER_BANNER_OPEN_FINDINGS}: "
            f"{findings_count if findings_count is not None else '—'}"
        )
        self._tasks_label.setText(
            f"📋 {AUDIT_PROGRAM_MANAGER_BANNER_OPEN_TASKS}: "
            f"{tasks_count if tasks_count is not None else '—'}"
        )

    def _set_dashboard_visible(self, visible: bool) -> None:
        self._program_column.setVisible(visible)
        self._visit_column.setVisible(visible)
        self._stats_column.setVisible(visible)
        self._visit_separator.setVisible(visible)
        self._stats_separator.setVisible(visible)
        self._empty_label.setVisible(not visible)

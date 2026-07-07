from dataclasses import dataclass
from datetime import date, datetime

from moduly.pravni_pozadavky.constants import CHANGE_TYPE_LABELS, CHECK_RUN_STATUS_LABELS
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value).strip()


def _fmt_datetime(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    return str(value).strip()


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


@dataclass(frozen=True)
class LegalCheckRunChangeExportRow:
    change_id: int
    change_type: str
    title: str
    evaluated_label: str
    published_at: str
    effective_from: str


@dataclass(frozen=True)
class LegalCheckRunExportRow:
    run_id: int
    title: str
    period_from: str
    period_to: str
    checked_at: str
    checked_by: str
    status: str
    note: str
    active_label: str
    changes_count: int
    evaluated_count: int
    unevaluated_count: int
    changes: list[LegalCheckRunChangeExportRow]


@dataclass(frozen=True)
class LegalCheckRunExportContext:
    """Kontext pro budoucí export kontrolních běhů legislativy."""

    generated_at: datetime
    rows: list[LegalCheckRunExportRow]

    @property
    def total_count(self) -> int:
        return len(self.rows)


class LegalCheckRunExportContextService:
    def build(
        self,
        *,
        active_only: bool | None = True,
        include_inactive_changes: bool = True,
    ) -> LegalCheckRunExportContext:
        if active_only is True:
            runs = legal_check_run_service.list_all(include_inactive=False)
        else:
            runs = legal_check_run_service.list_all(include_inactive=True)
        rows = [
            self._build_row(run, include_inactive_changes=include_inactive_changes)
            for run in runs
        ]
        return LegalCheckRunExportContext(
            generated_at=datetime.now(),
            rows=rows,
        )

    def build_for_run(self, run_id: int) -> LegalCheckRunExportContext | None:
        run = legal_check_run_service.get_by_id(run_id)
        if run is None:
            return None
        return LegalCheckRunExportContext(
            generated_at=datetime.now(),
            rows=[self._build_row(run, include_inactive_changes=True)],
        )

    def _build_row(
        self,
        run,
        *,
        include_inactive_changes: bool,
    ) -> LegalCheckRunExportRow:
        changes = legal_change_service.list_by_check_run(
            run.id,
            include_inactive=include_inactive_changes,
        )
        evaluated_count = sum(1 for change in changes if change.evaluated)
        unevaluated_count = len(changes) - evaluated_count
        return LegalCheckRunExportRow(
            run_id=run.id,
            title=_text(run.title),
            period_from=_fmt_date(run.period_from),
            period_to=_fmt_date(run.period_to),
            checked_at=_fmt_datetime(run.checked_at),
            checked_by=_text(run.checked_by),
            status=CHECK_RUN_STATUS_LABELS.get(run.status, run.status),
            note=_text(run.note),
            active_label="Aktivní" if run.active else "Neaktivní",
            changes_count=len(changes),
            evaluated_count=evaluated_count,
            unevaluated_count=unevaluated_count,
            changes=[self._build_change_row(change) for change in changes],
        )

    def _build_change_row(self, change) -> LegalCheckRunChangeExportRow:
        return LegalCheckRunChangeExportRow(
            change_id=change.id,
            change_type=CHANGE_TYPE_LABELS.get(change.change_type, change.change_type),
            title=_text(change.title),
            evaluated_label="Ano" if change.evaluated else "Ne",
            published_at=_fmt_date(change.published_at),
            effective_from=_fmt_date(change.effective_from),
        )


legal_check_run_export_context_service = LegalCheckRunExportContextService()

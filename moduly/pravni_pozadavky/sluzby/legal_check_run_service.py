from datetime import date, datetime

from moduly.pravni_pozadavky.constants import (
    CHECK_RUN_COMPLETED,
    CHECK_RUN_IN_PROGRESS,
    CHECK_RUN_NEW,
    DEFAULT_CHECK_RUN_STATUS,
    VALID_CHECK_RUN_STATUSES,
)
from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
from moduly.pravni_pozadavky.repository.legal_check_run_repository import (
    LegalCheckRunRepository,
)


class LegalCheckRunService:
    def __init__(self):
        self.repository = LegalCheckRunRepository()

    def list_all(self, *, include_inactive: bool = False) -> list[LegalCheckRun]:
        return self.repository.list_all(include_inactive=include_inactive)

    def list_for_selector(self) -> list[LegalCheckRun]:
        return self.repository.list_all(include_inactive=False)

    def get_by_id(self, run_id: int) -> LegalCheckRun | None:
        return self.repository.get_by_id(run_id)

    def create(
        self,
        *,
        title: str,
        period_from: date,
        period_to: date,
        checked_at: datetime | None = None,
        checked_by: str = "",
        status: str = DEFAULT_CHECK_RUN_STATUS,
        note: str = "",
        active: bool = True,
    ) -> LegalCheckRun:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Název kontroly je povinný.")
        self._validate_period(period_from, period_to)
        normalized_status = self._normalize_status(status)

        run = LegalCheckRun(
            title=normalized_title,
            period_from=period_from,
            period_to=period_to,
            checked_at=checked_at,
            checked_by=checked_by.strip(),
            status=normalized_status,
            note=note.strip(),
            active=active,
        )
        return self.repository.create(run)

    def update(
        self,
        run_id: int,
        *,
        title: str,
        period_from: date,
        period_to: date,
        checked_at: datetime | None = None,
        checked_by: str = "",
        status: str = DEFAULT_CHECK_RUN_STATUS,
        note: str = "",
        active: bool = True,
    ) -> LegalCheckRun | None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            return None

        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Název kontroly je povinný.")
        self._validate_period(period_from, period_to)

        run.title = normalized_title
        run.period_from = period_from
        run.period_to = period_to
        run.checked_at = checked_at
        run.checked_by = checked_by.strip()
        run.status = self._normalize_status(status)
        run.note = note.strip()
        run.active = active
        return self.repository.update(run)

    def deactivate(self, run_id: int) -> LegalCheckRun | None:
        return self.repository.deactivate(run_id)

    def restore(self, run_id: int) -> LegalCheckRun | None:
        return self.repository.restore(run_id)

    def start_run(self, run_id: int) -> LegalCheckRun | None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            return None
        run.status = CHECK_RUN_IN_PROGRESS
        if run.checked_at is None:
            run.checked_at = datetime.now()
        return self.repository.update(run)

    def complete_run(self, run_id: int) -> LegalCheckRun | None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            return None
        run.status = CHECK_RUN_COMPLETED
        if run.checked_at is None:
            run.checked_at = datetime.now()
        return self.repository.update(run)

    def _validate_period(self, period_from: date | None, period_to: date | None) -> None:
        if period_from is None:
            raise ValueError("Období od je povinné.")
        if period_to is None:
            raise ValueError("Období do je povinné.")

    def _normalize_status(self, status: str) -> str:
        normalized = (status or "").strip() or DEFAULT_CHECK_RUN_STATUS
        if normalized not in VALID_CHECK_RUN_STATUSES:
            raise ValueError("Neplatný stav kontroly.")
        return normalized


legal_check_run_service = LegalCheckRunService()

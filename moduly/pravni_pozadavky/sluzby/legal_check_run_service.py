from dataclasses import dataclass
from datetime import date, datetime

from core.services.app_runtime_service import application_started_at
from moduly.pravni_pozadavky.constants import (
    CHECK_RUN_CANCELLED,
    CHECK_RUN_COMPLETED,
    CHECK_RUN_CRASH_RECOVERY_MESSAGE,
    CHECK_RUN_ERROR,
    CHECK_RUN_IN_PROGRESS,
    CHECK_RUN_NEW,
    DEFAULT_CHECK_RUN_STATUS,
    VALID_CHECK_RUN_STATUSES,
    legal_document_display_label,
)
from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
from moduly.pravni_pozadavky.repository.legal_check_run_repository import (
    LegalCheckRunRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_check_run_callbacks import (
    CancelCheckCallback,
    CheckProgressCallback,
    CheckStatusCallback,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


@dataclass(frozen=True)
class AutomaticCheckRunResult:
    run: LegalCheckRun
    documents_checked_count: int
    changes_count: int
    is_first_check: bool = False


class LegalCheckRunService:
    def __init__(self):
        self.repository = LegalCheckRunRepository()

    def list_all(self, *, include_inactive: bool = False) -> list[LegalCheckRun]:
        return self.repository.list_all(include_inactive=include_inactive)

    def list_for_selector(self) -> list[LegalCheckRun]:
        return self.repository.list_all(include_inactive=False)

    def get_by_id(self, run_id: int) -> LegalCheckRun | None:
        return self.repository.get_by_id(run_id)

    def append_note(self, run_id: int, text: str) -> LegalCheckRun | None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            return None
        addition = (text or "").strip()
        if not addition:
            return run
        existing = (run.note or "").strip()
        run.note = f"{existing}\n\n{addition}" if existing else addition
        return self.repository.update(run)

    def get_last_completed_run(self) -> LegalCheckRun | None:
        return self.repository.get_last_completed()

    def is_first_automatic_check(self) -> bool:
        return self.get_last_completed_run() is None

    def get_run_completion_date(self, run: LegalCheckRun) -> date:
        if run.checked_at is not None:
            return run.checked_at.date()
        return run.period_to

    def recover_stale_in_progress_runs(
        self,
        *,
        app_started_at: datetime | None = None,
    ) -> list[LegalCheckRun]:
        threshold = app_started_at or application_started_at()
        recovered: list[LegalCheckRun] = []
        for run in self.repository.list_in_progress():
            start_time = run.started_at or run.created_at
            if start_time >= threshold:
                continue
            updated = self._mark_error(run.id, CHECK_RUN_CRASH_RECOVERY_MESSAGE)
            if updated is not None:
                recovered.append(updated)
        return recovered

    def run_automatic_check(
        self,
        *,
        period_from: date,
        period_to: date | None = None,
        on_status: CheckStatusCallback | None = None,
        on_progress: CheckProgressCallback | None = None,
        is_cancelled: CancelCheckCallback | None = None,
    ) -> AutomaticCheckRunResult:
        normalized_period_to = period_to or date.today()
        self._validate_period(period_from, normalized_period_to)
        if period_from > normalized_period_to:
            raise ValueError("Datum začátku kontroly nesmí být později než datum konce.")

        run = self._begin_automatic_check(period_from, normalized_period_to)
        is_first_check = self.is_first_automatic_check()
        deferred_reference_checksums: list[tuple[int, str]] = []
        try:
            self._notify_status(on_status, "Připravuji kontrolu…")
            if self._check_cancelled(is_cancelled):
                run = self._mark_cancelled(run.id)
                return self._build_result(run, is_first_check=is_first_check)

            documents = legal_document_service.list_all(include_inactive=False)
            total = len(documents)
            from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
                legal_check_novelization_service,
            )
            from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
                legal_document_version_service,
            )

            for index, document in enumerate(documents, start=1):
                if self._check_cancelled(is_cancelled):
                    run = self._mark_cancelled(run.id)
                    return self._build_result(run, is_first_check=is_first_check)
                label = legal_document_display_label(document)
                self._notify_progress(on_progress, index, total, label)
                if is_first_check:
                    pending_checksum = legal_check_novelization_service.initialize_reference_state(
                        document,
                    )
                    if pending_checksum is not None:
                        deferred_reference_checksums.append(pending_checksum)
                else:
                    legal_check_novelization_service.check_document(
                        document,
                        check_run_id=run.id,
                    )

            if self._check_cancelled(is_cancelled):
                run = self._mark_cancelled(run.id)
                return self._build_result(run, is_first_check=is_first_check)

            if is_first_check:
                changes_count = 0
                for version_id, checksum in deferred_reference_checksums:
                    legal_document_version_service.update_checksum(version_id, checksum)
            else:
                from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

                changes_count = len(
                    legal_change_service.list_by_check_run(run.id, include_inactive=False),
                )
            run = self._mark_completed(
                run.id,
                documents_checked_count=total,
                changes_found_count=changes_count,
            )
            return self._build_result(run, is_first_check=is_first_check)
        except ValueError:
            raise
        except Exception as exc:
            self._mark_error(run.id, str(exc))
            raise

    def _begin_automatic_check(self, period_from: date, period_to: date) -> LegalCheckRun:
        now = datetime.now()
        return self.create(
            title=f"Kontrola změn {period_to.strftime('%d.%m.%Y')}",
            period_from=period_from,
            period_to=period_to,
            started_at=now,
            status=CHECK_RUN_IN_PROGRESS,
        )

    def _mark_completed(
        self,
        run_id: int,
        *,
        documents_checked_count: int,
        changes_found_count: int,
    ) -> LegalCheckRun:
        run = self.repository.get_by_id(run_id)
        if run is None:
            raise ValueError("Kontrola změn nebyla nalezena.")
        run.status = CHECK_RUN_COMPLETED
        run.checked_at = datetime.now()
        run.documents_checked_count = documents_checked_count
        run.changes_found_count = changes_found_count
        run.error_message = ""
        return self.repository.update(run)

    def _mark_cancelled(self, run_id: int) -> LegalCheckRun:
        run = self.repository.get_by_id(run_id)
        if run is None:
            raise ValueError("Kontrola změn nebyla nalezena.")
        run.status = CHECK_RUN_CANCELLED
        run.checked_at = datetime.now()
        run.error_message = ""
        return self.repository.update(run)

    def _mark_error(self, run_id: int, message: str) -> LegalCheckRun | None:
        run = self.repository.get_by_id(run_id)
        if run is None:
            return None
        run.status = CHECK_RUN_ERROR
        run.checked_at = datetime.now()
        run.error_message = message.strip()
        return self.repository.update(run)

    def _build_result(
        self,
        run: LegalCheckRun,
        *,
        is_first_check: bool = False,
    ) -> AutomaticCheckRunResult:
        return AutomaticCheckRunResult(
            run=run,
            documents_checked_count=run.documents_checked_count or 0,
            changes_count=run.changes_found_count or 0,
            is_first_check=is_first_check,
        )

    def _check_cancelled(self, is_cancelled: CancelCheckCallback | None) -> bool:
        return is_cancelled is not None and is_cancelled()

    def _notify_status(
        self,
        on_status: CheckStatusCallback | None,
        message: str,
    ) -> None:
        if on_status is not None:
            on_status(message)

    def _notify_progress(
        self,
        on_progress: CheckProgressCallback | None,
        current: int,
        total: int,
        label: str,
    ) -> None:
        if on_progress is not None:
            on_progress(current, total, label)

    def create(
        self,
        *,
        title: str,
        period_from: date,
        period_to: date,
        checked_at: datetime | None = None,
        checked_by: str = "",
        started_at: datetime | None = None,
        status: str = DEFAULT_CHECK_RUN_STATUS,
        note: str = "",
        error_message: str = "",
        documents_checked_count: int | None = None,
        changes_found_count: int | None = None,
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
            started_at=started_at,
            status=normalized_status,
            note=note.strip(),
            error_message=error_message.strip(),
            documents_checked_count=documents_checked_count,
            changes_found_count=changes_found_count,
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
        started_at: datetime | None = None,
        status: str = DEFAULT_CHECK_RUN_STATUS,
        note: str = "",
        error_message: str = "",
        documents_checked_count: int | None = None,
        changes_found_count: int | None = None,
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
        run.started_at = started_at
        run.status = self._normalize_status(status)
        run.note = note.strip()
        run.error_message = error_message.strip()
        run.documents_checked_count = documents_checked_count
        run.changes_found_count = changes_found_count
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
        if run.started_at is None:
            run.started_at = datetime.now()
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

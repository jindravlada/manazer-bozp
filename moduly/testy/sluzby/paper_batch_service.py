"""Hromadná příprava papírových testů a jeden společný klíč dávky."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from moduly.testy.modely.test_exam import TestExam
from moduly.testy.sluzby.paper_test_export_service import (
    BatchPaperExportResult,
    paper_test_export_service,
)
from moduly.testy.sluzby.test_exam_service import test_exam_service


@dataclass(frozen=True)
class PaperBatchResult:
    exams: tuple[TestExam, ...]
    files: BatchPaperExportResult


def prepare_and_export_paper_batch(
    *,
    employee_ids: list[int],
    test_id: int | None,
    exam_date: date,
    directory: str | Path,
    valid_until: date | None = None,
    examiner_id: int | None = None,
    chair_id: int | None = None,
    member_ids: list[int] | None = None,
    include_shared_key: bool = False,
    rng=None,
) -> PaperBatchResult:
    """Nejdřív zapíše zkoušky, potom jejich ODT. Neúspěch souboru zkoušky nemaže."""
    exams = test_exam_service.prepare_paper_batch(
        employee_ids=employee_ids,
        test_id=test_id,
        exam_date=exam_date,
        valid_until=valid_until,
        examiner_id=examiner_id,
        chair_id=chair_id,
        member_ids=member_ids,
        rng=rng,
    )
    files = paper_test_export_service.export_batch(
        [int(exam.id) for exam in exams],
        directory,
        include_shared_key=include_shared_key,
    )
    return PaperBatchResult(exams=tuple(exams), files=files)


def format_batch_summary(result: PaperBatchResult) -> str:
    key_state = "vytvořen" if result.files.key_path is not None else "nevytvářen"
    lines = [
        f"Vytvořeno zkoušek: {len(result.exams)}",
        f"Vytvořeno testů: {len(result.files.test_paths)}",
        f"Společný klíč: {key_state}",
    ]
    if result.files.failures:
        lines.append(f"Nepodařilo se vytvořit souborů: {len(result.files.failures)}")
        for failure in result.files.failures:
            lines.append(f"{failure.employee_label}: {failure.path.name}")
    return "\n".join(lines)

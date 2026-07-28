"""Export checklistu přezkoumání opatření do ODT (A4 na výšku)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.export import OdtExportEngine, OdtParagraph, OdtRichContent, open_export_file
from core.services.storage_service import storage_service
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_PRINT_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_PRINT_EMPTY,
)
from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    risk_measure_review_service,
)


def _text(value) -> str:
    return str(value or "").strip()


def _format_date(value) -> str:
    if value is None:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return _text(value) or "—"


def split_checklist_measure_lines(text: str) -> list[str]:
    """Rozdělí text navazujícího opatření na položky checklistu (RISK-CHECKLIST-1).

    Hranice = Enter (``\\n`` / ``\\r\\n`` / ``\\r``). Prázdné řádky a okolní
    mezery se vynechají / oříznou.
    """
    if not text:
        return []
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if line:
            lines.append(line)
    return lines


# Papírový checklist do terénu – vždy prázdná políčka k ručnímu vyplnění.
# „Poznámka č.“ se nikdy neplní z elektronické evidence.
# Oddělovač: tabulátor → v ODT se renderuje jako <text:tab/> (rozestup přes řádek).
_CHECKLIST_CONTROL_LINE = "Vyhovuje ☐\tNevyhovuje ☐\tFoto ☐\tPoznámka č.:"


class RiskMeasureReviewChecklistExportService:
    TEMPLATE_NAME = "PrezkoumaniOpatreniChecklist.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "prezkoumani_opatreni_checklisty"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def build_context(self, review: RiskMeasureReview) -> dict:
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        return {
            "cislo_prezkoumani": _text(getattr(review, "review_number", None)) or "—",
            "datum": _format_date(getattr(review, "review_date", None)),
            "kontrolujici": _text(getattr(review, "reviewer_person_name", None)) or "—",
            "provoz": _text(getattr(review, "operation_name", None)) or "—",
            "pracoviste": _text(getattr(review, "workplace_name", None)) or "—",
            "cast_pracoviste": _text(getattr(review, "workplace_part_name", None)) or "—",
            "checklist_text": self._checklist_content(rows),
        }

    def generate_for_review(self, review: RiskMeasureReview) -> Path:
        if review is None or not getattr(review, "id", None):
            raise ValueError("Není vybrané uložené přezkoumání.")

        storage_service.ensure_structure()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        number = _text(getattr(review, "review_number", None)) or str(review.id)
        safe_number = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in number)
        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            f"PrezkoumaniChecklist-{safe_number}_{stamp}.odt",
        )
        self.engine.render(self.template_path(), output_path, self.build_context(review))
        return output_path

    def open_for_review(self, review: RiskMeasureReview) -> Path:
        path = self.generate_for_review(review)
        open_export_file(path, title=RISK_MEASURE_REVIEW_PRINT_DIALOG_TITLE)
        return path

    def _checklist_content(self, rows) -> OdtRichContent:
        if not rows:
            return OdtRichContent(
                paragraphs=[OdtParagraph.text(RISK_MEASURE_REVIEW_PRINT_EMPTY)]
            )

        paragraphs: list[OdtParagraph] = []
        first_item = True
        for row in rows:
            lines = split_checklist_measure_lines(row.measure_title or "")
            if not lines:
                lines = ["—"]
            for line in lines:
                if not first_item:
                    paragraphs.append(OdtParagraph.blank_line())
                first_item = False
                paragraphs.append(OdtParagraph.text(line, style="AuditCriterion"))
                paragraphs.append(OdtParagraph.text(_CHECKLIST_CONTROL_LINE))
        return OdtRichContent(paragraphs=paragraphs)


risk_measure_review_checklist_export_service = RiskMeasureReviewChecklistExportService()

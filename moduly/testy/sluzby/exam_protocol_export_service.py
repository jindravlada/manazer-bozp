"""Samostatný protokol po elektronické písemné části.

Papírová zkouška protokol znovu nedostane: má ho v tištěném testu.
Export jen čte snapshot a uložený výsledek. Nic nepřepisuje.
"""

from __future__ import annotations

from pathlib import Path

from core.export import OdtParagraph, OdtXmlFragment, odt_rich
from core.services.storage_service import storage_service
from moduly.testy.constants import (
    EXAM_STATUS_COMPLETED,
    WRITTEN_MODE_ELECTRONIC,
    WRITTEN_MODE_PAPER,
    WRITTEN_RESULT_PASSED,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.sluzby.exam_protocol_layout import (
    BLANK_EXAM_DATE_LINE,
    protocol_oral_items,
    protocol_people,
    render_electronic_protocol_xml,
)
from moduly.testy.sluzby.paper_test_export_service import (
    _DOCUMENT_END,
    _employee_name,
    _filename,
    _labeled,
    _odt_path,
    paper_test_export_service,
    plain_export_text,
)
from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service

_TEMPLATE_SUBDIR = "exporty"
_PROTOCOL_TEMPLATE = "ProtokolZkousky.odt"


def protocol_filename(exam: TestExam) -> str:
    return _filename("Protokol", exam)


def protocol_block_reason(exam: TestExam | None) -> str | None:
    """Prázdný řetězec nevrací. None znamená, že protokol vytisknout lze."""
    if exam is None:
        return "Zkouška nebyla nalezena."
    if exam.written_mode == WRITTEN_MODE_PAPER:
        return (
            "Papírová zkouška má protokol v tištěném testu. "
            "Samostatný protokol se nevytváří."
        )
    if exam.written_mode != WRITTEN_MODE_ELECTRONIC:
        return "Protokol o zkoušce lze vytisknout jen po elektronické písemné části."
    if exam.status != EXAM_STATUS_COMPLETED:
        return "Protokol o zkoušce lze vytisknout jen u dokončené zkoušky."
    if exam.written_result != WRITTEN_RESULT_PASSED:
        return "Protokol o zkoušce lze vytisknout jen když písemná část vyhověla."
    return None


class ExamProtocolExportService:
    def can_export(self, exam_id: int | None) -> bool:
        if not exam_id:
            return False
        return protocol_block_reason(test_exam_service.get_exam(exam_id)) is None

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(_TEMPLATE_SUBDIR, _PROTOCOL_TEMPLATE)

    def export(self, exam_id: int, path: str | Path) -> Path:
        exam = test_exam_service.get_exam(exam_id)
        reason = protocol_block_reason(exam)
        if reason is not None or exam is None:
            raise TestExamError(reason or "Zkouška nebyla nalezena.")
        template = self.template_path()
        if not template.is_file():
            raise TestExamError("Šablona protokolu o zkoušce nebyla nalezena.")
        target = _odt_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        oral_items = protocol_oral_items(test_exam_service.get_oral_questions(exam.id))
        people = protocol_people(exam, test_exam_service.get_examiners(exam.id))
        body = render_electronic_protocol_xml(
            _written_summary_lines(exam),
            oral_items,
            people,
        )
        paper_test_export_service.engine.render(
            template,
            target,
            {
                "header": odt_rich(_header(exam)),
                "protocol": OdtXmlFragment(xml=body + _DOCUMENT_END),
                "variant": "",
            },
        )
        return target.resolve()


def _written_summary_lines(exam: TestExam) -> list[str]:
    return [
        f"Počet otázek: {_count(exam.written_question_count)}",
        f"Správně: {_count(exam.written_correct_count)}",
        f"Chybně: {_count(exam.written_incorrect_count)}",
        f"Nezodpovězeno: {_count(exam.written_unanswered_count)}",
        f"Povolený počet chyb: {_count(exam.written_allowed_wrong_answers)}",
    ]


def _count(value: int | None) -> str:
    if value is None:
        return ""
    return str(int(value))


def _header(exam: TestExam) -> list[OdtParagraph]:
    paragraphs = [
        OdtParagraph.text(plain_export_text(exam.test_name), style="WrittenTitle"),
    ]
    name = _employee_name(exam)
    if name:
        paragraphs.append(OdtParagraph.text(name, style="WrittenMeta"))
    personal = _labeled("Osobní číslo", exam.employee_personal_number)
    if personal:
        paragraphs.append(OdtParagraph.text(personal, style="WrittenMeta"))
    workplace = _labeled("Pracoviště", exam.employee_workplace_name)
    if workplace:
        paragraphs.append(OdtParagraph.text(workplace, style="WrittenMeta"))
    roles = _labeled("Funkce", exam.employee_roles_text)
    if roles:
        paragraphs.append(OdtParagraph.text(roles, style="WrittenMeta"))
    paragraphs.append(OdtParagraph.text(BLANK_EXAM_DATE_LINE, style="WrittenMeta"))
    return paragraphs


exam_protocol_export_service = ExamProtocolExportService()

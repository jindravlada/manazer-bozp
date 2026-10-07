"""Samostatný protokol po elektronické písemné části.

Papírová zkouška protokol znovu nedostane: má ho v tištěném testu.
Export jen čte snapshot a uložený výsledek. Nic nepřepisuje.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from core.export import OdtParagraph, OdtXmlFragment, odt_rich
from core.services.storage_service import storage_service
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    EXAM_STATUS_COMPLETED,
    WRITTEN_MODE_ELECTRONIC,
    WRITTEN_MODE_PAPER,
    WRITTEN_RESULT_PASSED,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.sluzby.exam_protocol_layout import (
    BLANK_EXAM_DATE_LINE,
    ERROR_LIST_HEADING,
    NO_WRITTEN_ERRORS_LINE,
    protocol_oral_items,
    protocol_people,
    render_electronic_protocol_xml,
)
from moduly.testy.sluzby.paper_test_export_service import (
    _ANSWER_MAX_H_CM,
    _ANSWER_MAX_H_WITH_PROMPT_CM,
    _ANSWER_MAX_W_CM,
    _ANSWER_MIN_W_CM,
    _DOCUMENT_END,
    _QUESTION_MAX_H_CM,
    _QUESTION_MAX_H_WITH_CHOICES_CM,
    _QUESTION_MAX_W_CM,
    _QUESTION_MIN_W_CM,
    _employee_name,
    _filename,
    _frame_for,
    _labeled,
    _odt_path,
    _odt_text,
    paper_test_export_service,
    plain_export_text,
)
from moduly.testy.sluzby.written_answer_presentation import (
    TONE_CORRECT,
    TONE_ERROR,
    UNANSWERED_ERROR,
    is_incorrect_or_unanswered,
    present_answer,
    selected_answer,
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
        questions = test_exam_service.get_written_questions(exam.id)
        blocks = [
            (question, test_exam_service.get_written_answers(question.id))
            for question in questions
        ]
        choices = {
            int(choice.exam_question_id): choice
            for choice in test_exam_service.get_written_choices(exam.id)
        }
        with TemporaryDirectory(prefix="exam-protocol-") as temp_name:
            listing_xml, images = render_written_error_listing(
                blocks,
                choices,
                Path(temp_name),
            )
            body = render_electronic_protocol_xml(
                _written_summary_lines(exam),
                oral_items,
                people,
                error_listing_xml=listing_xml,
            )
            paper_test_export_service.engine.render(
                template,
                target,
                {
                    "header": odt_rich(_header(exam)),
                    "protocol": OdtXmlFragment(
                        xml=body + _DOCUMENT_END,
                        images=tuple(images),
                    ),
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


def render_written_error_listing(blocks, choices, temp_dir: Path) -> tuple[str, list[tuple[str, Path]]]:
    """Jen chybné a nezodpovězené otázky. Správné se nevypisují.

    Jedna otázka je keep-together tabulka. Mezi otázkami je jen malá mezera,
    takže se seznam může rozdělit a nevznikne prázdná stránka.
    """
    heading = f'<text:p text:style-name="ProtocolHeading">{_odt_text(ERROR_LIST_HEADING)}</text:p>'
    errors = []
    for question, answers in blocks:
        ordered = sorted(answers, key=lambda item: (item.position, item.id))
        selected = selected_answer(ordered, choices.get(int(question.id)))
        if is_incorrect_or_unanswered(selected):
            errors.append((question, ordered, selected))
    if not errors:
        return (
            heading + f'<text:p text:style-name="ProtocolText">{_odt_text(NO_WRITTEN_ERRORS_LINE)}</text:p>',
            [],
        )
    parts = [heading]
    images: list[tuple[str, Path]] = []
    image_index = 1
    last_index = len(errors) - 1
    for index, (question, answers, selected) in enumerate(errors):
        block, image_index = _error_question_block(
            question,
            answers,
            selected,
            temp_dir,
            images,
            image_index,
        )
        parts.append(block)
        if index != last_index:
            parts.append('<text:p text:style-name="ProtocolErrorGap"/>')
    return "".join(parts), images


def _error_question_block(question, answers, selected, temp_dir, images, image_index):
    image_answers = question.answer_kind == ANSWER_KIND_IMAGE
    prompt_path = test_exam_service.resolve_snapshot_image(question.image_stored_path)
    has_prompt = prompt_path is not None
    bits = [
        f'<text:p text:style-name="WrittenQuestion">'
        f"{int(question.position)}. {_odt_text(question.text)}</text:p>"
    ]
    if has_prompt and prompt_path is not None:
        frame, image_index = _frame_for(
            prompt_path,
            temp_dir,
            images,
            image_index,
            max_w=_QUESTION_MAX_W_CM,
            max_h=_QUESTION_MAX_H_WITH_CHOICES_CM if image_answers else _QUESTION_MAX_H_CM,
            min_w=_QUESTION_MIN_W_CM,
        )
        if frame:
            bits.append(f'<text:p text:style-name="WrittenImageLine">{frame}</text:p>')
    if selected is None:
        bits.append(_toned_paragraph("WrittenAnswer", UNANSWERED_ERROR, TONE_ERROR))
    if image_answers:
        table, image_index = _toned_choice_images(
            question,
            answers,
            selected,
            temp_dir,
            images,
            image_index,
            max_h=_ANSWER_MAX_H_WITH_PROMPT_CM if has_prompt else _ANSWER_MAX_H_CM,
        )
        bits.append(table)
    else:
        for answer in answers:
            caption, tone = present_answer(question, answer, selected, evaluated=True)
            bits.append(_toned_paragraph("WrittenAnswer", caption, tone))
    xml = (
        '<table:table table:style-name="WrittenBlock">'
        '<table:table-column table:style-name="WrittenBlockCol"/>'
        '<table:table-row table:style-name="WrittenBlockRow">'
        '<table:table-cell table:style-name="WrittenBlockCell" office:value-type="string">'
        f"{''.join(bits)}"
        "</table:table-cell></table:table-row></table:table>"
    )
    return xml, image_index


def _toned_choice_images(question, answers, selected, temp_dir, images, image_index, *, max_h: float):
    cells = []
    for answer in answers:
        caption, tone = present_answer(question, answer, selected, evaluated=True)
        frame = ""
        path = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
        if path is not None:
            frame, image_index = _frame_for(
                path,
                temp_dir,
                images,
                image_index,
                max_w=_ANSWER_MAX_W_CM,
                max_h=max_h,
                min_w=_ANSWER_MIN_W_CM,
            )
        image_xml = f'<text:p text:style-name="WrittenImageLine">{frame}</text:p>' if frame else ""
        cells.append(
            '<table:table-cell table:style-name="WrittenBlockCell" office:value-type="string">'
            f"{_toned_paragraph('WrittenChoiceLabel', caption, tone)}"
            f"{image_xml}"
            "</table:table-cell>"
        )
    xml = (
        '<table:table table:style-name="WrittenChoices">'
        '<table:table-column table:style-name="WrittenChoiceCol" table:number-columns-repeated="3"/>'
        '<table:table-row table:style-name="WrittenBlockRow">'
        f"{''.join(cells)}"
        "</table:table-row></table:table>"
    )
    return xml, image_index


def _toned_paragraph(paragraph_style: str, text: str, tone: str) -> str:
    escaped = _odt_text(text)
    if tone == TONE_ERROR:
        inner = f'<text:span text:style-name="ProtocolAnswerError">{escaped}</text:span>'
    elif tone == TONE_CORRECT:
        inner = f'<text:span text:style-name="ProtocolAnswerCorrect">{escaped}</text:span>'
    else:
        inner = escaped
    return f'<text:p text:style-name="{paragraph_style}">{inner}</text:p>'


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

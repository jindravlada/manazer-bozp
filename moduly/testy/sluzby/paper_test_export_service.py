"""Papírový písemný test a volitelný klíč ze snapshotu jedné zkoušky.

Generování jen čte uloženou variantu. Nelosuje otázky, nemění pořadí A/B/C
a nečte znění z aktuální banky. Stav zkoušky ani snapshot se nemění.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape as xml_escape

from PIL import Image

from core.export import OdtExportEngine, OdtParagraph, OdtXmlFragment, odt_rich
from core.services.storage_service import storage_service
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    PAPER_TEST_INSTRUCTION,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
from moduly.testy.sluzby.test_definition_service import format_test_duration
from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service

_TEMPLATE_SUBDIR = "exporty"
_TEST_TEMPLATE = "PisemnyTest.odt"
_KEY_TEMPLATE = "KlicPisemnehoTestu.odt"
# Budoucí souhrnný klíč složí stejné bloky pod sebe, jednu variantu po druhé.
ANSWER_KEY_BLOCK_SIZE = 15
# Dokument nesmí končit tabulkou: LibreOffice by za ni vložilo 14pt odstavec
# a ten po zaplněné stránce založí další, na které je jen patička.
_DOCUMENT_END = '<text:p text:style-name="WrittenDocumentEnd"/>'

_QUESTION_MAX_W_CM = 16.4
_QUESTION_MAX_H_CM = 9.0
_QUESTION_MAX_H_WITH_CHOICES_CM = 5.5
_QUESTION_MIN_W_CM = 6.0
_ANSWER_MAX_W_CM = 5.0
_ANSWER_MAX_H_CM = 6.5
_ANSWER_MAX_H_WITH_PROMPT_CM = 4.2
_ANSWER_MIN_W_CM = 3.6

_EMBED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif"}


@dataclass(frozen=True)
class PaperTestExportResult:
    test_path: Path
    key_path: Path | None = None


def plain_export_text(value: object) -> str:
    """Text do tisku. Chybějící hodnota nezůstane jako „None“."""
    if value is None:
        return ""
    return str(value).strip()


def variant_label(exam: TestExam) -> str:
    """Stabilní označení konkrétní zkoušky. Nový identifikátor se nezavádí."""
    exam_id = getattr(exam, "id", None)
    if exam_id is None:
        return ""
    return f"Varianta {int(exam_id)}"


class PaperTestExportService:
    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def can_export(self, exam_id: int | None) -> bool:
        if not exam_id:
            return False
        exam = test_exam_service.get_exam(exam_id)
        if exam is None or not exam.uses_written:
            return False
        return bool(test_exam_service.get_written_questions(exam.id))

    def test_filename(self, exam: TestExam) -> str:
        return _filename("Test", exam)

    def key_filename(self, exam: TestExam) -> str:
        return _filename("Klic", exam)

    def test_template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(_TEMPLATE_SUBDIR, _TEST_TEMPLATE)

    def key_template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(_TEMPLATE_SUBDIR, _KEY_TEMPLATE)

    def export(
        self,
        exam_id: int,
        test_path: str | Path,
        *,
        include_key: bool = False,
        key_path: str | Path | None = None,
    ) -> PaperTestExportResult:
        """Zapíše ODT test a volitelně klíč. Snapshot ani stav zkoušky nemění."""
        exam = test_exam_service.get_exam(exam_id)
        if exam is None or not exam.uses_written:
            raise TestExamError(
                "Písemný test lze vytvořit jen ze zkoušky s písemnou částí."
            )
        questions = test_exam_service.get_written_questions(exam.id)
        if not questions:
            raise TestExamError(
                "Písemný test lze vytvořit jen ze zkoušky s uloženým snapshotem otázek."
            )
        blocks = [
            (question, test_exam_service.get_written_answers(question.id))
            for question in questions
        ]

        target = _odt_path(test_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        template = self.test_template_path()
        if not template.is_file():
            raise TestExamError("Šablona písemného testu nebyla nalezena.")

        with TemporaryDirectory(prefix="paper-test-") as temp_name:
            temp_dir = Path(temp_name)
            questions_xml, images = _questions_fragment(blocks, temp_dir)
            self.engine.render(
                template,
                target,
                {
                    "header": odt_rich(_header_paragraphs(exam, for_key=False)),
                    "questions": OdtXmlFragment(xml=questions_xml, images=tuple(images)),
                    "variant": variant_label(exam),
                },
            )

        written_key: Path | None = None
        if include_key:
            key_target = _odt_path(key_path) if key_path is not None else target.with_name(
                self.key_filename(exam)
            )
            if key_target.resolve() == target.resolve():
                key_target = target.with_name(f"{target.stem}_klic.odt")
            key_template = self.key_template_path()
            if not key_template.is_file():
                raise TestExamError("Šablona klíče písemného testu nebyla nalezena.")
            self.engine.render(
                key_template,
                key_target,
                {
                    "header": odt_rich(_header_paragraphs(exam, for_key=True)),
                    "answers": OdtXmlFragment(
                        xml=(
                            render_compact_answer_key_xml(correct_answer_rows(blocks))
                            + _DOCUMENT_END
                        )
                    ),
                    "variant": variant_label(exam),
                },
            )
            written_key = key_target.resolve()

        return PaperTestExportResult(test_path=target.resolve(), key_path=written_key)


def _header_paragraphs(exam: TestExam, *, for_key: bool) -> list[OdtParagraph]:
    paragraphs: list[OdtParagraph] = [
        OdtParagraph.text(plain_export_text(exam.test_name), style="WrittenTitle"),
    ]
    if for_key:
        variant = variant_label(exam)
        if variant:
            paragraphs.append(OdtParagraph.text(variant, style="WrittenVariant"))
        return paragraphs
    name = _employee_name(exam)
    if name:
        paragraphs.append(OdtParagraph.text(name, style="WrittenMeta"))
    personal = _labeled("Osobní číslo", getattr(exam, "employee_personal_number", None))
    if personal:
        paragraphs.append(OdtParagraph.text(personal, style="WrittenMeta"))
    workplace = _labeled("Pracoviště", getattr(exam, "employee_workplace_name", None))
    if workplace:
        paragraphs.append(OdtParagraph.text(workplace, style="WrittenMeta"))
    exam_day = _date_line(getattr(exam, "exam_date", None))
    if exam_day:
        paragraphs.append(OdtParagraph.text(exam_day, style="WrittenMeta"))
    paragraphs.append(OdtParagraph.text(PAPER_TEST_INSTRUCTION, style="WrittenInstruction"))
    duration = _duration_line(getattr(exam, "written_duration_seconds", None))
    if duration:
        paragraphs.append(OdtParagraph.text(duration, style="WrittenMeta"))
    variant = variant_label(exam)
    if variant:
        paragraphs.append(OdtParagraph.text(variant, style="WrittenVariant"))
    return paragraphs


def _employee_name(exam: TestExam) -> str:
    display = plain_export_text(getattr(exam, "employee_display_name", None))
    if display:
        return display
    parts = [
        plain_export_text(getattr(exam, "employee_title_before", None)),
        plain_export_text(getattr(exam, "employee_first_name", None)),
        plain_export_text(getattr(exam, "employee_last_name", None)),
    ]
    name = " ".join(part for part in parts if part)
    after = plain_export_text(getattr(exam, "employee_title_after", None))
    if after:
        return f"{name}, {after}" if name else after
    return name


def _labeled(label: str, value: object) -> str:
    text = plain_export_text(value)
    if not text:
        return ""
    return f"{label}: {text}"


def _date_line(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return f"Datum zkoušky: {value.day}. {value.month}. {value.year}"
    text = plain_export_text(value)
    if not text:
        return ""
    return f"Datum zkoušky: {text}"


def _duration_line(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return f"Čas na písemnou část: {format_test_duration(seconds)}"


def correct_answer_rows(
    blocks: list[tuple[TestExamWrittenQuestion, list[TestExamWrittenAnswer]]],
) -> list[tuple[int, str]]:
    """Číslo otázky a správné písmeno v pořadí snapshotu. Nic se nelosuje."""
    rows: list[tuple[int, str]] = []
    for question, answers in blocks:
        letter = ""
        ordered = sorted(answers, key=lambda item: (int(item.position), int(item.id)))
        for answer in ordered:
            if answer.is_correct:
                letter = plain_export_text(answer.letter)
                break
        rows.append((int(question.position), letter))
    return rows


def split_answer_key_rows(
    rows: list[tuple[int, str]],
    *,
    block_size: int = ANSWER_KEY_BLOCK_SIZE,
) -> list[list[tuple[int, str]]]:
    """Rozdělí klíč na bloky. Jeden řádek A4 neunese třicet úzkých sloupců."""
    size = max(1, int(block_size))
    return [rows[start : start + size] for start in range(0, len(rows), size)]


def render_compact_answer_key_xml(
    rows: list[tuple[int, str]],
    *,
    block_size: int = ANSWER_KEY_BLOCK_SIZE,
) -> str:
    """Dvouřádková tabulka čísel a písmen, po blocích nejvýše ``block_size``.

    Vrací jen tabulky a mezeru mezi bloky. Záhlaví varianty ani koncový
    odstavec dokumentu sem nepatří, aby šel stejný blok později vložit
    do společného klíče pro více zkoušek.
    """
    parts: list[str] = []
    chunks = split_answer_key_rows(rows, block_size=block_size)
    for index, chunk in enumerate(chunks):
        count = len(chunk)
        number_cells = "".join(_key_cell(str(position), "WrittenKeyNumber") for position, _letter in chunk)
        letter_cells = "".join(
            _key_cell(letter or "—", "WrittenKeyLetter") for _position, letter in chunk
        )
        parts.append(
            f'<table:table table:style-name="WrittenKeyTable{count}">'
            f'<table:table-column table:style-name="WrittenKeyCol{count}" '
            f'table:number-columns-repeated="{count}"/>'
            '<table:table-row table:style-name="WrittenKeyRow">'
            f"{number_cells}</table:table-row>"
            '<table:table-row table:style-name="WrittenKeyRow">'
            f"{letter_cells}</table:table-row>"
            "</table:table>"
        )
        if index != len(chunks) - 1:
            parts.append('<text:p text:style-name="WrittenKeyGap"/>')
    return "".join(parts)


def _key_cell(text: str, style: str) -> str:
    return (
        '<table:table-cell table:style-name="WrittenKeyCell" office:value-type="string">'
        f'<text:p text:style-name="{style}">{_odt_text(text)}</text:p>'
        "</table:table-cell>"
    )


def _questions_fragment(
    blocks: list[tuple[TestExamWrittenQuestion, list[TestExamWrittenAnswer]]],
    temp_dir: Path,
) -> tuple[str, list[tuple[str, Path]]]:
    parts: list[str] = []
    images: list[tuple[str, Path]] = []
    image_index = 1
    last_index = len(blocks) - 1
    for index, (question, answers) in enumerate(blocks):
        image_answers = question.answer_kind == ANSWER_KIND_IMAGE
        prompt_path = test_exam_service.resolve_snapshot_image(question.image_stored_path)
        has_prompt = prompt_path is not None
        xml_bits: list[str] = [
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
                max_h=(
                    _QUESTION_MAX_H_WITH_CHOICES_CM
                    if image_answers
                    else _QUESTION_MAX_H_CM
                ),
                min_w=_QUESTION_MIN_W_CM,
            )
            if frame:
                xml_bits.append(
                    f'<text:p text:style-name="WrittenImageLine">{frame}</text:p>'
                )
        if image_answers:
            choice_xml, image_index = _choice_images_table(
                answers,
                temp_dir,
                images,
                image_index,
                max_h=(
                    _ANSWER_MAX_H_WITH_PROMPT_CM if has_prompt else _ANSWER_MAX_H_CM
                ),
            )
            xml_bits.append(choice_xml)
        else:
            ordered = sorted(answers, key=lambda item: (item.position, item.id))
            for answer in ordered:
                xml_bits.append(
                    f'<text:p text:style-name="WrittenAnswer">'
                    f"{_odt_text(answer.letter)})  {_odt_text(answer.text)}</text:p>"
                )
        # Mezera jen mezi otázkami. Za poslední tabulkou by 14pt odstavec
        # s dolním odsazením přetekl na stránku, kde už je jen patička varianty.
        spacer = "" if index == last_index else '<text:p text:style-name="WrittenSpacer"/>'
        parts.append(
            '<table:table table:style-name="WrittenBlock">'
            '<table:table-column table:style-name="WrittenBlockCol"/>'
            '<table:table-row table:style-name="WrittenBlockRow">'
            '<table:table-cell table:style-name="WrittenBlockCell" office:value-type="string">'
            f"{''.join(xml_bits)}"
            "</table:table-cell></table:table-row></table:table>"
            f"{spacer}"
        )
    parts.append(_DOCUMENT_END)
    return "".join(parts), images


def _choice_images_table(
    answers: list[TestExamWrittenAnswer],
    temp_dir: Path,
    images: list[tuple[str, Path]],
    image_index: int,
    *,
    max_h: float,
) -> tuple[str, int]:
    """A/B/C v jednom řádku, aby se obrázky nerozdělily mezi stránky."""
    cells: list[str] = []
    ordered = sorted(answers, key=lambda item: (item.position, item.id))
    for answer in ordered:
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
        image_xml = (
            f'<text:p text:style-name="WrittenImageLine">{frame}</text:p>' if frame else ""
        )
        cells.append(
            '<table:table-cell table:style-name="WrittenBlockCell" office:value-type="string">'
            f'<text:p text:style-name="WrittenChoiceLabel">{_odt_text(answer.letter)})</text:p>'
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


def _frame_for(
    source: Path,
    temp_dir: Path,
    images: list[tuple[str, Path]],
    image_index: int,
    *,
    max_w: float,
    max_h: float,
    min_w: float,
) -> tuple[str, int]:
    embedded = _embed_source(source, temp_dir, f"written_{image_index:03d}")
    if embedded is None:
        return "", image_index
    archive_name, path = embedded
    width_cm, height_cm = _fit_cm(path, max_w=max_w, max_h=max_h, min_w=min_w)
    images.append((archive_name, path))
    name = f"written_{image_index:03d}"
    href = xml_escape(archive_name, {'"': "&quot;"})
    frame = (
        f'<draw:frame draw:style-name="WrittenImage" draw:name="{name}" '
        f'text:anchor-type="as-char" '
        f'svg:width="{width_cm:.2f}cm" svg:height="{height_cm:.2f}cm">'
        f'<draw:image xlink:href="{href}" xlink:type="simple" '
        f'xlink:show="embed" xlink:actuate="onLoad"/>'
        f"</draw:frame>"
    )
    return frame, image_index + 1


def _embed_source(source: Path, temp_dir: Path, name: str) -> tuple[str, Path] | None:
    if not source.is_file():
        return None
    suffix = source.suffix.lower()
    if suffix in _EMBED_SUFFIXES:
        stored = ".jpg" if suffix == ".jpeg" else suffix
        return f"Pictures/{name}{stored}", source
    target = temp_dir / f"{name}.png"
    try:
        with Image.open(source) as image:
            image.convert("RGB").save(target, "PNG")
    except Exception:
        return None
    if not target.is_file():
        return None
    return f"Pictures/{name}.png", target


def _fit_cm(path: Path, *, max_w: float, max_h: float, min_w: float) -> tuple[float, float]:
    """Jedno měřítko pro obě strany. Obrázek se nedeformuje a nevejde se do limitu."""
    width_px, height_px = 4, 3
    try:
        with Image.open(path) as image:
            width_px, height_px = image.size
    except Exception:
        width_px, height_px = 4, 3
    if width_px <= 0 or height_px <= 0:
        return max_w, min(max_h, max_w * 0.75)
    width_cm = width_px * 2.54 / 96.0
    height_cm = height_px * 2.54 / 96.0
    scale = 1.0
    if width_cm < min_w:
        scale = min_w / width_cm
    if width_cm * scale > max_w:
        scale = max_w / width_cm
    if height_cm * scale > max_h:
        scale = max_h / height_cm
    return width_cm * scale, height_cm * scale


def _odt_text(value: object) -> str:
    text = plain_export_text(value)
    escaped = xml_escape(text)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<text:line-break/>")


def _filename(prefix: str, exam: TestExam) -> str:
    parts = [prefix]
    first = _safe_filename_part(getattr(exam, "employee_first_name", ""))
    last = _safe_filename_part(getattr(exam, "employee_last_name", ""))
    if first:
        parts.append(first)
    if last:
        parts.append(last)
    if not first and not last:
        parts.append("zamestnanec")
    exam_day = getattr(exam, "exam_date", None)
    if isinstance(exam_day, date):
        parts.append(f"{exam_day.year:04d}-{exam_day.month:02d}-{exam_day.day:02d}")
    else:
        parts.append("bez-data")
    return "_".join(parts) + ".odt"


def _safe_filename_part(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", plain_export_text(value))
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in ascii_text.strip()
    )
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned[:40]


def _odt_path(path: str | Path) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".odt":
        target = target.with_suffix(".odt")
    return target


paper_test_export_service = PaperTestExportService()

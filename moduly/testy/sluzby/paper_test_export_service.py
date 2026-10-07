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

from core.export import (
    OdtExportEngine,
    OdtExportError,
    OdtParagraph,
    OdtXmlFragment,
    odt_rich,
)
from core.services.storage_service import storage_service
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    PAPER_TEST_INSTRUCTION,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
from moduly.testy.sluzby.exam_protocol_layout import (
    BLANK_EXAM_DATE_LINE,
    protocol_oral_items,
    protocol_people,
    render_paper_protocol_xml,
)
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


@dataclass(frozen=True)
class BatchExportFailure:
    employee_label: str
    path: Path
    message: str


@dataclass(frozen=True)
class BatchPaperExportResult:
    test_paths: tuple[Path, ...]
    key_path: Path | None
    failures: tuple[BatchExportFailure, ...]
    include_shared_key: bool


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
            oral_items = protocol_oral_items(test_exam_service.get_oral_questions(exam.id))
            people = protocol_people(exam, test_exam_service.get_examiners(exam.id))
            self.engine.render(
                template,
                target,
                {
                    "header": odt_rich(_header_paragraphs(exam, for_key=False)),
                    "questions": OdtXmlFragment(
                        xml=(
                            questions_xml
                            + render_paper_protocol_xml(
                                oral_items,
                                people,
                                gender=getattr(exam, "employee_gender", None),
                            )
                            + _DOCUMENT_END
                        ),
                        images=tuple(images),
                    ),
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

    def export_batch(
        self,
        exam_ids: list[int],
        directory: str | Path,
        *,
        include_shared_key: bool = False,
    ) -> BatchPaperExportResult:
        """Zapíše test každé zkoušky a volitelně jeden společný klíč.

        Selhání souboru nemaže zkoušky. Každý test čte jen svůj snapshot.
        """
        folder = Path(directory)
        if not folder.is_dir():
            raise TestExamError("Vyberte existující složku pro testy.")
        exams = []
        for exam_id in exam_ids:
            exam = test_exam_service.get_exam(exam_id)
            if exam is None or not self.can_export(exam_id):
                raise TestExamError(
                    "Písemný test lze vytvořit jen ze zkoušky s uloženým snapshotem otázek."
                )
            exams.append(exam)
        paths = assign_batch_test_paths(folder, exams)
        written: list[Path] = []
        failures: list[BatchExportFailure] = []
        for exam, path in zip(exams, paths, strict=True):
            try:
                self.export(exam.id, path, include_key=False)
            except (TestExamError, OdtExportError, OSError) as error:
                path.unlink(missing_ok=True)
                failures.append(
                    BatchExportFailure(
                        employee_label=_batch_employee_label(exam),
                        path=path,
                        message=str(error),
                    )
                )
                continue
            written.append(path.resolve())

        key_path: Path | None = None
        if include_shared_key and exams:
            key_target = assign_batch_key_path(folder, exams[0].exam_date)
            try:
                self._write_shared_key(exams, key_target)
            except (TestExamError, OdtExportError, OSError) as error:
                key_target.unlink(missing_ok=True)
                failures.append(
                    BatchExportFailure(
                        employee_label="Společný klíč",
                        path=key_target,
                        message=str(error),
                    )
                )
            else:
                key_path = key_target.resolve()
        return BatchPaperExportResult(
            test_paths=tuple(written),
            key_path=key_path,
            failures=tuple(failures),
            include_shared_key=include_shared_key,
        )

    def _write_shared_key(self, exams: list[TestExam], key_target: Path) -> None:
        template = self.key_template_path()
        if not template.is_file():
            raise TestExamError("Šablona klíče písemného testu nebyla nalezena.")
        first = exams[0]
        variants = []
        for exam in exams:
            questions = test_exam_service.get_written_questions(exam.id)
            blocks = [
                (question, test_exam_service.get_written_answers(question.id))
                for question in questions
            ]
            variants.append((exam, correct_answer_rows(blocks)))
        self.engine.render(
            template,
            key_target,
            {
                "header": odt_rich(_batch_key_header(first)),
                "answers": OdtXmlFragment(
                    xml=render_batch_answer_key_xml(variants) + _DOCUMENT_END
                ),
                "variant": "",
            },
        )


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
    paragraphs.append(OdtParagraph.text(BLANK_EXAM_DATE_LINE, style="WrittenMeta"))
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


def assign_batch_test_paths(directory: Path, exams: list[TestExam]) -> list[Path]:
    """Stejné jméno a datum dostanou v názvu osobní číslo, existující soubor se nepřepíše."""
    used: set[str] = set()
    paths: list[Path] = []
    for exam in exams:
        path = _free_test_path(directory, exam, used)
        used.add(path.name.casefold())
        paths.append(path)
    return paths


def assign_batch_key_path(directory: Path, exam_day: date | None) -> Path:
    stamp = exam_day.isoformat() if isinstance(exam_day, date) else "bez-data"
    candidate = directory / f"Klic_testu_{stamp}.odt"
    index = 2
    while candidate.exists():
        candidate = directory / f"Klic_testu_{stamp}_{index}.odt"
        index += 1
    return candidate


def _free_test_path(directory: Path, exam: TestExam, used: set[str]) -> Path:
    primary = directory / _filename("Test", exam)
    if not _name_taken(primary, used):
        return primary
    number = _safe_filename_part(getattr(exam, "employee_personal_number", "")) or str(int(exam.id))
    numbered = directory / f"{primary.stem}_{number}.odt"
    if not _name_taken(numbered, used):
        return numbered
    return directory / f"{primary.stem}_{number}_{int(exam.id)}.odt"


def _name_taken(path: Path, used: set[str]) -> bool:
    return path.name.casefold() in used or path.exists()


def batch_variant_heading(exam: TestExam) -> str:
    """Varianta, jméno a osobní číslo. Pracoviště ani komise se do klíče nepíšou."""
    parts = [variant_label(exam)]
    name = _employee_name(exam)
    number = plain_export_text(getattr(exam, "employee_personal_number", None))
    if name:
        parts.append(name)
    if number:
        parts.append(number)
    return " – ".join(part for part in parts if part)


def render_batch_answer_key_xml(
    variants: list[tuple[TestExam, list[tuple[int, str]]]],
) -> str:
    """Jedna varianta a její kompaktní tabulky jako jeden celek.

    Tabulky skládá ``render_compact_answer_key_xml``. Mezi variantami není
    konec stránky. Řádek s ``keep-together`` drží variantu pohromadě, dokud
    se vejde na stránku.
    """
    parts: list[str] = []
    for index, (exam, rows) in enumerate(variants):
        tables = render_compact_answer_key_xml(rows)
        parts.append(
            '<table:table table:style-name="WrittenKeyBatch">'
            '<table:table-column table:style-name="WrittenKeyBatchCol"/>'
            '<table:table-row table:style-name="WrittenKeyBatchRow">'
            '<table:table-cell table:style-name="WrittenKeyBatchCell" office:value-type="string">'
            f'<text:p text:style-name="WrittenKeyVariant">{_odt_text(batch_variant_heading(exam))}</text:p>'
            f"{tables}"
            "</table:table-cell></table:table-row></table:table>"
        )
        if index != len(variants) - 1:
            parts.append('<text:p text:style-name="WrittenKeyVariantGap"/>')
    return "".join(parts)


def _batch_key_header(exam: TestExam) -> list[OdtParagraph]:
    paragraphs = [
        OdtParagraph.text(plain_export_text(exam.test_name), style="WrittenTitle"),
    ]
    exam_day = _date_line(getattr(exam, "exam_date", None))
    if exam_day:
        paragraphs.append(OdtParagraph.text(exam_day, style="WrittenMeta"))
    return paragraphs


def _batch_employee_label(exam: TestExam) -> str:
    name = _employee_name(exam) or plain_export_text(getattr(exam, "employee_display_name", ""))
    number = plain_export_text(getattr(exam, "employee_personal_number", None))
    if name and number:
        return f"{name} ({number})"
    return name or number or variant_label(exam)


paper_test_export_service = PaperTestExportService()

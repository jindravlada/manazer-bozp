"""Přímý PDF přehled živé metodiky (Audity / Prověrky) — bez ODT a LibreOffice."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextLayout,
    QTextOption,
)
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

PDF_RESOLUTION = 72
PDF_MARGIN_MM = 14.0

METHODOLOGY_PDF_AUDIT_TITLE = "Přehled auditních otázek"
METHODOLOGY_PDF_PROVERKY_TITLE = "Přehled otázek prověrek BOZP"
METHODOLOGY_PDF_DIALOG_TITLE = "Exportovat otázky do PDF"
METHODOLOGY_PDF_FILTER = "PDF soubory (*.pdf)"
METHODOLOGY_PDF_SAVED = "PDF bylo uloženo."
METHODOLOGY_PDF_FAILED = "PDF se nepodařilo uložit."
METHODOLOGY_PDF_EMPTY_NOTE = "Metodika neobsahuje žádné aktivní otázky."

PARAM_VERIFICATION_TYPE = "Typ ověření"
PARAM_SEVERITY = "Závažnost"
PARAM_DESCRIPTION = "Popis"

_DEFAULT_AUDIT_FILENAME_STEM = "Prehled_auditnich_otazek"
_DEFAULT_PROVERKY_FILENAME_STEM = "Prehled_otazek_proverek_BOZP"


@dataclass(frozen=True)
class MethodologyQuestion:
    text: str
    params: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MethodologySection:
    title: str
    questions: tuple[MethodologyQuestion, ...] = ()


@dataclass(frozen=True)
class MethodologyGroup:
    title: str
    sections: tuple[MethodologySection, ...] = ()


@dataclass(frozen=True)
class MethodologyQuestionsDocument:
    title: str
    created_on: date
    question_count: int
    groups: tuple[MethodologyGroup, ...] = field(default_factory=tuple)


def default_audit_pdf_filename(created_on: date | None = None) -> str:
    return _dated_filename(_DEFAULT_AUDIT_FILENAME_STEM, created_on)


def default_proverky_pdf_filename(created_on: date | None = None) -> str:
    return _dated_filename(_DEFAULT_PROVERKY_FILENAME_STEM, created_on)


def _dated_filename(stem: str, created_on: date | None) -> str:
    day = (created_on or date.today()).isoformat()
    return f"{stem}_{day}.pdf"


def format_created_on(created_on: date) -> str:
    return created_on.strftime("%d. %m. %Y")


def methodology_questions_plain_text(document: MethodologyQuestionsDocument) -> str:
    """Stejný obsah jako PDF, bez stránkování — pro kontrolu a testy."""
    lines = [
        document.title,
        f"Datum vytvoření: {format_created_on(document.created_on)}",
        f"Počet aktivních otázek: {document.question_count}",
    ]
    if document.question_count == 0:
        lines.append(METHODOLOGY_PDF_EMPTY_NOTE)
        return "\n".join(lines)

    for group in document.groups:
        lines.append(group.title)
        for section in group.sections:
            lines.append(section.title)
            for question in section.questions:
                lines.append(question.text)
                for label, value in question.params:
                    lines.append(f"{label}: {value}")
    return "\n".join(lines)


def choose_pdf_save_path(
    parent: QWidget | None,
    *,
    default_filename: str,
    title: str = METHODOLOGY_PDF_DIALOG_TITLE,
) -> str | None:
    path, _selected = QFileDialog.getSaveFileName(
        parent,
        title,
        default_filename,
        METHODOLOGY_PDF_FILTER,
    )
    if not path:
        return None
    if not path.lower().endswith(".pdf"):
        path = f"{path}.pdf"
    return path


def write_methodology_questions_pdf(
    document: MethodologyQuestionsDocument,
    path: str | Path,
) -> None:
    target = str(path)
    writer = QPdfWriter(target)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(PDF_RESOLUTION)
    writer.setPageMargins(
        QMarginsF(PDF_MARGIN_MM, PDF_MARGIN_MM, PDF_MARGIN_MM, PDF_MARGIN_MM),
        QPageLayout.Unit.Millimeter,
    )
    writer.setTitle(document.title)
    writer.setCreator("Manažer BOZP")

    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError(METHODOLOGY_PDF_FAILED)

    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        _MethodologyPdfRenderer(writer, painter, document).render()
    finally:
        painter.end()


def _mm_to_pt(mm: float) -> float:
    return mm / 25.4 * PDF_RESOLUTION


def _pdf_font_family() -> str:
    preferred = ("DejaVu Sans", "Noto Sans", "Liberation Sans", "FreeSans")
    available = set(QFontDatabase.families())
    for family in preferred:
        if family in available:
            return family
    app = QApplication.instance()
    if app is not None:
        family = app.font().family()
        if family:
            return family
    return "Sans Serif"


class _MethodologyPdfRenderer:
    def __init__(
        self,
        writer: QPdfWriter,
        painter: QPainter,
        document: MethodologyQuestionsDocument,
    ) -> None:
        self._writer = writer
        self._painter = painter
        self._document = document
        self._family = _pdf_font_family()
        self._page_no = 1
        page = QRectF(writer.pageLayout().paintRectPixels(PDF_RESOLUTION))
        self._left = page.left()
        self._right = page.right()
        self._top = page.top()
        self._bottom = page.bottom() - _mm_to_pt(7)
        self._width = self._right - self._left
        self._y = self._top
        self._title_font = self._font(13, bold=True)
        self._meta_font = self._font(9)
        self._header_font = self._font(8)
        self._group_font = self._font(11, bold=True)
        self._section_font = self._font(10, bold=True)
        self._question_font = self._font(9)
        self._param_font = self._font(8)
        self._muted = QColor(70, 70, 70)

    def _font(self, size: float, *, bold: bool = False) -> QFont:
        font = QFont(self._family)
        font.setPointSizeF(size)
        font.setBold(bold)
        return font

    def render(self) -> None:
        self._draw_running_header()
        self._draw_document_meta()
        if self._document.question_count == 0:
            self._draw_paragraph(METHODOLOGY_PDF_EMPTY_NOTE, self._meta_font)
            self._draw_page_number()
            return

        for group in self._document.groups:
            self._draw_group(group)
        self._draw_page_number()

    def _draw_group(self, group: MethodologyGroup) -> None:
        if not group.sections:
            return
        first_section = group.sections[0]
        first_question = first_section.questions[0]
        keep = (
            self._heading_height(group.title, self._group_font)
            + self._heading_height(first_section.title, self._section_font)
            + self._min_question_keep_height(first_question)
        )
        self._ensure_space(keep)
        self._y += _mm_to_pt(2.2)
        self._draw_heading(group.title, self._group_font)
        for index, section in enumerate(group.sections):
            self._draw_section(section, first_in_group=(index == 0))

    def _draw_section(self, section: MethodologySection, *, first_in_group: bool) -> None:
        if not section.questions:
            return
        first_question = section.questions[0]
        keep = self._heading_height(section.title, self._section_font)
        keep += self._min_question_keep_height(first_question)
        if not first_in_group:
            self._ensure_space(keep)
        self._y += _mm_to_pt(1.4)
        self._draw_heading(section.title, self._section_font)
        for question in section.questions:
            self._draw_question(question)

    def _min_question_keep_height(self, question: MethodologyQuestion) -> float:
        full = self._question_height(question)
        line = QFontMetricsF(self._question_font).lineSpacing()
        return min(full, line * 2.2)

    def _draw_document_meta(self) -> None:
        self._draw_paragraph(self._document.title, self._title_font)
        self._y += _mm_to_pt(1.2)
        self._draw_paragraph(
            f"Datum vytvoření: {format_created_on(self._document.created_on)}",
            self._meta_font,
        )
        self._draw_paragraph(
            f"Počet aktivních otázek: {self._document.question_count}",
            self._meta_font,
        )
        self._y += _mm_to_pt(2.0)

    def _draw_running_header(self) -> None:
        metrics = QFontMetricsF(self._header_font)
        header_h = metrics.height()
        self._painter.setPen(self._muted)
        self._painter.setFont(self._header_font)
        header_rect = QRectF(self._left, self._top, self._width, header_h)
        self._painter.drawText(
            header_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._document.title,
        )
        self._painter.setPen(QColor(0, 0, 0))
        rule_y = self._top + header_h + 2
        self._painter.drawLine(
            int(self._left),
            int(rule_y),
            int(self._right),
            int(rule_y),
        )
        self._y = rule_y + _mm_to_pt(3.5)

    def _draw_page_number(self) -> None:
        metrics = QFontMetricsF(self._header_font)
        footer_y = self._bottom + _mm_to_pt(1.5)
        self._painter.setPen(self._muted)
        self._painter.setFont(self._header_font)
        self._painter.drawText(
            QRectF(self._left, footer_y, self._width, metrics.height()),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            f"Strana {self._page_no}",
        )
        self._painter.setPen(QColor(0, 0, 0))

    def _new_page(self) -> None:
        self._draw_page_number()
        if not self._writer.newPage():
            raise RuntimeError(METHODOLOGY_PDF_FAILED)
        self._page_no += 1
        self._y = self._top
        self._draw_running_header()

    def _ensure_space(self, height: float) -> None:
        if self._y + height <= self._bottom:
            return
        if self._y <= self._top + _mm_to_pt(8):
            return
        self._new_page()

    def _heading_height(self, text: str, font: QFont) -> float:
        lines = _wrap_text(text, font, self._width)
        metrics = QFontMetricsF(font)
        return len(lines) * metrics.lineSpacing() + _mm_to_pt(0.6)

    def _draw_heading(self, text: str, font: QFont) -> None:
        self._draw_paragraph(text, font)

    def _question_height(self, question: MethodologyQuestion) -> float:
        height = self._heading_height(question.text, self._question_font)
        if question.params:
            param_line = "   ".join(f"{label}: {value}" for label, value in question.params)
            height += self._heading_height(param_line, self._param_font)
        height += _mm_to_pt(1.1)
        return height

    def _draw_question(self, question: MethodologyQuestion) -> None:
        first_line = QFontMetricsF(self._question_font).lineSpacing()
        self._ensure_space(first_line + _mm_to_pt(0.4))
        self._draw_flowing_paragraph(question.text, self._question_font)
        if question.params:
            param_line = "   ".join(
                f"{label}: {value}" for label, value in question.params if value
            )
            if param_line:
                self._painter.setPen(self._muted)
                self._draw_flowing_paragraph(param_line, self._param_font)
                self._painter.setPen(QColor(0, 0, 0))
        self._y += _mm_to_pt(1.0)

    def _draw_paragraph(self, text: str, font: QFont) -> None:
        lines = _wrap_text(text, font, self._width)
        metrics = QFontMetricsF(font)
        line_h = metrics.lineSpacing()
        self._painter.setFont(font)
        for line in lines:
            if self._y + line_h > self._bottom:
                self._new_page()
                self._painter.setFont(font)
            self._painter.drawText(
                QRectF(self._left, self._y, self._width, line_h),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                line,
            )
            self._y += line_h

    def _draw_flowing_paragraph(self, text: str, font: QFont) -> None:
        self._draw_paragraph(text, font)


def _wrap_text(text: str, font: QFont, width: float) -> list[str]:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return [""]
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    lines: list[str] = []
    for paragraph in raw.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        layout = QTextLayout(paragraph, font)
        layout.setTextOption(option)
        layout.beginLayout()
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            start = line.textStart()
            length = line.textLength()
            lines.append(paragraph[start : start + length])
        layout.endLayout()
        if not lines:
            lines.append(paragraph)
    return lines or [""]

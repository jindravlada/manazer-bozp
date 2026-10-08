"""Studijní otázky k vybranému testu z aktuálního katalogu.

Dokument obsahuje všechny aktivní otázky aktivních okruhů testu.
Počet otázek losovaných u zkoušky se nepoužije a odpovědi se nepřehazují.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from core.export import OdtExportEngine, OdtExportError, OdtXmlFragment
from core.services.storage_service import storage_service
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    ANSWER_LETTERS,
    STUDY_ORAL_HEADING,
    STUDY_QUESTIONS_EMPTY,
    STUDY_QUESTIONS_TITLE,
    STUDY_WRITTEN_HEADING,
)
from moduly.testy.sluzby.oral_question_service import oral_question_service
from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
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
    _frame_for,
    _odt_path,
    _odt_text,
    _safe_filename_part,
)
from moduly.testy.sluzby.test_definition_service import test_definition_service
from moduly.testy.sluzby.written_question_service import written_question_service
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)

_TEMPLATE_SUBDIR = "exporty"
_TEMPLATE_NAME = "StudijniOtazky.odt"


class StudyQuestionsError(ValueError):
    pass


@dataclass(frozen=True)
class StudyAnswer:
    letter: str
    text: str
    is_correct: bool
    image_path: Path | None


@dataclass(frozen=True)
class StudyQuestion:
    question_id: int
    text: str
    image_path: Path | None
    answer_kind: str
    answers: tuple[StudyAnswer, ...]


@dataclass(frozen=True)
class StudyTopic:
    topic_id: int
    name: str
    questions: tuple[StudyQuestion, ...]


@dataclass(frozen=True)
class StudyMaterial:
    test_name: str
    written: tuple[StudyTopic, ...]
    oral: tuple[StudyTopic, ...]

    @property
    def has_questions(self) -> bool:
        return any(topic.questions for topic in self.written) or any(
            topic.questions for topic in self.oral
        )


class StudyQuestionsExportService:
    def __init__(self) -> None:
        self.engine = OdtExportEngine()

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(_TEMPLATE_SUBDIR, _TEMPLATE_NAME)

    def filename(self, test_name: str) -> str:
        safe = _safe_filename_part(test_name) or "test"
        return f"Studijni_otazky_{safe}.odt"

    def collect(self, test_id: int | None) -> StudyMaterial:
        test = test_definition_service.get_test(test_id)
        if test is None:
            raise StudyQuestionsError("Test nebyl nalezen.")
        written = ()
        oral = ()
        if test.uses_written:
            written = tuple(
                _written_topics(test_definition_service.get_written_topics(test.id))
            )
        if test.uses_oral:
            oral = tuple(
                _oral_topics(test_definition_service.get_oral_topics(test.id))
            )
        return StudyMaterial(test_name=test.name, written=written, oral=oral)

    def export(self, test_id: int | None, path: str | Path) -> Path:
        material = self.collect(test_id)
        if not material.has_questions:
            raise StudyQuestionsError(STUDY_QUESTIONS_EMPTY)
        target = _odt_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        template = self.template_path()
        if not template.is_file():
            raise StudyQuestionsError("Šablona studijních otázek nebyla nalezena.")
        try:
            with TemporaryDirectory(prefix="study-questions-") as temp_name:
                body, images = _body_xml(material, Path(temp_name))
                self.engine.render(
                    template,
                    target,
                    {
                        "header": OdtXmlFragment(xml=_header_xml(material.test_name)),
                        "body": OdtXmlFragment(xml=body, images=tuple(images)),
                    },
                )
        except OdtExportError as exc:
            raise StudyQuestionsError("Studijní otázky se nepodařilo vytvořit.") from exc
        return target


def _written_topics(links) -> list[StudyTopic]:
    topics: list[StudyTopic] = []
    seen_topics: set[int] = set()
    seen_questions: set[int] = set()
    for link in links:
        topic_id = int(link.topic_id)
        if topic_id in seen_topics:
            continue
        seen_topics.add(topic_id)
        topic = written_question_topic_service.get_topic(topic_id)
        if topic is None or not topic.active:
            continue
        questions: list[StudyQuestion] = []
        for question in written_question_service.list_questions(topic_id=topic_id):
            if not question.active or int(question.id) in seen_questions:
                continue
            if int(question.topic_id) != topic_id:
                continue
            seen_questions.add(int(question.id))
            questions.append(_written_question(question))
        if questions:
            topics.append(
                StudyTopic(
                    topic_id=topic_id,
                    name=topic.name,
                    questions=tuple(questions),
                )
            )
    return topics


def _written_question(question) -> StudyQuestion:
    answers = written_question_service.get_answers(question.id)
    ordered = sorted(answers, key=lambda item: (item.position, item.id))
    image_answers = question.answer_kind == ANSWER_KIND_IMAGE
    rendered: list[StudyAnswer] = []
    for index, answer in enumerate(ordered):
        letter = ANSWER_LETTERS[index] if index < len(ANSWER_LETTERS) else str(index + 1)
        image = None
        if image_answers:
            image = written_question_service.attachment_path(answer.image_attachment_id)
        rendered.append(
            StudyAnswer(
                letter=letter,
                text=answer.text or "",
                is_correct=bool(answer.is_correct),
                image_path=image,
            )
        )
    return StudyQuestion(
        question_id=int(question.id),
        text=question.text,
        image_path=written_question_service.attachment_path(question.image_attachment_id),
        answer_kind=question.answer_kind,
        answers=tuple(rendered),
    )


def _oral_topics(links) -> list[StudyTopic]:
    topics: list[StudyTopic] = []
    seen_topics: set[int] = set()
    seen_questions: set[int] = set()
    for link in links:
        topic_id = int(link.topic_id)
        if topic_id in seen_topics:
            continue
        seen_topics.add(topic_id)
        topic = oral_question_topic_service.get_topic(topic_id)
        if topic is None or not topic.active:
            continue
        questions: list[StudyQuestion] = []
        for question in oral_question_service.list_questions(topic_id=topic_id):
            if not question.active or int(question.id) in seen_questions:
                continue
            if int(question.topic_id) != topic_id:
                continue
            seen_questions.add(int(question.id))
            questions.append(
                StudyQuestion(
                    question_id=int(question.id),
                    text=question.text,
                    image_path=None,
                    answer_kind="",
                    answers=(),
                )
            )
        if questions:
            topics.append(
                StudyTopic(
                    topic_id=topic_id,
                    name=topic.name,
                    questions=tuple(questions),
                )
            )
    return topics


def _header_xml(test_name: str) -> str:
    return (
        f'<text:p text:style-name="WrittenTitle">{_odt_text(STUDY_QUESTIONS_TITLE)}</text:p>'
        f'<text:p text:style-name="WrittenMeta">{_odt_text(test_name)}</text:p>'
    )


def _body_xml(material: StudyMaterial, temp_dir: Path) -> tuple[str, list[tuple[str, Path]]]:
    images: list[tuple[str, Path]] = []
    image_index = 1
    parts: list[str] = []
    sections = []
    if material.written:
        sections.append((STUDY_WRITTEN_HEADING, material.written, False))
    if material.oral:
        sections.append((STUDY_ORAL_HEADING, material.oral, True))
    question_total = sum(len(topic.questions) for _title, topics, _oral in sections for topic in topics)
    emitted = 0
    for title, topics, oral in sections:
        parts.append(f'<text:p text:style-name="StudySection">{_odt_text(title)}</text:p>')
        number = 1
        for topic in topics:
            parts.append(f'<text:p text:style-name="StudyTopic">{_odt_text(topic.name)}</text:p>')
            for question in topic.questions:
                if oral:
                    block = _oral_block(number, question.text)
                else:
                    block, image_index = _written_block(
                        number,
                        question,
                        temp_dir,
                        images,
                        image_index,
                    )
                parts.append(block)
                emitted += 1
                number += 1
                if emitted != question_total:
                    parts.append('<text:p text:style-name="WrittenSpacer"/>')
    parts.append(_DOCUMENT_END)
    return "".join(parts), images


def _oral_block(number: int, text: str) -> str:
    return _question_table(
        f'<text:p text:style-name="WrittenQuestion">{number}. {_odt_text(text)}</text:p>'
    )


def _written_block(
    number: int,
    question: StudyQuestion,
    temp_dir: Path,
    images: list[tuple[str, Path]],
    image_index: int,
) -> tuple[str, int]:
    image_answers = question.answer_kind == ANSWER_KIND_IMAGE
    bits = [
        f'<text:p text:style-name="WrittenQuestion">{number}. {_odt_text(question.text)}</text:p>'
    ]
    if question.image_path is not None:
        frame, image_index = _frame_for(
            question.image_path,
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
            bits.append(f'<text:p text:style-name="WrittenImageLine">{frame}</text:p>')
    if image_answers:
        choice_xml, image_index = _choice_table(
            question.answers,
            temp_dir,
            images,
            image_index,
            max_h=(
                _ANSWER_MAX_H_WITH_PROMPT_CM
                if question.image_path is not None
                else _ANSWER_MAX_H_CM
            ),
        )
        bits.append(choice_xml)
    else:
        for answer in question.answers:
            bits.append(_text_answer(answer))
    return _question_table("".join(bits)), image_index


def _text_answer(answer: StudyAnswer) -> str:
    label = f"{answer.letter})  {_odt_text(answer.text)}"
    if answer.is_correct:
        label = (
            '<text:span text:style-name="ProtocolAnswerCorrect">'
            f"✓ {label}</text:span>"
        )
    return f'<text:p text:style-name="WrittenAnswer">{label}</text:p>'


def _choice_table(
    answers: tuple[StudyAnswer, ...],
    temp_dir: Path,
    images: list[tuple[str, Path]],
    image_index: int,
    *,
    max_h: float,
) -> tuple[str, int]:
    cells: list[str] = []
    for answer in answers:
        frame = ""
        if answer.image_path is not None:
            frame, image_index = _frame_for(
                answer.image_path,
                temp_dir,
                images,
                image_index,
                max_w=_ANSWER_MAX_W_CM,
                max_h=max_h,
                min_w=_ANSWER_MIN_W_CM,
            )
        mark = f"✓ {answer.letter})" if answer.is_correct else f"{answer.letter})"
        label = _odt_text(mark)
        if answer.is_correct:
            label = f'<text:span text:style-name="ProtocolAnswerCorrect">{label}</text:span>'
        image_xml = (
            f'<text:p text:style-name="WrittenImageLine">{frame}</text:p>' if frame else ""
        )
        cells.append(
            '<table:table-cell table:style-name="WrittenBlockCell" office:value-type="string">'
            f'<text:p text:style-name="StudyChoicePlain">{label}</text:p>'
            f"{image_xml}"
            "</table:table-cell>"
        )
    xml = (
        '<table:table table:style-name="WrittenChoices">'
        '<table:table-column table:style-name="WrittenChoiceCol" '
        'table:number-columns-repeated="3"/>'
        '<table:table-row table:style-name="WrittenBlockRow">'
        f"{''.join(cells)}"
        "</table:table-row></table:table>"
    )
    return xml, image_index


def _question_table(inner: str) -> str:
    return (
        '<table:table table:style-name="WrittenBlock">'
        '<table:table-column table:style-name="WrittenBlockCol"/>'
        '<table:table-row table:style-name="WrittenBlockRow">'
        '<table:table-cell table:style-name="WrittenBlockCell" office:value-type="string">'
        f"{inner}"
        "</table:table-cell></table:table-row></table:table>"
    )


study_questions_export_service = StudyQuestionsExportService()

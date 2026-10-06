"""Elektronická písemná část zkoušky. Služba není závislá na Qt.

Čas, ukládání voleb a ukončení písemné části jdou volat bez obrazovky.
Pokračování havarovaného testu po novém spuštění aplikace sem nepatří;
uložené volby a čas zahájení na to později stačí.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.testy.constants import (
    EXAM_STATUS_PREPARED,
    EXAM_STATUS_STARTED,
    WRITTEN_FINISH_EXPIRED,
    WRITTEN_FINISH_SUBMITTED,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
from moduly.testy.repository.test_exam_repository import TestExamRepository
from moduly.testy.sluzby.test_exam_service import TestExamError

# Není autorizace administrátora. Jen oddělená vývojová cesta ven ze zamčeného UI.
WRITTEN_EXAM_DEV_EXIT_ENV = "MANAGER_BOZP_WRITTEN_EXAM_DEV_EXIT"


class WrittenExamClosed(TestExamError):
    """Písemná část už nejde měnit, protože byla ukončena nebo vypršel čas."""


@dataclass(frozen=True)
class WrittenAnswerOption:
    exam_answer_id: int
    letter: str
    text: str
    image_stored_path: str


@dataclass(frozen=True)
class WrittenQuestionCard:
    exam_question_id: int
    position: int
    text: str
    image_stored_path: str
    options: tuple[WrittenAnswerOption, ...]
    selected_exam_answer_id: int | None


@dataclass(frozen=True)
class WrittenExamScreen:
    """Pohled pro zaměstnance. Bez správné odpovědi, poznámky i interních klíčů."""

    exam_id: int
    test_name: str
    employee_display_name: str
    duration_seconds: int
    started_at: datetime | None
    finished_at: datetime | None
    finish_reason: str
    status: str
    questions: tuple[WrittenQuestionCard, ...]

    @property
    def finished(self) -> bool:
        return bool(self.finish_reason)


class WrittenExamClock:
    def now(self) -> datetime:
        return datetime.now()


class FixedWrittenExamClock:
    """Řízený čas pro testy a pro obrazovku, která nesmí odpočítávat naslepo."""

    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment

    def set(self, moment: datetime) -> None:
        self.moment = moment


def written_exam_dev_exit_enabled() -> bool:
    return os.environ.get(WRITTEN_EXAM_DEV_EXIT_ENV) == "1"


def remaining_written_seconds(
    started_at: datetime,
    duration_seconds: int,
    now: datetime,
) -> int:
    """Celé zbývající sekundy od uloženého zahájení.

    Zpoždění aplikace čas nepřidá. Výsledek není nikdy větší než limit
    a po vypršení je 0.
    """
    duration = int(duration_seconds)
    if duration <= 0:
        return 0
    elapsed = (now - started_at).total_seconds()
    if elapsed <= 0:
        return duration
    remaining = duration - elapsed
    if remaining <= 0:
        return 0
    return int(remaining)


def format_remaining_clock(total_seconds: int) -> str:
    seconds = max(0, int(total_seconds))
    minutes, rest = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{rest:02d}"
    return f"{minutes:02d}:{rest:02d}"


def format_remaining_label(total_seconds: int) -> str:
    return f"Zbývá: {format_remaining_clock(total_seconds)}"


def can_start_electronic_written_state(
    status: str,
    uses_written: bool,
    question_count: int,
) -> bool:
    return (
        status == EXAM_STATUS_PREPARED
        and bool(uses_written)
        and int(question_count) > 0
    )


def start_confirmation_text(
    *,
    employee_name: str,
    test_name: str,
    question_count: int,
    duration_seconds: int,
) -> str:
    return (
        "Zahájit elektronickou písemnou část?\n\n"
        f"Zaměstnanec: {employee_name}\n"
        f"Test: {test_name}\n"
        f"Počet písemných otázek: {question_count}\n"
        f"Časový limit: {format_remaining_clock(duration_seconds)}"
    )


def clamp_question_index(index: int, count: int) -> int:
    if count <= 0:
        return 0
    if index < 0:
        return 0
    if index >= count:
        return count - 1
    return int(index)


def step_question_index(index: int, count: int, step: int) -> int:
    return clamp_question_index(int(index) + int(step), count)


def question_answer_marks(
    question_ids: list[int],
    answered_ids: set[int],
    current_index: int,
) -> list[tuple[bool, bool]]:
    """(zodpovězeno, právě otevřeno) v pořadí otázek."""
    current = clamp_question_index(current_index, len(question_ids))
    return [
        (int(question_id) in answered_ids, index == current)
        for index, question_id in enumerate(question_ids)
    ]


class WrittenExamService:
    def __init__(self) -> None:
        self.repository = TestExamRepository()

    def can_start(self, exam_id: int) -> bool:
        exam = self.repository.get_by_id(exam_id)
        if exam is None:
            return False
        count = len(self.repository.get_written_questions(exam_id))
        return can_start_electronic_written_state(
            exam.status,
            exam.uses_written,
            count,
        )

    def confirmation_text(self, exam_id: int) -> str:
        exam = self._loaded_exam(exam_id)
        questions = self.repository.get_written_questions(exam_id)
        return start_confirmation_text(
            employee_name=exam.employee_display_name,
            test_name=exam.test_name,
            question_count=len(questions),
            duration_seconds=exam.written_duration_seconds,
        )

    def start(self, exam_id: int, *, now: datetime | None = None) -> TestExam:
        moment = self._moment(now)
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            questions = self._questions(session, exam.id)
            if exam.status != EXAM_STATUS_PREPARED:
                raise TestExamError(
                    "Elektronický test lze zahájit jen u zkoušky ve stavu Připraveno."
                )
            if not exam.uses_written or not questions:
                raise TestExamError("Zkouška nemá písemnou část.")
            exam.status = EXAM_STATUS_STARTED
            exam.written_started_at = moment
            exam.written_finished_at = None
            exam.written_finish_reason = ""
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
            return exam
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def screen(self, exam_id: int) -> WrittenExamScreen:
        session = get_session()
        try:
            exam = self._require(session, exam_id)
            questions = self._questions(session, exam.id)
            choices = {
                int(choice.exam_question_id): choice
                for choice in self._choices(session, exam.id)
            }
            cards = []
            for question in questions:
                options = tuple(
                    WrittenAnswerOption(
                        exam_answer_id=int(answer.id),
                        letter=answer.letter,
                        text=answer.text or "",
                        image_stored_path=answer.image_stored_path or "",
                    )
                    for answer in self._answers(session, question.id)
                )
                choice = choices.get(int(question.id))
                cards.append(
                    WrittenQuestionCard(
                        exam_question_id=int(question.id),
                        position=int(question.position),
                        text=question.text,
                        image_stored_path=question.image_stored_path or "",
                        options=options,
                        selected_exam_answer_id=(
                            int(choice.exam_answer_id) if choice is not None else None
                        ),
                    )
                )
            return WrittenExamScreen(
                exam_id=int(exam.id),
                test_name=exam.test_name,
                employee_display_name=exam.employee_display_name,
                duration_seconds=int(exam.written_duration_seconds),
                started_at=exam.written_started_at,
                finished_at=exam.written_finished_at,
                finish_reason=exam.written_finish_reason or "",
                status=exam.status,
                questions=tuple(cards),
            )
        finally:
            session.close()

    def choices(self, exam_id: int) -> list[TestExamWrittenChoice]:
        self._loaded_exam(exam_id)
        return self.repository.get_written_choices(exam_id)

    def unanswered_count(self, exam_id: int) -> int:
        view = self.screen(exam_id)
        return sum(
            1 for question in view.questions if question.selected_exam_answer_id is None
        )

    def save_choice(
        self,
        exam_id: int,
        exam_question_id: int,
        exam_answer_id: int,
        *,
        now: datetime | None = None,
    ) -> None:
        moment = self._moment(now)
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            self._ensure_open(exam, moment)
            question = session.get(TestExamWrittenQuestion, int(exam_question_id))
            if question is None or int(question.exam_id) != int(exam.id):
                raise TestExamError("Otázka nepatří k této zkoušce.")
            answer = session.get(TestExamWrittenAnswer, int(exam_answer_id))
            if answer is None or int(answer.exam_question_id) != int(question.id):
                raise TestExamError("Odpověď nepatří k této otázce.")
            choice = session.scalar(
                select(TestExamWrittenChoice).where(
                    TestExamWrittenChoice.exam_id == int(exam.id),
                    TestExamWrittenChoice.exam_question_id == int(question.id),
                )
            )
            if choice is None:
                session.add(
                    TestExamWrittenChoice(
                        exam_id=int(exam.id),
                        exam_question_id=int(question.id),
                        exam_answer_id=int(answer.id),
                        selected_letter=answer.letter,
                        saved_at=moment,
                    )
                )
            else:
                choice.exam_answer_id = int(answer.id)
                choice.selected_letter = answer.letter
                choice.saved_at = moment
            session.commit()
        except WrittenExamClosed:
            session.commit()
            raise
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def submit(self, exam_id: int, *, now: datetime | None = None) -> str:
        """Ukončí písemnou část. Po vypršení času uloží důvod vypršení."""
        moment = self._moment(now)
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
                raise TestExamError("Písemná část není zahájená.")
            if exam.written_finish_reason:
                raise WrittenExamClosed("Písemná část už byla ukončena.")
            if (
                remaining_written_seconds(
                    exam.written_started_at,
                    exam.written_duration_seconds,
                    moment,
                )
                <= 0
            ):
                reason = WRITTEN_FINISH_EXPIRED
            else:
                reason = WRITTEN_FINISH_SUBMITTED
            self._mark_finished(exam, reason, moment)
            session.commit()
            return reason
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def sync_deadline(self, exam_id: int, *, now: datetime | None = None) -> str:
        """Když limit vypršel, ukončí písemnou část. Jinak vrátí stávající důvod."""
        moment = self._moment(now)
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            if exam.written_finish_reason:
                reason = exam.written_finish_reason
                session.rollback()
                return reason
            if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
                session.rollback()
                return ""
            if (
                remaining_written_seconds(
                    exam.written_started_at,
                    exam.written_duration_seconds,
                    moment,
                )
                > 0
            ):
                session.rollback()
                return ""
            self._mark_finished(exam, WRITTEN_FINISH_EXPIRED, moment)
            session.commit()
            return WRITTEN_FINISH_EXPIRED
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def _ensure_open(self, exam: TestExam, now: datetime) -> None:
        if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
            raise TestExamError("Písemná část není zahájená.")
        if exam.written_finish_reason:
            raise WrittenExamClosed("Písemná část už byla ukončena.")
        if (
            remaining_written_seconds(
                exam.written_started_at,
                exam.written_duration_seconds,
                now,
            )
            <= 0
        ):
            self._mark_finished(exam, WRITTEN_FINISH_EXPIRED, now)
            raise WrittenExamClosed("Čas písemné části vypršel.")

    def _mark_finished(self, exam: TestExam, reason: str, now: datetime) -> None:
        exam.written_finished_at = now
        exam.written_finish_reason = reason
        if exam.status == EXAM_STATUS_PREPARED:
            exam.status = EXAM_STATUS_STARTED

    def _moment(self, now: datetime | None) -> datetime:
        if now is None:
            return datetime.now()
        if not isinstance(now, datetime):
            raise TestExamError("Neplatný čas.")
        return now

    def _loaded_exam(self, exam_id: int) -> TestExam:
        exam = self.repository.get_by_id(exam_id)
        if exam is None:
            raise TestExamError("Zkouška nebyla nalezena.")
        return exam

    def _require(self, session, exam_id: int) -> TestExam:
        exam = session.get(TestExam, int(exam_id))
        if exam is None:
            raise TestExamError("Zkouška nebyla nalezena.")
        return exam

    def _questions(self, session, exam_id: int) -> list[TestExamWrittenQuestion]:
        stmt = (
            select(TestExamWrittenQuestion)
            .where(TestExamWrittenQuestion.exam_id == int(exam_id))
            .order_by(TestExamWrittenQuestion.position, TestExamWrittenQuestion.id)
        )
        return list(session.scalars(stmt))

    def _answers(self, session, exam_question_id: int) -> list[TestExamWrittenAnswer]:
        stmt = (
            select(TestExamWrittenAnswer)
            .where(TestExamWrittenAnswer.exam_question_id == int(exam_question_id))
            .order_by(TestExamWrittenAnswer.position, TestExamWrittenAnswer.id)
        )
        return list(session.scalars(stmt))

    def _choices(self, session, exam_id: int) -> list[TestExamWrittenChoice]:
        stmt = (
            select(TestExamWrittenChoice)
            .where(TestExamWrittenChoice.exam_id == int(exam_id))
            .order_by(TestExamWrittenChoice.id)
        )
        return list(session.scalars(stmt))


written_exam_service = WrittenExamService()

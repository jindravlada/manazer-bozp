"""Písemná část zkoušky. Služba není závislá na Qt.

Elektronický průběh měří čas od zahájení. Papírový přepis A/B/C ukládá
stejné volby a vyhodnotí je stejnou službou, ale časový limit jako dobu
přepisu nepoužívá. Pokračování nemění snapshot ani pořadí otázek.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import object_session

from core.database.session import get_session
from moduly.testy.constants import (
    ANSWER_LETTERS,
    ELECTRONIC_BLOCKS_PAPER,
    EXAM_STATUS_COMPLETED,
    EXAM_STATUS_PREPARED,
    EXAM_STATUS_STARTED,
    PAPER_BLOCKS_ELECTRONIC,
    PAPER_ENTRY_LOCKED,
    WRITTEN_FINISH_EXPIRED,
    WRITTEN_FINISH_PAPER,
    WRITTEN_FINISH_SUBMITTED,
    WRITTEN_MODE_ELECTRONIC,
    WRITTEN_MODE_PAPER,
    WRITTEN_OUTCOME_CORRECT,
    WRITTEN_OUTCOME_INCORRECT,
    WRITTEN_OUTCOME_UNANSWERED,
    WRITTEN_RESULT_FAILED,
    WRITTEN_RESULT_PASSED,
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


@dataclass
class _RunningExamClock:
    """Kotva jedné zkoušky v tomto procesu. Nepřežije ukončení aplikace."""

    started_at: datetime
    wall_anchor: datetime
    mono_anchor: float
    issued: datetime
    blocked: bool


_running_clocks: dict[tuple[str, int, str, str], _RunningExamClock] = {}


def _exam_clock_scope() -> str:
    from core.services.storage_service import storage_service

    return str(storage_service.database_path)


def _instant_key(moment: datetime) -> str:
    return moment.isoformat(sep=" ", timespec="microseconds")


def effective_exam_now(
    exam_id: int,
    started_at: datetime,
    wall_now: datetime,
    *,
    identity: str = "",
    monotonic_time: float | None = None,
) -> datetime:
    """Čas pro limit během běžící instance.

    Posun hodin zpět, který zůstane po zahájení, limit neprodlouží:
    platí vyšší z nástěnného času a času od monotónní kotvy.
    Čas starší než zahájení limit neobnoví. Vrátí se okamžik těsně
    před startem, aby zbývající čas byl 0 a zkouška skončila vypršením.
    Nový proces kotvu nemá. Tehdy čas starší než start také končí vypršením,
    takže se nevrátí celý limit. ``identity`` oddělí záznamy se stejným
    číslem, například po smazání řádku v testech.
    """
    mono = time.monotonic() if monotonic_time is None else float(monotonic_time)
    key = (_exam_clock_scope(), int(exam_id), _instant_key(started_at), identity)
    track = _running_clocks.get(key)
    if wall_now < started_at:
        if track is None:
            _running_clocks[key] = _RunningExamClock(
                started_at=started_at,
                wall_anchor=started_at,
                mono_anchor=mono,
                issued=started_at,
                blocked=True,
            )
        else:
            track.blocked = True
        return started_at - timedelta(microseconds=1)
    if track is not None and track.blocked:
        return started_at - timedelta(microseconds=1)
    if track is None:
        _running_clocks[key] = _RunningExamClock(
            started_at=started_at,
            wall_anchor=wall_now,
            mono_anchor=mono,
            issued=wall_now,
            blocked=False,
        )
        return wall_now
    elapsed = mono - track.mono_anchor
    if elapsed < 0:
        elapsed = 0.0
    from_mono = track.wall_anchor + timedelta(seconds=elapsed)
    candidate = wall_now if wall_now > from_mono else from_mono
    if candidate < track.issued:
        candidate = track.issued
    track.issued = candidate
    return candidate


def remaining_written_seconds(
    started_at: datetime,
    duration_seconds: int,
    now: datetime,
) -> int:
    """Celé zbývající sekundy od uloženého zahájení.

    Čas starší než zahájení je vypršení, ne nový plný limit.
    V okamžiku zahájení zbývá celý limit. Výsledek není nikdy větší
    než limit a po vypršení je 0.
    """
    duration = int(duration_seconds)
    if duration <= 0:
        return 0
    if now < started_at:
        return 0
    elapsed = (now - started_at).total_seconds()
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


def written_part_finished(
    *,
    status: str,
    written_finish_reason: str | None,
    written_finished_at: datetime | None,
) -> bool:
    """Písemná část už byla odevzdána, vypršela, nebo je zkouška dokončená."""
    return bool(
        str(written_finish_reason or "").strip()
        or written_finished_at is not None
        or status == EXAM_STATUS_COMPLETED
    )


def paper_blocked_by_electronic_mode(written_mode: str | None) -> bool:
    """NULL a prázdný režim ještě nejsou electronic."""
    return str(written_mode or "") == WRITTEN_MODE_ELECTRONIC


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


def is_written_part_in_progress(
    status: str,
    started_at: datetime | None,
    finished_at: datetime | None,
    finish_reason: str | None,
) -> bool:
    """Zahájeno, písemná část běží a ještě nebyla odevzdána ani vypršela."""
    return (
        status == EXAM_STATUS_STARTED
        and started_at is not None
        and finished_at is None
        and not str(finish_reason or "").strip()
    )


def normalize_answer_letter(value: object) -> str:
    """A/a, B/b a C/c. Cokoli jiného není platná odpověď."""
    text = str(value or "").strip()
    if len(text) != 1:
        return ""
    letter = text.upper()
    if letter not in ANSWER_LETTERS:
        return ""
    return letter


def electronic_written_action(
    *,
    status: str,
    uses_written: bool,
    question_count: int,
    written_started_at: datetime | None,
    written_finished_at: datetime | None,
    written_finish_reason: str | None,
    written_mode: str = "",
) -> str:
    """``continue``, ``start``, nebo prázdný řetězec, když akce není."""
    if str(written_mode or "") == WRITTEN_MODE_PAPER:
        return ""
    if is_written_part_in_progress(
        status,
        written_started_at,
        written_finished_at,
        written_finish_reason,
    ):
        return "continue"
    if can_start_electronic_written_state(status, uses_written, question_count):
        return "start"
    return ""


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


@dataclass(frozen=True)
class PaperEntryLine:
    """Jedna otázka v přepisu. Bez správné odpovědi a bez vyhodnocení."""

    exam_question_id: int
    position: int
    letter: str


@dataclass(frozen=True)
class PaperEntrySheet:
    exam_id: int
    employee_display_name: str
    test_name: str
    lines: tuple[PaperEntryLine, ...]

    @property
    def question_count(self) -> int:
        return len(self.lines)


@dataclass(frozen=True)
class WrittenPartScore:
    """Uložené vyhodnocení písemné části. Nezávisí na živé bance otázek."""

    question_count: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    allowed_wrong_answers: int
    result: str

    @property
    def error_count(self) -> int:
        return self.incorrect_count + self.unanswered_count


def score_written_outcomes(
    outcomes: list[str],
    allowed_wrong_answers: int,
) -> WrittenPartScore:
    """Chyba je chybná i nezodpovězená otázka. Limit se bere ze snapshotu zkoušky."""
    correct = 0
    incorrect = 0
    unanswered = 0
    for outcome in outcomes:
        if outcome == WRITTEN_OUTCOME_CORRECT:
            correct += 1
        elif outcome == WRITTEN_OUTCOME_INCORRECT:
            incorrect += 1
        elif outcome == WRITTEN_OUTCOME_UNANSWERED:
            unanswered += 1
        else:
            raise TestExamError("Neznámý výsledek písemné otázky.")
    allowed = int(allowed_wrong_answers)
    if isinstance(allowed_wrong_answers, bool) or allowed < 0:
        raise TestExamError("Povolený počet chyb není platný.")
    errors = incorrect + unanswered
    result = WRITTEN_RESULT_PASSED if errors <= allowed else WRITTEN_RESULT_FAILED
    return WrittenPartScore(
        question_count=len(outcomes),
        correct_count=correct,
        incorrect_count=incorrect,
        unanswered_count=unanswered,
        allowed_wrong_answers=allowed,
        result=result,
    )


class WrittenExamService:
    def __init__(self) -> None:
        self.repository = TestExamRepository()

    def can_start(self, exam_id: int) -> bool:
        return self.electronic_action(exam_id) == "start"

    def can_continue(self, exam_id: int) -> bool:
        return self.electronic_action(exam_id) == "continue"

    def electronic_action(self, exam_id: int) -> str:
        exam = self.repository.get_by_id(exam_id)
        if exam is None:
            return ""
        count = len(self.repository.get_written_questions(exam_id))
        return electronic_written_action(
            status=exam.status,
            uses_written=exam.uses_written,
            question_count=count,
            written_started_at=exam.written_started_at,
            written_finished_at=exam.written_finished_at,
            written_finish_reason=exam.written_finish_reason,
            written_mode=exam.written_mode or "",
        )

    def resume(self, exam_id: int, *, now: datetime | None = None) -> str:
        """Naváže na rozpracovaný test.

        Nezakládá zkoušku, snapshot ani nový čas. Když limit od původního
        zahájení už vypršel, písemnou část ukončí jako vypršení a vrátí
        ``expired``. Jinak vrátí prázdný řetězec a test zůstane otevřený.
        """
        if not self.can_continue(exam_id):
            raise TestExamError("V elektronickém testu nelze pokračovat.")
        before = self._loaded_exam(exam_id)
        started_at = before.written_started_at
        reason = self.sync_deadline(exam_id, now=now)
        after = self._loaded_exam(exam_id)
        if after.written_started_at != started_at:
            raise TestExamError("Čas písemné části se nesmí nastavit znovu.")
        if reason == WRITTEN_FINISH_EXPIRED:
            return reason
        if reason or not self.can_continue(exam_id):
            raise TestExamError("V elektronickém testu nelze pokračovat.")
        return ""

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
            if (exam.written_mode or "") == WRITTEN_MODE_PAPER:
                raise TestExamError(PAPER_BLOCKS_ELECTRONIC)
            if exam.status != EXAM_STATUS_PREPARED:
                raise TestExamError(
                    "Elektronický test lze zahájit jen u zkoušky ve stavu Připraveno."
                )
            if not exam.uses_written or not questions:
                raise TestExamError("Zkouška nemá písemnou část.")
            exam.status = EXAM_STATUS_STARTED
            exam.written_mode = WRITTEN_MODE_ELECTRONIC
            exam.written_started_at = moment
            exam.written_time_mark = moment
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

    def can_enter_paper(self, exam_id: int | None) -> bool:
        """Jedna připravená zkouška s písemným snapshotem, dokud část není hotová.

        Nevyplněný ``written_mode`` (NULL i prázdný řetězec) akci neblokuje.
        Režim electronic a dokončená písemná část ano.
        """
        if not exam_id:
            return False
        exam = self.repository.get_by_id(exam_id)
        if exam is None:
            return False
        if written_part_finished(
            status=exam.status,
            written_finish_reason=exam.written_finish_reason,
            written_finished_at=exam.written_finished_at,
        ):
            return False
        if paper_blocked_by_electronic_mode(exam.written_mode):
            return False
        if exam.status != EXAM_STATUS_PREPARED or exam.written_started_at is not None:
            return False
        if not exam.uses_written:
            return False
        return bool(self.repository.get_written_questions(exam.id))

    def paper_sheet(self, exam_id: int) -> PaperEntrySheet:
        """Přehled přepisu. Neobsahuje správné odpovědi ani vyhodnocení."""
        if not self.can_enter_paper(exam_id):
            raise TestExamError("Papírové odpovědi u této zkoušky nelze zadat.")
        session = get_session()
        try:
            exam = self._require(session, exam_id)
            choices = {
                int(choice.exam_question_id): choice
                for choice in self._choices(session, exam.id)
            }
            lines = []
            for question in self._questions(session, exam.id):
                choice = choices.get(int(question.id))
                lines.append(
                    PaperEntryLine(
                        exam_question_id=int(question.id),
                        position=int(question.position),
                        letter=choice.selected_letter if choice is not None else "",
                    )
                )
            return PaperEntrySheet(
                exam_id=int(exam.id),
                employee_display_name=exam.employee_display_name,
                test_name=exam.test_name,
                lines=tuple(lines),
            )
        finally:
            session.close()

    def save_paper_letter(
        self,
        exam_id: int,
        exam_question_id: int,
        letter: object,
        *,
        now: datetime | None = None,
    ) -> None:
        """Uloží A/B/C k otázce snapshotu. Časový limit zkoušky nespouští."""
        normalized = normalize_answer_letter(letter)
        if not normalized:
            raise TestExamError("Odpověď musí být A, B nebo C.")
        moment = self._moment(now)
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            self._ensure_paper_editable(session, exam)
            question = session.get(TestExamWrittenQuestion, int(exam_question_id))
            if question is None or int(question.exam_id) != int(exam.id):
                raise TestExamError("Otázka nepatří k této zkoušce.")
            answer = next(
                (
                    item
                    for item in self._answers(session, question.id)
                    if item.letter == normalized
                ),
                None,
            )
            if answer is None:
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
            exam.written_mode = WRITTEN_MODE_PAPER
            session.commit()
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def clear_paper_answer(self, exam_id: int, exam_question_id: int) -> None:
        """Smaže volbu otázky. Nezodpovězená otázka zůstane chybou až při vyhodnocení."""
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            self._ensure_paper_editable(session, exam)
            question = session.get(TestExamWrittenQuestion, int(exam_question_id))
            if question is None or int(question.exam_id) != int(exam.id):
                raise TestExamError("Otázka nepatří k této zkoušce.")
            choice = session.scalar(
                select(TestExamWrittenChoice).where(
                    TestExamWrittenChoice.exam_id == int(exam.id),
                    TestExamWrittenChoice.exam_question_id == int(question.id),
                )
            )
            if choice is not None:
                session.delete(choice)
            session.commit()
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def evaluate_paper(self, exam_id: int, *, now: datetime | None = None) -> TestExam:
        """Uzavře papírovou písemnou část stejným výpočtem jako elektronický test."""
        moment = self._moment(now)
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._require(session, exam_id)
            self._ensure_paper_editable(session, exam)
            exam.written_mode = WRITTEN_MODE_PAPER
            self._mark_finished(session, exam, WRITTEN_FINISH_PAPER, moment)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
            return exam
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

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
            moment = self._observed_now(exam, moment)
            self._ensure_open(session, exam, moment)
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
            self._apply_time_mark(session, exam, moment, minimum_step=None)
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
            moment = self._observed_now(exam, moment)
            if exam.written_finish_reason:
                raise WrittenExamClosed("Písemná část už byla ukončena.")
            if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
                raise TestExamError("Písemná část není zahájená.")
            if self._limit_reached(exam, moment):
                reason = WRITTEN_FINISH_EXPIRED
            else:
                reason = WRITTEN_FINISH_SUBMITTED
            self._mark_finished(session, exam, reason, moment)
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
            moment = self._observed_now(exam, moment)
            if exam.written_finish_reason:
                reason = exam.written_finish_reason
                session.rollback()
                return reason
            if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
                session.rollback()
                return ""
            if not self._limit_reached(exam, moment):
                exam_key = int(exam.id)
                session.rollback()
                self._write_time_mark(exam_key, moment, minimum_step=None)
                return ""
            self._mark_finished(session, exam, WRITTEN_FINISH_EXPIRED, moment)
            session.commit()
            return WRITTEN_FINISH_EXPIRED
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def _ensure_paper_editable(self, session, exam: TestExam) -> None:
        if written_part_finished(
            status=exam.status,
            written_finish_reason=exam.written_finish_reason,
            written_finished_at=exam.written_finished_at,
        ):
            raise TestExamError(PAPER_ENTRY_LOCKED)
        if (
            paper_blocked_by_electronic_mode(exam.written_mode)
            or exam.status == EXAM_STATUS_STARTED
            or exam.written_started_at is not None
        ):
            raise TestExamError(ELECTRONIC_BLOCKS_PAPER)
        if exam.status != EXAM_STATUS_PREPARED:
            raise TestExamError("Papírové odpovědi lze zadávat jen u připravené zkoušky.")
        questions = self._questions(session, exam.id)
        if not exam.uses_written or not questions:
            raise TestExamError("Zkouška nemá písemnou část.")

    def observed_now(self, exam_id: int, wall_now: datetime) -> datetime:
        """Stejný hlídaný čas, jaký použije uložení odpovědi a vypršení."""
        return self._observed_now(self._loaded_exam(exam_id), wall_now)

    def note_running_mark(
        self,
        exam_id: int,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> None:
        """Zapíše efektivní čas běžící zkoušky. Dokončenou zkoušku nemění.

        Průběžný zápis posune značku nejvýše jednou za sekundu.
        ``force`` je pro uložení odpovědi a řádné zavření okna.
        """
        wall = self._moment(now)
        session = get_session()
        pending: tuple[int, datetime] | None = None
        try:
            exam = self._require(session, exam_id)
            if not self._mark_is_open(exam):
                return
            moment = self._observed_now(exam, wall)
            if exam.written_started_at is not None and moment < exam.written_started_at:
                return
            pending = (int(exam.id), moment)
        finally:
            session.close()
        if pending is not None:
            self._write_time_mark(
                pending[0],
                pending[1],
                minimum_step=None if force else timedelta(seconds=1),
            )

    def _observed_now(self, exam: TestExam, wall_now: datetime) -> datetime:
        if exam.written_started_at is None:
            return wall_now
        created = exam.created_at or exam.written_started_at
        guarded = effective_exam_now(
            int(exam.id),
            exam.written_started_at,
            wall_now,
            identity=_instant_key(created),
        )
        if guarded < exam.written_started_at:
            return guarded
        floor = self._stored_time_floor(exam)
        if floor is not None and guarded < floor:
            return floor
        return guarded

    def _stored_time_floor(self, exam: TestExam) -> datetime | None:
        """Nejpozdější už zaznamenaný čas. Značka se nižším časem nenahrazuje."""
        if exam.written_time_mark is not None:
            return exam.written_time_mark
        latest_answer = self._latest_choice_saved_at(exam)
        candidates = [
            item
            for item in (exam.written_started_at, latest_answer)
            if item is not None
        ]
        if not candidates:
            return None
        return max(candidates)

    def _latest_choice_saved_at(self, exam: TestExam) -> datetime | None:
        session = object_session(exam)
        if session is None:
            return None
        return session.scalar(
            select(func.max(TestExamWrittenChoice.saved_at)).where(
                TestExamWrittenChoice.exam_id == int(exam.id)
            )
        )

    def _mark_is_open(self, exam: TestExam) -> bool:
        if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
            return False
        return not written_part_finished(
            status=exam.status,
            written_finish_reason=exam.written_finish_reason,
            written_finished_at=exam.written_finished_at,
        )

    def _apply_time_mark(
        self,
        session,
        exam: TestExam,
        moment: datetime,
        *,
        minimum_step: timedelta | None,
    ) -> None:
        """Podmíněný zápis ve stejné transakci. Starší čas novější značku nepřepíše."""
        if not self._mark_is_open(exam):
            return
        if exam.written_started_at is not None and moment < exam.written_started_at:
            return
        current = exam.written_time_mark
        if current is not None and moment <= current:
            return
        if (
            minimum_step is not None
            and current is not None
            and moment < current + minimum_step
        ):
            return
        self._conditional_mark_update(session, int(exam.id), moment)
        session.expire(exam, ["written_time_mark"])

    def _write_time_mark(
        self,
        exam_id: int,
        moment: datetime,
        *,
        minimum_step: timedelta | None,
    ) -> None:
        """Samostatný zápis. Podmínka se vyhodnotí až nad posledním commitnutým řádkem."""
        session = get_session()
        try:
            exam = session.get(TestExam, int(exam_id))
            if exam is None or not self._mark_is_open(exam):
                session.rollback()
                return
            current = exam.written_time_mark
            if exam.written_started_at is not None and moment < exam.written_started_at:
                session.rollback()
                return
            if current is not None and moment <= current:
                session.rollback()
                return
            if (
                minimum_step is not None
                and current is not None
                and moment < current + minimum_step
            ):
                session.rollback()
                return
            session.commit()
            self._conditional_mark_update(session, int(exam_id), moment)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _conditional_mark_update(self, session, exam_id: int, moment: datetime) -> None:
        session.execute(
            update(TestExam)
            .where(
                TestExam.id == int(exam_id),
                TestExam.status == EXAM_STATUS_STARTED,
                or_(
                    TestExam.written_finish_reason.is_(None),
                    TestExam.written_finish_reason == "",
                ),
                or_(
                    TestExam.written_time_mark.is_(None),
                    TestExam.written_time_mark < moment,
                ),
            )
            .values(written_time_mark=moment)
        )

    def _limit_reached(self, exam: TestExam, now: datetime) -> bool:
        if exam.written_started_at is None:
            return False
        return (
            remaining_written_seconds(
                exam.written_started_at,
                exam.written_duration_seconds,
                now,
            )
            <= 0
        )

    def _ensure_open(self, session, exam: TestExam, now: datetime) -> None:
        if exam.written_finish_reason:
            raise WrittenExamClosed("Písemná část už byla ukončena.")
        if exam.status != EXAM_STATUS_STARTED or exam.written_started_at is None:
            raise TestExamError("Písemná část není zahájená.")
        if self._limit_reached(exam, now):
            self._mark_finished(session, exam, WRITTEN_FINISH_EXPIRED, now)
            raise WrittenExamClosed("Čas písemné části vypršel.")

    def _mark_finished(self, session, exam: TestExam, reason: str, now: datetime) -> None:
        if exam.written_started_at is not None and now < exam.written_started_at:
            now = exam.written_started_at
        exam.written_finished_at = now
        exam.written_finish_reason = reason
        self._record_written_result(session, exam, now)
        exam.status = EXAM_STATUS_COMPLETED

    def _record_written_result(self, session, exam: TestExam, now: datetime) -> None:
        """Vyhodnotí snapshot této zkoušky. Už uložený výsledek znovu nepočítá."""
        if exam.written_evaluated_at is not None:
            return
        questions = self._questions(session, exam.id)
        choices = {
            int(choice.exam_question_id): choice
            for choice in self._choices(session, exam.id)
        }
        outcomes: list[str] = []
        for question in questions:
            choice = choices.get(int(question.id))
            if choice is None:
                outcomes.append(WRITTEN_OUTCOME_UNANSWERED)
                continue
            answer = session.get(TestExamWrittenAnswer, int(choice.exam_answer_id))
            if (
                answer is None
                or int(answer.exam_question_id) != int(question.id)
                or not answer.is_correct
            ):
                outcomes.append(WRITTEN_OUTCOME_INCORRECT)
                continue
            outcomes.append(WRITTEN_OUTCOME_CORRECT)
        score = score_written_outcomes(outcomes, int(exam.allowed_wrong_answers))
        exam.written_question_count = score.question_count
        exam.written_correct_count = score.correct_count
        exam.written_incorrect_count = score.incorrect_count
        exam.written_unanswered_count = score.unanswered_count
        exam.written_allowed_wrong_answers = score.allowed_wrong_answers
        exam.written_result = score.result
        exam.exam_result = score.result
        exam.written_evaluated_at = now

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

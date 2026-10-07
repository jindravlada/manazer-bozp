"""Příprava konkrétní zkoušky a neměnný snapshot. Služba není závislá na Qt."""

from __future__ import annotations

import calendar
import hashlib
import random
from datetime import date, datetime
from pathlib import Path

from core.database.session import get_session
from core.models.attachment import Attachment
from core.services.storage_service import storage_service
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.constants import (
    ANSWER_KIND_IMAGE,
    ANSWER_LETTERS,
    EXAM_ROLE_CHAIR,
    EXAM_ROLE_EXAMINER,
    EXAM_ROLE_MEMBER,
    EXAM_SNAPSHOT_ENTITY,
    EXAM_STATUS_COMPLETED,
    EXAM_STATUS_PREPARED,
    EXAMINER_MODE_COMMISSION,
    EXAMINER_MODE_NONE,
    EXAMINER_MODE_SINGLE,
    VALIDITY_UNIT_MONTHS,
    VALIDITY_UNIT_YEARS,
    WRITTEN_RESULT_FAILED,
    WRITTEN_RESULT_PASSED,
)
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.modely.test_exam_examiner import TestExamExaminer
from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
from moduly.testy.repository.test_exam_repository import TestExamRepository
from moduly.testy.sluzby.oral_question_service import oral_question_service
from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
from moduly.testy.sluzby.test_definition_service import (
    test_definition_service,
    total_written_seconds,
)
from moduly.testy.sluzby.test_employee_service import test_employee_service
from moduly.testy.sluzby.written_question_service import written_question_service
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)


class TestExamError(ValueError):
    pass


EXAMINEE_CANNOT_EXAMINE = (
    "Testovaný zaměstnanec nemůže být současně zkoušejícím ani členem/členkou komise."
)


def _batch_person_label(employee) -> str:
    name = str(getattr(employee, "display_name", "") or "").strip()
    if not name:
        name = " ".join(
            part
            for part in (
                str(getattr(employee, "last_name", "") or "").strip(),
                str(getattr(employee, "first_name", "") or "").strip(),
            )
            if part
        )
    number = str(getattr(employee, "personal_number", "") or "").strip()
    if number:
        return f"{name} ({number})" if name else number
    return name or "zaměstnanec"


def add_calendar_months(value: date, months: int) -> date:
    """Přičte kalendářní měsíce. 31. 1. + 1 měsíc je poslední únor, ne 31 dní."""
    year = value.year
    month_index = value.month + int(months)
    year += (month_index - 1) // 12
    month = (month_index - 1) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last_day))


def calculate_valid_until(exam_date: date, value: int, unit: str) -> date:
    """2 roky od 15. 12. 2026 jsou 15. 12. 2028, ne 730 dnů."""
    amount = int(value)
    if amount <= 0:
        raise TestExamError("Doba platnosti musí být větší než 0.")
    if unit == VALIDITY_UNIT_YEARS:
        return add_calendar_months(exam_date, amount * 12)
    if unit == VALIDITY_UNIT_MONTHS:
        return add_calendar_months(exam_date, amount)
    raise TestExamError("Zvolte jednotku platnosti.")


def format_exam_date(value: date) -> str:
    return f"{value.day}. {value.month}. {value.year}"


def select_and_shuffle(pools: list[tuple[str, list, int]], rng, *, oral: bool = False) -> list:
    """Z každého okruhu vezme přesně daný počet a výsledek promíchá.

    ``pools`` jsou trojice (název okruhu, dostupné otázky, požadovaný počet)
    v pořadí definice Testu. Jedna otázka se ve výsledku neopakuje.
    """
    chosen: list = []
    used: set[int] = set()
    label = "Ústní okruh" if oral else "Okruh"
    for topic_name, questions, count in pools:
        available = [question for question in questions if int(question.id) not in used]
        if len(available) < int(count):
            raise TestExamError(
                f"{label} „{topic_name}“ má {len(available)} aktivních otázek, "
                f"zkouška požaduje {int(count)}."
            )
        picked = list(rng.sample(available, int(count)))
        used.update(int(question.id) for question in picked)
        chosen.extend(picked)
    rng.shuffle(chosen)
    return chosen


def shuffle_answers(answers: list, rng) -> list:
    """Promíchá tři odpovědi a zachová právě jednu správnou."""
    if len(answers) != 3:
        raise TestExamError("Otázka v bance nemá právě 3 odpovědi.")
    if sum(1 for answer in answers if answer.is_correct) != 1:
        raise TestExamError("Otázka v bance nemá právě jednu správnou odpověď.")
    ordered = list(answers)
    rng.shuffle(ordered)
    return ordered


class TestExamService:
    def __init__(self) -> None:
        self.repository = TestExamRepository()

    def prepare_exam(
        self,
        *,
        employee_id: int | None,
        test_id: int | None,
        exam_date: date,
        valid_until: date | None = None,
        examiner_id: int | None = None,
        chair_id: int | None = None,
        member_ids: list[int] | None = None,
        rng: random.Random | None = None,
    ) -> TestExam:
        """Vytvoří celou zkoušku v jednom zápisu, nebo neuloží nic.

        ``rng`` je jen pro testy. Bez něj se použije systémový generátor.
        """
        generator = rng if rng is not None else random.SystemRandom()
        employee = self._require_active_employee(employee_id)
        test = self._require_active_test(test_id)
        exam_day = self._as_date(exam_date, "Zvolte datum zkoušky.")
        valid_day = (
            self._as_date(valid_until, "Zvolte datum „Platí do“.")
            if valid_until is not None
            else calculate_valid_until(exam_day, test.validity_value, test.validity_unit)
        )
        if valid_day < exam_day:
            raise TestExamError("Datum „Platí do“ nesmí být před datem zkoušky.")

        people = self._validate_people(
            test.examiner_mode,
            employee_id=int(employee.id),
            examiner_id=examiner_id,
            chair_id=chair_id,
            member_ids=list(member_ids or []),
        )
        written_plan = []
        oral_plan = []
        if test.uses_written:
            written_plan = self._plan_written(test.id, generator)
        if test.uses_oral:
            oral_plan = self._plan_oral(test.id, generator)
        duration = (
            total_written_seconds(len(written_plan), test.seconds_per_question)
            if test.uses_written
            else 0
        )

        created_files: list[Path] = []
        committed = False
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = self._insert_prepared_exam(
                session,
                employee=employee,
                test=test,
                exam_day=exam_day,
                valid_day=valid_day,
                people=people,
                written_plan=written_plan,
                oral_plan=oral_plan,
                duration=duration,
                created_files=created_files,
            )
            session.commit()
            committed = True
            session.refresh(exam)
            session.expunge(exam)
            return exam
        except TestExamError:
            session.rollback()
            raise
        except Exception as error:
            session.rollback()
            raise TestExamError("Zkoušku se nepodařilo připravit.") from error
        finally:
            if not committed:
                self._discard_files(created_files)
            session.close()

    def prepare_paper_batch(
        self,
        *,
        employee_ids: list[int],
        test_id: int | None,
        exam_date: date,
        valid_until: date | None = None,
        examiner_id: int | None = None,
        chair_id: int | None = None,
        member_ids: list[int] | None = None,
        rng: random.Random | None = None,
    ) -> list[TestExam]:
        """Připraví samostatnou zkoušku každému zaměstnanci v jedné transakci.

        Kontroly, které lze udělat předem, proběhnou dřív, než se cokoli zapíše.
        Každá zkouška má vlastní snapshot a vlastní losování. Při chybě nezůstane
        část dávky.
        """
        generator = rng if rng is not None else random.SystemRandom()
        members = list(member_ids or [])
        test = self._require_active_test(test_id)
        if not test.uses_written:
            raise TestExamError("Hromadně lze připravit jen test s písemnou částí.")
        exam_day = self._as_date(exam_date, "Zvolte datum zkoušky.")
        valid_day = (
            self._as_date(valid_until, "Zvolte datum „Platí do“.")
            if valid_until is not None
            else calculate_valid_until(exam_day, test.validity_value, test.validity_unit)
        )
        if valid_day < exam_day:
            raise TestExamError("Datum „Platí do“ nesmí být před datem zkoušky.")

        employees = self._batch_employees(employee_ids)
        self._reject_batch_conflicts(
            test.examiner_mode,
            employees,
            examiner_id=examiner_id,
            chair_id=chair_id,
            member_ids=members,
        )
        try:
            self._validate_people(
                test.examiner_mode,
                employee_id=int(employees[0].id),
                examiner_id=examiner_id,
                chair_id=chair_id,
                member_ids=members,
            )
        except TestExamError as error:
            raise TestExamError(f"{error}\nNevytvořila se žádná zkouška.") from error

        try:
            plans = []
            for employee in employees:
                people = self._validate_people(
                    test.examiner_mode,
                    employee_id=int(employee.id),
                    examiner_id=examiner_id,
                    chair_id=chair_id,
                    member_ids=members,
                )
                written_plan = self._plan_written(test.id, generator) if test.uses_written else []
                oral_plan = self._plan_oral(test.id, generator) if test.uses_oral else []
                duration = (
                    total_written_seconds(len(written_plan), test.seconds_per_question)
                    if test.uses_written
                    else 0
                )
                plans.append((employee, people, written_plan, oral_plan, duration))
        except TestExamError as error:
            raise TestExamError(f"{error}\nNevytvořila se žádná zkouška.") from error

        created_files: list[Path] = []
        committed = False
        session = get_session()
        session.expire_on_commit = False
        created: list[TestExam] = []
        try:
            for employee, people, written_plan, oral_plan, duration in plans:
                created.append(
                    self._insert_prepared_exam(
                        session,
                        employee=employee,
                        test=test,
                        exam_day=exam_day,
                        valid_day=valid_day,
                        people=people,
                        written_plan=written_plan,
                        oral_plan=oral_plan,
                        duration=duration,
                        created_files=created_files,
                    )
                )
            session.commit()
            committed = True
            for exam in created:
                session.refresh(exam)
                session.expunge(exam)
            return created
        except TestExamError as error:
            session.rollback()
            raise TestExamError(f"{error}\nNevytvořila se žádná zkouška.") from error
        except Exception as error:
            session.rollback()
            raise TestExamError(
                "Hromadnou přípravu se nepodařilo dokončit.\nNevytvořila se žádná zkouška."
            ) from error
        finally:
            if not committed:
                self._discard_files(created_files)
            session.close()

    def _insert_prepared_exam(
        self,
        session,
        *,
        employee,
        test,
        exam_day: date,
        valid_day: date,
        people: list[dict],
        written_plan: list[dict],
        oral_plan: list[dict],
        duration: int,
        created_files: list[Path],
    ) -> TestExam:
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=test.id,
            exam_date=exam_day,
            valid_until=valid_day,
            status=EXAM_STATUS_PREPARED,
            examiner_mode=test.examiner_mode,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_title_before=employee.title_before or "",
            employee_title_after=employee.title_after or "",
            employee_display_name=employee.display_name,
            employee_workplace_name=self._workplace_name(employee.workplace_id),
            employee_roles_text=self._roles_text(employee.id),
            test_name=test.name,
            uses_written=bool(test.uses_written),
            uses_oral=bool(test.uses_oral),
            allowed_wrong_answers=int(test.allowed_wrong_answers),
            seconds_per_question=int(test.seconds_per_question),
            written_duration_seconds=duration,
            validity_value=int(test.validity_value),
            validity_unit=test.validity_unit,
        )
        session.add(exam)
        session.flush()

        for position, person in enumerate(people, start=1):
            session.add(
                TestExamExaminer(
                    exam_id=exam.id,
                    employee_id=person["employee"].id,
                    display_name=person["employee"].display_name,
                    role=person["role"],
                    position=position,
                )
            )

        for position, item in enumerate(written_plan, start=1):
            question = item["question"]
            row = TestExamWrittenQuestion(
                exam_id=exam.id,
                source_question_id=question.id,
                topic_name=item["topic_name"],
                text=question.text,
                answer_kind=question.answer_kind,
                position=position,
                image_stored_path="",
                image_sha256="",
            )
            session.add(row)
            session.flush()
            if question.image_attachment_id:
                path, digest = self._freeze_image(
                    session,
                    exam.id,
                    question.image_attachment_id,
                    f"q{position}-zadani",
                    created_files,
                )
                row.image_stored_path = path
                row.image_sha256 = digest
            for answer_position, answer in enumerate(item["answers"], start=1):
                letter = ANSWER_LETTERS[answer_position - 1]
                answer_row = TestExamWrittenAnswer(
                    exam_question_id=row.id,
                    letter=letter,
                    position=answer_position,
                    text=answer.text or "",
                    is_correct=bool(answer.is_correct),
                    image_stored_path="",
                    image_sha256="",
                )
                session.add(answer_row)
                session.flush()
                if question.answer_kind == ANSWER_KIND_IMAGE:
                    path, digest = self._freeze_image(
                        session,
                        exam.id,
                        answer.image_attachment_id,
                        f"q{position}-{letter.lower()}",
                        created_files,
                    )
                    answer_row.image_stored_path = path
                    answer_row.image_sha256 = digest

        for position, item in enumerate(oral_plan, start=1):
            session.add(
                TestExamOralQuestion(
                    exam_id=exam.id,
                    source_question_id=item["question"].id,
                    topic_name=item["topic_name"],
                    text=item["question"].text,
                    position=position,
                )
            )
        return exam

    def _batch_employees(self, employee_ids: list[int]) -> list:
        if not employee_ids:
            raise TestExamError("Vyberte alespoň jednoho zaměstnance.")
        ordered = []
        seen: set[int] = set()
        missing: list[str] = []
        inactive: list[str] = []
        for raw in employee_ids:
            try:
                employee_id = int(raw)
            except (TypeError, ValueError):
                missing.append(str(raw))
                continue
            if employee_id in seen:
                raise TestExamError("Zaměstnanec je ve výběru vícekrát.")
            seen.add(employee_id)
            employee = test_employee_service.get_employee(employee_id)
            if employee is None:
                missing.append(str(employee_id))
                continue
            if not employee.active:
                inactive.append(_batch_person_label(employee))
                continue
            ordered.append(employee)
        if missing or inactive:
            lines = ["Hromadnou přípravu nelze provést."]
            if missing:
                lines.append("Zaměstnanec nebyl nalezen: " + ", ".join(missing) + ".")
            if inactive:
                lines.append("Zkoušku lze připravit jen pro aktivního zaměstnance:")
                lines.extend(inactive)
            lines.append("Nevytvořila se žádná zkouška.")
            raise TestExamError("\n".join(lines))
        return ordered

    def _reject_batch_conflicts(
        self,
        mode: str,
        employees: list,
        *,
        examiner_id: int | None,
        chair_id: int | None,
        member_ids: list[int],
    ) -> None:
        blocked: set[int] = set()
        if mode == EXAMINER_MODE_SINGLE and examiner_id is not None:
            blocked.add(int(examiner_id))
        elif mode == EXAMINER_MODE_COMMISSION:
            if chair_id is not None:
                blocked.add(int(chair_id))
            blocked.update(int(member_id) for member_id in member_ids)
        conflicts = [employee for employee in employees if int(employee.id) in blocked]
        if not conflicts:
            return
        lines = [
            "Hromadnou přípravu nelze provést. "
            "Tito zaměstnanci jsou současně vybraní ke zkoušce a jako zkoušející nebo člen(ka) komise:",
        ]
        lines.extend(_batch_person_label(employee) for employee in conflicts)
        lines.append("Nevytvořila se žádná zkouška.")
        raise TestExamError("\n".join(lines))

    def get_exam(self, exam_id: int | None) -> TestExam | None:
        if not exam_id:
            return None
        return self.repository.get_by_id(exam_id)

    def list_exams(self) -> list[TestExam]:
        return self.repository.get_all()

    def get_examiners(self, exam_id: int) -> list[TestExamExaminer]:
        self._require_exam(exam_id)
        return self.repository.get_examiners(exam_id)

    def get_written_questions(self, exam_id: int) -> list[TestExamWrittenQuestion]:
        self._require_exam(exam_id)
        return self.repository.get_written_questions(exam_id)

    def get_written_answers(self, exam_question_id: int) -> list[TestExamWrittenAnswer]:
        return self.repository.get_written_answers(exam_question_id)

    def get_written_choices(self, exam_id: int) -> list[TestExamWrittenChoice]:
        self._require_exam(exam_id)
        return self.repository.get_written_choices(exam_id)

    def get_oral_questions(self, exam_id: int) -> list[TestExamOralQuestion]:
        self._require_exam(exam_id)
        return self.repository.get_oral_questions(exam_id)

    def oral_failure_action(self, exam: TestExam | None) -> str:
        """``record``, ``clear``, nebo prázdný řetězec, když akce není."""
        if exam is None or not self._oral_failure_exam_ready(exam):
            return ""
        if exam.oral_failed_at is not None:
            return "clear"
        return "record"

    def record_oral_failure(self, exam_id: int, *, now: datetime | None = None) -> TestExam:
        """Zapíše neúspěch ústní části. Písemný výsledek ani jeho počty nemění."""
        moment = self._moment(now)
        return self._update_oral_failure(exam_id, failed_at=moment)

    def clear_oral_failure(self, exam_id: int) -> TestExam:
        """Zruší evidovaný neúspěch a vrátí výsledek zkoušky na uložený písemný."""
        return self._update_oral_failure(exam_id, failed_at=None)

    def _oral_failure_exam_ready(self, exam: TestExam) -> bool:
        return (
            exam.status == EXAM_STATUS_COMPLETED
            and bool(exam.uses_oral)
            and exam.written_result == WRITTEN_RESULT_PASSED
        )

    def _update_oral_failure(
        self,
        exam_id: int,
        *,
        failed_at: datetime | None,
    ) -> TestExam:
        session = get_session()
        session.expire_on_commit = False
        try:
            exam = session.get(TestExam, int(exam_id))
            if exam is None:
                raise TestExamError("Zkouška nebyla nalezena.")
            self._validate_oral_failure_change(exam, recording=failed_at is not None)
            if failed_at is None:
                exam.oral_failed_at = None
                exam.exam_result = exam.written_result
            else:
                exam.oral_failed_at = failed_at
                exam.exam_result = WRITTEN_RESULT_FAILED
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
            return exam
        except TestExamError:
            session.rollback()
            raise
        finally:
            session.close()

    def _validate_oral_failure_change(self, exam: TestExam, *, recording: bool) -> None:
        if exam.status != EXAM_STATUS_COMPLETED:
            raise TestExamError(
                "Neúspěch ústní části lze zaznamenat jen u dokončené zkoušky."
                if recording
                else "Neúspěch ústní části lze zrušit jen u dokončené zkoušky."
            )
        if not exam.uses_oral:
            raise TestExamError("Zkouška podle snapshotu nemá ústní část.")
        if exam.written_result != WRITTEN_RESULT_PASSED:
            raise TestExamError(
                "Neúspěch ústní části lze zaznamenat jen když písemná část vyhověla."
            )
        if recording and exam.oral_failed_at is not None:
            raise TestExamError("Neúspěch ústní části už je zaznamenán.")
        if not recording and exam.oral_failed_at is None:
            raise TestExamError("Neúspěch ústní části není zaznamenán.")

    def _moment(self, now: datetime | None) -> datetime:
        if now is None:
            return datetime.now()
        if not isinstance(now, datetime):
            raise TestExamError("Neplatný čas.")
        return now

    def resolve_snapshot_image(self, relative_path: str | None) -> Path | None:
        text = str(relative_path or "").strip()
        if not text:
            return None
        path = storage_service.attachment_absolute(text)
        return path if path.is_file() else None

    def _plan_written(self, test_id: int, rng) -> list[dict]:
        pools = []
        for quota in test_definition_service.get_written_topics(test_id):
            topic = written_question_topic_service.get_topic(quota.topic_id)
            if topic is None:
                raise TestExamError("Zvolený okruh neexistuje.")
            questions = (
                written_question_service.list_questions(
                    include_inactive=False,
                    topic_id=topic.id,
                )
                if topic.active
                else []
            )
            pools.append((topic.name, questions, quota.question_count))
        selected = select_and_shuffle(pools, rng, oral=False)
        plan = []
        for question in selected:
            topic = written_question_topic_service.get_topic(question.topic_id)
            answers = shuffle_answers(
                written_question_service.get_answers(question.id),
                rng,
            )
            plan.append(
                {
                    "question": question,
                    "topic_name": topic.name if topic is not None else "",
                    "answers": answers,
                }
            )
        return plan

    def _plan_oral(self, test_id: int, rng) -> list[dict]:
        pools = []
        for quota in test_definition_service.get_oral_topics(test_id):
            topic = oral_question_topic_service.get_topic(quota.topic_id)
            if topic is None:
                raise TestExamError("Zvolený okruh neexistuje.")
            questions = (
                oral_question_service.list_questions(
                    include_inactive=False,
                    topic_id=topic.id,
                )
                if topic.active
                else []
            )
            pools.append((topic.name, questions, quota.question_count))
        selected = select_and_shuffle(pools, rng, oral=True)
        plan = []
        for question in selected:
            topic = oral_question_topic_service.get_topic(question.topic_id)
            plan.append(
                {
                    "question": question,
                    "topic_name": topic.name if topic is not None else "",
                }
            )
        return plan

    def _validate_people(
        self,
        mode: str,
        *,
        employee_id: int,
        examiner_id: int | None,
        chair_id: int | None,
        member_ids: list[int],
    ) -> list[dict]:
        if mode == EXAMINER_MODE_NONE:
            if examiner_id or chair_id or member_ids:
                raise TestExamError("Tento test nevyžaduje zkoušejícího.")
            return []
        if mode == EXAMINER_MODE_SINGLE:
            if chair_id or member_ids:
                raise TestExamError("Tento test má jednoho zkoušejícího, ne komisi.")
            examiner = self._require_other_examiner(
                examiner_id,
                employee_id,
                "Zkoušejícího",
            )
            return [{"employee": examiner, "role": EXAM_ROLE_EXAMINER}]
        if mode == EXAMINER_MODE_COMMISSION:
            if examiner_id:
                raise TestExamError(
                    "U komise se vybírá předseda/předsedkyně komise a člen(ka) komise."
                )
            chair = self._require_other_examiner(
                chair_id,
                employee_id,
                "Předsedu/předsedkyni komise",
            )
            if not member_ids:
                raise TestExamError("Přidejte alespoň člena/členku komise.")
            people = [{"employee": chair, "role": EXAM_ROLE_CHAIR}]
            seen = {int(chair.id)}
            for member_id in member_ids:
                member = self._require_other_examiner(
                    member_id,
                    employee_id,
                    "Člena/členku komise",
                )
                if int(member.id) in seen:
                    if int(member.id) == int(chair.id):
                        raise TestExamError(
                            "Předseda/předsedkyně komise nemůže být současně členem/členkou komise."
                        )
                    raise TestExamError("Osoba je v komisi vícekrát.")
                seen.add(int(member.id))
                people.append({"employee": member, "role": EXAM_ROLE_MEMBER})
            return people
        raise TestExamError("Zvolte režim zkoušejících.")

    def _require_other_examiner(
        self,
        selected_id: int | None,
        employee_id: int,
        label: str,
    ):
        if selected_id is not None and int(selected_id) == int(employee_id):
            raise TestExamError(EXAMINEE_CANNOT_EXAMINE)
        return self._require_eligible(selected_id, label)

    def _require_eligible(self, employee_id: int | None, label: str):
        employee = test_employee_service.get_employee(employee_id)
        if employee is None or not employee.active or not employee.may_examine:
            raise TestExamError(
                f"{label} lze vybrat jen z aktivních zaměstnanců, kteří mohou zkoušet."
            )
        return employee

    def _require_active_employee(self, employee_id: int | None):
        if not employee_id:
            raise TestExamError("Zvolte zaměstnance.")
        employee = test_employee_service.get_employee(int(employee_id))
        if employee is None:
            raise TestExamError("Zaměstnanec nebyl nalezen.")
        if not employee.active:
            raise TestExamError("Zkoušku lze připravit jen pro aktivního zaměstnance.")
        return employee

    def _require_active_test(self, test_id: int | None):
        if not test_id:
            raise TestExamError("Zvolte test.")
        test = test_definition_service.get_test(int(test_id))
        if test is None:
            raise TestExamError("Test nebyl nalezen.")
        if not test.active:
            raise TestExamError("Zkoušku lze připravit jen podle aktivního testu.")
        return test

    def _require_exam(self, exam_id: int) -> TestExam:
        exam = self.repository.get_by_id(int(exam_id))
        if exam is None:
            raise TestExamError("Zkouška nebyla nalezena.")
        return exam

    def _as_date(self, value, message: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        raise TestExamError(message)

    def _workplace_name(self, workplace_id: int) -> str:
        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace is not None else ""

    def _roles_text(self, employee_id: int) -> str:
        names = []
        for role_id in test_employee_service.get_role_ids(employee_id):
            role = responsibility_role_service.get_by_id(role_id)
            if role is not None and role.name:
                names.append(role.name)
        return ", ".join(names)

    def _freeze_image(
        self,
        session,
        exam_id: int,
        attachment_id: int | None,
        name: str,
        created_files: list[Path],
    ) -> tuple[str, str]:
        source = written_question_service.attachment_path(attachment_id)
        if source is None:
            raise TestExamError("Obrázek se nepodařilo zmrazit.")
        # Bajty už normalizovaného obrázku. Snapshot je znovu nezmenšuje ani nekomprimuje.
        data = source.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        target_dir = storage_service.attachment_dir(EXAM_SNAPSHOT_ENTITY, exam_id)
        target = target_dir / f"{name}-{digest[:12]}{source.suffix.lower()}"
        target.write_bytes(data)
        created_files.append(target)
        relative = target.resolve().relative_to(storage_service.attachments_dir.resolve()).as_posix()
        session.add(
            Attachment(
                entity_type=EXAM_SNAPSHOT_ENTITY,
                entity_id=int(exam_id),
                original_path="",
                stored_path=relative,
                filename=target.name,
            )
        )
        return relative, digest

    def _discard_files(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue


test_exam_service = TestExamService()

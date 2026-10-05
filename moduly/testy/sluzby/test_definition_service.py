"""Definice Testů. Služba není závislá na Qt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete

from core.database.session import get_session
from moduly.testy.constants import (
    DEFAULT_SECONDS_PER_QUESTION,
    EXAMINER_MODES,
    VALIDITY_UNIT_MONTHS,
    VALIDITY_UNIT_YEARS,
    VALIDITY_UNITS,
)
from moduly.testy.modely.test_definition import TestDefinition
from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
from moduly.testy.modely.test_definition_written_topic import TestDefinitionWrittenTopic
from moduly.testy.repository.test_definition_repository import TestDefinitionRepository
from moduly.testy.sluzby.oral_question_service import oral_question_service
from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
from moduly.testy.sluzby.written_question_service import written_question_service
from moduly.testy.sluzby.written_question_topic_service import (
    normalize_topic_name,
    written_question_topic_service,
)


class TestDefinitionError(ValueError):
    pass


@dataclass(frozen=True)
class TestTopicQuota:
    """Počet otázek, které se mají z jednoho okruhu později vybrat."""

    topic_id: int
    question_count: int


def total_written_questions(quotas: list[TestTopicQuota]) -> int:
    return sum(max(0, int(item.question_count)) for item in quotas)


def total_written_seconds(question_count: int, seconds_per_question: int) -> int:
    return int(question_count) * int(seconds_per_question)


def format_test_duration(total_seconds: int) -> str:
    seconds = max(0, int(total_seconds))
    minutes, rest = divmod(seconds, 60)
    if rest == 0:
        return f"{minutes} min"
    if minutes == 0:
        return f"{rest} s"
    return f"{minutes} min {rest} s"


def format_validity(value: int, unit: str) -> str:
    """Kalendářní délka. 2 roky nejsou 730 dnů."""
    if unit == VALIDITY_UNIT_MONTHS:
        return _czech_count(value, one="měsíc", few="měsíce", many="měsíců")
    if unit == VALIDITY_UNIT_YEARS:
        return _czech_count(value, one="rok", few="roky", many="let")
    return str(value)


def _czech_count(value: int, *, one: str, few: str, many: str) -> str:
    number = abs(int(value))
    if number % 100 in range(11, 15):
        word = many
    elif number % 10 == 1:
        word = one
    elif number % 10 in (2, 3, 4):
        word = few
    else:
        word = many
    return f"{int(value)} {word}"


class TestDefinitionService:
    def __init__(self) -> None:
        self.repository = TestDefinitionRepository()

    def create_test(
        self,
        *,
        name: str,
        description: str = "",
        active: bool = True,
        uses_written: bool = False,
        allowed_wrong_answers: int = 0,
        seconds_per_question: int = DEFAULT_SECONDS_PER_QUESTION,
        uses_oral: bool = False,
        examiner_mode: str,
        validity_value: int,
        validity_unit: str,
        written_topics: list[TestTopicQuota] | None = None,
        oral_topics: list[TestTopicQuota] | None = None,
    ) -> TestDefinition:
        return self._save(
            None,
            name=name,
            description=description,
            active=active,
            uses_written=uses_written,
            allowed_wrong_answers=allowed_wrong_answers,
            seconds_per_question=seconds_per_question,
            uses_oral=uses_oral,
            examiner_mode=examiner_mode,
            validity_value=validity_value,
            validity_unit=validity_unit,
            written_topics=list(written_topics or []),
            oral_topics=list(oral_topics or []),
        )

    def update_test(
        self,
        test_id: int,
        *,
        name: str,
        description: str = "",
        active: bool = True,
        uses_written: bool = False,
        allowed_wrong_answers: int = 0,
        seconds_per_question: int = DEFAULT_SECONDS_PER_QUESTION,
        uses_oral: bool = False,
        examiner_mode: str,
        validity_value: int,
        validity_unit: str,
        written_topics: list[TestTopicQuota] | None = None,
        oral_topics: list[TestTopicQuota] | None = None,
    ) -> TestDefinition:
        return self._save(
            test_id,
            name=name,
            description=description,
            active=active,
            uses_written=uses_written,
            allowed_wrong_answers=allowed_wrong_answers,
            seconds_per_question=seconds_per_question,
            uses_oral=uses_oral,
            examiner_mode=examiner_mode,
            validity_value=validity_value,
            validity_unit=validity_unit,
            written_topics=list(written_topics or []),
            oral_topics=list(oral_topics or []),
        )

    def get_test(self, test_id: int | None) -> TestDefinition | None:
        if not test_id:
            return None
        return self.repository.get_by_id(test_id)

    def list_tests(self, *, include_inactive: bool = False) -> list[TestDefinition]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_written_topics(self, test_id: int) -> list[TestDefinitionWrittenTopic]:
        self._require_test(test_id)
        return self.repository.get_written_topics(test_id)

    def get_oral_topics(self, test_id: int) -> list[TestDefinitionOralTopic]:
        self._require_test(test_id)
        return self.repository.get_oral_topics(test_id)

    def written_question_count(self, test_id: int) -> int:
        test = self._require_test(test_id)
        if not test.uses_written:
            return 0
        return sum(row.question_count for row in self.repository.get_written_topics(test_id))

    def written_duration_seconds(self, test_id: int) -> int:
        test = self._require_test(test_id)
        return total_written_seconds(
            self.written_question_count(test_id),
            test.seconds_per_question,
        )

    def set_active(self, test_id: int, *, active: bool) -> TestDefinition:
        test = self._require_test(test_id)
        session = get_session()
        try:
            row = session.get(TestDefinition, test.id)
            if row is None:
                raise TestDefinitionError("Test nebyl nalezen.")
            row.active = bool(active)
            row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def deactivate(self, test_id: int) -> TestDefinition:
        return self.set_active(test_id, active=False)

    def activate(self, test_id: int) -> TestDefinition:
        return self.set_active(test_id, active=True)

    def _save(
        self,
        test_id: int | None,
        *,
        name: str,
        description: str,
        active: bool,
        uses_written: bool,
        allowed_wrong_answers: int,
        seconds_per_question: int,
        uses_oral: bool,
        examiner_mode: str,
        validity_value: int,
        validity_unit: str,
        written_topics: list[TestTopicQuota],
        oral_topics: list[TestTopicQuota],
    ) -> TestDefinition:
        existing = self._require_test(test_id) if test_id else None
        stored_name = self._validate_name(name)
        self._ensure_unique_name(
            stored_name,
            exclude_test_id=existing.id if existing is not None else None,
        )
        written_on = bool(uses_written)
        oral_on = bool(uses_oral)
        if not written_on and not oral_on:
            raise TestDefinitionError("Zapněte písemnou nebo ústní část.")
        if written_on and not written_topics:
            raise TestDefinitionError("Písemná část musí obsahovat alespoň jeden okruh.")
        if oral_on and not oral_topics:
            raise TestDefinitionError("Ústní část musí obsahovat alespoň jeden okruh.")

        existing_written = (
            {row.topic_id for row in self.repository.get_written_topics(existing.id)}
            if existing is not None
            else set()
        )
        existing_oral = (
            {row.topic_id for row in self.repository.get_oral_topics(existing.id)}
            if existing is not None
            else set()
        )
        written_quotas = self._validate_quotas(
            written_topics,
            part_enabled=written_on,
            existing_ids=existing_written,
            topic_getter=written_question_topic_service.get_topic,
            question_counter=self._active_written_questions,
            oral=False,
        )
        oral_quotas = self._validate_quotas(
            oral_topics,
            part_enabled=oral_on,
            existing_ids=existing_oral,
            topic_getter=oral_question_topic_service.get_topic,
            question_counter=self._active_oral_questions,
            oral=True,
        )
        allowed = self._validate_allowed_errors(allowed_wrong_answers)
        seconds = self._validate_seconds(seconds_per_question)
        if written_on and allowed >= total_written_questions(written_quotas):
            raise TestDefinitionError(
                "Povolený počet chyb musí být menší než celkový počet písemných otázek."
            )
        mode = self._validate_examiner_mode(examiner_mode)
        validity, unit = self._validate_validity(validity_value, validity_unit)
        stored_description = str(description or "").strip()

        session = get_session()
        session.expire_on_commit = False
        try:
            if existing is None:
                test = TestDefinition(
                    name=stored_name,
                    description=stored_description,
                    active=bool(active),
                    uses_written=written_on,
                    allowed_wrong_answers=allowed,
                    seconds_per_question=seconds,
                    uses_oral=oral_on,
                    examiner_mode=mode,
                    validity_value=validity,
                    validity_unit=unit,
                )
                session.add(test)
                session.flush()
            else:
                test = session.get(TestDefinition, existing.id)
                if test is None:
                    raise TestDefinitionError("Test nebyl nalezen.")
                test.name = stored_name
                test.description = stored_description
                test.active = bool(active)
                test.uses_written = written_on
                test.allowed_wrong_answers = allowed
                test.seconds_per_question = seconds
                test.uses_oral = oral_on
                test.examiner_mode = mode
                test.validity_value = validity
                test.validity_unit = unit
                test.updated_at = datetime.now()
                session.execute(
                    delete(TestDefinitionWrittenTopic).where(
                        TestDefinitionWrittenTopic.test_id == test.id
                    )
                )
                session.execute(
                    delete(TestDefinitionOralTopic).where(
                        TestDefinitionOralTopic.test_id == test.id
                    )
                )
                session.flush()

            for position, quota in enumerate(written_quotas, start=1):
                session.add(
                    TestDefinitionWrittenTopic(
                        test_id=test.id,
                        topic_id=quota.topic_id,
                        question_count=quota.question_count,
                        position=position,
                    )
                )
            for position, quota in enumerate(oral_quotas, start=1):
                session.add(
                    TestDefinitionOralTopic(
                        test_id=test.id,
                        topic_id=quota.topic_id,
                        question_count=quota.question_count,
                        position=position,
                    )
                )
            session.commit()
            session.refresh(test)
            session.expunge(test)
            return test
        except TestDefinitionError:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _require_test(self, test_id: int) -> TestDefinition:
        test = self.repository.get_by_id(int(test_id))
        if test is None:
            raise TestDefinitionError("Test nebyl nalezen.")
        return test

    def _validate_name(self, name: str) -> str:
        stored_name = " ".join(str(name or "").strip().split())
        if not stored_name:
            raise TestDefinitionError("Vyplňte název testu.")
        return stored_name

    def _ensure_unique_name(self, name: str, *, exclude_test_id: int | None) -> None:
        normalized = normalize_topic_name(name)
        for test in self.repository.get_all(include_inactive=True):
            if test.id == exclude_test_id:
                continue
            if normalize_topic_name(test.name) == normalized:
                raise TestDefinitionError(f"Test „{test.name}“ již existuje.")

    def _validate_quotas(
        self,
        items: list[TestTopicQuota],
        *,
        part_enabled: bool,
        existing_ids: set[int],
        topic_getter,
        question_counter,
        oral: bool,
    ) -> list[TestTopicQuota]:
        seen: set[int] = set()
        normalized: list[TestTopicQuota] = []
        for item in items:
            topic = topic_getter(int(item.topic_id) if item.topic_id else 0)
            if topic is None:
                raise TestDefinitionError("Zvolený okruh neexistuje.")
            if topic.id in seen:
                raise TestDefinitionError(f"Okruh „{topic.name}“ je ve skladbě vícekrát.")
            seen.add(topic.id)
            count = self._validate_count(item.question_count, topic.name)
            if not topic.active and topic.id not in existing_ids:
                raise TestDefinitionError("Do nové skladby lze přidat jen aktivní okruh.")
            if part_enabled and topic.active:
                available = question_counter(topic.id)
                if available < count:
                    label = "Ústní okruh" if oral else "Okruh"
                    raise TestDefinitionError(
                        f"{label} „{topic.name}“ má {available} aktivních otázek, "
                        f"test požaduje {count}."
                    )
            normalized.append(TestTopicQuota(topic_id=topic.id, question_count=count))
        return normalized

    def _validate_count(self, value: int, topic_name: str) -> int:
        if isinstance(value, bool):
            number = 0
        else:
            try:
                number = int(value)
            except (TypeError, ValueError):
                number = 0
        if number <= 0:
            raise TestDefinitionError(
                f"Počet otázek u okruhu „{topic_name}“ musí být větší než 0."
            )
        return number

    def _validate_allowed_errors(self, value: int) -> int:
        if isinstance(value, bool):
            raise TestDefinitionError("Povolený počet chyb nesmí být záporný.")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise TestDefinitionError("Povolený počet chyb nesmí být záporný.") from None
        if number < 0:
            raise TestDefinitionError("Povolený počet chyb nesmí být záporný.")
        return number

    def _validate_seconds(self, value: int) -> int:
        if isinstance(value, bool):
            raise TestDefinitionError("Čas na jednu otázku musí být větší než 0.")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise TestDefinitionError("Čas na jednu otázku musí být větší než 0.") from None
        if number <= 0:
            raise TestDefinitionError("Čas na jednu otázku musí být větší než 0.")
        return number

    def _validate_examiner_mode(self, mode: str) -> str:
        stored = str(mode or "").strip()
        if stored not in EXAMINER_MODES:
            raise TestDefinitionError("Zvolte režim zkoušejících.")
        return stored

    def _validate_validity(self, value: int, unit: str) -> tuple[int, str]:
        if isinstance(value, bool):
            raise TestDefinitionError("Doba platnosti musí být větší než 0.")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise TestDefinitionError("Doba platnosti musí být větší než 0.") from None
        if number <= 0:
            raise TestDefinitionError("Doba platnosti musí být větší než 0.")
        stored_unit = str(unit or "").strip()
        if stored_unit not in VALIDITY_UNITS:
            raise TestDefinitionError("Zvolte jednotku platnosti.")
        return number, stored_unit

    def _active_written_questions(self, topic_id: int) -> int:
        return len(
            written_question_service.list_questions(
                include_inactive=False,
                topic_id=topic_id,
            )
        )

    def _active_oral_questions(self, topic_id: int) -> int:
        return len(
            oral_question_service.list_questions(
                include_inactive=False,
                topic_id=topic_id,
            )
        )


test_definition_service = TestDefinitionService()

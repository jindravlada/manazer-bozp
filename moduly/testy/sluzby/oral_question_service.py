"""Banka ústních otázek. Služba není závislá na Qt."""

from __future__ import annotations

from datetime import datetime

from moduly.testy.modely.oral_question import OralQuestion
from moduly.testy.modely.oral_question_topic import OralQuestionTopic
from moduly.testy.repository.oral_question_repository import OralQuestionRepository
from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service


class OralQuestionError(ValueError):
    pass


class OralQuestionService:
    def __init__(self) -> None:
        self.repository = OralQuestionRepository()

    def create_question(
        self,
        *,
        topic_id: int | None,
        text: str,
        note: str = "",
        active: bool = True,
    ) -> OralQuestion:
        topic = self._require_topic(topic_id, existing=None)
        question = OralQuestion(
            topic_id=topic.id,
            text=self._validate_text(text),
            note=str(note or "").strip(),
            active=bool(active),
        )
        return self.repository.add(question)

    def get_question(self, question_id: int | None) -> OralQuestion | None:
        if not question_id:
            return None
        return self.repository.get_by_id(question_id)

    def list_questions(
        self,
        *,
        include_inactive: bool = False,
        topic_id: int | None = None,
    ) -> list[OralQuestion]:
        return self.repository.get_all(
            include_inactive=include_inactive,
            topic_id=topic_id,
        )

    def update_question(
        self,
        question_id: int,
        *,
        topic_id: int | None,
        text: str,
        note: str = "",
        active: bool = True,
    ) -> OralQuestion:
        existing = self._require_question(question_id)
        topic = self._require_topic(topic_id, existing)
        existing.topic_id = topic.id
        existing.text = self._validate_text(text)
        existing.note = str(note or "").strip()
        existing.active = bool(active)
        existing.updated_at = datetime.now()
        return self.repository.update(existing)

    def set_active(self, question_id: int, *, active: bool) -> OralQuestion:
        question = self._require_question(question_id)
        question.active = bool(active)
        question.updated_at = datetime.now()
        return self.repository.update(question)

    def deactivate(self, question_id: int) -> OralQuestion:
        return self.set_active(question_id, active=False)

    def activate(self, question_id: int) -> OralQuestion:
        return self.set_active(question_id, active=True)

    def _require_question(self, question_id: int) -> OralQuestion:
        question = self.repository.get_by_id(int(question_id))
        if question is None:
            raise OralQuestionError("Otázka nebyla nalezena.")
        return question

    def _require_topic(
        self,
        topic_id: int | None,
        existing: OralQuestion | None,
    ) -> OralQuestionTopic:
        if not topic_id:
            raise OralQuestionError("Zvolte okruh.")
        topic = oral_question_topic_service.get_topic(int(topic_id))
        if topic is None:
            raise OralQuestionError("Zvolený okruh neexistuje.")
        same_inactive = (
            existing is not None
            and int(existing.topic_id) == int(topic.id)
            and not topic.active
        )
        if not topic.active and not same_inactive:
            raise OralQuestionError(
                "Novou otázku nebo jiný okruh lze zvolit jen z aktivních okruhů."
            )
        return topic

    def _validate_text(self, text: str) -> str:
        stored = str(text or "").strip()
        if not stored:
            raise OralQuestionError("Vyplňte text otázky.")
        return stored


oral_question_service = OralQuestionService()

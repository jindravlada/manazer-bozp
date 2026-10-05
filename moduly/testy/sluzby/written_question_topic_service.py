"""Číselník okruhů písemných otázek."""

from __future__ import annotations

from datetime import datetime

from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
from moduly.testy.repository.written_question_topic_repository import (
    WrittenQuestionTopicRepository,
)


class WrittenQuestionTopicError(ValueError):
    pass


def normalize_topic_name(name: str) -> str:
    """Sjednotí název pro porovnání duplicit, bez ohledu na velikost písmen."""
    return " ".join(str(name or "").strip().split()).casefold()


class WrittenQuestionTopicService:
    def __init__(self) -> None:
        self.repository = WrittenQuestionTopicRepository()

    def create_topic(
        self,
        *,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> WrittenQuestionTopic:
        stored_name = self._validate_name(name)
        self._ensure_unique_name(stored_name)
        topic = WrittenQuestionTopic(
            name=stored_name,
            description=self._normalize_description(description),
            active=bool(active),
        )
        return self.repository.add(topic)

    def get_topic(self, topic_id: int | None) -> WrittenQuestionTopic | None:
        if not topic_id:
            return None
        return self.repository.get_by_id(topic_id)

    def list_topics(self, *, include_inactive: bool = False) -> list[WrittenQuestionTopic]:
        return self.repository.get_all(include_inactive=include_inactive)

    def update_topic(
        self,
        topic_id: int,
        *,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> WrittenQuestionTopic:
        topic = self._require_topic(topic_id)
        stored_name = self._validate_name(name)
        self._ensure_unique_name(stored_name, exclude_topic_id=topic_id)
        topic.name = stored_name
        topic.description = self._normalize_description(description)
        topic.active = bool(active)
        topic.updated_at = datetime.now()
        return self.repository.update(topic)

    def set_active(self, topic_id: int, *, active: bool) -> WrittenQuestionTopic:
        topic = self._require_topic(topic_id)
        topic.active = bool(active)
        topic.updated_at = datetime.now()
        return self.repository.update(topic)

    def deactivate(self, topic_id: int) -> WrittenQuestionTopic:
        return self.set_active(topic_id, active=False)

    def activate(self, topic_id: int) -> WrittenQuestionTopic:
        return self.set_active(topic_id, active=True)

    def _require_topic(self, topic_id: int) -> WrittenQuestionTopic:
        topic = self.repository.get_by_id(topic_id)
        if topic is None:
            raise WrittenQuestionTopicError("Okruh nebyl nalezen.")
        return topic

    def _validate_name(self, name: str) -> str:
        stored_name = " ".join(str(name or "").strip().split())
        if not stored_name:
            raise WrittenQuestionTopicError("Vyplňte název okruhu.")
        return stored_name

    def _normalize_description(self, description: str) -> str:
        return str(description or "").strip()

    def _ensure_unique_name(
        self,
        name: str,
        *,
        exclude_topic_id: int | None = None,
    ) -> None:
        normalized = normalize_topic_name(name)
        for topic in self.repository.get_all(include_inactive=True):
            if topic.id == exclude_topic_id:
                continue
            if normalize_topic_name(topic.name) == normalized:
                raise WrittenQuestionTopicError(f"Okruh „{topic.name}“ již existuje.")


written_question_topic_service = WrittenQuestionTopicService()

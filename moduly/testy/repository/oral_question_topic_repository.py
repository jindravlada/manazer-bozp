from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.testy.modely.oral_question_topic import OralQuestionTopic


class OralQuestionTopicRepository:
    def get_all(self, *, include_inactive: bool = False) -> list[OralQuestionTopic]:
        with get_session() as session:
            stmt = select(OralQuestionTopic)
            if not include_inactive:
                stmt = stmt.where(OralQuestionTopic.active == True)  # noqa: E712
            topics = list(session.scalars(stmt))

        return czech_sorted(topics, key=lambda topic: topic.name.casefold())

    def get_by_id(self, topic_id: int) -> OralQuestionTopic | None:
        with get_session() as session:
            return session.get(OralQuestionTopic, topic_id)

    def add(self, topic: OralQuestionTopic) -> OralQuestionTopic:
        with get_session() as session:
            session.add(topic)
            session.commit()
            session.refresh(topic)
            return topic

    def update(self, topic: OralQuestionTopic) -> OralQuestionTopic:
        with get_session() as session:
            topic = session.merge(topic)
            session.commit()
            session.refresh(topic)
            return topic

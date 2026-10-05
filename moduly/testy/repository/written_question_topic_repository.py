from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.testy.modely.written_question_topic import WrittenQuestionTopic


class WrittenQuestionTopicRepository:
    def get_all(self, *, include_inactive: bool = False) -> list[WrittenQuestionTopic]:
        with get_session() as session:
            stmt = select(WrittenQuestionTopic)
            if not include_inactive:
                stmt = stmt.where(WrittenQuestionTopic.active == True)  # noqa: E712
            topics = list(session.scalars(stmt))

        return czech_sorted(topics, key=lambda topic: topic.name.casefold())

    def get_by_id(self, topic_id: int) -> WrittenQuestionTopic | None:
        with get_session() as session:
            return session.get(WrittenQuestionTopic, topic_id)

    def add(self, topic: WrittenQuestionTopic) -> WrittenQuestionTopic:
        with get_session() as session:
            session.add(topic)
            session.commit()
            session.refresh(topic)
            return topic

    def update(self, topic: WrittenQuestionTopic) -> WrittenQuestionTopic:
        with get_session() as session:
            topic = session.merge(topic)
            session.commit()
            session.refresh(topic)
            return topic

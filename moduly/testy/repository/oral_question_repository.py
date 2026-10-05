from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.testy.modely.oral_question import OralQuestion


class OralQuestionRepository:
    def get_all(
        self,
        *,
        include_inactive: bool = False,
        topic_id: int | None = None,
    ) -> list[OralQuestion]:
        with get_session() as session:
            stmt = select(OralQuestion)
            if not include_inactive:
                stmt = stmt.where(OralQuestion.active == True)  # noqa: E712
            if topic_id is not None:
                stmt = stmt.where(OralQuestion.topic_id == int(topic_id))
            questions = list(session.scalars(stmt))

        return czech_sorted(questions, key=lambda question: question.text.casefold())

    def get_by_id(self, question_id: int) -> OralQuestion | None:
        with get_session() as session:
            return session.get(OralQuestion, question_id)

    def add(self, question: OralQuestion) -> OralQuestion:
        with get_session() as session:
            session.add(question)
            session.commit()
            session.refresh(question)
            return question

    def update(self, question: OralQuestion) -> OralQuestion:
        with get_session() as session:
            question = session.merge(question)
            session.commit()
            session.refresh(question)
            return question

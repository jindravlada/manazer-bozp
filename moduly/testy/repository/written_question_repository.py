from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.testy.modely.written_question import WrittenQuestion
from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer


class WrittenQuestionRepository:
    def get_all(
        self,
        *,
        include_inactive: bool = False,
        topic_id: int | None = None,
    ) -> list[WrittenQuestion]:
        with get_session() as session:
            stmt = select(WrittenQuestion)
            if not include_inactive:
                stmt = stmt.where(WrittenQuestion.active == True)  # noqa: E712
            if topic_id is not None:
                stmt = stmt.where(WrittenQuestion.topic_id == int(topic_id))
            questions = list(session.scalars(stmt))

        return czech_sorted(questions, key=lambda question: question.text.casefold())

    def get_by_id(self, question_id: int) -> WrittenQuestion | None:
        with get_session() as session:
            return session.get(WrittenQuestion, question_id)

    def get_answers(self, question_id: int) -> list[WrittenQuestionAnswer]:
        with get_session() as session:
            stmt = (
                select(WrittenQuestionAnswer)
                .where(WrittenQuestionAnswer.question_id == int(question_id))
                .order_by(WrittenQuestionAnswer.position, WrittenQuestionAnswer.id)
            )
            return list(session.scalars(stmt))

from sqlalchemy import select

from core.database.session import get_session
from moduly.testy.modely.test_exam import TestExam
from moduly.testy.modely.test_exam_examiner import TestExamExaminer
from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion


class TestExamRepository:
    def get_all(self) -> list[TestExam]:
        with get_session() as session:
            stmt = select(TestExam).order_by(TestExam.exam_date.desc(), TestExam.id.desc())
            return list(session.scalars(stmt))

    def get_by_id(self, exam_id: int) -> TestExam | None:
        with get_session() as session:
            return session.get(TestExam, exam_id)

    def get_examiners(self, exam_id: int) -> list[TestExamExaminer]:
        with get_session() as session:
            stmt = (
                select(TestExamExaminer)
                .where(TestExamExaminer.exam_id == int(exam_id))
                .order_by(TestExamExaminer.position, TestExamExaminer.id)
            )
            return list(session.scalars(stmt))

    def get_written_questions(self, exam_id: int) -> list[TestExamWrittenQuestion]:
        with get_session() as session:
            stmt = (
                select(TestExamWrittenQuestion)
                .where(TestExamWrittenQuestion.exam_id == int(exam_id))
                .order_by(TestExamWrittenQuestion.position, TestExamWrittenQuestion.id)
            )
            return list(session.scalars(stmt))

    def get_written_answers(self, exam_question_id: int) -> list[TestExamWrittenAnswer]:
        with get_session() as session:
            stmt = (
                select(TestExamWrittenAnswer)
                .where(TestExamWrittenAnswer.exam_question_id == int(exam_question_id))
                .order_by(TestExamWrittenAnswer.position, TestExamWrittenAnswer.id)
            )
            return list(session.scalars(stmt))

    def get_oral_questions(self, exam_id: int) -> list[TestExamOralQuestion]:
        with get_session() as session:
            stmt = (
                select(TestExamOralQuestion)
                .where(TestExamOralQuestion.exam_id == int(exam_id))
                .order_by(TestExamOralQuestion.position, TestExamOralQuestion.id)
            )
            return list(session.scalars(stmt))

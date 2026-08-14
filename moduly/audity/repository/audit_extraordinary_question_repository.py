"""Repository pro mimořádné auditní otázky (AUDIT-EXTRAORDINARY-1)."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit_extraordinary_question import (
    AuditExtraordinaryQuestion,
    AuditExtraordinaryQuestionTarget,
)


class AuditExtraordinaryQuestionRepository:
    def list_questions(self) -> list[AuditExtraordinaryQuestion]:
        with get_session() as session:
            rows = list(
                session.scalars(
                    select(AuditExtraordinaryQuestion).order_by(
                        AuditExtraordinaryQuestion.assigned_on.desc(),
                        AuditExtraordinaryQuestion.id.desc(),
                    )
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def get_question(self, question_id: int) -> AuditExtraordinaryQuestion | None:
        with get_session() as session:
            row = session.get(AuditExtraordinaryQuestion, int(question_id))
            if row is None:
                return None
            session.expunge(row)
            return row

    def list_targets_for_question(
        self,
        question_id: int,
    ) -> list[AuditExtraordinaryQuestionTarget]:
        with get_session() as session:
            rows = list(
                session.scalars(
                    select(AuditExtraordinaryQuestionTarget)
                    .where(
                        AuditExtraordinaryQuestionTarget.question_id == int(question_id)
                    )
                    .order_by(AuditExtraordinaryQuestionTarget.id)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def list_all_targets(self) -> list[AuditExtraordinaryQuestionTarget]:
        with get_session() as session:
            rows = list(
                session.scalars(select(AuditExtraordinaryQuestionTarget))
            )
            for row in rows:
                session.expunge(row)
            return rows

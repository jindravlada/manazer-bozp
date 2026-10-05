from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted
from moduly.testy.modely.test_definition import TestDefinition
from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
from moduly.testy.modely.test_definition_written_topic import TestDefinitionWrittenTopic


class TestDefinitionRepository:
    def get_all(self, *, include_inactive: bool = False) -> list[TestDefinition]:
        with get_session() as session:
            stmt = select(TestDefinition)
            if not include_inactive:
                stmt = stmt.where(TestDefinition.active == True)  # noqa: E712
            tests = list(session.scalars(stmt))

        return czech_sorted(tests, key=lambda test: test.name.casefold())

    def get_by_id(self, test_id: int) -> TestDefinition | None:
        with get_session() as session:
            return session.get(TestDefinition, test_id)

    def get_written_topics(self, test_id: int) -> list[TestDefinitionWrittenTopic]:
        with get_session() as session:
            stmt = (
                select(TestDefinitionWrittenTopic)
                .where(TestDefinitionWrittenTopic.test_id == int(test_id))
                .order_by(
                    TestDefinitionWrittenTopic.position,
                    TestDefinitionWrittenTopic.id,
                )
            )
            return list(session.scalars(stmt))

    def get_oral_topics(self, test_id: int) -> list[TestDefinitionOralTopic]:
        with get_session() as session:
            stmt = (
                select(TestDefinitionOralTopic)
                .where(TestDefinitionOralTopic.test_id == int(test_id))
                .order_by(
                    TestDefinitionOralTopic.position,
                    TestDefinitionOralTopic.id,
                )
            )
            return list(session.scalars(stmt))

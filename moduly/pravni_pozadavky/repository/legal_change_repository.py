from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.modely.legal_change import LegalChange


class LegalChangeRepository:
    def _ordered(self, stmt):
        return stmt.order_by(
            LegalChange.published_at.desc().nullslast(),
            LegalChange.id.desc(),
        )

    def list_all(self, *, include_inactive: bool = False) -> list[LegalChange]:
        with get_session() as session:
            stmt = self._ordered(select(LegalChange))
            if not include_inactive:
                stmt = stmt.where(LegalChange.active.is_(True))
            return list(session.scalars(stmt))

    def list_by_document(
        self,
        document_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        with get_session() as session:
            stmt = self._ordered(
                select(LegalChange).where(LegalChange.legal_document_id == document_id),
            )
            if not include_inactive:
                stmt = stmt.where(LegalChange.active.is_(True))
            return list(session.scalars(stmt))

    def list_by_version(
        self,
        version_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        with get_session() as session:
            stmt = self._ordered(
                select(LegalChange).where(LegalChange.legal_document_version_id == version_id),
            )
            if not include_inactive:
                stmt = stmt.where(LegalChange.active.is_(True))
            return list(session.scalars(stmt))

    def list_by_section(
        self,
        section_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        with get_session() as session:
            stmt = self._ordered(
                select(LegalChange).where(LegalChange.legal_section_id == section_id),
            )
            if not include_inactive:
                stmt = stmt.where(LegalChange.active.is_(True))
            return list(session.scalars(stmt))

    def list_by_check_run(
        self,
        check_run_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalChange]:
        with get_session() as session:
            stmt = self._ordered(
                select(LegalChange).where(LegalChange.legal_check_run_id == check_run_id),
            )
            if not include_inactive:
                stmt = stmt.where(LegalChange.active.is_(True))
            return list(session.scalars(stmt))

    def get_by_id(self, change_id: int) -> LegalChange | None:
        with get_session() as session:
            return session.get(LegalChange, change_id)

    def create(self, change: LegalChange) -> LegalChange:
        with get_session() as session:
            session.add(change)
            session.commit()
            session.refresh(change)
            return change

    def update(self, change: LegalChange) -> LegalChange:
        with get_session() as session:
            change = session.merge(change)
            session.commit()
            session.refresh(change)
            return change

    def deactivate(self, change_id: int) -> LegalChange | None:
        change = self.get_by_id(change_id)
        if change is None:
            return None
        change.active = False
        return self.update(change)

    def restore(self, change_id: int) -> LegalChange | None:
        change = self.get_by_id(change_id)
        if change is None:
            return None
        change.active = True
        return self.update(change)

from core.shared.constants import (
    LINK_RELATED,
    VALID_LINK_ENTITY_TYPES,
    VALID_LINK_TYPES,
)
from core.shared.modely.entity_link import EntityLink
from core.shared.repository.entity_link_repository import EntityLinkRepository


class EntityLinkService:
    def __init__(self):
        self.repository = EntityLinkRepository()

    def list_for_source(
        self,
        source_type: str,
        source_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[EntityLink]:
        return self.repository.list_for_source(
            source_type,
            source_id,
            include_inactive=include_inactive,
        )

    def list_for_target(
        self,
        target_type: str,
        target_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[EntityLink]:
        return self.repository.list_for_target(
            target_type,
            target_id,
            include_inactive=include_inactive,
        )

    def list_between(
        self,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[EntityLink]:
        return self.repository.list_between(
            source_type,
            source_id,
            target_type,
            target_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, link_id: int) -> EntityLink | None:
        return self.repository.get_by_id(link_id)

    def create(
        self,
        *,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        link_type: str = LINK_RELATED,
        note: str = "",
        active: bool = True,
    ) -> EntityLink:
        normalized = self._normalize_payload(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            link_type=link_type,
        )
        self._ensure_not_duplicate(**normalized)

        link = EntityLink(
            source_type=normalized["source_type"],
            source_id=normalized["source_id"],
            target_type=normalized["target_type"],
            target_id=normalized["target_id"],
            link_type=normalized["link_type"],
            note=note.strip(),
            active=active,
        )
        return self.repository.create(link)

    def update(
        self,
        link_id: int,
        *,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        link_type: str = LINK_RELATED,
        note: str = "",
        active: bool = True,
    ) -> EntityLink | None:
        link = self.repository.get_by_id(link_id)
        if link is None:
            return None

        normalized = self._normalize_payload(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            link_type=link_type,
        )
        self._ensure_not_duplicate(exclude_id=link_id, **normalized)

        link.source_type = normalized["source_type"]
        link.source_id = normalized["source_id"]
        link.target_type = normalized["target_type"]
        link.target_id = normalized["target_id"]
        link.link_type = normalized["link_type"]
        link.note = note.strip()
        link.active = active
        return self.repository.update(link)

    def deactivate(self, link_id: int) -> EntityLink | None:
        link = self.repository.get_by_id(link_id)
        if link is None:
            return None
        link.active = False
        return self.repository.update(link)

    def restore(self, link_id: int) -> EntityLink | None:
        link = self.repository.get_by_id(link_id)
        if link is None:
            return None

        duplicate = self.repository.find_active_duplicate(
            source_type=link.source_type,
            source_id=link.source_id,
            target_type=link.target_type,
            target_id=link.target_id,
            link_type=link.link_type,
            exclude_id=link.id,
        )
        if duplicate is not None:
            raise ValueError("Aktivní vazba se stejnými parametry už existuje.")

        link.active = True
        return self.repository.update(link)

    def delete(self, link_id: int) -> bool:
        return self.repository.delete(link_id)

    def reassign_entity_id(self, entity_type: str, from_id: int, to_id: int) -> None:
        if from_id == to_id:
            return

        normalized_type = (entity_type or "").strip()
        if not normalized_type:
            raise ValueError("Typ entity je povinný.")

        for link in self.repository.list_for_source(
            normalized_type,
            from_id,
            include_inactive=True,
        ):
            duplicate = self.repository.find_active_duplicate(
                source_type=normalized_type,
                source_id=to_id,
                target_type=link.target_type,
                target_id=link.target_id,
                link_type=link.link_type,
            )
            if duplicate is not None:
                self.repository.delete(link.id)
                continue

            link.source_id = to_id
            self.repository.update(link)

        for link in self.repository.list_for_target(
            normalized_type,
            from_id,
            include_inactive=True,
        ):
            duplicate = self.repository.find_active_duplicate(
                source_type=link.source_type,
                source_id=link.source_id,
                target_type=normalized_type,
                target_id=to_id,
                link_type=link.link_type,
            )
            if duplicate is not None:
                self.repository.delete(link.id)
                continue

            if link.source_type == normalized_type and link.source_id == from_id:
                link.source_id = to_id
            link.target_id = to_id
            self.repository.update(link)

    def _normalize_payload(
        self,
        *,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        link_type: str,
    ) -> dict:
        normalized_source_type = (source_type or "").strip()
        normalized_target_type = (target_type or "").strip()
        normalized_link_type = (link_type or "").strip() or LINK_RELATED

        if not normalized_source_type:
            raise ValueError("Zdrojový typ entity je povinný.")
        if not isinstance(source_id, int) or source_id <= 0:
            raise ValueError("Zdrojové ID entity je povinné.")
        if not normalized_target_type:
            raise ValueError("Cílový typ entity je povinný.")
        if not isinstance(target_id, int) or target_id <= 0:
            raise ValueError("Cílové ID entity je povinné.")
        if normalized_link_type not in VALID_LINK_TYPES:
            raise ValueError("Neplatný typ vazby.")

        if (
            normalized_source_type == normalized_target_type
            and source_id == target_id
        ):
            raise ValueError("Objekt nelze navázat sám na sebe.")

        return {
            "source_type": normalized_source_type,
            "source_id": source_id,
            "target_type": normalized_target_type,
            "target_id": target_id,
            "link_type": normalized_link_type,
        }

    def _ensure_not_duplicate(
        self,
        *,
        source_type: str,
        source_id: int,
        target_type: str,
        target_id: int,
        link_type: str,
        exclude_id: int | None = None,
    ) -> None:
        duplicate = self.repository.find_active_duplicate(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            link_type=link_type,
            exclude_id=exclude_id,
        )
        if duplicate is not None:
            raise ValueError("Aktivní vazba se stejnými parametry už existuje.")


entity_link_service = EntityLinkService()

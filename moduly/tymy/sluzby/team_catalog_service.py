import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.tymy.constants import (
    DEFAULT_TEAM_ROLES,
    DEFAULT_TEAM_TYPES,
    TEAM_ROLES_CATALOG_PATH,
    TEAM_TYPES_CATALOG_PATH,
)


@dataclass(frozen=True)
class CatalogItem:
    id: str
    nazev: str
    popis: str
    poradi: int
    aktivni: bool


class TeamCatalogService:
    """Načítání a správa číselníků typů týmů a rolí v týmu."""

    def __init__(self) -> None:
        self._team_types: list[CatalogItem] | None = None
        self._team_roles: list[CatalogItem] | None = None

    def reload(self) -> None:
        self._team_types = None
        self._team_roles = None

    def get_team_types(self, *, active_only: bool = True) -> list[CatalogItem]:
        items = self._load_team_types()
        if active_only:
            items = [item for item in items if item.aktivni]
        return sorted(items, key=lambda item: (item.poradi, item.nazev))

    def get_team_roles(self, *, active_only: bool = True) -> list[CatalogItem]:
        items = self._load_team_roles()
        if active_only:
            items = [item for item in items if item.aktivni]
        return sorted(items, key=lambda item: (item.poradi, item.nazev))

    def get_team_type_by_id(self, type_id: str) -> CatalogItem | None:
        type_id = str(type_id or "").strip()
        if not type_id:
            return None
        for item in self._load_team_types():
            if item.id == type_id:
                return item
        return None

    def get_team_role_by_id(self, role_id: str) -> CatalogItem | None:
        role_id = str(role_id or "").strip()
        if not role_id:
            return None
        for item in self._load_team_roles():
            if item.id == role_id:
                return item
        return None

    def save_team_types(self, items: list[dict]) -> None:
        payload = {
            "verze": self._read_catalog(self._team_types_path()).get("verze", 1),
            "typy": items,
        }
        self._write_catalog(self._team_types_path(), payload)
        self._team_types = None

    def save_team_roles(self, items: list[dict]) -> None:
        payload = {
            "verze": self._read_catalog(self._team_roles_path()).get("verze", 1),
            "role": items,
        }
        self._write_catalog(self._team_roles_path(), payload)
        self._team_roles = None

    def _load_team_types(self) -> list[CatalogItem]:
        if self._team_types is not None:
            return self._team_types

        raw = self._read_catalog(self._team_types_path())
        entries = raw.get("typy")
        if not isinstance(entries, list) or not entries:
            entries = [deepcopy(item) for item in DEFAULT_TEAM_TYPES]

        self._team_types = [self._normalize_item(entry) for entry in entries if isinstance(entry, dict)]
        if not self._team_types:
            self._team_types = [self._normalize_item(deepcopy(item)) for item in DEFAULT_TEAM_TYPES]
        return self._team_types

    def _load_team_roles(self) -> list[CatalogItem]:
        if self._team_roles is not None:
            return self._team_roles

        raw = self._read_catalog(self._team_roles_path())
        entries = raw.get("role")
        if not isinstance(entries, list) or not entries:
            entries = [deepcopy(item) for item in DEFAULT_TEAM_ROLES]

        self._team_roles = [self._normalize_item(entry) for entry in entries if isinstance(entry, dict)]
        if not self._team_roles:
            self._team_roles = [self._normalize_item(deepcopy(item)) for item in DEFAULT_TEAM_ROLES]
        return self._team_roles

    def _team_types_path(self) -> Path:
        return editable_catalog_service.ensure_catalog(
            storage_service.ciselniky_dir,
            TEAM_TYPES_CATALOG_PATH,
        )

    def _team_roles_path(self) -> Path:
        return editable_catalog_service.ensure_catalog(
            storage_service.ciselniky_dir,
            TEAM_ROLES_CATALOG_PATH,
        )

    @staticmethod
    def _read_catalog(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _write_catalog(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _normalize_item(entry: dict) -> CatalogItem:
        item_id = str(entry.get("id") or "").strip()
        nazev = str(entry.get("nazev") or item_id).strip()
        return CatalogItem(
            id=item_id or nazev.lower().replace(" ", "_"),
            nazev=nazev,
            popis=str(entry.get("popis") or "").strip(),
            poradi=int(entry.get("poradi") or 0),
            aktivni=bool(entry.get("aktivni", True)),
        )


team_catalog_service = TeamCatalogService()

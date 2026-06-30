import json
from dataclasses import dataclass
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service

_CATALOG_DIR = "proverky"
_OBLASTI_FILE = f"{_CATALOG_DIR}/oblasti.json"

_KNOWLEDGE_LIST_FIELDS = (
    "kontrolni_body",
    "typicke_zavady",
    "doporucene_postupy",
    "legislativa",
    "historie",
)

SECTION_LIST_BLOCKS: tuple[tuple[str, str], ...] = (
    ("Kontrolní body", "kontrolni_body"),
    ("Typické závady", "typicke_zavady"),
    ("Doporučené postupy", "doporucene_postupy"),
    ("Legislativa", "legislativa"),
    ("Historie", "historie"),
)


@dataclass(frozen=True)
class InspectionAreaDefinition:
    id: str
    nazev: str
    popis: str
    poradi: int
    aktivni: bool
    soubor_znalosti: str | None

    @property
    def has_knowledge_file(self) -> bool:
        return bool(self.soubor_znalosti)


class ProverkyKnowledgeService:
    """Načítání znalostní báze oblastí prověrek z editovatelných JSON číselníků."""

    def ensure_catalogs(self) -> None:
        editable_catalog_service.ensure_catalog(self.ciselniky_dir, _OBLASTI_FILE)
        self._ensure_knowledge_files_from_areas_catalog()

    def _ensure_knowledge_files_from_areas_catalog(self) -> None:
        path = self.proverky_dir / "oblasti.json"
        if not path.is_file():
            return

        payload = self._load_json(path)
        for raw in payload.get("oblasti") or []:
            if not isinstance(raw, dict):
                continue
            soubor = raw.get("soubor_znalosti")
            if not soubor:
                continue
            relative_path = f"{_CATALOG_DIR}/{str(soubor).strip()}"
            editable_catalog_service.ensure_catalog(self.ciselniky_dir, relative_path)

    @property
    def ciselniky_dir(self) -> Path:
        return storage_service.ciselniky_dir

    @property
    def proverky_dir(self) -> Path:
        return self.ciselniky_dir / _CATALOG_DIR

    def get_areas(self, *, include_inactive: bool = False) -> list[InspectionAreaDefinition]:
        self.ensure_catalogs()
        payload = self._load_json(self.proverky_dir / "oblasti.json")
        raw_areas = payload.get("oblasti") or []

        areas: list[InspectionAreaDefinition] = []
        for raw in raw_areas:
            if not isinstance(raw, dict):
                continue
            area = self._parse_area_definition(raw)
            if area is None:
                continue
            if not include_inactive and not area.aktivni:
                continue
            areas.append(area)

        areas.sort(key=lambda item: (item.poradi, item.nazev.lower()))
        return areas

    def load_area_knowledge(self, area: InspectionAreaDefinition) -> dict | None:
        if not area.soubor_znalosti:
            return None

        self.ensure_catalogs()
        path = self.proverky_dir / area.soubor_znalosti
        if not path.is_file():
            return None

        return self._load_json(path)

    def get_active_sections(self, knowledge: dict) -> list[dict]:
        sections = knowledge.get("sekce") or []
        active = [
            section
            for section in sections
            if isinstance(section, dict) and section.get("aktivni", True)
        ]
        active.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return active

    def section_has_content(self, section: dict) -> bool:
        nested = section.get("sekce") or []
        if nested:
            return True

        for field in _KNOWLEDGE_LIST_FIELDS:
            values = section.get(field) or []
            if values:
                return True

        return False

    def _parse_area_definition(self, raw: dict) -> InspectionAreaDefinition | None:
        area_id = str(raw.get("id") or "").strip()
        nazev = str(raw.get("nazev") or "").strip()
        if not area_id or not nazev:
            return None

        soubor = raw.get("soubor_znalosti")
        soubor_znalosti = str(soubor).strip() if soubor else None

        return InspectionAreaDefinition(
            id=area_id,
            nazev=nazev,
            popis=str(raw.get("popis") or "").strip(),
            poradi=int(raw.get("poradi") or 0),
            aktivni=bool(raw.get("aktivni", True)),
            soubor_znalosti=soubor_znalosti,
        )

    def _load_json(self, path: Path) -> dict:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Neplatný JSON číselník: {path}")
        return payload


proverky_knowledge_service = ProverkyKnowledgeService()

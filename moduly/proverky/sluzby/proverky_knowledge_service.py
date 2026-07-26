import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.proverky.constants import (
    CONTROL_POINT_SEVERITY_DEFAULT,
    CONTROL_POINT_SEVERITY_KRITICKA,
    CONTROL_POINT_SEVERITY_NIZKA,
    CONTROL_POINT_SEVERITY_STREDNI,
    CONTROL_POINT_SEVERITY_VYSOKA,
    VERIFICATION_TYPE_DEFAULT,
)

_VALID_CONTROL_POINT_SEVERITIES = frozenset(
    {
        CONTROL_POINT_SEVERITY_KRITICKA,
        CONTROL_POINT_SEVERITY_VYSOKA,
        CONTROL_POINT_SEVERITY_STREDNI,
        CONTROL_POINT_SEVERITY_NIZKA,
    }
)

_CATALOG_DIR = "proverky"
_OBLASTI_FILE = f"{_CATALOG_DIR}/oblasti.json"
_ZAVAZNOST_SEED_SYNC_KEY = "zavaznost_seed_sync"
_ZAVAZNOST_SEED_SYNC_VERSION = 1

KNOWLEDGE_NODE_AREA = "area"
KNOWLEDGE_NODE_SECTION = "section"

_KNOWLEDGE_LIST_FIELDS = (
    "postup_kontroly",
    "referencni_fotografie",
    "kontrolni_body",
    "typicke_zavady",
    "doporucene_postupy",
    "legislativa",
    "historie",
)

EDITABLE_SECTION_PROCEDURE_FIELDS: tuple[tuple[str, str], ...] = (
    ("Postup kontroly", "postup_kontroly"),
)

EDITABLE_SECTION_REFERENCE_FIELDS: tuple[tuple[str, str], ...] = (
    ("📷 Referenční fotografie", "referencni_fotografie"),
)

EDITABLE_SECTION_LIST_FIELDS: tuple[tuple[str, str], ...] = (
    ("Kontrolní body", "kontrolni_body"),
    ("Typické závady", "typicke_zavady"),
    ("Doporučené postupy", "doporucene_postupy"),
    ("Legislativa", "legislativa"),
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


@dataclass(frozen=True)
class KnowledgeTreeNode:
    """Uzel znalostního stromu — oblast nebo sekce s volitelnými potomky."""

    node_type: str
    node_id: str
    label: str
    area_id: str
    area_label: str
    section: dict | None = None
    children: tuple["KnowledgeTreeNode", ...] = field(default_factory=tuple)


class ProverkyKnowledgeService:
    """Načítání znalostní báze oblastí prověrek z editovatelných JSON číselníků."""

    def ensure_catalogs(self) -> None:
        user_path = editable_catalog_service.ensure_catalog(self.ciselniky_dir, _OBLASTI_FILE)
        self._upgrade_areas_catalog_from_seed(user_path)
        self._ensure_knowledge_files_from_areas_catalog()

    def _upgrade_areas_catalog_from_seed(self, user_path: Path) -> None:
        if not user_path.is_file():
            return

        bundled_path = editable_catalog_service.bundled_path(_OBLASTI_FILE)
        if not bundled_path.is_file():
            return

        user_data = self._load_json(user_path)
        seed_data = self._load_json(bundled_path)
        if not self._merge_areas_catalog_from_seed(user_data, seed_data):
            return

        user_path.write_text(
            json.dumps(user_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _merge_areas_catalog_from_seed(self, user: dict, seed: dict) -> bool:
        changed = False

        user_areas = user.setdefault("oblasti", [])
        if not isinstance(user_areas, list):
            user_areas = []
            user["oblasti"] = user_areas
            changed = True

        user_by_id = self._areas_by_id(user_areas)
        for seed_area in seed.get("oblasti") or []:
            if not isinstance(seed_area, dict):
                continue

            area_id = str(seed_area.get("id") or "").strip()
            if not area_id:
                continue

            user_area = user_by_id.get(area_id)
            if user_area is None:
                user_areas.append(deepcopy(seed_area))
                user_by_id[area_id] = user_areas[-1]
                changed = True
                continue

            if self._merge_area_fields_from_seed(user_area, seed_area):
                changed = True

        seed_verze = int(seed.get("verze") or 0)
        user_verze = int(user.get("verze") or 0)
        if changed and seed_verze > user_verze:
            user["verze"] = seed_verze

        return changed

    def _merge_area_fields_from_seed(self, user_area: dict, seed_area: dict) -> bool:
        changed = False

        if self._text_field_is_empty(user_area.get("popis")):
            seed_popis = str(seed_area.get("popis") or "").strip()
            if seed_popis:
                user_area["popis"] = seed_popis
                changed = True

        user_soubor = user_area.get("soubor_znalosti")
        if user_soubor is None or not str(user_soubor).strip():
            seed_soubor = seed_area.get("soubor_znalosti")
            if seed_soubor and str(seed_soubor).strip():
                user_area["soubor_znalosti"] = seed_soubor
                changed = True

        return changed

    @staticmethod
    def _areas_by_id(areas: list | None) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for area in areas or []:
            if not isinstance(area, dict):
                continue
            area_id = str(area.get("id") or "").strip()
            if area_id:
                result[area_id] = area
        return result

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
            user_path = editable_catalog_service.ensure_catalog(self.ciselniky_dir, relative_path)
            self._upgrade_knowledge_file_from_seed(user_path, relative_path)

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

    def get_area_by_id(self, area_id: str) -> InspectionAreaDefinition | None:
        for area in self.get_areas(include_inactive=True):
            if area.id == area_id:
                return area
        return None

    def get_knowledge_tree(self, *, include_inactive: bool = False) -> list[KnowledgeTreeNode]:
        roots: list[KnowledgeTreeNode] = []
        for area in self.get_areas(include_inactive=include_inactive):
            children: tuple[KnowledgeTreeNode, ...] = ()
            if area.has_knowledge_file:
                knowledge = self.load_area_knowledge(area)
                if knowledge:
                    if include_inactive:
                        sections = [
                            section
                            for section in (knowledge.get("sekce") or [])
                            if isinstance(section, dict)
                        ]
                        sections.sort(
                            key=lambda item: (
                                int(item.get("poradi") or 0),
                                str(item.get("nazev") or "").casefold(),
                            )
                        )
                    else:
                        sections = self.get_active_sections(knowledge)
                    children = self._build_section_nodes(
                        area,
                        sections,
                        include_inactive=include_inactive,
                    )

            roots.append(
                KnowledgeTreeNode(
                    node_type=KNOWLEDGE_NODE_AREA,
                    node_id=area.id,
                    label=area.nazev,
                    area_id=area.id,
                    area_label=area.nazev,
                    children=children,
                )
            )
        return roots

    def find_tree_node(
        self,
        roots: list[KnowledgeTreeNode],
        *,
        area_id: str,
        section_id: str | None = None,
    ) -> KnowledgeTreeNode | None:
        for root in roots:
            if root.area_id != area_id:
                continue
            if section_id is None:
                return root
            found = self._find_section_node(root.children, section_id)
            if found is not None:
                return found
        return None

    def _build_section_nodes(
        self,
        area: InspectionAreaDefinition,
        sections: list[dict],
        *,
        include_inactive: bool = False,
    ) -> tuple[KnowledgeTreeNode, ...]:
        nodes: list[KnowledgeTreeNode] = []
        for section in sections:
            raw_nested = section.get("sekce") or []
            if include_inactive:
                nested = [item for item in raw_nested if isinstance(item, dict)]
                nested.sort(
                    key=lambda item: (
                        int(item.get("poradi") or 0),
                        str(item.get("nazev") or "").casefold(),
                    )
                )
            elif raw_nested:
                nested = self.get_active_sections(section)
            else:
                nested = []
            child_nodes = (
                self._build_section_nodes(
                    area,
                    nested,
                    include_inactive=include_inactive,
                )
                if nested
                else ()
            )
            nodes.append(
                KnowledgeTreeNode(
                    node_type=KNOWLEDGE_NODE_SECTION,
                    node_id=str(section.get("id") or ""),
                    label=str(section.get("nazev") or "—"),
                    area_id=area.id,
                    area_label=area.nazev,
                    section=section,
                    children=child_nodes,
                )
            )
        return tuple(nodes)

    @staticmethod
    def _find_section_node(
        nodes: tuple[KnowledgeTreeNode, ...],
        section_id: str,
    ) -> KnowledgeTreeNode | None:
        for node in nodes:
            if node.node_id == section_id:
                return node
            if node.children:
                found = ProverkyKnowledgeService._find_section_node(node.children, section_id)
                if found is not None:
                    return found
        return None

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

    def get_active_items(self, items: list | None) -> list[dict]:
        active = [
            item
            for item in (items or [])
            if isinstance(item, dict) and item.get("aktivni", True)
        ]
        active.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return active

    def get_general_reference_photos(self, section: dict) -> list[dict]:
        photos: list[dict] = []
        for raw in section.get("referencni_fotografie") or []:
            if not isinstance(raw, dict):
                continue
            if not raw.get("aktivni", True):
                continue

            control_point_id = raw.get("control_point_id")
            if control_point_id is not None and str(control_point_id).strip():
                continue

            soubor = str(raw.get("soubor") or "").strip()
            if not soubor:
                continue

            photos.append(raw)

        photos.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return photos

    def _upgrade_knowledge_file_from_seed(self, user_path: Path, relative_path: str) -> None:
        if not user_path.is_file():
            return

        bundled_path = editable_catalog_service.bundled_path(relative_path)
        if not bundled_path.is_file():
            return

        user_data = self._load_json(user_path)
        seed_data = self._load_json(bundled_path)
        if not self._merge_knowledge_from_seed(user_data, seed_data):
            return

        user_path.write_text(
            json.dumps(user_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _merge_knowledge_from_seed(self, user: dict, seed: dict) -> bool:
        changed = False

        user_sections = self._sections_by_id(user.get("sekce"))
        seed_sections = self._sections_by_id(seed.get("sekce"))
        full_severity_sync = int(user.get(_ZAVAZNOST_SEED_SYNC_KEY) or 0) < _ZAVAZNOST_SEED_SYNC_VERSION

        for section_id, seed_section in seed_sections.items():
            user_section = user_sections.get(section_id)
            if user_section is None:
                continue

            for field in _KNOWLEDGE_LIST_FIELDS:
                if field == "kontrolni_body":
                    continue
                if not self._list_field_is_empty(user_section.get(field)):
                    continue
                seed_values = seed_section.get(field) or []
                if not seed_values:
                    continue
                user_section[field] = deepcopy(seed_values)
                changed = True

            if self._merge_control_point_severity_from_seed(
                user_section,
                seed_section,
                full_sync=full_severity_sync,
            ):
                changed = True

            if self._text_field_is_empty(user_section.get("popis")):
                seed_popis = str(seed_section.get("popis") or "").strip()
                if seed_popis:
                    user_section["popis"] = seed_popis
                    changed = True

        if full_severity_sync:
            user[_ZAVAZNOST_SEED_SYNC_KEY] = _ZAVAZNOST_SEED_SYNC_VERSION
            changed = True

        seed_verze = int(seed.get("verze") or 0)
        user_verze = int(user.get("verze") or 0)
        if changed and seed_verze > user_verze:
            user["verze"] = seed_verze

        return changed

    def _merge_control_point_severity_from_seed(
        self,
        user_section: dict,
        seed_section: dict,
        *,
        full_sync: bool,
    ) -> bool:
        user_items = user_section.get("kontrolni_body") or []
        seed_items = seed_section.get("kontrolni_body") or []
        if not user_items or not seed_items:
            return False

        seed_by_id: dict[str, str] = {}
        for seed_item in seed_items:
            if not isinstance(seed_item, dict):
                continue
            item_id = str(seed_item.get("id") or "").strip()
            if item_id:
                seed_by_id[item_id] = self.normalize_control_point_severity(
                    seed_item.get("zavaznost")
                )

        changed = False
        for user_item in user_items:
            if not isinstance(user_item, dict):
                continue
            item_id = str(user_item.get("id") or "").strip()
            if not item_id or item_id not in seed_by_id:
                continue

            if not full_sync and user_item.get("zavaznost") not in (None, ""):
                continue

            new_severity = seed_by_id[item_id]
            if user_item.get("zavaznost") != new_severity:
                user_item["zavaznost"] = new_severity
                changed = True

        return changed

    @staticmethod
    def _sections_by_id(sections: list | None) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id") or "").strip()
            if section_id:
                result[section_id] = section
        return result

    @staticmethod
    def _list_field_is_empty(value) -> bool:
        if value is None:
            return True
        if isinstance(value, list):
            return len(value) == 0
        return False

    @staticmethod
    def _text_field_is_empty(value) -> bool:
        return not str(value or "").strip()

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

    def list_sections(
        self,
        area_id: str,
        *,
        include_inactive: bool = True,
    ) -> list[dict]:
        area = self.get_area_by_id(area_id)
        if area is None or not area.has_knowledge_file:
            return []

        knowledge = self.load_area_knowledge(area)
        if knowledge is None:
            return []

        return self._collect_sections(knowledge.get("sekce") or [], include_inactive=include_inactive)

    def get_section(self, area_id: str, section_id: str) -> dict | None:
        area = self.get_area_by_id(area_id)
        if area is None or not area.has_knowledge_file:
            return None

        knowledge = self.load_area_knowledge(area)
        if knowledge is None:
            return None

        found = self._find_section_in_sections(knowledge.get("sekce") or [], section_id)
        if found is None:
            return None

        _parent_list, index = found
        return deepcopy(_parent_list[index])

    @staticmethod
    def normalize_legal_requirement_id(value) -> int | None:
        if value is None or value == "":
            return None
        try:
            requirement_id = int(value)
        except (TypeError, ValueError):
            return None
        if requirement_id <= 0:
            return None
        return requirement_id

    def resolve_legal_requirement_id(
        self,
        value,
        *,
        existing_id=None,
    ) -> tuple[int | None, list[str]]:
        """Ověří vazbu na řídicí proces (stejná pravidla jako auditní metodika)."""
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        requirement_id = self.normalize_legal_requirement_id(value)
        if requirement_id is None:
            return None, []

        existing_normalized = self.normalize_legal_requirement_id(existing_id)
        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            return None, ["Vybraný řídicí proces nebyl nalezen."]
        if not requirement.active and requirement_id != existing_normalized:
            return None, ["Vybraný řídicí proces není aktivní."]
        return requirement_id, []

    def save_section(
        self,
        area_id: str,
        section_id: str,
        section_data: dict,
    ) -> tuple[bool, list[str]]:
        area = self.get_area_by_id(area_id)
        if area is None or not area.has_knowledge_file:
            return False, ["Oblast nebyla nalezena."]

        knowledge = self.load_area_knowledge(area)
        if knowledge is None:
            return False, ["Soubor znalostí nelze načíst."]

        found = self._find_section_in_sections(knowledge.get("sekce") or [], section_id)
        if found is None:
            return False, [f"Sekce '{section_id}' nebyla nalezena."]

        parent_list, index = found
        existing = parent_list[index]
        updated = deepcopy(existing)
        updated.update(section_data)
        updated["id"] = section_id
        updated["historie"] = existing.get("historie") or []
        updated["sekce"] = existing.get("sekce") or []

        if "legal_requirement_id" in section_data:
            legal_requirement_id, link_errors = self.resolve_legal_requirement_id(
                section_data.get("legal_requirement_id"),
                existing_id=existing.get("legal_requirement_id"),
            )
            if link_errors:
                return False, link_errors
            if legal_requirement_id is not None:
                updated["legal_requirement_id"] = legal_requirement_id
            else:
                updated.pop("legal_requirement_id", None)

        parent_list[index] = updated
        if not self._save_knowledge(area, knowledge):
            return False, ["Uložení sekce se nezdařilo."]
        return True, []

    def generate_item_id(self, nazev: str, existing_ids: set[str]) -> str:
        base = self._slugify(nazev) or "polozka"
        candidate = base
        counter = 2
        while candidate in existing_ids:
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    @staticmethod
    def normalize_control_point_severity(value) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in _VALID_CONTROL_POINT_SEVERITIES:
            return normalized
        return CONTROL_POINT_SEVERITY_DEFAULT

    @classmethod
    def get_control_point_severity(cls, item: dict | None) -> str:
        if not isinstance(item, dict):
            return CONTROL_POINT_SEVERITY_DEFAULT
        return cls.normalize_control_point_severity(item.get("zavaznost"))

    @classmethod
    def normalize_kontrolni_body(cls, items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id") or "").strip()
            nazev = str(raw.get("nazev") or "").strip()
            if not item_id or not nazev:
                continue
            normalized.append(
                {
                    "id": item_id,
                    "nazev": nazev,
                    "popis": str(raw.get("popis") or "").strip(),
                    "poradi": (index + 1) * 10,
                    "aktivni": bool(raw.get("aktivni", True)),
                    "zavaznost": cls.normalize_control_point_severity(raw.get("zavaznost")),
                    "verification_type": cls.normalize_verification_type(
                        raw.get("verification_type")
                    ),
                }
            )
        return normalized

    @staticmethod
    def normalize_verification_type(value) -> str:
        from moduly.proverky.constants import (
            VERIFICATION_TYPE_DOCUMENTATION,
            VERIFICATION_TYPE_TERRAIN,
        )

        normalized = str(value or "").strip().lower()
        if normalized in {
            VERIFICATION_TYPE_DOCUMENTATION,
            VERIFICATION_TYPE_TERRAIN,
        }:
            return normalized
        if normalized in {"dokumentace", "documentation", "doc"}:
            return VERIFICATION_TYPE_DOCUMENTATION
        if normalized in {"terén", "teren", "terrain", "field"}:
            return VERIFICATION_TYPE_TERRAIN
        return VERIFICATION_TYPE_DEFAULT

    @classmethod
    def get_verification_type(cls, item: dict | None) -> str:
        if not isinstance(item, dict):
            return VERIFICATION_TYPE_DEFAULT
        return cls.normalize_verification_type(item.get("verification_type"))

    @staticmethod
    def normalize_list_items(items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id") or "").strip()
            nazev = str(raw.get("nazev") or "").strip()
            if not item_id or not nazev:
                continue
            normalized.append(
                {
                    "id": item_id,
                    "nazev": nazev,
                    "popis": str(raw.get("popis") or "").strip(),
                    "poradi": (index + 1) * 10,
                    "aktivni": bool(raw.get("aktivni", True)),
                }
            )
        return normalized

    @staticmethod
    def normalize_procedure_steps(items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id") or "").strip()
            text = str(raw.get("text") or "").strip()
            if not item_id or not text:
                continue
            normalized.append(
                {
                    "id": item_id,
                    "text": text,
                    "poradi": (index + 1) * 10,
                    "aktivni": bool(raw.get("aktivni", True)),
                }
            )
        return normalized

    @staticmethod
    def normalize_reference_photos(items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id") or "").strip()
            nazev = str(raw.get("nazev") or "").strip()
            soubor = str(raw.get("soubor") or "").strip()
            if not item_id or not nazev or not soubor:
                continue

            control_point_id = raw.get("control_point_id")
            if control_point_id is None or not str(control_point_id).strip():
                control_point_value = None
            else:
                control_point_value = str(control_point_id).strip()

            normalized.append(
                {
                    "id": item_id,
                    "nazev": nazev,
                    "popis": str(raw.get("popis") or "").strip(),
                    "soubor": soubor,
                    "control_point_id": control_point_value,
                    "poradi": (index + 1) * 10,
                    "aktivni": bool(raw.get("aktivni", True)),
                }
            )
        return normalized

    def _save_knowledge(self, area: InspectionAreaDefinition, data: dict) -> bool:
        if not area.soubor_znalosti:
            return False

        path = self.proverky_dir / area.soubor_znalosti
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return False
        return True

    def _collect_sections(
        self,
        sections: list,
        *,
        include_inactive: bool,
    ) -> list[dict]:
        collected: list[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not include_inactive and not section.get("aktivni", True):
                continue
            collected.append(section)
            nested = section.get("sekce") or []
            if nested:
                collected.extend(self._collect_sections(nested, include_inactive=include_inactive))
        collected.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return collected

    def _find_section_in_sections(
        self,
        sections: list,
        section_id: str,
    ) -> tuple[list, int] | None:
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            if str(section.get("id") or "").strip() == section_id:
                return sections, index
            nested = section.get("sekce") or []
            found = self._find_section_in_sections(nested, section_id)
            if found is not None:
                return found
        return None

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.strip().lower())
        ascii_text = "".join(
            character for character in normalized if not unicodedata.combining(character)
        )
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
        return slug


proverky_knowledge_service = ProverkyKnowledgeService()

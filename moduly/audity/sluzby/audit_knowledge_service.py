import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.audity.constants import (
    CONTROL_POINT_SEVERITY_DEFAULT,
    CONTROL_POINT_SEVERITY_KRITICKA,
    CONTROL_POINT_SEVERITY_NIZKA,
    CONTROL_POINT_SEVERITY_STREDNI,
    CONTROL_POINT_SEVERITY_VYSOKA,
)
from moduly.audity.sluzby.audit_knowledge_validator import SECTION_REQUIRED_FIELDS


class AuditCatalogError(Exception):
    """Povinný číselník auditů chybí nebo jej nelze načíst."""

_SKIP_SECTION_BACKFILL_FIELDS = frozenset(
    {
        "auditni_tvrzeni",
        "navodne_otazky",
        "kontrolni_body",
        "historie",
    }
)

_VALID_CONTROL_POINT_SEVERITIES = frozenset(
    {
        CONTROL_POINT_SEVERITY_KRITICKA,
        CONTROL_POINT_SEVERITY_VYSOKA,
        CONTROL_POINT_SEVERITY_STREDNI,
        CONTROL_POINT_SEVERITY_NIZKA,
    }
)

_CATALOG_DIR = "audity"
_PROCESY_FILE = f"{_CATALOG_DIR}/procesy.json"
_ZAVAZNOST_SEED_SYNC_KEY = "zavaznost_seed_sync"
_ZAVAZNOST_SEED_SYNC_VERSION = 1

KNOWLEDGE_NODE_PROCESS = "process"
KNOWLEDGE_NODE_SECTION = "section"

_KNOWLEDGE_LIST_FIELDS = (
    "postup_kontroly",
    "referencni_fotografie",
    "kontrolni_body",
    "auditni_tvrzeni",
    "navodne_otazky",
    "typicke_neshody",
    "typicke_zavady",
    "doporucene_postupy",
    "doporucene_rozhovory",
    "pozorovani_v_provozu",
    "legislativa",
    "pozadavky_normy",
    "objektivni_dukazy",
    "pkz",
    "pozorovani",
    "poznamky_auditora",
    "vazby_procesy",
    "historie",
)

_KNOWLEDGE_TEXT_FIELDS = (
    "ucel_procesu",
    "proc_je_dulezity",
    "ocekavany_vystup",
    "cil_overeni",
)

_MERGE_ADDITIVE_LIST_FIELDS = frozenset(_KNOWLEDGE_LIST_FIELDS)

_SECTION_TEXT_FIELDS = ("popis", "cil_overeni")

EDITABLE_SECTION_PROCEDURE_FIELDS: tuple[tuple[str, str], ...] = (
    ("Postup auditu", "postup_kontroly"),
)

EDITABLE_SECTION_REFERENCE_FIELDS: tuple[tuple[str, str], ...] = (
    ("📷 Referenční fotografie", "referencni_fotografie"),
)

EDITABLE_SECTION_ASSERTION_FIELDS: tuple[tuple[str, str], ...] = (
    ("Auditní tvrzení", "auditni_tvrzeni"),
)

EDITABLE_SECTION_LIST_FIELDS: tuple[tuple[str, str], ...] = (
    ("Objektivní důkazy", "objektivni_dukazy"),
    ("Doporučené rozhovory", "doporucene_rozhovory"),
    ("Pozorování v provozu", "pozorovani_v_provozu"),
    ("Typické neshody", "typicke_neshody"),
    ("Typické závady", "typicke_zavady"),
    ("Doporučené postupy", "doporucene_postupy"),
    ("Legislativa", "legislativa"),
    ("Požadavky norem", "pozadavky_normy"),
    ("PKZ", "pkz"),
    ("Pozorování", "pozorovani"),
    ("Poznámky auditora", "poznamky_auditora"),
    ("Vazby na procesy", "vazby_procesy"),
)

SECTION_LIST_BLOCKS: tuple[tuple[str, str], ...] = (
    ("Auditní tvrzení", "auditni_tvrzeni"),
    ("Objektivní důkazy", "objektivni_dukazy"),
    ("Doporučené rozhovory", "doporucene_rozhovory"),
    ("Pozorování v provozu", "pozorovani_v_provozu"),
    ("Typické neshody", "typicke_neshody"),
    ("Typické závady", "typicke_zavady"),
    ("Doporučené postupy", "doporucene_postupy"),
    ("Legislativa", "legislativa"),
    ("Požadavky norem", "pozadavky_normy"),
    ("PKZ", "pkz"),
    ("Pozorování", "pozorovani"),
    ("Poznámky auditora", "poznamky_auditora"),
    ("Vazby na procesy", "vazby_procesy"),
    ("Historie", "historie"),
)


@dataclass(frozen=True)
class AuditProcessDefinition:
    id: str
    nazev: str
    popis: str
    ucel_procesu: str
    poradi: int
    aktivni: bool
    soubor_znalosti: str | None

    @property
    def has_knowledge_file(self) -> bool:
        return bool(self.soubor_znalosti)


@dataclass(frozen=True)
class KnowledgeTreeNode:
    """Uzel znalostního stromu — auditovaný proces nebo kritérium s volitelnými potomky."""

    node_type: str
    node_id: str
    label: str
    process_id: str
    process_label: str
    section: dict | None = None
    children: tuple["KnowledgeTreeNode", ...] = field(default_factory=tuple)


class AuditKnowledgeService:
    """Načítání znalostní báze auditovaných procesů z editovatelných JSON číselníků."""

    def ensure_catalogs(self) -> None:
        user_path = editable_catalog_service.ensure_catalog(self.ciselniky_dir, _PROCESY_FILE)
        self._upgrade_processes_catalog_from_seed(user_path)
        self._ensure_knowledge_files_from_processes_catalog()

    def _upgrade_processes_catalog_from_seed(self, user_path: Path) -> None:
        if not user_path.is_file():
            return

        bundled_path = editable_catalog_service.bundled_path(_PROCESY_FILE)
        if not bundled_path.is_file():
            return

        user_data = self._load_json(user_path)
        seed_data = self._load_json(bundled_path)
        if not self._merge_processes_catalog_from_seed(user_data, seed_data):
            return

        user_path.write_text(
            json.dumps(user_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _merge_processes_catalog_from_seed(self, user: dict, seed: dict) -> bool:
        changed = False

        user_processes = user.setdefault("procesy", [])
        if not isinstance(user_processes, list):
            user_processes = []
            user["procesy"] = user_processes
            changed = True

        user_by_id = self._processes_by_id(user_processes)
        for seed_process in seed.get("procesy") or []:
            if not isinstance(seed_process, dict):
                continue

            process_id = str(seed_process.get("id") or "").strip()
            if not process_id:
                continue

            user_process = user_by_id.get(process_id)
            if user_process is None:
                user_processes.append(deepcopy(seed_process))
                user_by_id[process_id] = user_processes[-1]
                changed = True
                continue

            if self._merge_process_fields_from_seed(user_process, seed_process):
                changed = True

        seed_verze = int(seed.get("verze") or 0)
        user_verze = int(user.get("verze") or 0)
        if changed and seed_verze > user_verze:
            user["verze"] = seed_verze

        return changed

    def _merge_process_fields_from_seed(self, user_process: dict, seed_process: dict) -> bool:
        changed = False

        if self._text_field_is_empty(user_process.get("popis")):
            seed_popis = str(seed_process.get("popis") or "").strip()
            if seed_popis:
                user_process["popis"] = seed_popis
                changed = True

        if self._text_field_is_empty(user_process.get("ucel_procesu")):
            seed_ucel = str(seed_process.get("ucel_procesu") or "").strip()
            if seed_ucel:
                user_process["ucel_procesu"] = seed_ucel
                changed = True

        user_soubor = user_process.get("soubor_znalosti")
        if user_soubor is None or not str(user_soubor).strip():
            seed_soubor = seed_process.get("soubor_znalosti")
            if seed_soubor and str(seed_soubor).strip():
                user_process["soubor_znalosti"] = seed_soubor
                changed = True

        return changed

    @staticmethod
    def _processes_by_id(processes: list | None) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for process in processes or []:
            if not isinstance(process, dict):
                continue
            process_id = str(process.get("id") or "").strip()
            if process_id:
                result[process_id] = process
        return result

    def _ensure_knowledge_files_from_processes_catalog(self) -> None:
        path = self.audity_dir / "procesy.json"
        if not path.is_file():
            return

        payload = self._load_json(path)
        for raw in payload.get("procesy") or []:
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
    def audity_dir(self) -> Path:
        return self.ciselniky_dir / _CATALOG_DIR

    def get_processes(
        self,
        *,
        include_inactive: bool = False,
        ensure: bool = True,
    ) -> list[AuditProcessDefinition]:
        if ensure:
            self.ensure_catalogs()
        payload = self._load_processes_catalog()
        raw_processes = payload.get("procesy") or []

        processes: list[AuditProcessDefinition] = []
        for raw in raw_processes:
            if not isinstance(raw, dict):
                continue
            process = self._parse_process_definition(raw)
            if process is None:
                continue
            if not include_inactive and not process.aktivni:
                continue
            processes.append(process)

        processes.sort(key=lambda item: (item.poradi, item.nazev.lower()))
        return processes

    def _load_processes_catalog(self) -> dict:
        path = self.audity_dir / "procesy.json"
        if not path.is_file():
            raise AuditCatalogError(
                "Chybí povinný číselník auditů:\n"
                f"{path}\n\n"
                "Soubor se při startu aplikace kopíruje z distribuovaných dat. "
                "Zkontrolujte instalaci (AppImage musí obsahovat adresář ciselniky/) "
                "nebo obnovte výchozí číselníky."
            )
        try:
            return self._load_json(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AuditCatalogError(
                "Číselník auditů nelze načíst:\n"
                f"{path}\n\n"
                f"Detail: {exc}"
            ) from exc

    def get_process_by_id(
        self,
        process_id: str,
        *,
        ensure: bool = True,
    ) -> AuditProcessDefinition | None:
        for process in self.get_processes(include_inactive=True, ensure=ensure):
            if process.id == process_id:
                return process
        return None

    def get_knowledge_tree(
        self,
        *,
        include_inactive: bool = False,
        ensure: bool = True,
    ) -> list[KnowledgeTreeNode]:
        roots: list[KnowledgeTreeNode] = []
        for process in self.get_processes(include_inactive=include_inactive, ensure=ensure):
            children: tuple[KnowledgeTreeNode, ...] = ()
            if process.has_knowledge_file:
                knowledge = self.load_process_knowledge(process, ensure=ensure)
                if knowledge:
                    criteria = self._filter_sections(
                        knowledge.get("sekce") or [],
                        include_inactive=include_inactive,
                    )
                    children = self._build_criterion_nodes(
                        process,
                        criteria,
                        include_inactive=include_inactive,
                    )

            roots.append(
                KnowledgeTreeNode(
                    node_type=KNOWLEDGE_NODE_PROCESS,
                    node_id=process.id,
                    label=process.nazev,
                    process_id=process.id,
                    process_label=process.nazev,
                    children=children,
                )
            )
        return roots

    def find_tree_node(
        self,
        roots: list[KnowledgeTreeNode],
        *,
        process_id: str,
        criterion_id: str | None = None,
    ) -> KnowledgeTreeNode | None:
        for root in roots:
            if root.process_id != process_id:
                continue
            if criterion_id is None:
                return root
            found = self._find_criterion_node(root.children, criterion_id)
            if found is not None:
                return found
        return None

    def _build_criterion_nodes(
        self,
        process: AuditProcessDefinition,
        criteria: list[dict],
        *,
        include_inactive: bool = False,
    ) -> tuple[KnowledgeTreeNode, ...]:
        nodes: list[KnowledgeTreeNode] = []
        for criterion in criteria:
            nested_sections = criterion.get("sekce") or []
            nested = (
                self._filter_sections(nested_sections, include_inactive=include_inactive)
                if nested_sections
                else []
            )
            child_nodes = (
                self._build_criterion_nodes(process, nested, include_inactive=include_inactive)
                if nested
                else ()
            )
            nodes.append(
                KnowledgeTreeNode(
                    node_type=KNOWLEDGE_NODE_SECTION,
                    node_id=str(criterion.get("id") or ""),
                    label=str(criterion.get("nazev") or "—"),
                    process_id=process.id,
                    process_label=process.nazev,
                    section=criterion,
                    children=child_nodes,
                )
            )
        return tuple(nodes)

    @staticmethod
    def _filter_sections(sections: list, *, include_inactive: bool) -> list[dict]:
        filtered: list[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not include_inactive and not section.get("aktivni", True):
                continue
            filtered.append(section)

        filtered.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return filtered

    @staticmethod
    def _find_criterion_node(
        nodes: tuple[KnowledgeTreeNode, ...],
        criterion_id: str,
    ) -> KnowledgeTreeNode | None:
        for node in nodes:
            if node.node_id == criterion_id:
                return node
            if node.children:
                found = AuditKnowledgeService._find_criterion_node(node.children, criterion_id)
                if found is not None:
                    return found
        return None

    def load_process_knowledge(
        self,
        process: AuditProcessDefinition,
        *,
        ensure: bool = True,
    ) -> dict | None:
        if not process.soubor_znalosti:
            return None

        if ensure:
            self.ensure_catalogs()
        path = self.audity_dir / process.soubor_znalosti
        if not path.is_file():
            return None

        return self._load_json(path)

    @staticmethod
    def collect_section_ids(sections: list) -> set[str]:
        collected: set[str] = set()
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id") or "").strip()
            if section_id:
                collected.add(section_id)
            collected.update(
                AuditKnowledgeService.collect_section_ids(section.get("sekce") or [])
            )
        return collected

    @staticmethod
    def get_next_section_poradi(knowledge: dict) -> int:
        sections = knowledge.get("sekce") or []
        if not isinstance(sections, list) or not sections:
            return 10

        max_poradi = 0
        for section in sections:
            if not isinstance(section, dict):
                continue
            try:
                max_poradi = max(max_poradi, int(section.get("poradi") or 0))
            except (TypeError, ValueError):
                continue
        return max_poradi + 10 if max_poradi else 10

    def get_process_metadata(
        self,
        process_id: str,
        *,
        ensure: bool = True,
    ) -> dict | None:
        process = self.get_process_by_id(process_id, ensure=ensure)
        if process is None or not process.soubor_znalosti:
            return None

        knowledge = self.load_process_knowledge(process, ensure=ensure)
        if knowledge is None:
            return None

        return {
            "nazev": str(knowledge.get("nazev") or process.nazev or "").strip(),
            "popis": str(knowledge.get("popis") or process.popis or "").strip(),
            "ucel_procesu": str(
                knowledge.get("ucel_procesu") or process.ucel_procesu or ""
            ).strip(),
            "proc_je_dulezity": str(knowledge.get("proc_je_dulezity") or "").strip(),
            "ocekavany_vystup": str(knowledge.get("ocekavany_vystup") or "").strip(),
            "poradi": int(knowledge.get("poradi") if knowledge.get("poradi") is not None else process.poradi),
            "aktivni": bool(
                knowledge.get("aktivni")
                if knowledge.get("aktivni") is not None
                else process.aktivni
            ),
        }

    def get_active_criteria(self, knowledge: dict) -> list[dict]:
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
        full_severity_sync = int(user.get(_ZAVAZNOST_SEED_SYNC_KEY) or 0) < _ZAVAZNOST_SEED_SYNC_VERSION

        merged_sections, sections_changed = self._merge_sections_list_from_seed(
            user.get("sekce"),
            seed.get("sekce"),
            full_severity_sync=full_severity_sync,
        )
        if sections_changed:
            user["sekce"] = merged_sections
            changed = True

        if full_severity_sync:
            user[_ZAVAZNOST_SEED_SYNC_KEY] = _ZAVAZNOST_SEED_SYNC_VERSION
            changed = True

        for field in _KNOWLEDGE_TEXT_FIELDS:
            if not self._text_field_is_empty(user.get(field)):
                continue
            seed_value = str(seed.get(field) or "").strip()
            if seed_value:
                user[field] = seed_value
                changed = True

        for field in ("vazby_procesy", "pozadavky_norem"):
            merged_items, field_changed = self._merge_additive_list_from_seed(
                user.get(field),
                seed.get(field),
            )
            if field_changed:
                user[field] = merged_items
                changed = True

        seed_verze = int(seed.get("verze") or 0)
        user_verze = int(user.get("verze") or 0)
        if changed and seed_verze > user_verze:
            user["verze"] = seed_verze

        return changed

    def _merge_sections_list_from_seed(
        self,
        user_sections: list | None,
        seed_sections: list | None,
        *,
        full_severity_sync: bool,
    ) -> tuple[list, bool]:
        user_list = list(user_sections or []) if isinstance(user_sections, list) else []
        seed_list = [
            section
            for section in (seed_sections or [])
            if isinstance(section, dict)
        ]
        if not seed_list:
            return user_list, False

        user_by_id = self._sections_by_id(user_list)
        changed = False

        for seed_section in seed_list:
            section_id = str(seed_section.get("id") or "").strip()
            if not section_id:
                continue

            user_section = user_by_id.get(section_id)
            if user_section is None:
                user_list.append(deepcopy(seed_section))
                user_by_id[section_id] = user_list[-1]
                changed = True
                continue

            if self._merge_section_fields_from_seed(
                user_section,
                seed_section,
                full_severity_sync=full_severity_sync,
            ):
                changed = True

        user_list.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return user_list, changed

    def _merge_section_fields_from_seed(
        self,
        user_section: dict,
        seed_section: dict,
        *,
        full_severity_sync: bool,
    ) -> bool:
        changed = False

        for field in SECTION_REQUIRED_FIELDS:
            if field in user_section or field in _SKIP_SECTION_BACKFILL_FIELDS:
                continue
            if field in seed_section:
                user_section[field] = deepcopy(seed_section[field])
                changed = True
            elif field == "sekce":
                user_section[field] = []
                changed = True

        if self._merge_auditni_tvrzeni_from_seed(user_section, seed_section):
            changed = True

        for field in _MERGE_ADDITIVE_LIST_FIELDS:
            merged_items, field_changed = self._merge_additive_list_from_seed(
                user_section.get(field),
                seed_section.get(field),
            )
            if field_changed:
                user_section[field] = merged_items
                changed = True

        for field in ("kontrolni_body", "auditni_tvrzeni"):
            if self._merge_control_point_severity_from_seed(
                user_section,
                seed_section,
                field=field,
                full_sync=full_severity_sync,
            ):
                changed = True

        nested_sections, nested_changed = self._merge_sections_list_from_seed(
            user_section.get("sekce"),
            seed_section.get("sekce"),
            full_severity_sync=full_severity_sync,
        )
        if nested_changed:
            user_section["sekce"] = nested_sections
            changed = True

        for field in _SECTION_TEXT_FIELDS:
            if not self._text_field_is_empty(user_section.get(field)):
                continue
            seed_value = str(seed_section.get(field) or "").strip()
            if seed_value:
                user_section[field] = seed_value
                changed = True

        return changed

    @staticmethod
    def _merge_additive_list_from_seed(
        user_items: list | None,
        seed_items: list | None,
    ) -> tuple[list, bool]:
        seed_list = [
            item for item in (seed_items or []) if isinstance(item, dict)
        ]
        if not seed_list:
            return list(user_items or []) if isinstance(user_items, list) else [], False

        user_list = list(user_items or []) if isinstance(user_items, list) else []
        user_by_id: dict[str, dict] = {}
        for item in user_list:
            item_id = str(item.get("id") or "").strip()
            if item_id:
                user_by_id[item_id] = item

        changed = False
        for seed_item in seed_list:
            item_id = str(seed_item.get("id") or "").strip()
            if not item_id or item_id in user_by_id:
                continue
            user_list.append(deepcopy(seed_item))
            user_by_id[item_id] = user_list[-1]
            changed = True

        return user_list, changed

    def _merge_auditni_tvrzeni_from_seed(
        self,
        user_section: dict,
        seed_section: dict,
    ) -> bool:
        seed_items = seed_section.get("auditni_tvrzeni") or []
        if not seed_items:
            return False

        user_items = user_section.get("auditni_tvrzeni") or []
        if user_items:
            return False

        user_section["auditni_tvrzeni"] = deepcopy(seed_items)
        if user_section.get("navodne_otazky"):
            user_section["navodne_otazky"] = []
        return True

    def _merge_control_point_severity_from_seed(
        self,
        user_section: dict,
        seed_section: dict,
        *,
        field: str = "kontrolni_body",
        full_sync: bool,
    ) -> bool:
        user_items = user_section.get(field) or []
        seed_items = seed_section.get(field) or []
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

        for field in _KNOWLEDGE_TEXT_FIELDS:
            if str(section.get(field) or "").strip():
                return True

        for field in _KNOWLEDGE_LIST_FIELDS:
            values = section.get(field) or []
            if values:
                return True

        return False

    @staticmethod
    def get_text_field(data: dict | None, field: str) -> str:
        if not data:
            return ""
        return str(data.get(field) or "").strip()

    def has_active_list(self, data: dict | None, field: str) -> bool:
        if not data:
            return False
        return bool(self.get_active_items(data.get(field)))

    def _parse_process_definition(self, raw: dict) -> AuditProcessDefinition | None:
        process_id = str(raw.get("id") or "").strip()
        nazev = str(raw.get("nazev") or "").strip()
        if not process_id or not nazev:
            return None

        soubor = raw.get("soubor_znalosti")
        soubor_znalosti = str(soubor).strip() if soubor else None

        return AuditProcessDefinition(
            id=process_id,
            nazev=nazev,
            popis=str(raw.get("popis") or "").strip(),
            ucel_procesu=str(raw.get("ucel_procesu") or "").strip(),
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

    def list_criteria(
        self,
        process_id: str,
        *,
        include_inactive: bool = True,
    ) -> list[dict]:
        process = self.get_process_by_id(process_id)
        if process is None or not process.has_knowledge_file:
            return []

        knowledge = self.load_process_knowledge(process)
        if knowledge is None:
            return []

        return self._collect_criteria(knowledge.get("sekce") or [], include_inactive=include_inactive)

    def get_criterion(
        self,
        process_id: str,
        criterion_id: str,
        *,
        ensure: bool = True,
    ) -> dict | None:
        process = self.get_process_by_id(process_id, ensure=ensure)
        if process is None or not process.has_knowledge_file:
            return None

        knowledge = self.load_process_knowledge(process, ensure=ensure)
        if knowledge is None:
            return None

        found = self._find_criterion_in_sections(knowledge.get("sekce") or [], criterion_id)
        if found is None:
            return None

        _parent_list, index = found
        return deepcopy(_parent_list[index])

    def save_criterion(self, process_id: str, criterion_id: str, criterion_data: dict) -> bool:
        process = self.get_process_by_id(process_id)
        if process is None or not process.has_knowledge_file:
            return False

        knowledge = self.load_process_knowledge(process)
        if knowledge is None:
            return False

        found = self._find_criterion_in_sections(knowledge.get("sekce") or [], criterion_id)
        if found is None:
            return False

        parent_list, index = found
        existing = parent_list[index]
        updated = deepcopy(existing)
        updated.update(criterion_data)
        updated["id"] = criterion_id
        updated["historie"] = existing.get("historie") or []
        updated["sekce"] = existing.get("sekce") or []
        parent_list[index] = updated
        return self._save_knowledge(process, knowledge)

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
    def normalize_auditni_tvrzeni(cls, items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id") or "").strip()
            text = str(raw.get("text") or raw.get("nazev") or "").strip()
            if not item_id or not text:
                continue
            poradi = raw.get("poradi")
            normalized.append(
                {
                    "id": item_id,
                    "text": text,
                    "nazev": text,
                    "popis": str(raw.get("popis") or "").strip(),
                    "poradi": poradi if poradi is not None else (index + 1) * 10,
                    "aktivni": bool(raw.get("aktivni", True)),
                    "zavaznost": cls.normalize_control_point_severity(raw.get("zavaznost")),
                }
            )
        return normalized

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
                }
            )
        return normalized

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
            poradi = raw.get("poradi")
            try:
                poradi_value = int(poradi) if poradi is not None else (index + 1) * 10
            except (TypeError, ValueError):
                poradi_value = (index + 1) * 10
            normalized.append(
                {
                    "id": item_id,
                    "nazev": nazev,
                    "popis": str(raw.get("popis") or "").strip(),
                    "poradi": poradi_value,
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

    @staticmethod
    def normalize_reference_photos_for_editor(items: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            item_id = str(raw.get("id") or "").strip()
            nazev = str(raw.get("nazev") or "").strip()
            if not item_id or not nazev:
                continue

            control_point_id = raw.get("control_point_id")
            if control_point_id is None or not str(control_point_id).strip():
                control_point_value = None
            else:
                control_point_value = str(control_point_id).strip()

            poradi = raw.get("poradi")
            try:
                poradi_value = int(poradi) if poradi is not None else (index + 1) * 10
            except (TypeError, ValueError):
                poradi_value = (index + 1) * 10

            normalized.append(
                {
                    "id": item_id,
                    "nazev": nazev,
                    "popis": str(raw.get("popis") or "").strip(),
                    "soubor": str(raw.get("soubor") or "").strip(),
                    "control_point_id": control_point_value,
                    "poradi": poradi_value,
                    "aktivni": bool(raw.get("aktivni", True)),
                }
            )
        return normalized

    def _save_knowledge(self, process: AuditProcessDefinition, data: dict) -> bool:
        if not process.soubor_znalosti:
            return False

        path = self.audity_dir / process.soubor_znalosti
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return False
        return True

    def _collect_criteria(
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
                collected.extend(
                    self._collect_criteria(nested, include_inactive=include_inactive)
                )
        collected.sort(
            key=lambda item: (
                int(item.get("poradi") or 0),
                str(item.get("nazev") or "").lower(),
            )
        )
        return collected

    def _find_criterion_in_sections(
        self,
        sections: list,
        criterion_id: str,
    ) -> tuple[list, int] | None:
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            if str(section.get("id") or "").strip() == criterion_id:
                return sections, index
            nested = section.get("sekce") or []
            found = self._find_criterion_in_sections(nested, criterion_id)
            if found is not None:
                return found
        return None

    def get_audit_questions(self, criterion: dict) -> list[dict]:
        auditni_tvrzeni = criterion.get("auditni_tvrzeni")
        if auditni_tvrzeni:
            return self.normalize_auditni_tvrzeni(self.get_active_items(auditni_tvrzeni))

        for field in ("navodne_otazky", "kontrolni_body", "auditni_otazky"):
            items = criterion.get(field)
            if items:
                return self.get_active_items(items)
        return []

    @staticmethod
    def question_stable_key(process_id: str, criterion_id: str, question_id: str) -> str:
        return f"{process_id}/{criterion_id}/{question_id}"

    def normalize_audit_questions(self, items: list[dict]) -> list[dict]:
        return self.normalize_kontrolni_body(items)

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.strip().lower())
        ascii_text = "".join(
            character for character in normalized if not unicodedata.combining(character)
        )
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
        return slug


audit_knowledge_service = AuditKnowledgeService()

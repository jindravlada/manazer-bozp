from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from core.database.session import get_session
from core.services.backup_manifest_service import backup_manifest_service
from core.services.cz_nace_service import cz_nace_service
from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.kniha_urazu.services.ciselnik_service import kniha_urazu_ciselnik_service
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.vysetrovani_mu.constants import ISHIKAWA_CATEGORIES
from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service

MODULE_GLOBAL = "Globální číselníky"
MODULE_KNIHA_URAZU = "Modul Kniha úrazů"
MODULE_PROVERKY = "Prověrky"
MODULE_AUDITY = "Audity"
MODULE_RIDICI = "Řídicí procesy"
MODULE_VYSETROVANI_MU = "Vyšetřování MU"
MODULE_OTHER = "Další moduly"

# Pozůstatky odstraněného modulu Týmy – nezobrazovat v katalogu Správy dat.
_EXCLUDED_WORKSPACE_JSON_STEMS = frozenset({"role_v_tymu", "typy_tymu"})

MODULE_ORDER = (
    MODULE_GLOBAL,
    MODULE_KNIHA_URAZU,
    MODULE_PROVERKY,
    MODULE_AUDITY,
    MODULE_RIDICI,
    MODULE_VYSETROVANI_MU,
    MODULE_OTHER,
)

STORAGE_DATABASE = "databáze"
STORAGE_JSON = "JSON"
STORAGE_BUNDLED_JSON = "JSON (vestavěný)"
STORAGE_HARDCODED = "vestavěný seznam"

_KIND_JSON_WORKSPACE = "json_workspace"
_KIND_JSON_BUNDLED = "json_bundled"
_KIND_DATABASE = "database"
_KIND_HARDCODED = "hardcoded"


@dataclass(frozen=True)
class CodebookEntry:
    codebook_id: str
    name: str
    module: str
    storage_type: str
    path: str
    item_count: int
    last_modified: str | None
    exportable: bool
    importable: bool
    kind: str
    relative_path: str | None = None


class CodebookCatalogService:
    """Centrální přehled všech číselníků v aplikaci."""

    _AUDIT_REGISTRY = "audity/procesy.json"
    _PROVERKY_REGISTRY = "proverky/oblasti.json"

    _GLOBAL_DB_CODEBOOKS: tuple[tuple[str, str, str], ...] = (
        ("db:workplaces", "Provozy a pracoviště", "workplaces"),
        ("db:thp_workers", "THP pracovníci", "thp_workers"),
        ("db:employer", "Zaměstnavatel", "employers"),
        ("db:responsibility_roles", "Funkce / role", "responsibility_roles"),
        ("db:persons", "Osoby", "persons"),
    )

    _KNIHA_URAZU_FILES: tuple[tuple[str, str, str], ...] = (
        ("bundled:statni_obcanstvi", "Státní občanství", "statni_obcanstvi.json"),
        ("bundled:cz_isco", "CZ-ISCO (druh práce)", "cz_isco.json"),
        ("bundled:druh_zraneni", "Druhy zranění", "suip_druh_zraneni.json"),
        ("bundled:zranena_cast_tela", "Zraněné části těla", "suip_zranena_cast_tela.json"),
        ("bundled:cinnost_pri_urazu", "Činnosti při úrazu", "suip_cinnost_pri_urazu.json"),
        (
            "bundled:charakteristika_pracoviste",
            "Charakteristika pracoviště",
            "suip_charakteristika_pracoviste.json",
        ),
        ("bundled:zdroj_urazu", "Zdroje úrazu", "suip_zdroj_urazu.json"),
        ("bundled:pricina_urazu", "Příčiny úrazu", "suip_pricina_urazu.json"),
        ("bundled:okresy", "Okresy", "okresy.json"),
    )

    def list_codebooks(self) -> list[CodebookEntry]:
        entries: list[CodebookEntry] = []
        seen_ids: set[str] = set()

        for entry in self._global_db_entries():
            if entry.codebook_id not in seen_ids:
                entries.append(entry)
                seen_ids.add(entry.codebook_id)

        for entry in self._kniha_urazu_entries():
            if entry.codebook_id not in seen_ids:
                entries.append(entry)
                seen_ids.add(entry.codebook_id)

        for entry in self._workspace_json_entries():
            if entry.codebook_id not in seen_ids:
                entries.append(entry)
                seen_ids.add(entry.codebook_id)

        ridici = self._ridici_procesy_entry()
        if ridici.codebook_id not in seen_ids:
            entries.append(ridici)
            seen_ids.add(ridici.codebook_id)

        cz_nace = self._cz_nace_entry()
        if cz_nace.codebook_id not in seen_ids:
            entries.append(cz_nace)
            seen_ids.add(cz_nace.codebook_id)

        hardcoded = self._hardcoded_kniha_urazu_entries()
        for entry in hardcoded:
            if entry.codebook_id not in seen_ids:
                entries.append(entry)
                seen_ids.add(entry.codebook_id)

        return entries

    def grouped_codebooks(self) -> dict[str, list[CodebookEntry]]:
        grouped = {module: [] for module in MODULE_ORDER}
        for entry in self.list_codebooks():
            grouped.setdefault(entry.module, []).append(entry)
        return {module: grouped[module] for module in MODULE_ORDER if grouped[module]}

    def list_group_entries(self, module: str) -> list[CodebookEntry]:
        return list(self.grouped_codebooks().get(module) or [])

    def get_by_id(self, codebook_id: str) -> CodebookEntry | None:
        for entry in self.list_codebooks():
            if entry.codebook_id == codebook_id:
                return entry
        return None

    def count_all(self) -> int:
        return len(self.list_codebooks())

    def _global_db_entries(self) -> list[CodebookEntry]:
        result: list[CodebookEntry] = []
        for codebook_id, name, table_name in self._GLOBAL_DB_CODEBOOKS:
            count = self._count_db_codebook(table_name)
            result.append(
                CodebookEntry(
                    codebook_id=codebook_id,
                    name=name,
                    module=MODULE_GLOBAL,
                    storage_type=STORAGE_DATABASE,
                    path=f"databáze / {table_name}",
                    item_count=count,
                    last_modified=self._db_last_modified(table_name),
                    exportable=True,
                    importable=True,
                    kind=_KIND_DATABASE,
                )
            )
        return result

    def _kniha_urazu_entries(self) -> list[CodebookEntry]:
        data_dir = kniha_urazu_ciselnik_service.data_dir
        result: list[CodebookEntry] = []
        for codebook_id, name, filename in self._KNIHA_URAZU_FILES:
            path = data_dir / filename
            if not path.is_file():
                if filename == "okresy.json":
                    result.append(
                        CodebookEntry(
                            codebook_id="hardcoded:okresy",
                            name="Okresy",
                            module=MODULE_KNIHA_URAZU,
                            storage_type=STORAGE_HARDCODED,
                            path="moduly/kniha_urazu/services/ciselnik_service.py",
                            item_count=len(kniha_urazu_ciselnik_service.okresy()),
                            last_modified=None,
                            exportable=True,
                            importable=False,
                            kind=_KIND_HARDCODED,
                        )
                    )
                continue
            count = self._count_bundled_json(path)
            result.append(
                CodebookEntry(
                    codebook_id=codebook_id,
                    name=name,
                    module=MODULE_KNIHA_URAZU,
                    storage_type=STORAGE_BUNDLED_JSON,
                    path=str(path),
                    item_count=count,
                    last_modified=self._file_mtime(path),
                    exportable=True,
                    importable=False,
                    kind=_KIND_JSON_BUNDLED,
                    relative_path=f"kniha_urazu/{filename}",
                )
            )
        return result

    def _hardcoded_kniha_urazu_entries(self) -> list[CodebookEntry]:
        pojistovny = kniha_urazu_ciselnik_service.zdravotni_pojistovny()
        return [
            CodebookEntry(
                codebook_id="hardcoded:zdravotni_pojistovny",
                name="Zdravotní pojišťovny",
                module=MODULE_KNIHA_URAZU,
                storage_type=STORAGE_HARDCODED,
                path="moduly/kniha_urazu/services/ciselnik_service.py",
                item_count=len([item for item in pojistovny if item]),
                last_modified=None,
                exportable=True,
                importable=False,
                kind=_KIND_HARDCODED,
            ),
        ]

    def _cz_nace_entry(self) -> CodebookEntry:
        path = cz_nace_service.file_path.resolve()
        count = len(cz_nace_service.get_all_displays())
        return CodebookEntry(
            codebook_id="bundled:cz_nace",
            name="CZ-NACE",
            module=MODULE_OTHER,
            storage_type=STORAGE_BUNDLED_JSON,
            path=str(path),
            item_count=count,
            last_modified=self._file_mtime(path),
            exportable=True,
            importable=False,
            kind=_KIND_JSON_BUNDLED,
            relative_path="cz_nace/cz_nace.json",
        )

    def _ridici_procesy_entry(self) -> CodebookEntry:
        count = self._count_control_processes()
        return CodebookEntry(
            codebook_id="db:control_processes",
            name="Řídicí procesy",
            module=MODULE_RIDICI,
            storage_type=STORAGE_DATABASE,
            path="databáze / legal_requirements (řídicí procesy)",
            item_count=count,
            last_modified=self._control_processes_last_modified(),
            exportable=True,
            importable=False,
            kind=_KIND_DATABASE,
        )

    def _workspace_json_entries(self) -> list[CodebookEntry]:
        editable_catalog_service.ensure_all(storage_service.ciselniky_dir)
        ciselniky_dir = storage_service.ciselniky_dir
        if not ciselniky_dir.exists():
            return []

        process_names = self._audit_process_names()
        area_names = self._proverky_area_names()
        result: list[CodebookEntry] = []

        for path in sorted(ciselniky_dir.rglob("*.json")):
            if not path.is_file() or path.name.startswith("_"):
                continue
            if path.stem in _EXCLUDED_WORKSPACE_JSON_STEMS:
                continue

            relative = path.relative_to(ciselniky_dir).as_posix()
            module = self._module_for_json_path(relative)
            name = self._name_for_json_path(relative, process_names, area_names)
            result.append(
                CodebookEntry(
                    codebook_id=f"json:{relative}",
                    name=name,
                    module=module,
                    storage_type=STORAGE_JSON,
                    path=str(path),
                    item_count=self._count_json_file(path, relative),
                    last_modified=self._file_mtime(path),
                    exportable=True,
                    importable=True,
                    kind=_KIND_JSON_WORKSPACE,
                    relative_path=relative,
                )
            )

        return result

    def _module_for_json_path(self, relative_path: str) -> str:
        if relative_path.startswith("audity/"):
            return MODULE_AUDITY
        if relative_path.startswith("proverky/"):
            return MODULE_PROVERKY
        if relative_path.startswith("modulove/vysetrovani_mu/"):
            return MODULE_VYSETROVANI_MU
        return MODULE_GLOBAL

    def _name_for_json_path(
        self,
        relative_path: str,
        process_names: dict[str, str],
        area_names: dict[str, str],
    ) -> str:
        filename = Path(relative_path).name
        if relative_path == self._AUDIT_REGISTRY:
            return "Procesy auditu"
        if relative_path == self._PROVERKY_REGISTRY:
            return "Oblasti prověrek"
        if relative_path == "modulove/vysetrovani_mu/ishikawa_faktory.json":
            return "Ishikawa faktory"
        if relative_path.startswith("audity/"):
            return process_names.get(filename, filename.replace(".json", "").replace("_", " "))
        if relative_path.startswith("proverky/"):
            return area_names.get(filename, filename.replace(".json", "").replace("_", " "))
        return filename.replace(".json", "")

    def _audit_process_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        try:
            for process in audit_knowledge_service.get_processes(include_inactive=True):
                if process.soubor_znalosti:
                    names[process.soubor_znalosti] = process.nazev
        except Exception:
            pass
        return names

    def _proverky_area_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        try:
            for area in proverky_knowledge_service.get_areas(include_inactive=True):
                if area.soubor_znalosti:
                    names[area.soubor_znalosti] = area.nazev
        except Exception:
            pass
        return names

    def _count_db_codebook(self, table_name: str) -> int:
        if table_name == "workplaces":
            return len(settings_service.get_workplaces(include_inactive=True))
        if table_name == "thp_workers":
            return len(settings_service.get_workers(include_inactive=True))
        if table_name == "employers":
            employer = settings_service.get_employer()
            return 1 if employer is not None else 0
        if table_name == "responsibility_roles":
            return len(responsibility_role_service.get_all(include_inactive=True))
        if table_name == "persons":
            return len(person_service.get_all(include_inactive=True))
        return 0

    def _count_control_processes(self) -> int:
        try:
            with get_session() as session:
                return (
                    session.scalar(
                        select(func.count()).select_from(LegalRequirement).where(
                            LegalRequirement.parent_requirement_id.is_not(None)
                        )
                    )
                    or 0
                )
        except Exception:
            return 0

    def _control_processes_last_modified(self) -> str | None:
        try:
            with get_session() as session:
                value = session.scalar(select(func.max(LegalRequirement.updated_at)))
                if value is None:
                    return None
                if isinstance(value, datetime):
                    return value.isoformat(timespec="seconds")
                return str(value)
        except Exception:
            return None

    def _db_last_modified(self, table_name: str) -> str | None:
        if table_name == "employers":
            employer = settings_service.get_employer()
            if employer is None:
                return None
            created = getattr(employer, "created_at", None)
            if isinstance(created, datetime):
                return created.isoformat(timespec="seconds")
            return None

        models = {
            "workplaces": settings_service.get_workplaces,
            "thp_workers": settings_service.get_workers,
            "responsibility_roles": responsibility_role_service.get_all,
            "persons": person_service.get_all,
        }
        loader = models.get(table_name)
        if loader is None:
            return None

        items = loader(include_inactive=True)
        timestamps: list[datetime] = []
        for item in items:
            for attr in ("updated_at", "created_at"):
                value = getattr(item, attr, None)
                if isinstance(value, datetime):
                    timestamps.append(value)
        if not timestamps:
            return None
        return max(timestamps).isoformat(timespec="seconds")

    def _count_bundled_json(self, path: Path) -> int:
        if not path.is_file():
            return 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if isinstance(payload, list):
            return len(payload)
        return 0

    def _count_json_file(self, path: Path, relative_path: str) -> int:
        if not path.is_file():
            return 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0

        if relative_path == self._AUDIT_REGISTRY:
            return len(payload.get("procesy") or [])
        if relative_path == self._PROVERKY_REGISTRY:
            return len(payload.get("oblasti") or [])
        if relative_path == "modulove/vysetrovani_mu/ishikawa_faktory.json":
            return self._count_ishikawa_factors(payload)
        if backup_manifest_service._is_audit_methodology(relative_path):
            return self._count_knowledge_sections(payload)
        if backup_manifest_service._is_proverky_methodology(relative_path):
            return self._count_knowledge_sections(payload)
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            return len(payload)
        return 0

    def _count_ishikawa_factors(self, payload: dict) -> int:
        total = 0
        for entry in payload.values():
            if isinstance(entry, dict):
                factors = entry.get("factors") or []
                if isinstance(factors, list):
                    total += len(factors)
        if total:
            return total
        try:
            return sum(
                len(ishikawa_factors_service.get_factors(category))
                for category in ISHIKAWA_CATEGORIES
            )
        except Exception:
            return 0

    def _count_knowledge_sections(self, payload: dict) -> int:
        sections = payload.get("sekce") or []

        def walk(nodes: list) -> int:
            total = 0
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                total += 1
                children = node.get("sekce") or []
                if isinstance(children, list):
                    total += walk(children)
            return total

        if isinstance(sections, list):
            return walk(sections)
        return 0

    def _file_mtime(self, path: Path) -> str | None:
        if not path.is_file():
            return None
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            return None


codebook_catalog_service = CodebookCatalogService()

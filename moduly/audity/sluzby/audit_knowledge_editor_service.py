"""Infrastruktura pro editaci znalostní databáze auditů (pouze uživatelská kopie JSON)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_EDITABLE_LIST_FIELDS
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_knowledge_validator import (
    PROCESY_BASENAME,
    VALID_ZAVAZNOST,
    load_json_file,
    normalize_legacy_knowledge_data,
    validate_all_catalogs,
    validate_knowledge_data,
    validate_knowledge_file,
    validate_procesy_registry_data,
)

_NEW_SECTION_EMPTY_LIST_FIELDS: tuple[str, ...] = (
    "sekce",
    "postup_kontroly",
    "kontrolni_body",
    "navodne_otazky",
    "objektivni_dukazy",
    "doporucene_rozhovory",
    "pozorovani_v_provozu",
    "typicke_neshody",
    "typicke_zavady",
    "pkz",
    "pozorovani",
    "vazby_procesy",
    "pozadavky_normy",
    "poznamky_auditora",
    "referencni_fotografie",
    "doporucene_postupy",
    "legislativa",
    "historie",
    "auditni_tvrzeni",
)

_CATALOG_DIR = "audity"
_BACKUP_SUBDIR = "backups"
_MAX_BACKUPS_PER_FILE = 10


@dataclass(frozen=True)
class LoadedKnowledgeFile:
    relative_path: str
    data: dict


@dataclass(frozen=True)
class LoadAllResult:
    files: tuple[LoadedKnowledgeFile, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class AssertionQuestionKindChange:
    """Jedna změna druhu otázky v dávce (AUDIT-METHOD-SAVE-BATCH-4A)."""

    process_id: str
    section_id: str
    assertion_id: str
    question_kind: str


class AuditKnowledgeEditorService:
    """Ukládání a validace metodiky auditora — výhradně uživatelská kopie."""

    def user_ciselniky_dir(self) -> Path:
        return storage_service.ciselniky_dir

    def user_audity_dir(self) -> Path:
        return self.user_ciselniky_dir() / _CATALOG_DIR

    def bundled_audity_dir(self) -> Path:
        return editable_catalog_service.bundled_dir() / _CATALOG_DIR

    def ensure_user_catalogs(self) -> None:
        editable_catalog_service.ensure_all(self.user_ciselniky_dir())
        audit_knowledge_service.ensure_catalogs()

    def resolve_user_path(self, relative_path: str) -> Path:
        normalized = relative_path.strip().replace("\\", "/")
        if normalized.startswith(f"{_CATALOG_DIR}/"):
            normalized = normalized[len(f"{_CATALOG_DIR}/") :]
        return self.user_audity_dir() / normalized

    def assert_user_writable_path(self, path: Path) -> None:
        resolved = path.resolve()
        user_audity = self.user_audity_dir().resolve()
        bundled_audity = self.bundled_audity_dir().resolve()

        try:
            resolved.relative_to(user_audity)
        except ValueError as exc:
            raise PermissionError(
                f"Zapisovat lze pouze do uživatelské kopie: {user_audity}"
            ) from exc

        try:
            resolved.relative_to(bundled_audity)
            raise PermissionError(
                "Bundled seed v repozitáři nelze upravovat z editoru."
            )
        except ValueError:
            pass

    def load_json_safe(self, path: Path) -> tuple[dict | None, str | None]:
        if not path.is_file():
            return None, f"Soubor neexistuje: {path.name}"
        try:
            data = load_json_file(path)
            if path.name != PROCESY_BASENAME:
                normalize_legacy_knowledge_data(data)
            return data, None
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return None, f"{path.name}: {exc}"

    def load_all_knowledge_files(self) -> LoadAllResult:
        self.ensure_user_catalogs()

        procesy_path = self.user_audity_dir() / PROCESY_BASENAME
        registry, error = self.load_json_safe(procesy_path)
        if error or registry is None:
            return LoadAllResult((), (error or "procesy.json: prázdný obsah",))

        loaded: list[LoadedKnowledgeFile] = []
        errors: list[str] = []

        processes = registry.get("procesy") or []
        if not isinstance(processes, list):
            return LoadAllResult((), ("procesy.json: pole 'procesy' musí být seznam",))

        seen: set[str] = set()
        for index, raw in enumerate(processes):
            if not isinstance(raw, dict):
                errors.append(f"procesy.json[{index}]: proces není objekt")
                continue

            soubor = str(raw.get("soubor_znalosti") or "").strip()
            if not soubor:
                process_id = str(raw.get("id") or index).strip()
                errors.append(f"procesy.json: proces '{process_id}' nemá soubor_znalosti")
                continue
            if soubor in seen:
                continue
            seen.add(soubor)

            relative_path = f"{_CATALOG_DIR}/{soubor}"
            path = self.user_audity_dir() / soubor
            data, load_error = self.load_json_safe(path)
            if load_error:
                errors.append(load_error)
                continue
            assert data is not None
            loaded.append(LoadedKnowledgeFile(relative_path=relative_path, data=data))

        return LoadAllResult(tuple(loaded), tuple(errors))

    def validate_user_catalogs(self) -> list[str]:
        self.ensure_user_catalogs()
        return validate_all_catalogs(self.user_audity_dir())

    def validate_user_file(self, relative_path: str, data: dict | None = None) -> list[str]:
        path = self.resolve_user_path(relative_path)
        if data is None:
            return validate_knowledge_file(path)
        if path.name == PROCESY_BASENAME:
            return validate_procesy_registry_data(data, source_name=path.name)
        return validate_knowledge_data(data, source_name=path.name)

    @staticmethod
    def validate_no_list_items_removed(
        before: list,
        after: list,
        *,
        path: str,
    ) -> list[str]:
        """V1: položky se nesmí mazat, pouze deaktivovat (aktivni=false)."""
        before_ids = {
            str(item.get("id") or "").strip()
            for item in before
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        after_ids = {
            str(item.get("id") or "").strip()
            for item in after
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        removed = sorted(before_ids - after_ids)
        if removed:
            return [
                f"{path}: odstranění položek není povoleno ({', '.join(removed)})"
            ]
        return []

    def backup_dir(self) -> Path:
        return self.user_audity_dir() / _BACKUP_SUBDIR

    def backup_file(self, path: Path) -> Path | None:
        if not path.is_file():
            return None

        self.assert_user_writable_path(path)
        backup_root = self.backup_dir()
        backup_root.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.name}.{timestamp}.bak"
        backup_path = backup_root / backup_name
        shutil.copy2(path, backup_path)
        self._prune_backups(path.name)
        return backup_path

    def _prune_backups(self, source_filename: str) -> None:
        backup_root = self.backup_dir()
        if not backup_root.is_dir():
            return

        pattern = f"{source_filename}.*.bak"
        backups = sorted(
            backup_root.glob(pattern),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for stale in backups[_MAX_BACKUPS_PER_FILE:]:
            try:
                stale.unlink()
            except OSError:
                pass

    def atomic_write_json(self, path: Path, data: dict) -> None:
        self.assert_user_writable_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = path.with_name(f"{path.name}.tmp")
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(path)

    def save_user_json(
        self,
        relative_path: str,
        data: dict,
        *,
        skip_validation: bool = False,
    ) -> list[str]:
        path = self.resolve_user_path(relative_path)
        self.assert_user_writable_path(path)

        if path.name != PROCESY_BASENAME:
            normalize_legacy_knowledge_data(data)

        if not skip_validation:
            errors = self.validate_user_file(relative_path, data)
            if errors:
                return errors

        if path.is_file():
            self.backup_file(path)

        try:
            self.atomic_write_json(path, data)
        except OSError as exc:
            return [f"{path.name}: zápis selhal ({exc})"]

        post_errors = self.validate_user_file(relative_path)
        if post_errors:
            backup = self._latest_backup(path.name)
            if backup is not None:
                shutil.copy2(backup, path)
            return post_errors + [
                f"{path.name}: uložený soubor neprošel validací, obnovena záloha"
            ]

        return []

    def _latest_backup(self, source_filename: str) -> Path | None:
        backup_root = self.backup_dir()
        if not backup_root.is_dir():
            return None
        backups = sorted(
            backup_root.glob(f"{source_filename}.*.bak"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return backups[0] if backups else None

    def save_section_metadata(
        self,
        process_id: str,
        section_id: str,
        metadata: dict,
        *,
        skip_legal_resolve: bool = False,
    ) -> list[str]:
        self.ensure_user_catalogs()

        process = audit_knowledge_service.get_process_by_id(process_id)
        if process is None or not process.soubor_znalosti:
            return [f"Proces '{process_id}' nebyl nalezen."]

        relative_path = f"{_CATALOG_DIR}/{process.soubor_znalosti}"
        path = self.resolve_user_path(relative_path)
        data, error = self.load_json_safe(path)
        if error or data is None:
            return [error or f"Soubor {process.soubor_znalosti} nelze načíst."]

        found = audit_knowledge_service._find_criterion_in_sections(
            data.get("sekce") or [],
            section_id,
        )
        if found is None:
            return [f"Oblast '{section_id}' v procesu '{process_id}' nebyla nalezena."]

        nazev = str(metadata.get("nazev") or "").strip()
        if not nazev:
            return ["Název oblasti ověření musí být vyplněn."]

        try:
            poradi = int(metadata.get("poradi") or 0)
        except (TypeError, ValueError):
            return ["Pořadí musí být celé číslo."]

        parent_list, index = found
        existing = parent_list[index]
        updated = deepcopy(existing)
        updated["id"] = section_id
        updated["nazev"] = nazev
        updated["popis"] = str(metadata.get("popis") or "").strip()
        updated["cil_overeni"] = str(metadata.get("cil_overeni") or "").strip()
        updated["poradi"] = poradi
        updated["aktivni"] = bool(metadata.get("aktivni", True))
        if "legal_requirement_id" in metadata:
            if skip_legal_resolve:
                legal_requirement_id = self.normalize_legal_requirement_id(
                    metadata.get("legal_requirement_id")
                )
            else:
                legal_requirement_id, link_errors = self._resolve_legal_requirement_id(
                    metadata.get("legal_requirement_id"),
                    existing_id=existing.get("legal_requirement_id"),
                )
                if link_errors:
                    return link_errors
            if legal_requirement_id is not None:
                updated["legal_requirement_id"] = legal_requirement_id
            else:
                updated.pop("legal_requirement_id", None)
        parent_list[index] = updated

        return self.save_user_json(relative_path, data)

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

    def _resolve_legal_requirement_id(
        self,
        value,
        *,
        existing_id=None,
    ) -> tuple[int | None, list[str]]:
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

    @staticmethod
    def build_new_section(
        *,
        section_id: str,
        nazev: str,
        popis: str,
        cil_overeni: str,
        poradi: int,
        aktivni: bool,
        legal_requirement_id: int | None = None,
    ) -> dict:
        section = {
            "id": section_id,
            "nazev": nazev,
            "popis": popis,
            "cil_overeni": cil_overeni,
            "poradi": poradi,
            "aktivni": aktivni,
        }
        if legal_requirement_id is not None:
            section["legal_requirement_id"] = legal_requirement_id
        for field in _NEW_SECTION_EMPTY_LIST_FIELDS:
            section[field] = []
        return section

    def suggest_next_section_poradi(self, process_id: str) -> int:
        self.ensure_user_catalogs()
        process = audit_knowledge_service.get_process_by_id(process_id)
        if process is None or not process.soubor_znalosti:
            return 10

        knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
        if knowledge is None:
            return 10

        return audit_knowledge_service.get_next_section_poradi(knowledge)

    def create_section(
        self,
        process_id: str,
        payload: dict,
    ) -> tuple[str | None, list[str]]:
        self.ensure_user_catalogs()

        process = audit_knowledge_service.get_process_by_id(process_id)
        if process is None or not process.soubor_znalosti:
            return None, [f"Proces '{process_id}' nebyl nalezen."]

        nazev = str(payload.get("nazev") or "").strip()
        if not nazev:
            return None, ["Název oblasti ověření musí být vyplněn."]

        try:
            poradi = int(payload.get("poradi"))
        except (TypeError, ValueError):
            return None, ["Pořadí musí být celé číslo."]

        relative_path = f"{_CATALOG_DIR}/{process.soubor_znalosti}"
        path = self.resolve_user_path(relative_path)
        data, error = self.load_json_safe(path)
        if error or data is None:
            return None, [error or f"Soubor {process.soubor_znalosti} nelze načíst."]

        sections = data.get("sekce")
        if sections is None:
            sections = []
        if not isinstance(sections, list):
            return None, ["Pole 'sekce' musí být seznam."]

        before_sections = deepcopy(sections)
        existing_ids = audit_knowledge_service.collect_section_ids(sections)

        section_id = str(payload.get("id") or "").strip()
        if not section_id:
            section_id = audit_knowledge_service.generate_item_id(nazev, existing_ids)
        if section_id in existing_ids:
            return None, [f"Identifikátor '{section_id}' již existuje."]

        legal_requirement_id, link_errors = self._resolve_legal_requirement_id(
            payload.get("legal_requirement_id"),
        )
        if link_errors:
            return None, link_errors

        new_section = self.build_new_section(
            section_id=section_id,
            nazev=nazev,
            popis=str(payload.get("popis") or "").strip(),
            cil_overeni=str(payload.get("cil_overeni") or "").strip(),
            poradi=poradi,
            aktivni=bool(payload.get("aktivni", True)),
            legal_requirement_id=legal_requirement_id,
        )
        sections.append(new_section)
        data["sekce"] = sections

        errors = self.save_user_json(relative_path, data)
        if errors:
            data["sekce"] = before_sections
            return None, errors

        return section_id, []

    def _restore_written_user_json_files(
        self,
        written: list[tuple[str, Path]],
        created_paths: list[Path],
    ) -> list[str]:
        """Obnoví již zapsané soubory ze ``.bak``. Chyby obnovy nesmí zmizet."""
        restore_errors: list[str] = []
        created = set(created_paths)
        for _relative_path, path in written:
            try:
                backup = self._latest_backup(path.name)
                if backup is not None:
                    shutil.copy2(backup, path)
                elif path in created:
                    path.unlink()
            except OSError as exc:
                restore_errors.append(
                    f"{path.name}: obnovení ze zálohy selhalo ({exc})"
                )
        return restore_errors

    def _save_user_json_files(
        self,
        files: tuple[tuple[str, dict], ...],
        *,
        write_error_template: str = "Zápis metadat procesu selhal ({exc})",
        post_validation_message: str = (
            "Uložená metadata procesu neprošla validací, obnovena záloha."
        ),
    ) -> list[str]:
        resolved: list[tuple[str, Path, dict]] = []
        errors: list[str] = []

        for relative_path, data in files:
            path = self.resolve_user_path(relative_path)
            file_errors = self.validate_user_file(relative_path, data)
            if file_errors:
                errors.extend(file_errors)
            resolved.append((relative_path, path, data))

        if errors:
            return errors

        for _relative_path, path, _data in resolved:
            if path.is_file():
                self.backup_file(path)

        written: list[tuple[str, Path]] = []
        created_paths: list[Path] = []
        try:
            for relative_path, path, data in resolved:
                existed_before = path.is_file()
                self.atomic_write_json(path, data)
                if not existed_before:
                    created_paths.append(path)
                written.append((relative_path, path))
        except OSError as exc:
            restore_errors = self._restore_written_user_json_files(
                written, created_paths
            )
            return [write_error_template.format(exc=exc)] + restore_errors

        post_errors: list[str] = []
        for relative_path, _path in written:
            post_errors.extend(self.validate_user_file(relative_path))

        if post_errors:
            restore_errors = self._restore_written_user_json_files(
                written, created_paths
            )
            return post_errors + [post_validation_message] + restore_errors

        return []

    def save_process_metadata(self, process_id: str, metadata: dict) -> list[str]:
        self.ensure_user_catalogs()

        process = audit_knowledge_service.get_process_by_id(process_id)
        if process is None or not process.soubor_znalosti:
            return [f"Proces '{process_id}' nebyl nalezen."]

        nazev = str(metadata.get("nazev") or "").strip()
        if not nazev:
            return ["Název procesu musí být vyplněn."]

        try:
            poradi = int(metadata.get("poradi") or 0)
        except (TypeError, ValueError):
            return ["Pořadí musí být celé číslo."]

        popis = str(metadata.get("popis") or "").strip()
        aktivni = bool(metadata.get("aktivni", True))
        ucel_procesu = str(metadata.get("ucel_procesu") or "").strip()
        proc_je_dulezity = str(metadata.get("proc_je_dulezity") or "").strip()
        ocekavany_vystup = str(metadata.get("ocekavany_vystup") or "").strip()

        procesy_relative = f"{_CATALOG_DIR}/{PROCESY_BASENAME}"
        knowledge_relative = f"{_CATALOG_DIR}/{process.soubor_znalosti}"

        procesy_path = self.resolve_user_path(procesy_relative)
        knowledge_path = self.resolve_user_path(knowledge_relative)

        procesy_data, procesy_error = self.load_json_safe(procesy_path)
        knowledge_data, knowledge_error = self.load_json_safe(knowledge_path)
        if procesy_error or procesy_data is None:
            return [procesy_error or "procesy.json nelze načíst."]
        if knowledge_error or knowledge_data is None:
            return [knowledge_error or f"Soubor {process.soubor_znalosti} nelze načíst."]

        processes = procesy_data.get("procesy") or []
        registry_entry = None
        for index, raw in enumerate(processes):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("id") or "").strip() != process_id:
                continue
            registry_entry = deepcopy(raw)
            processes[index] = registry_entry
            break

        if registry_entry is None:
            return [f"Proces '{process_id}' nebyl nalezen v procesy.json."]

        registry_entry["id"] = process_id
        registry_entry["nazev"] = nazev
        registry_entry["popis"] = popis
        registry_entry["poradi"] = poradi
        registry_entry["aktivni"] = aktivni

        knowledge_data["id"] = process_id
        knowledge_data["nazev"] = nazev
        knowledge_data["popis"] = popis
        knowledge_data["poradi"] = poradi
        knowledge_data["aktivni"] = aktivni
        knowledge_data["ucel_procesu"] = ucel_procesu
        knowledge_data["proc_je_dulezity"] = proc_je_dulezity
        knowledge_data["ocekavany_vystup"] = ocekavany_vystup

        return self._save_user_json_files(
            (
                (procesy_relative, procesy_data),
                (knowledge_relative, knowledge_data),
            )
        )

    def collect_process_ids(self) -> set[str]:
        self.ensure_user_catalogs()
        procesy_path = self.user_audity_dir() / PROCESY_BASENAME
        data, error = self.load_json_safe(procesy_path)
        if error or data is None:
            return set()

        collected: set[str] = set()
        for raw in data.get("procesy") or []:
            if not isinstance(raw, dict):
                continue
            process_id = str(raw.get("id") or "").strip()
            if process_id:
                collected.add(process_id)
        return collected

    def suggest_next_process_poradi(self) -> int:
        self.ensure_user_catalogs()
        procesy_path = self.user_audity_dir() / PROCESY_BASENAME
        data, error = self.load_json_safe(procesy_path)
        if error or data is None:
            return 10

        processes = data.get("procesy") or []
        if not isinstance(processes, list) or not processes:
            return 10

        max_poradi = 0
        for raw in processes:
            if not isinstance(raw, dict):
                continue
            try:
                max_poradi = max(max_poradi, int(raw.get("poradi") or 0))
            except (TypeError, ValueError):
                continue
        return max_poradi + 10 if max_poradi else 10

    @staticmethod
    def build_new_process_knowledge(
        *,
        process_id: str,
        nazev: str,
        popis: str,
        ucel_procesu: str,
        proc_je_dulezity: str,
        ocekavany_vystup: str,
        poradi: int,
        aktivni: bool,
    ) -> dict:
        return {
            "verze": 1,
            "id": process_id,
            "nazev": nazev,
            "popis": popis,
            "ucel_procesu": ucel_procesu,
            "proc_je_dulezity": proc_je_dulezity,
            "ocekavany_vystup": ocekavany_vystup,
            "poradi": poradi,
            "aktivni": aktivni,
            "vazby_procesy": [],
            "pozadavky_norem": [],
            "sekce": [],
            "zavaznost_seed_sync": 1,
        }

    def create_process(self, payload: dict) -> tuple[str | None, list[str]]:
        self.ensure_user_catalogs()

        nazev = str(payload.get("nazev") or "").strip()
        if not nazev:
            return None, ["Název procesu musí být vyplněn."]

        try:
            poradi = int(payload.get("poradi"))
        except (TypeError, ValueError):
            return None, ["Pořadí musí být celé číslo."]

        popis = str(payload.get("popis") or "").strip()
        ucel_procesu = str(payload.get("ucel_procesu") or "").strip()
        proc_je_dulezity = str(payload.get("proc_je_dulezity") or "").strip()
        ocekavany_vystup = str(payload.get("ocekavany_vystup") or "").strip()
        aktivni = bool(payload.get("aktivni", True))

        procesy_relative = f"{_CATALOG_DIR}/{PROCESY_BASENAME}"
        procesy_path = self.resolve_user_path(procesy_relative)
        procesy_data, procesy_error = self.load_json_safe(procesy_path)
        if procesy_error or procesy_data is None:
            return None, [procesy_error or "procesy.json nelze načíst."]

        processes = procesy_data.get("procesy")
        if processes is None:
            processes = []
        if not isinstance(processes, list):
            return None, ["Pole 'procesy' musí být seznam."]

        before_processes = deepcopy(processes)
        existing_ids = self.collect_process_ids()

        process_id = str(payload.get("id") or "").strip()
        if not process_id:
            process_id = audit_knowledge_service.generate_item_id(nazev, existing_ids)
        if process_id in existing_ids:
            return None, [f"Identifikátor '{process_id}' již existuje."]

        knowledge_filename = f"{process_id}.json"
        knowledge_relative = f"{_CATALOG_DIR}/{knowledge_filename}"
        knowledge_path = self.resolve_user_path(knowledge_relative)
        if knowledge_path.is_file():
            return None, [f"Soubor '{knowledge_filename}' již existuje."]

        registry_entry = {
            "id": process_id,
            "nazev": nazev,
            "popis": popis,
            "ucel_procesu": ucel_procesu,
            "poradi": poradi,
            "aktivni": aktivni,
            "soubor_znalosti": knowledge_filename,
        }
        knowledge_data = self.build_new_process_knowledge(
            process_id=process_id,
            nazev=nazev,
            popis=popis,
            ucel_procesu=ucel_procesu,
            proc_je_dulezity=proc_je_dulezity,
            ocekavany_vystup=ocekavany_vystup,
            poradi=poradi,
            aktivni=aktivni,
        )

        processes.append(registry_entry)
        procesy_data["procesy"] = processes

        errors = self._save_user_json_files(
            (
                (procesy_relative, procesy_data),
                (knowledge_relative, knowledge_data),
            )
        )
        if errors:
            procesy_data["procesy"] = before_processes
            return None, errors

        return process_id, []

    def _resolve_section_context(
        self,
        process_id: str,
        section_id: str,
    ) -> tuple[str, dict, list, int, dict] | tuple[None, list[str]]:
        self.ensure_user_catalogs()

        process = audit_knowledge_service.get_process_by_id(process_id)
        if process is None or not process.soubor_znalosti:
            return None, [f"Proces '{process_id}' nebyl nalezen."]

        relative_path = f"{_CATALOG_DIR}/{process.soubor_znalosti}"
        data, error = self.load_json_safe(self.resolve_user_path(relative_path))
        if error or data is None:
            return None, [error or f"Soubor {process.soubor_znalosti} nelze načíst."]

        found = audit_knowledge_service._find_criterion_in_sections(
            data.get("sekce") or [],
            section_id,
        )
        if found is None:
            return None, [f"Oblast '{section_id}' v procesu '{process_id}' nebyla nalezena."]

        parent_list, index = found
        section = parent_list[index]
        return (relative_path, data, parent_list, index, section), []

    @staticmethod
    def _validate_assertion_payload(payload: dict, *, require_id: bool) -> tuple[dict | None, list[str]]:
        from moduly.audity.constants import (
            AUDIT_QUESTION_KIND_OPERATION,
            AUDIT_QUESTION_KIND_SYSTEM,
            KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED,
        )
        from moduly.audity.sluzby.audit_question_kind import (
            AuditQuestionKindError,
            interpret_question_kind,
            validate_question_kind,
        )

        item_id = str(payload.get("id") or "").strip()
        if require_id and not item_id:
            return None, ["Chybí identifikátor auditního tvrzení."]

        text = str(payload.get("text") or payload.get("nazev") or "").strip()
        if not text:
            return None, ["Text auditního tvrzení musí být vyplněn."]

        try:
            poradi = int(payload.get("poradi"))
        except (TypeError, ValueError):
            return None, ["Pořadí musí být celé číslo."]

        zavaznost = str(payload.get("zavaznost") or "").strip().lower()
        if not zavaznost:
            return None, ["Závažnost musí být vyplněna."]
        if zavaznost not in VALID_ZAVAZNOST:
            return None, [f"Neplatná závažnost '{zavaznost}'."]

        verification_type = audit_knowledge_service.normalize_verification_type(
            payload.get("verification_type")
        )

        normalized = {
            "text": text,
            "nazev": text,
            "popis": str(payload.get("popis") or "").strip(),
            "poradi": poradi,
            "aktivni": bool(payload.get("aktivni", True)),
            "zavaznost": zavaznost,
            "verification_type": verification_type,
        }
        if item_id:
            normalized["id"] = item_id

        # AUDIT-METHOD-V2b: druh jen při explicitním uložení z dialogu / nové otázky.
        # Částečné update (např. typ ověření) key nevyžadují — nezařazené zůstávají.
        if "question_kind" in payload:
            try:
                kind = validate_question_kind(
                    payload.get("question_kind"),
                    allow_legacy=False,
                    allow_missing=True,
                )
            except AuditQuestionKindError as exc:
                return None, [str(exc)]
            kind = interpret_question_kind(payload.get("question_kind"))
            if kind not in (AUDIT_QUESTION_KIND_SYSTEM, AUDIT_QUESTION_KIND_OPERATION):
                return None, [KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED]
            normalized["question_kind"] = kind

        return normalized, []

    def _save_section_assertions(
        self,
        *,
        relative_path: str,
        data: dict,
        section: dict,
        before_assertions: list,
        after_assertions: list,
        require_pre_v2_backup: bool = False,
    ) -> list[str]:
        removal_errors = self.validate_no_list_items_removed(
            before_assertions,
            after_assertions,
            path=f"{section.get('id')}.auditni_tvrzeni",
        )
        if removal_errors:
            return removal_errors

        if require_pre_v2_backup:
            from moduly.audity.sluzby.audit_method_v2_backup_service import (
                AuditMethodV2BackupError,
                ensure_pre_v2_backup,
            )

            try:
                ensure_pre_v2_backup()
            except AuditMethodV2BackupError as exc:
                return [str(exc)]

        section["auditni_tvrzeni"] = after_assertions
        return self.save_user_json(relative_path, data)

    def save_assertion(
        self,
        process_id: str,
        section_id: str,
        payload: dict,
        *,
        assertion_id: str | None = None,
    ) -> list[str]:
        context, errors = self._resolve_section_context(process_id, section_id)
        if errors:
            return errors
        assert context is not None

        relative_path, data, _parent_list, _index, section = context
        before_assertions = deepcopy(section.get("auditni_tvrzeni") or [])
        after_assertions = deepcopy(before_assertions)
        existing_ids = {
            str(item.get("id") or "").strip()
            for item in after_assertions
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }

        normalized, validation_errors = self._validate_assertion_payload(
            {**payload, "id": assertion_id or payload.get("id")},
            require_id=assertion_id is not None,
        )
        if validation_errors:
            return validation_errors
        assert normalized is not None

        if assertion_id:
            target_id = assertion_id.strip()
            if not target_id:
                return ["Chybí identifikátor auditního tvrzení."]
            if target_id not in existing_ids:
                return [f"Auditní tvrzení '{target_id}' nebylo nalezeno."]

            updated = False
            for index, item in enumerate(after_assertions):
                if not isinstance(item, dict):
                    continue
                if str(item.get("id") or "").strip() != target_id:
                    continue
                # Zachovej neznámá metadata; přepiš jen validovaná pole payloadu.
                after_assertions[index] = {
                    **item,
                    **normalized,
                    "id": target_id,
                }
                updated = True
                break
            if not updated:
                return [f"Auditní tvrzení '{target_id}' nebylo nalezeno."]
        else:
            new_id = audit_knowledge_service.generate_item_id(
                normalized["text"],
                existing_ids,
            )
            if new_id in existing_ids:
                return [f"Identifikátor '{new_id}' již existuje."]
            after_assertions.append({**normalized, "id": new_id})

        return self._save_section_assertions(
            relative_path=relative_path,
            data=data,
            section=section,
            before_assertions=before_assertions,
            after_assertions=after_assertions,
            require_pre_v2_backup=True,
        )

    def set_assertion_question_kind(
        self,
        process_id: str,
        section_id: str,
        assertion_id: str,
        question_kind: str,
    ) -> list[str]:
        """Zapíše ``question_kind`` (včetně Nezařazeno) — jedna změna přes dávku."""
        return self.set_assertion_question_kinds_batch(
            (
                AssertionQuestionKindChange(
                    process_id=process_id,
                    section_id=section_id,
                    assertion_id=assertion_id,
                    question_kind=question_kind,
                ),
            )
        )

    def set_assertion_question_kinds_batch(
        self,
        changes: Sequence[AssertionQuestionKindChange],
    ) -> list[str]:
        """Zapíše dávku druhů otázek — každý knowledge JSON nejvýše jednou."""
        normalized, errors = self._normalize_question_kind_changes(changes)
        if errors:
            return errors
        if not normalized:
            return []

        self.ensure_user_catalogs()

        processes_by_id = {
            process.id: process
            for process in audit_knowledge_service.get_processes(
                include_inactive=True,
                ensure=False,
            )
        }

        grouped: dict[str, list[AssertionQuestionKindChange]] = {}
        load_errors: list[str] = []
        for change in normalized:
            process = processes_by_id.get(change.process_id)
            if process is None or not process.soubor_znalosti:
                load_errors.append(f"Proces '{change.process_id}' nebyl nalezen.")
                continue
            relative_path = f"{_CATALOG_DIR}/{process.soubor_znalosti}"
            grouped.setdefault(relative_path, []).append(change)
        if load_errors:
            return load_errors

        originals: dict[str, dict] = {}
        for relative_path in grouped:
            path = self.resolve_user_path(relative_path)
            data, error = self.load_json_safe(path)
            if error or data is None:
                load_errors.append(
                    error or f"Soubor {path.name} nelze načíst."
                )
                continue
            originals[relative_path] = data
        if load_errors:
            return load_errors

        working_files: dict[str, dict] = {
            relative_path: deepcopy(data)
            for relative_path, data in originals.items()
        }
        mutated_paths: list[str] = []
        apply_errors: list[str] = []
        for relative_path, file_changes in grouped.items():
            working = working_files[relative_path]
            mutated, file_errors = self._apply_question_kind_changes_to_document(
                working,
                file_changes,
            )
            if file_errors:
                apply_errors.extend(file_errors)
            elif mutated:
                mutated_paths.append(relative_path)
        if apply_errors:
            return apply_errors
        if not mutated_paths:
            return []

        pre_errors = self._ensure_pre_v2_backup_for_kind_batch()
        if pre_errors:
            return pre_errors

        files = tuple(
            (relative_path, working_files[relative_path])
            for relative_path in mutated_paths
        )
        return self._save_user_json_files(
            files,
            write_error_template="Zápis knowledge souboru selhal ({exc})",
            post_validation_message=(
                "Uložený knowledge soubor neprošel validací, obnovena záloha."
            ),
        )

    def _normalize_question_kind_changes(
        self,
        changes: Sequence[AssertionQuestionKindChange],
    ) -> tuple[list[AssertionQuestionKindChange], list[str]]:
        from moduly.audity.constants import (
            AUDIT_QUESTION_KIND_OPERATION,
            AUDIT_QUESTION_KIND_SYSTEM,
            AUDIT_QUESTION_KIND_UNCLASSIFIED,
        )
        from moduly.audity.sluzby.audit_question_kind import (
            AuditQuestionKindError,
            interpret_question_kind,
            validate_question_kind,
        )

        errors: list[str] = []
        by_identity: dict[tuple[str, str, str], AssertionQuestionKindChange] = {}
        for raw in changes:
            process_id = str(raw.process_id or "").strip()
            section_id = str(raw.section_id or "").strip()
            assertion_id = str(raw.assertion_id or "").strip()
            if not process_id:
                errors.append("Chybí identifikátor procesu.")
                continue
            if not section_id:
                errors.append("Chybí identifikátor oblasti ověření.")
                continue
            if not assertion_id:
                errors.append("Chybí identifikátor auditního tvrzení.")
                continue
            try:
                kind = validate_question_kind(
                    raw.question_kind,
                    allow_legacy=False,
                    allow_missing=True,
                )
            except AuditQuestionKindError as exc:
                errors.append(str(exc))
                continue
            kind = interpret_question_kind(raw.question_kind)
            if kind not in (
                AUDIT_QUESTION_KIND_SYSTEM,
                AUDIT_QUESTION_KIND_OPERATION,
                AUDIT_QUESTION_KIND_UNCLASSIFIED,
            ):
                errors.append(
                    f"Neplatný druh otázky pro editor: {raw.question_kind!r}"
                )
                continue
            identity = (process_id, section_id, assertion_id)
            normalized = AssertionQuestionKindChange(
                process_id=process_id,
                section_id=section_id,
                assertion_id=assertion_id,
                question_kind=kind,
            )
            existing = by_identity.get(identity)
            if existing is None:
                by_identity[identity] = normalized
                continue
            if existing.question_kind != kind:
                errors.append(
                    "Konfliktní dávka: tvrzení "
                    f"'{process_id}/{section_id}/{assertion_id}' "
                    "má různé cílové druhy otázky."
                )
        if errors:
            return [], errors
        return list(by_identity.values()), []

    def _apply_question_kind_changes_to_document(
        self,
        working: dict,
        file_changes: Sequence[AssertionQuestionKindChange],
    ) -> tuple[bool, list[str]]:
        from moduly.audity.sluzby.audit_question_kind import interpret_question_kind

        mutated = False
        errors: list[str] = []
        by_section: dict[str, list[AssertionQuestionKindChange]] = {}
        for change in file_changes:
            by_section.setdefault(change.section_id, []).append(change)

        for section_id, section_changes in by_section.items():
            process_id = section_changes[0].process_id
            found = audit_knowledge_service._find_criterion_in_sections(
                working.get("sekce") or [],
                section_id,
            )
            if found is None:
                errors.append(
                    f"Oblast '{section_id}' v procesu '{process_id}' nebyla nalezena."
                )
                continue
            parent_list, index = found
            section = parent_list[index]
            before_assertions = list(section.get("auditni_tvrzeni") or [])
            after_assertions = list(before_assertions)
            for change in section_changes:
                matches = [
                    item_index
                    for item_index, item in enumerate(after_assertions)
                    if isinstance(item, dict)
                    and str(item.get("id") or "").strip() == change.assertion_id
                ]
                if not matches:
                    errors.append(
                        f"Auditní tvrzení '{change.assertion_id}' nebylo nalezeno."
                    )
                    continue
                if len(matches) > 1:
                    errors.append(
                        f"Auditní tvrzení '{change.assertion_id}' v oblasti "
                        f"'{section_id}' není jednoznačné."
                    )
                    continue
                item_index = matches[0]
                item = after_assertions[item_index]
                current = interpret_question_kind(item.get("question_kind"))
                if current == change.question_kind:
                    continue
                after_assertions[item_index] = {
                    **item,
                    "question_kind": change.question_kind,
                }
                mutated = True
            if errors:
                continue
            removal_errors = self.validate_no_list_items_removed(
                before_assertions,
                after_assertions,
                path=f"{section.get('id')}.auditni_tvrzeni",
            )
            if removal_errors:
                errors.extend(removal_errors)
                continue
            section["auditni_tvrzeni"] = after_assertions
        return mutated, errors

    def _ensure_pre_v2_backup_for_kind_batch(self) -> list[str]:
        from moduly.audity.sluzby.audit_method_v2_backup_service import (
            AuditMethodV2BackupError,
            ensure_pre_v2_backup,
        )

        try:
            ensure_pre_v2_backup()
        except AuditMethodV2BackupError as exc:
            return [str(exc)]
        return []

    def set_assertion_active(
        self,
        process_id: str,
        section_id: str,
        assertion_id: str,
        *,
        aktivni: bool,
    ) -> list[str]:
        context, errors = self._resolve_section_context(process_id, section_id)
        if errors:
            return errors
        assert context is not None

        relative_path, data, _parent_list, _index, section = context
        before_assertions = deepcopy(section.get("auditni_tvrzeni") or [])
        after_assertions = deepcopy(before_assertions)
        target_id = assertion_id.strip()
        if not target_id:
            return ["Chybí identifikátor auditního tvrzení."]

        updated = False
        for index, item in enumerate(after_assertions):
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "").strip() != target_id:
                continue
            updated_item = deepcopy(item)
            updated_item["aktivni"] = aktivni
            after_assertions[index] = updated_item
            updated = True
            break

        if not updated:
            return [f"Auditní tvrzení '{target_id}' nebylo nalezeno."]

        return self._save_section_assertions(
            relative_path=relative_path,
            data=data,
            section=section,
            before_assertions=before_assertions,
            after_assertions=after_assertions,
        )

    @staticmethod
    def _validate_described_list_item_payload(
        payload: dict,
        *,
        require_id: bool,
    ) -> tuple[dict | None, list[str]]:
        item_id = str(payload.get("id") or "").strip()
        if require_id and not item_id:
            return None, ["Chybí identifikátor položky."]

        nazev = str(payload.get("nazev") or payload.get("text") or "").strip()
        if not nazev:
            return None, ["Název kroku musí být vyplněn."]

        try:
            poradi = int(payload.get("poradi"))
        except (TypeError, ValueError):
            return None, ["Pořadí musí být celé číslo."]

        normalized = {
            "nazev": nazev,
            "popis": str(payload.get("popis") or "").strip(),
            "poradi": poradi,
            "aktivni": bool(payload.get("aktivni", True)),
        }
        if item_id:
            normalized["id"] = item_id
        return normalized, []

    @staticmethod
    def _validate_reference_photo_payload(
        payload: dict,
        *,
        require_id: bool,
    ) -> tuple[dict | None, list[str]]:
        item_id = str(payload.get("id") or "").strip()
        if require_id and not item_id:
            return None, ["Chybí identifikátor položky."]

        nazev = str(payload.get("nazev") or "").strip()
        if not nazev:
            return None, ["Název referenční fotografie musí být vyplněn."]

        try:
            poradi = int(payload.get("poradi"))
        except (TypeError, ValueError):
            return None, ["Pořadí musí být celé číslo."]

        aktivni = bool(payload.get("aktivni", True))
        soubor = str(payload.get("soubor") or "").strip()
        if aktivni and not soubor:
            return None, ["Soubor referenční fotografie musí být vyplněn u aktivní položky."]

        normalized = {
            "nazev": nazev,
            "popis": str(payload.get("popis") or "").strip(),
            "soubor": soubor,
            "poradi": poradi,
            "aktivni": aktivni,
        }
        control_point_id = payload.get("control_point_id")
        if control_point_id is not None and str(control_point_id).strip():
            normalized["control_point_id"] = str(control_point_id).strip()
        if item_id:
            normalized["id"] = item_id
        return normalized, []

    @staticmethod
    def _validate_section_list_payload(
        field_name: str,
        payload: dict,
        *,
        require_id: bool,
    ) -> tuple[dict | None, list[str]]:
        if field_name == "postup_kontroly":
            return AuditKnowledgeEditorService._validate_described_list_item_payload(
                payload,
                require_id=require_id,
            )
        if field_name == "referencni_fotografie":
            return AuditKnowledgeEditorService._validate_reference_photo_payload(
                payload,
                require_id=require_id,
            )
        return AuditKnowledgeEditorService._validate_list_item_payload(
            payload,
            require_id=require_id,
        )

    @staticmethod
    def _validate_list_item_payload(payload: dict, *, require_id: bool) -> tuple[dict | None, list[str]]:
        item_id = str(payload.get("id") or "").strip()
        if require_id and not item_id:
            return None, ["Chybí identifikátor položky."]

        text = str(payload.get("nazev") or payload.get("text") or "").strip()
        if not text:
            return None, ["Text položky musí být vyplněn."]

        try:
            poradi = int(payload.get("poradi"))
        except (TypeError, ValueError):
            return None, ["Pořadí musí být celé číslo."]

        normalized = {
            "nazev": text,
            "poradi": poradi,
            "aktivni": bool(payload.get("aktivni", True)),
        }
        popis = str(payload.get("popis") or "").strip()
        if popis:
            normalized["popis"] = popis
        if item_id:
            normalized["id"] = item_id
        return normalized, []

    def _save_section_list(
        self,
        *,
        relative_path: str,
        data: dict,
        section: dict,
        field_name: str,
        before_items: list,
        after_items: list,
    ) -> list[str]:
        removal_errors = self.validate_no_list_items_removed(
            before_items,
            after_items,
            path=f"{section.get('id')}.{field_name}",
        )
        if removal_errors:
            return removal_errors

        section[field_name] = after_items
        return self.save_user_json(relative_path, data)

    def save_section_list_item(
        self,
        process_id: str,
        section_id: str,
        field_name: str,
        payload: dict,
        *,
        item_id: str | None = None,
    ) -> list[str]:
        if field_name not in KNOWLEDGE_EDITOR_SECTION_EDITABLE_LIST_FIELDS:
            return [f"Pole '{field_name}' nelze editovat v tomto editoru."]

        context, errors = self._resolve_section_context(process_id, section_id)
        if errors:
            return errors
        assert context is not None

        relative_path, data, _parent_list, _index, section = context
        before_items = deepcopy(section.get(field_name) or [])
        after_items = deepcopy(before_items)
        existing_ids = {
            str(item.get("id") or "").strip()
            for item in after_items
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }

        normalized, validation_errors = self._validate_section_list_payload(
            field_name,
            {**payload, "id": item_id or payload.get("id")},
            require_id=item_id is not None,
        )
        if validation_errors:
            return validation_errors
        assert normalized is not None

        if item_id:
            target_id = item_id.strip()
            if not target_id:
                return ["Chybí identifikátor položky."]
            if target_id not in existing_ids:
                return [f"Položka '{target_id}' nebyla nalezena."]

            updated = False
            for index, item in enumerate(after_items):
                if not isinstance(item, dict):
                    continue
                if str(item.get("id") or "").strip() != target_id:
                    continue
                merged = deepcopy(item)
                merged.update(normalized)
                merged["id"] = target_id
                after_items[index] = merged
                updated = True
                break
            if not updated:
                return [f"Položka '{target_id}' nebyla nalezena."]
        else:
            new_id = audit_knowledge_service.generate_item_id(
                normalized["nazev"],
                existing_ids,
            )
            if new_id in existing_ids:
                return [f"Identifikátor '{new_id}' již existuje."]
            after_items.append({**normalized, "id": new_id})

        return self._save_section_list(
            relative_path=relative_path,
            data=data,
            section=section,
            field_name=field_name,
            before_items=before_items,
            after_items=after_items,
        )

    def set_section_list_item_active(
        self,
        process_id: str,
        section_id: str,
        field_name: str,
        item_id: str,
        *,
        aktivni: bool,
    ) -> list[str]:
        if field_name not in KNOWLEDGE_EDITOR_SECTION_EDITABLE_LIST_FIELDS:
            return [f"Pole '{field_name}' nelze editovat v tomto editoru."]

        context, errors = self._resolve_section_context(process_id, section_id)
        if errors:
            return errors
        assert context is not None

        relative_path, data, _parent_list, _index, section = context
        before_items = deepcopy(section.get(field_name) or [])
        after_items = deepcopy(before_items)
        target_id = item_id.strip()
        if not target_id:
            return ["Chybí identifikátor položky."]

        updated = False
        for index, item in enumerate(after_items):
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "").strip() != target_id:
                continue
            updated_item = deepcopy(item)
            updated_item["aktivni"] = aktivni
            if field_name == "referencni_fotografie" and aktivni:
                soubor = str(updated_item.get("soubor") or "").strip()
                if not soubor:
                    return [
                        f"Referenční fotografie '{target_id}' nelze aktivovat bez souboru."
                    ]
            after_items[index] = updated_item
            updated = True
            break

        if not updated:
            return [f"Položka '{target_id}' nebyla nalezena."]

        return self._save_section_list(
            relative_path=relative_path,
            data=data,
            section=section,
            field_name=field_name,
            before_items=before_items,
            after_items=after_items,
        )


audit_knowledge_editor_service = AuditKnowledgeEditorService()

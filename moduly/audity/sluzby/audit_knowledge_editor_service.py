"""Infrastruktura pro editaci znalostní databáze auditů (pouze uživatelská kopie JSON)."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_LIST_FIELDS
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_knowledge_validator import (
    PROCESY_BASENAME,
    VALID_ZAVAZNOST,
    load_json_file,
    validate_all_catalogs,
    validate_knowledge_data,
    validate_knowledge_file,
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
            return load_json_file(path), None
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
        parent_list[index] = updated

        return self.save_user_json(relative_path, data)

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

        normalized = {
            "text": text,
            "nazev": text,
            "popis": str(payload.get("popis") or "").strip(),
            "poradi": poradi,
            "aktivni": bool(payload.get("aktivni", True)),
            "zavaznost": zavaznost,
        }
        if item_id:
            normalized["id"] = item_id
        return normalized, []

    def _save_section_assertions(
        self,
        *,
        relative_path: str,
        data: dict,
        section: dict,
        before_assertions: list,
        after_assertions: list,
    ) -> list[str]:
        removal_errors = self.validate_no_list_items_removed(
            before_assertions,
            after_assertions,
            path=f"{section.get('id')}.auditni_tvrzeni",
        )
        if removal_errors:
            return removal_errors

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
                after_assertions[index] = {
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
        )

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
        if field_name not in KNOWLEDGE_EDITOR_SECTION_LIST_FIELDS:
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

        normalized, validation_errors = self._validate_list_item_payload(
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
        if field_name not in KNOWLEDGE_EDITOR_SECTION_LIST_FIELDS:
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

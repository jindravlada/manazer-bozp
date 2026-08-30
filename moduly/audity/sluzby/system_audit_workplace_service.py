"""Globální nastavení systémového provozu pro audity (AUDIT-METHOD-V2a).

Hodnota ``system_audit_workplace_id`` se používá pouze při sestavení snapshotu
nového auditu v2. Změna nastavení neovlivní již snapshotované audity.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.services.storage_service import storage_service
from moduly.audity.constants import (
    SYSTEM_AUDIT_WORKPLACE_SETTING_KEY,
    SYSTEM_AUDIT_WORKPLACE_SETTINGS_FILE,
)
from moduly.nastaveni.modely.workplace import Workplace
from moduly.nastaveni.sluzby.settings_service import settings_service


class SystemAuditWorkplaceError(ValueError):
    """Chyba načtení / uložení systémového provozu."""


class SystemAuditWorkplaceService:
    """Perzistence globálního systémového provozu (bez finálního UI)."""

    def settings_path(self) -> Path:
        return storage_service.config_dir / SYSTEM_AUDIT_WORKPLACE_SETTINGS_FILE

    def _load(self) -> dict:
        path = self.settings_path()
        if not path.is_file():
            return {}
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, payload: dict) -> None:
        storage_service.ensure_structure()
        path = self.settings_path()
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def get_system_audit_workplace_id(self) -> int | None:
        raw = self._load().get(SYSTEM_AUDIT_WORKPLACE_SETTING_KEY)
        if raw is None or raw == "":
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise SystemAuditWorkplaceError(
                f"Neplatná hodnota {SYSTEM_AUDIT_WORKPLACE_SETTING_KEY}: {raw!r}"
            ) from exc
        if value <= 0:
            return None
        return value

    def get_system_audit_workplace(self) -> Workplace | None:
        workplace_id = self.get_system_audit_workplace_id()
        if workplace_id is None:
            return None
        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            raise SystemAuditWorkplaceError(
                f"Systémový provoz (id={workplace_id}) neexistuje."
            )
        return workplace

    def require_system_audit_workplace_id(self) -> int:
        """Vrátí ID systémového provozu nebo vyvolá jasnou chybu."""
        from moduly.audity.constants import (
            AUDIT_START_MISSING_SYSTEM_WORKPLACE,
            SYSTEM_AUDIT_WORKPLACE_INVALID_MESSAGE,
        )
        from moduly.audity.sluzby.audit_auditable_workplace_service import (
            is_auditable_workplace,
        )

        workplace_id = self.get_system_audit_workplace_id()
        if workplace_id is None:
            raise SystemAuditWorkplaceError(AUDIT_START_MISSING_SYSTEM_WORKPLACE)
        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            raise SystemAuditWorkplaceError(AUDIT_START_MISSING_SYSTEM_WORKPLACE)
        if not is_auditable_workplace(workplace):
            raise SystemAuditWorkplaceError(SYSTEM_AUDIT_WORKPLACE_INVALID_MESSAGE)
        return int(workplace.id)

    def is_saved_system_workplace_valid(self) -> bool:
        """True, pokud je uložené ID auditovatelný provoz (nebo není nastaveno)."""
        from moduly.audity.sluzby.audit_auditable_workplace_service import (
            is_auditable_workplace,
        )

        workplace_id = self.get_system_audit_workplace_id()
        if workplace_id is None:
            return True
        workplace = settings_service.get_workplace_by_id(workplace_id)
        return is_auditable_workplace(workplace)

    def set_system_audit_workplace_id(self, workplace_id: int | None) -> int | None:
        """
        Uloží odkaz na existující Workplace, nebo vymaže nastavení (None).

        Neukládá název provozu natvrdo — pouze ID.
        Před první v2 změnou vytvoří jednorázovou zálohu.
        """
        from moduly.audity.constants import AUDITABLE_WORKPLACE_REQUIRED_MESSAGE
        from moduly.audity.sluzby.audit_auditable_workplace_service import (
            is_auditable_workplace,
        )
        from moduly.audity.sluzby.audit_method_v2_backup_service import (
            AuditMethodV2BackupError,
            ensure_pre_v2_backup,
        )

        current = self.get_system_audit_workplace_id()
        if workplace_id is None or workplace_id == 0:
            if current is None:
                return None
            try:
                ensure_pre_v2_backup()
            except AuditMethodV2BackupError:
                raise
            payload = self._load()
            payload[SYSTEM_AUDIT_WORKPLACE_SETTING_KEY] = None
            self._save(payload)
            return None

        try:
            workplace_id_int = int(workplace_id)
        except (TypeError, ValueError) as exc:
            raise SystemAuditWorkplaceError(
                f"Neplatné ID systémového provozu: {workplace_id!r}"
            ) from exc
        if workplace_id_int <= 0:
            raise SystemAuditWorkplaceError(
                f"Neplatné ID systémového provozu: {workplace_id!r}"
            )

        workplace = settings_service.get_workplace_by_id(workplace_id_int)
        if workplace is None:
            raise SystemAuditWorkplaceError(
                f"Systémový provoz (id={workplace_id_int}) neexistuje."
            )
        if not is_auditable_workplace(workplace):
            raise SystemAuditWorkplaceError(AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)

        if current == int(workplace.id):
            return int(workplace.id)

        try:
            ensure_pre_v2_backup()
        except AuditMethodV2BackupError:
            raise

        payload = self._load()
        payload[SYSTEM_AUDIT_WORKPLACE_SETTING_KEY] = int(workplace.id)
        self._save(payload)
        return int(workplace.id)

    def persist_saved_system_workplace_id(self, workplace_id: int | None) -> int | None:
        """Zapíše ID systémového provozu bez DB lookupu.

        Validace existence a auditovatelnosti musí proběhnout předem
        (GUI vlákno). Worker tak nepotřebuje SQLAlchemy session z editoru.
        Před první v2 změnou vytvoří jednorázovou zálohu.
        """
        from moduly.audity.sluzby.audit_method_v2_backup_service import (
            AuditMethodV2BackupError,
            ensure_pre_v2_backup,
        )

        current = self.get_system_audit_workplace_id()
        if workplace_id is None or workplace_id == 0:
            normalized: int | None = None
        else:
            try:
                normalized = int(workplace_id)
            except (TypeError, ValueError) as exc:
                raise SystemAuditWorkplaceError(
                    f"Neplatné ID systémového provozu: {workplace_id!r}"
                ) from exc
            if normalized <= 0:
                raise SystemAuditWorkplaceError(
                    f"Neplatné ID systémového provozu: {workplace_id!r}"
                )

        if current == normalized:
            return current

        try:
            ensure_pre_v2_backup()
        except AuditMethodV2BackupError:
            raise

        payload = self._load()
        payload[SYSTEM_AUDIT_WORKPLACE_SETTING_KEY] = normalized
        self._save(payload)
        return normalized


system_audit_workplace_service = SystemAuditWorkplaceService()

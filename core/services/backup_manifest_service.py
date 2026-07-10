import json
import zipfile
from pathlib import Path

from sqlalchemy import func, select

from core.database.session import get_session
from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from moduly.audity.modely.audit import Audit
from moduly.kniha_urazu.modely.accident import Accident
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.ukoly.modely.task import Task

_AUDIT_CATALOG_FILES = frozenset({"procesy.json"})
_PROVERKY_CATALOG_FILES = frozenset({"oblasti.json", "prvni_pomoc.json"})


class BackupManifestService:
    """Sestavení a ověření manifestu kompletní zálohy."""

    DATABASE_RELATIVE_PATH = "databaze/manager_bozp.db"

    def full_backup_content_labels(self) -> list[str]:
        """Položky skutečně zahrnuté do celkové zálohy pracovního prostoru."""
        return [
            "databáze aplikace",
            "globální číselníky",
            "modulové číselníky",
            "auditní metodiky",
            "metodiky prověrek",
            "uživatelské šablony",
            "uživatelská nastavení",
        ]

    def _is_audit_methodology(self, relative_path: str) -> bool:
        parts = Path(relative_path).parts
        if len(parts) != 2 or parts[0] != "audity":
            return False
        name = parts[1]
        return name.endswith(".json") and name not in _AUDIT_CATALOG_FILES and not name.startswith("_")

    def _is_proverky_methodology(self, relative_path: str) -> bool:
        parts = Path(relative_path).parts
        if len(parts) != 2 or parts[0] != "proverky":
            return False
        name = parts[1]
        return (
            name.endswith(".json")
            and name not in _PROVERKY_CATALOG_FILES
            and not name.startswith("_")
        )

    def _is_global_catalog(self, relative_path: str) -> bool:
        if self._is_audit_methodology(relative_path) or self._is_proverky_methodology(relative_path):
            return False
        if relative_path.startswith("modulove/"):
            return False
        return relative_path.endswith(".json")

    def _is_module_catalog(self, relative_path: str) -> bool:
        return relative_path.startswith("modulove/") and relative_path.endswith(".json")

    def _count_paths(self, relative_paths: list[str]) -> dict[str, int]:
        return {
            "global_catalogs": sum(1 for path in relative_paths if self._is_global_catalog(path)),
            "module_catalogs": sum(1 for path in relative_paths if self._is_module_catalog(path)),
            "audit_methodologies": sum(
                1 for path in relative_paths if self._is_audit_methodology(path)
            ),
            "proverky_methodologies": sum(
                1 for path in relative_paths if self._is_proverky_methodology(path)
            ),
        }

    def _count_workspace_catalog_paths(self) -> dict[str, int]:
        ciselniky_dir = storage_service.ciselniky_dir
        if not ciselniky_dir.exists():
            return {
                "global_catalogs": 0,
                "module_catalogs": 0,
                "audit_methodologies": 0,
                "proverky_methodologies": 0,
            }

        relative_paths = [
            path.relative_to(ciselniky_dir).as_posix()
            for path in ciselniky_dir.rglob("*.json")
            if path.is_file()
        ]
        return self._count_paths(relative_paths)

    def _count_database_records(self) -> dict[str, int]:
        counts = {
            "legal_documents": 0,
            "control_processes": 0,
            "tasks": 0,
            "accidents": 0,
            "audits": 0,
            "inspections": 0,
        }
        try:
            with get_session() as session:
                counts["legal_documents"] = session.scalar(select(func.count()).select_from(LegalDocument)) or 0
                counts["control_processes"] = (
                    session.scalar(
                        select(func.count()).select_from(LegalRequirement).where(
                            LegalRequirement.parent_requirement_id.is_not(None)
                        )
                    )
                    or 0
                )
                counts["tasks"] = session.scalar(select(func.count()).select_from(Task)) or 0
                counts["accidents"] = session.scalar(select(func.count()).select_from(Accident)) or 0
                counts["audits"] = session.scalar(select(func.count()).select_from(Audit)) or 0
                counts["inspections"] = (
                    session.scalar(select(func.count()).select_from(BozpInspection)) or 0
                )
        except Exception:
            pass
        return counts

    def _zip_catalog_paths(self, names: list[str]) -> list[str]:
        prefix = "ciselniky/"
        return [
            name[len(prefix) :]
            for name in names
            if name.startswith(prefix) and name.endswith(".json") and not name.endswith("/")
        ]

    def build_manifest(
        self,
        zip_path: Path | str,
        *,
        backup_type: str = BACKUP_TYPE_FULL,
        include_database_counts: bool = True,
    ) -> dict:
        source = Path(zip_path)
        manifest: dict = {
            "path": str(source.resolve()),
            "backup_type": backup_type,
            "zip_exists": source.is_file(),
            "zip_readable": False,
            "zip_crc_ok": False,
            "database_path": self.DATABASE_RELATIVE_PATH,
            "database_included": False,
            "file_count": 0,
            "global_catalogs": 0,
            "module_catalogs": 0,
            "audit_methodologies": 0,
            "proverky_methodologies": 0,
            "verified": False,
            "verification_errors": [],
        }

        if not manifest["zip_exists"]:
            manifest["verification_errors"].append("ZIP soubor neexistuje.")
            return manifest

        try:
            with zipfile.ZipFile(source, "r") as zf:
                manifest["zip_readable"] = True
                bad_file = zf.testzip()
                manifest["zip_crc_ok"] = bad_file is None
                if bad_file:
                    manifest["verification_errors"].append(
                        f"Kontrolní součet ZIPu selhal u souboru: {bad_file}"
                    )

                names = [name for name in zf.namelist() if not name.endswith("/")]
                manifest["file_count"] = len(names)
                manifest["database_included"] = self.DATABASE_RELATIVE_PATH in names
                if not manifest["database_included"]:
                    manifest["verification_errors"].append(
                        "Záloha neobsahuje očekávanou databázi."
                    )

                catalog_counts = self._count_paths(self._zip_catalog_paths(names))
                manifest.update(catalog_counts)

                if backup_service.VERSION_FILE in names:
                    try:
                        version_info = json.loads(
                            zf.read(backup_service.VERSION_FILE).decode("utf-8")
                        )
                        manifest["version_info"] = version_info
                    except Exception as exc:
                        manifest["verification_errors"].append(
                            f"Manifest VERSION.json nelze načíst: {exc}"
                        )
        except zipfile.BadZipFile:
            manifest["verification_errors"].append("ZIP soubor nelze otevřít.")
        except OSError as exc:
            manifest["verification_errors"].append(f"ZIP soubor nelze přečíst: {exc}")

        if include_database_counts:
            manifest["database_counts"] = self._count_database_records()

        manifest["workspace_database_path"] = str(storage_service.database_path.resolve())
        manifest["editable_catalogs_registered"] = len(editable_catalog_service.registered_paths())

        manifest["verified"] = (
            manifest["zip_exists"]
            and manifest["zip_readable"]
            and manifest["zip_crc_ok"]
            and manifest["database_included"]
            and not manifest["verification_errors"]
        )
        return manifest

    def workspace_snapshot(self) -> dict:
        snapshot = self._count_workspace_catalog_paths()
        snapshot["database_counts"] = self._count_database_records()
        snapshot["workspace_database_path"] = str(storage_service.database_path.resolve())
        return snapshot


backup_manifest_service = BackupManifestService()

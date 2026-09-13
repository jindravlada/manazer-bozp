import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service
from core.services.storage_service import storage_service
from core.version import APP_NAME, APP_VERSION


BACKUP_TYPE_FULL = "celkova"
BACKUP_TYPE_DATABASE = "databaze"
BACKUP_TYPE_CATALOGS_TEMPLATES = "ciselniky-sablony"

BACKUP_TYPE_LABELS: dict[str, str] = {
    BACKUP_TYPE_FULL: "Celková záloha",
    BACKUP_TYPE_DATABASE: "Záloha databáze",
    BACKUP_TYPE_CATALOGS_TEMPLATES: "Záloha číselníků a šablon",
}

BACKUP_TYPE_RESTORE_LABELS: dict[str, str] = {
    BACKUP_TYPE_FULL: "Celková obnova",
    BACKUP_TYPE_DATABASE: "Obnova databáze",
    BACKUP_TYPE_CATALOGS_TEMPLATES: "Obnova číselníků a šablon",
}

BACKUP_PREFIX_BY_TYPE: dict[str, str] = {
    BACKUP_TYPE_FULL: "manager-bozp-backup-celkova",
    BACKUP_TYPE_DATABASE: "manager-bozp-backup-databaze",
    BACKUP_TYPE_CATALOGS_TEMPLATES: "manager-bozp-backup-ciselniky-sablony",
}


class BackupService:
    """Záloha a obnova uživatelského pracovního prostoru aplikace."""

    VERSION_FILE = "VERSION.json"
    BACKUP_PREFIX = "manager-bozp-backup"

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H%M%S")

    def default_backup_path(self, backup_type: str = BACKUP_TYPE_FULL) -> Path:
        storage_service.ensure_structure()
        prefix = BACKUP_PREFIX_BY_TYPE.get(backup_type, self.BACKUP_PREFIX)
        return storage_service.backups_dir / f"{prefix}-{self._timestamp()}.zip"

    def _content_for_type(self, backup_type: str) -> list[str]:
        if backup_type == BACKUP_TYPE_DATABASE:
            return ["databaze"]
        if backup_type == BACKUP_TYPE_CATALOGS_TEMPLATES:
            return ["ciselniky", "templates"]
        return [
            "databaze",
            "prilohy",
            "control_results",
            "templates",
            "export",
            "konfigurace",
            "ciselniky",
            "import",
            "logy",
        ]

    def _build_version_info(self, backup_type: str) -> dict:
        base = storage_service.base.resolve()
        catalog_paths = editable_catalog_service.registered_paths()
        existing_catalogs = [
            path.relative_to(storage_service.ciselniky_dir).as_posix()
            for path in editable_catalog_service.iter_existing_user_catalogs(
                storage_service.ciselniky_dir
            )
        ]

        return {
            "program": APP_NAME,
            "verze": APP_VERSION,
            "typ": "zaloha-pracovniho-prostoru",
            "typ_zalohy": backup_type,
            "vytvoreno": datetime.now().isoformat(timespec="seconds"),
            "root": str(base),
            "obsah": self._content_for_type(backup_type),
            "editovatelne_ciselniky": catalog_paths,
            "ciselniky_v_zaloh": existing_catalogs,
        }

    def _detect_backup_type(self, info: dict) -> str:
        stored = info.get("typ_zalohy")
        if stored in BACKUP_TYPE_LABELS:
            return stored

        if info.get("typ") == "zaloha-pracovniho-prostoru":
            return BACKUP_TYPE_FULL

        obsah = info.get("obsah", [])
        if obsah == ["databaze"]:
            return BACKUP_TYPE_DATABASE
        if set(obsah) == {"ciselniky", "templates"}:
            return BACKUP_TYPE_CATALOGS_TEMPLATES

        return BACKUP_TYPE_FULL

    def _validate_restore_type(self, info: dict, restore_type: str) -> None:
        detected = self._detect_backup_type(info)
        if detected != restore_type:
            raise ValueError(
                f"Soubor obsahuje {BACKUP_TYPE_LABELS[detected].lower()}, "
                f"nelze použít pro {BACKUP_TYPE_RESTORE_LABELS[restore_type].lower()}."
            )

    def _add_directory_to_zip(
        self,
        zf: zipfile.ZipFile,
        directory: Path,
        base: Path,
        exclude: Path | None = None,
    ) -> None:
        if not directory.exists():
            return

        exclude_resolved = exclude.resolve() if exclude else None
        for path in directory.rglob("*"):
            if not path.is_file():
                continue

            resolved = path.resolve()
            if exclude_resolved and resolved == exclude_resolved:
                continue

            try:
                rel = path.relative_to(base)
            except ValueError:
                continue

            if rel.parts and rel.parts[0] == "zalohy":
                continue

            zf.write(path, rel.as_posix())

    def _add_full_workspace_to_zip(
        self,
        zf: zipfile.ZipFile,
        base: Path,
        exclude: Path | None = None,
    ) -> None:
        if not base.exists():
            return

        exclude_resolved = exclude.resolve() if exclude else None
        for path in base.rglob("*"):
            if path.is_dir():
                continue

            resolved = path.resolve()
            if exclude_resolved and resolved == exclude_resolved:
                continue

            try:
                rel = path.relative_to(base)
            except ValueError:
                continue

            if rel.parts and rel.parts[0] == "zalohy":
                continue

            zf.write(path, rel.as_posix())

    def create_backup(
        self,
        target_path: str | Path | None = None,
        backup_type: str = BACKUP_TYPE_FULL,
    ) -> Path:
        if backup_type not in BACKUP_TYPE_LABELS:
            raise ValueError(f"Neznámý typ zálohy: {backup_type}")

        storage_service.ensure_structure()
        target = Path(target_path) if target_path else self.default_backup_path(backup_type)
        target.parent.mkdir(parents=True, exist_ok=True)

        base = storage_service.base.resolve()
        version = self._build_version_info(backup_type)

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(self.VERSION_FILE, json.dumps(version, indent=4, ensure_ascii=False))

            if backup_type == BACKUP_TYPE_FULL:
                self._add_full_workspace_to_zip(zf, base, exclude=target)
            elif backup_type == BACKUP_TYPE_DATABASE:
                self._add_directory_to_zip(zf, storage_service.database_dir, base, exclude=target)
            elif backup_type == BACKUP_TYPE_CATALOGS_TEMPLATES:
                self._add_directory_to_zip(zf, storage_service.ciselniky_dir, base, exclude=target)
                self._add_directory_to_zip(zf, storage_service.templates_dir, base, exclude=target)

        return target

    def read_backup_info(self, source_path: str | Path) -> dict:
        source = Path(source_path)
        with zipfile.ZipFile(source, "r") as zf:
            try:
                return json.loads(zf.read(self.VERSION_FILE).decode("utf-8"))
            except Exception:
                return {}

    def _create_safety_backup(self, backup_type: str) -> tuple[Path, dict]:
        from core.backup.safety_backup import (
            SAFETY_PREFIX_BEFORE_RESTORE,
            create_verified_application_safety_backup,
        )

        return create_verified_application_safety_backup(
            filename_prefix=f"{SAFETY_PREFIX_BEFORE_RESTORE}-{backup_type}",
            blocked_operation="Obnova nebyla spuštěna.",
        )

    def verify_backup_integrity(
        self,
        source_path: str | Path,
        *,
        backup_type: str = BACKUP_TYPE_FULL,
    ) -> dict:
        from core.services.backup_manifest_service import backup_manifest_service

        return backup_manifest_service.build_manifest(
            source_path,
            backup_type=backup_type,
            include_database_counts=True,
        )

    def _execute_restore(self, source_path: str | Path, restore_type: str) -> None:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)

        info = self.read_backup_info(source)
        self._validate_restore_type(info, restore_type)

        storage_service.ensure_structure()

        base = storage_service.base
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            with zipfile.ZipFile(source, "r") as zf:
                zf.extractall(tmp)

            if restore_type == BACKUP_TYPE_FULL:
                items = [item for item in tmp.iterdir() if item.name != self.VERSION_FILE]
            else:
                dirs = self._content_for_type(restore_type)
                items = [tmp / name for name in dirs if (tmp / name).exists()]

            for item in items:
                self._replace_item(item, base / item.name)

        storage_service.ensure_structure()

    def restore_backup_with_verified_safety(
        self,
        source_path: str | Path,
        restore_type: str = BACKUP_TYPE_FULL,
    ) -> dict:
        """Vytvoří ověřenou bezpečnostní zálohu ``*.mbbackup`` a teprve potom spustí obnovu."""
        if restore_type not in BACKUP_TYPE_RESTORE_LABELS:
            raise ValueError(f"Neznámý typ obnovy: {restore_type}")

        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)

        info = self.read_backup_info(source)
        self._validate_restore_type(info, restore_type)

        safety_path, safety_manifest = self._create_safety_backup(restore_type)
        if not safety_manifest.get("verified"):
            errors = safety_manifest.get("verification_errors") or ["Neznámá chyba ověření."]
            try:
                safety_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ValueError(
                "Bezpečnostní záloha se nepodařila ověřit. Obnova nebyla spuštěna.\n\n"
                + "\n".join(str(item) for item in errors)
            )

        self._execute_restore(source, restore_type)

        return {
            "restored_path": str(source.resolve()),
            "restored_at": datetime.now().isoformat(timespec="seconds"),
            "safety_backup_path": str(safety_path.resolve()),
            "safety_backup_manifest": safety_manifest,
            "integrity_check": self.verify_backup_integrity(source, backup_type=restore_type),
        }

    def _replace_item(self, source: Path, target: Path) -> None:
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def restore_backup(
        self,
        source_path: str | Path,
        restore_type: str = BACKUP_TYPE_FULL,
    ) -> None:
        """Obnoví obsah zálohy do ~/.local/share/manazer-bozp.

        Před obnovou vytvoří ověřenou bezpečnostní zálohu ``*.mbbackup``.
        """
        if restore_type not in BACKUP_TYPE_RESTORE_LABELS:
            raise ValueError(f"Neznámý typ obnovy: {restore_type}")

        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)

        info = self.read_backup_info(source)
        self._validate_restore_type(info, restore_type)

        storage_service.ensure_structure()
        self._create_safety_backup(restore_type)
        self._execute_restore(source, restore_type)

    def requires_restart_after_restore(self, restore_type: str) -> bool:
        return restore_type in (BACKUP_TYPE_FULL, BACKUP_TYPE_DATABASE)


backup_service = BackupService()

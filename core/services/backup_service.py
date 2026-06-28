import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from core.services.storage_service import storage_service


class BackupService:
    """Záloha a obnova celého uživatelského pracovního prostoru aplikace."""

    VERSION_FILE = "VERSION.json"
    BACKUP_PREFIX = "manager-bozp-backup"

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H%M%S")

    def default_backup_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.backups_dir / f"{self.BACKUP_PREFIX}-{self._timestamp()}.zip"

    def create_backup(self, target_path: str | Path | None = None) -> Path:
        storage_service.ensure_structure()
        target = Path(target_path) if target_path else self.default_backup_path()
        target.parent.mkdir(parents=True, exist_ok=True)

        base = storage_service.base.resolve()
        target_resolved = target.resolve()

        version = {
            "program": "Manažer BOZP",
            "verze": "3.0",
            "typ": "zaloha-pracovniho-prostoru",
            "vytvoreno": datetime.now().isoformat(timespec="seconds"),
            "root": str(base),
        }

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(self.VERSION_FILE, json.dumps(version, indent=4, ensure_ascii=False))
            if not base.exists():
                return target

            for path in base.rglob("*"):
                if path.is_dir():
                    continue

                resolved = path.resolve()
                if resolved == target_resolved:
                    continue

                # Zálohy nezálohujeme do zálohy, aby nevznikaly obří rekurzivní archivy.
                try:
                    rel = path.relative_to(base)
                except ValueError:
                    continue
                if rel.parts and rel.parts[0] == "zalohy":
                    continue

                zf.write(path, rel.as_posix())

        return target

    def read_backup_info(self, source_path: str | Path) -> dict:
        source = Path(source_path)
        with zipfile.ZipFile(source, "r") as zf:
            try:
                return json.loads(zf.read(self.VERSION_FILE).decode("utf-8"))
            except Exception:
                return {}

    def restore_backup(self, source_path: str | Path) -> None:
        """Obnoví obsah zálohy do ~/.local/share/manazer-bozp.

        Obnova přepíše uživatelský pracovní prostor. Před obnovou vytvoří
        bezpečnostní zálohu aktuálního stavu do adresáře zalohy.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)

        storage_service.ensure_structure()
        self.create_backup(storage_service.backups_dir / f"pred-obnovou-{self._timestamp()}.zip")

        base = storage_service.base
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            with zipfile.ZipFile(source, "r") as zf:
                zf.extractall(tmp)

            for item in tmp.iterdir():
                if item.name == self.VERSION_FILE:
                    continue
                target = base / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

        storage_service.ensure_structure()


backup_service = BackupService()

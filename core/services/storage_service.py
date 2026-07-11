import os
import platform
import shutil
from pathlib import Path

from core.paths import project_root


class StorageService:
    """
    Jednotná správa uživatelských dat aplikace.

    Linux:
        ~/.local/share/manazer-bozp

    Windows:
        %LOCALAPPDATA%\\manazer-bozp
    """

    APP_NAME = "manazer-bozp"
    DATABASE_NAME = "manager_bozp.db"

    def __init__(self):
        if platform.system() == "Windows":
            self.base = Path(os.environ["LOCALAPPDATA"]) / self.APP_NAME
        else:
            self.base = Path.home() / ".local" / "share" / self.APP_NAME

        self.ensure_structure()

    def ensure_structure(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.imports_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.ciselniky_dir.mkdir(parents=True, exist_ok=True)
        self.control_results_dir.mkdir(parents=True, exist_ok=True)

        self.ensure_default_templates()
        self.ensure_editable_catalogs()

    @property
    def database_dir(self) -> Path:
        return self.base / "databaze"

    @property
    def database_path(self) -> Path:
        return self.database_dir / self.DATABASE_NAME

    @property
    def attachments_dir(self) -> Path:
        return self.base / "prilohy"

    @property
    def backups_dir(self) -> Path:
        return self.base / "zalohy"

    @property
    def exports_dir(self) -> Path:
        return self.base / "export"

    @property
    def imports_dir(self) -> Path:
        return self.base / "import"

    @property
    def logs_dir(self) -> Path:
        return self.base / "logy"

    @property
    def templates_dir(self) -> Path:
        return self.base / "templates"

    def template_file(self, *parts: str) -> Path:
        """Vrátí cestu k uživatelské šabloně v ~/.local/share/manazer-bozp/templates."""
        return self.templates_dir.joinpath(*parts)

    def bundled_template_file(self, *parts: str) -> Path | None:
        """Vrátí cestu k dodávané šabloně z balíčku aplikace."""
        for source_root in self.bundled_template_roots():
            candidate = source_root.joinpath(*parts)
            if candidate.exists():
                return candidate
        return None

    def export_file(self, *parts: str) -> Path:
        """Vrátí cestu k exportnímu souboru v ~/.local/share/manazer-bozp/export."""
        path = self.exports_dir.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_dir(self) -> Path:
        return self.base / "konfigurace"

    @property
    def ciselniky_dir(self) -> Path:
        return self.base / "ciselniky"

    @property
    def control_results_dir(self) -> Path:
        return self.base / "control_results"

    def ensure_editable_catalogs(self) -> None:
        from core.services.editable_catalog_service import editable_catalog_service

        editable_catalog_service.ensure_all(self.ciselniky_dir)

    def bundled_templates_dir(self) -> Path:
        """Výchozí šablony modulu Kniha úrazů dodané s aplikací / AppImage."""
        return project_root() / "moduly" / "kniha_urazu" / "templates"

    def bundled_template_roots(self) -> list[Path]:
        root = project_root()
        return [
            root / "moduly" / "kniha_urazu" / "templates",
            root / "moduly" / "proverky" / "templates",
            root / "moduly" / "audity" / "templates",
        ]

    def ensure_default_templates(self) -> None:
        """Zkopíruje výchozí šablony do .local, ale nikdy nepřepíše uživatelské úpravy."""
        target_root = self.templates_dir
        for source_root in self.bundled_template_roots():
            if not source_root.exists():
                continue

            for source in source_root.rglob("*"):
                relative = source.relative_to(source_root)
                target = target_root / relative
                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copy2(source, target)

    def attachment_dir(self, entity_type: str, entity_id: int) -> Path:
        path = self.attachments_dir / entity_type / str(entity_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def attachment_absolute(self, relative_path: str) -> Path:
        return self.attachments_dir / relative_path


storage_service = StorageService()

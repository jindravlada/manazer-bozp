import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditableCatalog:
    """Definice editovatelného číselníku v uživatelském pracovním prostoru."""

    relative_path: str


# Registr editovatelných číselníků – pro nový číselník stačí přidat položku zde.
EDITABLE_CATALOGS: tuple[EditableCatalog, ...] = (
    EditableCatalog("modulove/vysetrovani_mu/ishikawa_faktory.json"),
    EditableCatalog("proverky/oblasti.json"),
    EditableCatalog("proverky/prvni_pomoc.json"),
    EditableCatalog("audity/procesy.json"),
    EditableCatalog("audity/urazy_mimo_udalosti.json"),
)


class EditableCatalogService:
    """Správa editovatelných číselníků v uživatelském pracovním prostoru."""

    CISELNIKY_DIR_NAME = "ciselniky"

    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def bundled_dir(self) -> Path:
        return self.project_root() / self.CISELNIKY_DIR_NAME

    def bundled_path(self, relative_path: str) -> Path:
        return self.bundled_dir() / relative_path

    def user_path(self, user_dir: Path, relative_path: str) -> Path:
        return user_dir / relative_path

    def registered_paths(self) -> tuple[str, ...]:
        return tuple(catalog.relative_path for catalog in EDITABLE_CATALOGS)

    def ensure_all(self, user_dir: Path) -> None:
        user_dir.mkdir(parents=True, exist_ok=True)
        for catalog in EDITABLE_CATALOGS:
            self.ensure_catalog(user_dir, catalog.relative_path)

    def ensure_catalog(self, user_dir: Path, relative_path: str) -> Path:
        target = self.user_path(user_dir, relative_path)
        if target.exists():
            return target

        target.parent.mkdir(parents=True, exist_ok=True)

        bundled = self.bundled_path(relative_path)
        if bundled.exists() and bundled.is_file():
            shutil.copy2(bundled, target)
            return target

        return target

    def iter_existing_user_catalogs(self, user_dir: Path) -> list[Path]:
        if not user_dir.exists():
            return []

        result: list[Path] = []
        for catalog in EDITABLE_CATALOGS:
            path = self.user_path(user_dir, catalog.relative_path)
            if path.is_file():
                result.append(path)
        return result


editable_catalog_service = EditableCatalogService()

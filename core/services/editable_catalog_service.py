import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from core.paths import project_root as resolve_project_root


@dataclass(frozen=True)
class EditableCatalog:
    """Definice editovatelného číselníku v uživatelském pracovním prostoru."""

    relative_path: str


_BASE_EDITABLE_CATALOGS: tuple[EditableCatalog, ...] = (
    EditableCatalog("modulove/vysetrovani_mu/ishikawa_faktory.json"),
    EditableCatalog("proverky/oblasti.json"),
    EditableCatalog("proverky/prvni_pomoc.json"),
    EditableCatalog("audity/procesy.json"),
)

_SKIP_SEED_NAMES = frozenset({".gitkeep", "README.md"})


def _load_audity_knowledge_catalogs(root: Path) -> tuple[EditableCatalog, ...]:
    procesy_path = root / "ciselniky" / "audity" / "procesy.json"
    if not procesy_path.is_file():
        return ()

    try:
        with procesy_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ()

    catalogs: list[EditableCatalog] = []
    seen = {catalog.relative_path for catalog in _BASE_EDITABLE_CATALOGS}
    for raw in payload.get("procesy") or []:
        if not isinstance(raw, dict):
            continue
        soubor = str(raw.get("soubor_znalosti") or "").strip()
        if not soubor:
            continue
        relative_path = f"audity/{soubor}"
        if relative_path in seen:
            continue
        catalogs.append(EditableCatalog(relative_path))
        seen.add(relative_path)

    return tuple(catalogs)


def _build_editable_catalogs() -> tuple[EditableCatalog, ...]:
    return _BASE_EDITABLE_CATALOGS + _load_audity_knowledge_catalogs(resolve_project_root())


# Registr editovatelných číselníků – pro nový číselník stačí přidat položku zde.
EDITABLE_CATALOGS: tuple[EditableCatalog, ...] = _build_editable_catalogs()


class EditableCatalogService:
    """Správa editovatelných číselníků v uživatelském pracovním prostoru."""

    CISELNIKY_DIR_NAME = "ciselniky"

    def project_root(self) -> Path:
        return resolve_project_root()

    def bundled_dir(self) -> Path:
        return self.project_root() / self.CISELNIKY_DIR_NAME

    def bundled_path(self, relative_path: str) -> Path:
        return self.bundled_dir() / relative_path

    def user_path(self, user_dir: Path, relative_path: str) -> Path:
        return user_dir / relative_path

    def registered_paths(self) -> tuple[str, ...]:
        return tuple(catalog.relative_path for catalog in EDITABLE_CATALOGS)

    def ensure_all(self, user_dir: Path) -> None:
        """Doplní chybějící distribuované číselníky; existující soubory nepřepisuje."""
        user_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_bundled_defaults(user_dir)
        for catalog in EDITABLE_CATALOGS:
            self.ensure_catalog(user_dir, catalog.relative_path)

    def ensure_bundled_defaults(self, user_dir: Path) -> None:
        """Zkopíruje všechny soubory z distribuovaných ``ciselniky/``, pokud v cíli chybí."""
        bundled = self.bundled_dir()
        if not bundled.is_dir():
            return

        for source in bundled.rglob("*"):
            if not source.is_file():
                continue
            if source.name in _SKIP_SEED_NAMES:
                continue

            relative = source.relative_to(bundled)
            target = user_dir / relative
            if target.exists():
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

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

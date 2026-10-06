import hashlib
import logging
import os
import platform
import shutil
import stat
from pathlib import Path

from core.paths import project_root
from core.utils.confined_path import require_confined_path

logger = logging.getLogger(__name__)

_WORKSPACE_DIR_MODE = 0o700


def ensure_private_workspace_root(path: Path) -> None:
    """Na POSIX nastaví kořen workspace na 0700, pokud patří aktuálnímu uživateli.

    Windows se nemění. Symlink kořen se nenasleduje. Chyba nesmí shodit start.
    """
    if platform.system() == "Windows" or os.name == "nt":
        return
    try:
        info = os.lstat(path)
    except OSError:
        logger.warning("Nelze ověřit práva workspace %s.", path, exc_info=True)
        return
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return
    try:
        if info.st_uid != os.getuid():
            logger.warning(
                "Workspace %s nepatří aktuálnímu uživateli, práva se nemění.",
                path,
            )
            return
    except AttributeError:
        return
    if stat.S_IMODE(info.st_mode) == _WORKSPACE_DIR_MODE:
        return
    try:
        os.chmod(path, _WORKSPACE_DIR_MODE, follow_symlinks=False)
    except (OSError, NotImplementedError, TypeError):
        logger.warning(
            "Nepodařilo se nastavit práva workspace %s.",
            path,
            exc_info=True,
        )


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
        ensure_private_workspace_root(self.base)
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
            root / "moduly" / "rizeni_rizik" / "templates",
            root / "moduly" / "testy" / "templates",
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
                    self._write_template_bundle_hash(target, self._file_sha256(source))

    def resolve_editable_template(self, *parts: str) -> Path:
        """Vrátí uživatelskou šablonu v .local, synchronizovanou z balíčku.

        - AppImage/vývoj dodá výchozí šablonu z ``moduly/.../templates``.
        - Uživatel ji může upravit v ``~/.local/share/manazer-bozp/templates``.
        - Neupravenou kopii při aktualizaci balíčku obnovíme z dodané šablony.
        - Upravenou kopii (např. s logem) nepřepisujeme.
        """
        user_path = self.template_file(*parts)
        bundled = self.bundled_template_file(*parts)
        user_path.parent.mkdir(parents=True, exist_ok=True)

        if bundled is None:
            return user_path

        bundled_hash = self._file_sha256(bundled)
        meta_path = self._template_bundle_hash_path(user_path)

        if not user_path.exists():
            shutil.copy2(bundled, user_path)
            self._write_template_bundle_hash(user_path, bundled_hash)
            return user_path

        user_hash = self._file_sha256(user_path)
        if meta_path.exists():
            recorded = meta_path.read_text(encoding="utf-8").strip()
            if user_hash == recorded:
                if recorded != bundled_hash:
                    shutil.copy2(bundled, user_path)
                    self._write_template_bundle_hash(user_path, bundled_hash)
                return user_path
            # Uživatelská úprava – ponechat.
            return user_path

        # Starší instalace bez markeru: pokud soubor stále odpovídá balíčku,
        # založ marker; jinak považuj za upravený.
        if user_hash == bundled_hash:
            self._write_template_bundle_hash(user_path, bundled_hash)
        return user_path

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _template_bundle_hash_path(template_path: Path) -> Path:
        return template_path.with_name(template_path.name + ".bundle_sha256")

    def _write_template_bundle_hash(self, template_path: Path, digest: str) -> None:
        meta_path = self._template_bundle_hash_path(template_path)
        meta_path.write_text(digest + "\n", encoding="utf-8")

    def attachment_dir(self, entity_type: str, entity_id: int) -> Path:
        path = self.attachments_dir / entity_type / str(entity_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def attachment_absolute(self, relative_path: str) -> Path:
        """Vrátí cestu uvnitř ``prilohy/``. Absolutní cesta, ``..`` i symlink ven jsou chyba."""
        return require_confined_path(
            self.attachments_dir,
            relative_path,
            message="Cesta přílohy je mimo adresář prilohy.",
        )


storage_service = StorageService()

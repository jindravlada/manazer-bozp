"""Společný dialog pro výběr fotografie s náhledy (UX-PHOTO-1 / UX-PHOTO-2 / UX-PHOTO-3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtGui import QIcon, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.services.storage_service import storage_service
from core.ui.native_folder_dialog import (
    PHOTO_FOLDER_DIALOG_TITLE,
    choose_existing_directory,
)

PHOTO_PICKER_TITLE = "Vybrat fotografii"
PHOTO_PICKER_TITLE_MULTI = "Vybrat fotografie"
PHOTO_PICKER_EMPTY = "V této složce nejsou žádné podporované fotografie."
PHOTO_PICKER_PREVIEW_UNAVAILABLE = "Náhled není dostupný"
PHOTO_PICKER_PREVIEW_BROKEN = "Soubor nelze načíst"
PHOTO_PICKER_SELECT_LABEL = "Vybrat fotografii"
PHOTO_PICKER_SELECT_MULTI_LABEL = "Vybrat fotografie"
PHOTO_PICKER_CANCEL_LABEL = "Zrušit"
PHOTO_PICKER_UP_LABEL = "O úroveň výš"
PHOTO_PICKER_BROWSE_LABEL = "Vybrat složku"
PHOTO_PICKER_REFRESH_LABEL = "Obnovit"
PHOTO_PICKER_ROTATE_LEFT_LABEL = "⟲ Otočit vlevo"
PHOTO_PICKER_ROTATE_RIGHT_LABEL = "⟳ Otočit vpravo"
PHOTO_PICKER_ROTATE_UNSUPPORTED = "Otočení tohoto formátu není podporováno."
PHOTO_PICKER_ROTATE_CONFIRM_TITLE = "Otočení fotografie"
PHOTO_PICKER_ROTATE_CONFIRM_TEXT = (
    "Fotografie bude otočena přímo v původním souboru.\n\nPokračovat?"
)
PHOTO_PICKER_ROTATE_DONT_ASK = "Příště se již neptat."
PHOTO_PICKER_ROTATE_ERROR_TITLE = "Otočení fotografie"

# Veřejné konstanty velikosti miniatur (testy / případné ladění UI).
THUMB_ICON_SIZE = 160
THUMB_GRID_SIZE = (190, 215)

PHOTO_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
)
# Formáty, které umíme bezpečně přepsat přes Pillow (bez nových závislostí).
ROTATABLE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_HEIC_EXTENSIONS = frozenset({".heic", ".heif"})

SORT_NAME = "name"
SORT_DATE_NEWEST = "date_newest"
SORT_DATE_OLDEST = "date_oldest"

_THUMB_SIZE = THUMB_ICON_SIZE
_GRID_WIDTH = THUMB_GRID_SIZE[0]
_GRID_HEIGHT = THUMB_GRID_SIZE[1]
_SETTINGS_FILE = "ui.ini"
_LAST_DIRECTORY_KEY = "photo_picker/last_directory"
_SKIP_ROTATE_CONFIRM_KEY = "photo_picker/skip_rotate_confirm"
_EXIF_ORIENTATION = 274
_ROLE_PATH = Qt.ItemDataRole.UserRole
_ROLE_MTIME = Qt.ItemDataRole.UserRole + 1
_ROLE_SIZE = Qt.ItemDataRole.UserRole + 2
_ROLE_PREVIEW_OK = Qt.ItemDataRole.UserRole + 3


class PhotoRotateError(Exception):
    """Chyba při otočení / přepisu fotografie na disku."""


def is_supported_photo(path: str | Path) -> bool:
    """True, pokud přípona patří mezi podporované formáty fotografií."""
    return Path(path).suffix.lower() in PHOTO_EXTENSIONS


def list_photo_files(directory: str | Path) -> list[Path]:
    """Vrátí podporované fotografie ve složce (ne rekurzivně)."""
    root = Path(directory)
    if not root.is_dir():
        return []
    files: list[Path] = []
    try:
        for entry in root.iterdir():
            if entry.is_file() and is_supported_photo(entry):
                files.append(entry)
    except OSError:
        return []
    return files


def default_pictures_directory() -> Path:
    """Domovský adresář / Obrázky, případně home."""
    home = Path.home()
    for name in ("Pictures", "Obrázky", "Images"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home


def photo_picker_settings() -> QSettings:
    directory = storage_service.config_dir
    directory.mkdir(parents=True, exist_ok=True)
    return QSettings(
        str(directory / _SETTINGS_FILE),
        QSettings.Format.IniFormat,
    )


def get_last_photo_directory() -> Path | None:
    raw = photo_picker_settings().value(_LAST_DIRECTORY_KEY)
    if raw is None:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.is_dir() else None


def set_last_photo_directory(directory: str | Path) -> None:
    path = Path(directory).expanduser().resolve()
    if not path.is_dir():
        return
    settings = photo_picker_settings()
    settings.setValue(_LAST_DIRECTORY_KEY, str(path))
    settings.sync()


def get_skip_rotate_confirm() -> bool:
    raw = photo_picker_settings().value(_SKIP_ROTATE_CONFIRM_KEY, False)
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    return text in {"1", "true", "yes", "on"}


def set_skip_rotate_confirm(skip: bool) -> None:
    settings = photo_picker_settings()
    settings.setValue(_SKIP_ROTATE_CONFIRM_KEY, bool(skip))
    settings.sync()


def resolve_initial_directory(initial_directory: str | Path | None = None) -> Path:
    """Pořadí: initial → poslední uložená → Obrázky/home."""
    if initial_directory is not None:
        candidate = Path(initial_directory).expanduser()
        if candidate.is_dir():
            return candidate.resolve()
    last = get_last_photo_directory()
    if last is not None:
        return last
    return default_pictures_directory().resolve()


def is_rotation_supported(path: str | Path) -> bool:
    """True, pokud formát umíme bezpečně přepsat při otočení."""
    return Path(path).suffix.lower() in ROTATABLE_EXTENSIONS


def _normalize_exif_orientation(exif) -> object | None:
    """Nastaví Orientation=1 (normální). Vrátí upravený Exif, nebo None."""
    if not exif:
        return None
    try:
        exif[_EXIF_ORIENTATION] = 1
    except Exception:
        return None
    return exif


def _save_rotated_image(image, path: Path, *, suffix: str, exif=None) -> None:
    """Uloží otočený obrázek do path se zachováním formátu a kvality."""
    save_kwargs: dict = {}
    icc = image.info.get("icc_profile")
    if icc:
        save_kwargs["icc_profile"] = icc

    normalized = _normalize_exif_orientation(exif)
    if suffix in {".jpg", ".jpeg"}:
        save_kwargs["format"] = "JPEG"
        save_kwargs["quality"] = 95
        save_kwargs["optimize"] = True
        if normalized is not None:
            save_kwargs["exif"] = normalized
    elif suffix == ".png":
        save_kwargs["format"] = "PNG"
        save_kwargs["optimize"] = True
        if normalized is not None:
            save_kwargs["exif"] = normalized
    elif suffix == ".webp":
        save_kwargs["format"] = "WEBP"
        save_kwargs["quality"] = 95
        save_kwargs["method"] = 6
        if normalized is not None:
            save_kwargs["exif"] = normalized
    else:
        raise PhotoRotateError(PHOTO_PICKER_ROTATE_UNSUPPORTED)

    tmp_path = path.with_name(f".{path.name}.rotate-tmp")
    try:
        image.save(tmp_path, **save_kwargs)
        tmp_path.replace(path)
    except OSError as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise PhotoRotateError(
            f"Soubor se nepodařilo přepsat:\n{path}\n\n{exc}"
        ) from exc
    except Exception as exc:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise PhotoRotateError(
            f"Otočení fotografie se nezdařilo:\n{path}\n\n{exc}"
        ) from exc


def rotate_photo_file(path: str | Path, degrees: int) -> Path:
    """Otočí fotografii přímo v původním souboru o ±90°.

    degrees: -90 (vlevo / CCW) nebo +90 (vpravo / CW).
    Vrátí Path ke stejnému souboru. EXIF Orientation nastaví na normální.
    """
    if degrees not in (-90, 90):
        raise PhotoRotateError("Podporováno je pouze otočení o ±90°.")

    target = Path(path)
    if not target.is_file():
        raise PhotoRotateError(f"Soubor neexistuje:\n{target}")
    if not is_rotation_supported(target):
        raise PhotoRotateError(PHOTO_PICKER_ROTATE_UNSUPPORTED)

    try:
        from PIL import Image, ImageOps
    except Exception as exc:
        raise PhotoRotateError(
            "Pro otočení fotografie je potřeba knihovna Pillow."
        ) from exc

    suffix = target.suffix.lower()
    preserved_exif = None
    try:
        with Image.open(target) as opened:
            try:
                preserved_exif = opened.getexif()
            except Exception:
                preserved_exif = None
            # Nejdřív aplikovat EXIF Orientation do pixelů, pak otočit.
            image = ImageOps.exif_transpose(opened) or opened
            image.load()
            image = image.copy()
    except Exception as exc:
        raise PhotoRotateError(
            f"Fotografii se nepodařilo načíst:\n{target}\n\n{exc}"
        ) from exc

    try:
        if degrees == -90:
            rotated = image.transpose(Image.Transpose.ROTATE_90)
        else:
            rotated = image.transpose(Image.Transpose.ROTATE_270)
    except Exception as exc:
        raise PhotoRotateError(
            f"Otočení fotografie se nezdařilo:\n{target}\n\n{exc}"
        ) from exc

    _save_rotated_image(rotated, target, suffix=suffix, exif=preserved_exif)
    return target.resolve()


@dataclass(frozen=True)
class _CacheKey:
    path: str
    mtime_ns: int
    size: int


class _ThumbnailSignals(QObject):
    finished = Signal(int, str, object, bool)
    # generation, absolute path, QImage|None, preview_ok


class _ThumbnailJob(QRunnable):
    def __init__(self, *, generation: int, path: Path, mtime_ns: int, size: int):
        super().__init__()
        self.generation = generation
        self.path = path
        self.mtime_ns = mtime_ns
        self.size = size
        self.signals = _ThumbnailSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        image: QImage | None = None
        preview_ok = False
        suffix = self.path.suffix.lower()
        try:
            if suffix in _HEIC_EXTENSIONS:
                # Qt obvykle HEIC neumí bez pluginu – nabídnout výběr bez náhledu.
                preview_ok = True
            else:
                loaded = QImage(str(self.path))
                if not loaded.isNull():
                    image = fit_image_on_canvas(loaded, _THUMB_SIZE)
                    preview_ok = True
        except Exception:
            image = None
            preview_ok = False
        self.signals.finished.emit(
            self.generation,
            str(self.path.resolve()),
            image,
            preview_ok,
        )


def fit_image_on_canvas(image: QImage, size: int = _THUMB_SIZE) -> QImage:
    """Zmenší obrázek na jednotné plátno se zachováním poměru stran."""
    if image.isNull() or size <= 0:
        canvas = QImage(size, size, QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)
        return canvas

    scaled = image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawImage(x, y, scaled)
    painter.end()
    return canvas


def _format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def _format_mtime(path: Path) -> str:
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return "—"
    return datetime.fromtimestamp(stamp).strftime("%d.%m.%Y %H:%M")


def _try_capture_date(path: Path) -> str | None:
    """EXIF datum pořízení přes Pillow, pokud je snadno dostupné."""
    try:
        from PIL import Image, ExifTags
    except Exception:
        return None
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            if not exif:
                return None
            tag_map = {ExifTags.TAGS.get(key, key): value for key, value in exif.items()}
            raw = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
            if not raw:
                return None
            text = str(raw).strip()
            for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt).strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    continue
            return text
    except Exception:
        return None


class PhotoPickerDialog(QDialog):
    """Dialog pro výběr jedné nebo více fotografií s náhledy a navigací ve složkách."""

    def __init__(
        self,
        parent=None,
        *,
        initial_directory: str | Path | None = None,
        allow_multiple: bool = False,
    ):
        super().__init__(parent)
        self._allow_multiple = bool(allow_multiple)
        self.setWindowTitle(
            PHOTO_PICKER_TITLE_MULTI if self._allow_multiple else PHOTO_PICKER_TITLE
        )
        self.setMinimumSize(1000, 650)
        self.resize(1100, 700)
        self._focus_list_pending = True

        self._directory = resolve_initial_directory(initial_directory)
        self._sort_mode = SORT_NAME
        self._generation = 0
        self._thumb_cache: dict[_CacheKey, tuple[QPixmap | None, bool]] = {}
        self._placeholder_icon = self._build_placeholder_icon()
        self._selected_path: Path | None = None
        self._selected_paths: list[Path] = []
        self._pool = QThreadPool.globalInstance()

        self._build_ui()
        self._wire_shortcuts()
        self._load_directory(self._directory)

    @classmethod
    def get_photo(
        cls,
        parent=None,
        *,
        initial_directory: str | Path | None = None,
    ) -> Path | None:
        """Výběr jedné fotografie (zpětná kompatibilita)."""
        dialog = cls(
            parent=parent,
            initial_directory=initial_directory,
            allow_multiple=False,
        )
        dialog.showMaximized()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_path()
        return None

    @classmethod
    def get_photos(
        cls,
        parent=None,
        *,
        initial_directory: str | Path | None = None,
    ) -> list[Path]:
        """Výběr jedné nebo více fotografií. Prázdný seznam = zrušeno."""
        dialog = cls(
            parent=parent,
            initial_directory=initial_directory,
            allow_multiple=True,
        )
        dialog.showMaximized()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_paths()
        return []

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.isMaximized():
            self.showMaximized()
        if self._focus_list_pending:
            self._focus_list_pending = False
            self._list.setFocus(Qt.FocusReason.OtherFocusReason)

    def selected_path(self) -> Path | None:
        return self._selected_path

    def selected_paths(self) -> list[Path]:
        if self._selected_paths:
            return list(self._selected_paths)
        if self._selected_path is not None:
            return [self._selected_path]
        return []

    def current_directory(self) -> Path:
        return self._directory

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._path_label = QLabel()
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._path_label.setWordWrap(True)
        toolbar.addWidget(self._path_label, 1)

        self._up_btn = QPushButton(PHOTO_PICKER_UP_LABEL)
        self._browse_btn = QPushButton(PHOTO_PICKER_BROWSE_LABEL)
        self._refresh_btn = QPushButton(PHOTO_PICKER_REFRESH_LABEL)
        toolbar.addWidget(self._up_btn)
        toolbar.addWidget(self._browse_btn)
        toolbar.addWidget(self._refresh_btn)
        root.addLayout(toolbar)

        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Řazení:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Název", SORT_NAME)
        self._sort_combo.addItem("Datum – nejnovější první", SORT_DATE_NEWEST)
        self._sort_combo.addItem("Datum – nejstarší první", SORT_DATE_OLDEST)
        sort_row.addWidget(self._sort_combo)
        sort_row.addStretch()
        root.addLayout(sort_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(_THUMB_SIZE, _THUMB_SIZE))
        self._list.setGridSize(QSize(_GRID_WIDTH, _GRID_HEIGHT))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
            if self._allow_multiple
            else QListWidget.SelectionMode.SingleSelection
        )
        self._list.setWordWrap(True)
        self._list.setUniformItemSizes(True)
        self._list.setSpacing(8)
        self._list.setStyleSheet(
            """
            QListWidget::item {
                border: 2px solid transparent;
                border-radius: 4px;
                padding: 2px;
            }
            QListWidget::item:selected {
                border: 2px solid palette(highlight);
                background: palette(midlight);
            }
            QListWidget::item:hover {
                border: 2px solid palette(mid);
            }
            """
        )
        left_layout.addWidget(self._list)
        self._empty_label = QLabel(PHOTO_PICKER_EMPTY)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setObjectName("InfoText")
        self._empty_label.hide()
        left_layout.addWidget(self._empty_label)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        self._info_name = QLabel("—")
        self._info_name.setWordWrap(True)
        self._info_name.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        font = self._info_name.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize() + 2, 12))
        self._info_name.setFont(font)
        right_layout.addWidget(self._info_name)

        self._info_dims = QLabel("Rozměry: —")
        self._info_size = QLabel("Velikost: —")
        self._info_mtime = QLabel("Změněno: —")
        self._info_taken = QLabel("Pořízeno: —")
        for label in (
            self._info_dims,
            self._info_size,
            self._info_mtime,
            self._info_taken,
        ):
            right_layout.addWidget(label)

        rotate_row = QHBoxLayout()
        self._rotate_left_btn = QPushButton(PHOTO_PICKER_ROTATE_LEFT_LABEL)
        self._rotate_right_btn = QPushButton(PHOTO_PICKER_ROTATE_RIGHT_LABEL)
        self._rotate_left_btn.setEnabled(False)
        self._rotate_right_btn.setEnabled(False)
        rotate_row.addWidget(self._rotate_left_btn)
        rotate_row.addWidget(self._rotate_right_btn)
        rotate_row.addStretch()
        right_layout.addLayout(rotate_row)

        self._rotate_hint = QLabel("")
        self._rotate_hint.setObjectName("InfoText")
        self._rotate_hint.setWordWrap(True)
        self._rotate_hint.hide()
        right_layout.addWidget(self._rotate_hint)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(280, 280)
        self._preview.setText("Vyberte fotografii")
        self._preview.setObjectName("InfoText")
        right_layout.addWidget(self._preview, 1)
        right_layout.addStretch(0)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        buttons = QDialogButtonBox()
        self._cancel_btn = buttons.addButton(
            PHOTO_PICKER_CANCEL_LABEL, QDialogButtonBox.ButtonRole.RejectRole
        )
        self._select_btn = buttons.addButton(
            PHOTO_PICKER_SELECT_MULTI_LABEL
            if self._allow_multiple
            else PHOTO_PICKER_SELECT_LABEL,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self._select_btn.setEnabled(False)
        self._select_btn.setDefault(True)
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._up_btn.clicked.connect(self._go_up)
        self._browse_btn.clicked.connect(self._browse_folder)
        self._refresh_btn.clicked.connect(self._refresh)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._rotate_left_btn.clicked.connect(lambda: self._rotate_selected(-90))
        self._rotate_right_btn.clicked.connect(lambda: self._rotate_selected(90))

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.reject)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self._accept_selection)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self._accept_selection)

    def _build_placeholder_icon(self) -> QIcon:
        pixmap = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
        pixmap.fill(Qt.GlobalColor.lightGray)
        return QIcon(pixmap)

    def _load_directory(self, directory: Path) -> None:
        self._generation += 1
        generation = self._generation
        self._directory = directory.resolve() if directory.is_dir() else default_pictures_directory()
        self._path_label.setText(str(self._directory))
        self._up_btn.setEnabled(self._directory.parent != self._directory)
        self._list.clear()
        self._selected_path = None
        self._selected_paths = []
        self._select_btn.setEnabled(False)
        self._clear_preview()

        files = list_photo_files(self._directory)
        files = self._sorted_files(files)
        self._empty_label.setVisible(not files)
        self._list.setVisible(bool(files))

        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            item = QListWidgetItem(self._placeholder_icon, self._elide_name(path.name))
            item.setData(_ROLE_PATH, str(path.resolve()))
            item.setData(_ROLE_MTIME, int(stat.st_mtime_ns))
            item.setData(_ROLE_SIZE, int(stat.st_size))
            item.setData(_ROLE_PREVIEW_OK, False)
            item.setToolTip(f"{path.name}\n{path}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self._list.addItem(item)
            self._enqueue_thumbnail(generation, path, stat.st_mtime_ns, stat.st_size)

        QApplication.processEvents()

    def _sorted_files(self, files: list[Path]) -> list[Path]:
        if self._sort_mode == SORT_DATE_NEWEST:
            return sorted(
                files,
                key=lambda p: (self._safe_mtime(p), p.name.casefold()),
                reverse=True,
            )
        if self._sort_mode == SORT_DATE_OLDEST:
            return sorted(
                files,
                key=lambda p: (self._safe_mtime(p), p.name.casefold()),
            )
        return sorted(files, key=lambda p: p.name.casefold())

    @staticmethod
    def _safe_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    @staticmethod
    def _elide_name(name: str, limit: int = 26) -> str:
        if len(name) <= limit:
            return name
        stem = Path(name).stem
        suffix = Path(name).suffix
        keep = max(4, limit - len(suffix) - 1)
        if len(stem) <= keep:
            return name[: limit - 1] + "…"
        return stem[:keep] + "…" + suffix

    def _enqueue_thumbnail(
        self,
        generation: int,
        path: Path,
        mtime_ns: int,
        size: int,
    ) -> None:
        key = _CacheKey(str(path.resolve()), mtime_ns, size)
        cached = self._thumb_cache.get(key)
        if cached is not None:
            pixmap, preview_ok = cached
            self._apply_thumbnail(generation, str(path.resolve()), pixmap, preview_ok)
            return

        job = _ThumbnailJob(
            generation=generation,
            path=path,
            mtime_ns=mtime_ns,
            size=size,
        )
        job.signals.finished.connect(self._on_thumbnail_finished)
        self._pool.start(job)

    @Slot(int, str, object, bool)
    def _on_thumbnail_finished(
        self,
        generation: int,
        path_text: str,
        image: object,
        preview_ok: bool,
    ) -> None:
        if generation != self._generation:
            return
        pixmap: QPixmap | None = None
        if isinstance(image, QImage) and not image.isNull():
            pixmap = QPixmap.fromImage(image)
        try:
            path = Path(path_text)
            stat = path.stat()
            key = _CacheKey(path_text, int(stat.st_mtime_ns), int(stat.st_size))
            self._thumb_cache[key] = (pixmap, preview_ok)
        except OSError:
            pass
        self._apply_thumbnail(generation, path_text, pixmap, preview_ok)

    def _apply_thumbnail(
        self,
        generation: int,
        path_text: str,
        pixmap: QPixmap | None,
        preview_ok: bool,
    ) -> None:
        if generation != self._generation:
            return
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is None or item.data(_ROLE_PATH) != path_text:
                continue
            item.setData(_ROLE_PREVIEW_OK, bool(preview_ok))
            if pixmap is not None and not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
            else:
                item.setIcon(self._placeholder_icon)
            break
        current = self._list.currentItem()
        if current is not None and current.data(_ROLE_PATH) == path_text:
            self._update_preview_for_item(current)

    def _go_up(self) -> None:
        parent = self._directory.parent
        if parent != self._directory:
            self._load_directory(parent)

    def _browse_folder(self) -> None:
        selected = choose_existing_directory(
            self,
            PHOTO_FOLDER_DIALOG_TITLE,
            str(self._directory),
        )
        if selected:
            self._load_directory(Path(selected))

    def _refresh(self) -> None:
        self._load_directory(self._directory)

    def _on_sort_changed(self) -> None:
        self._sort_mode = str(self._sort_combo.currentData() or SORT_NAME)
        # Přerovnat položky bez opětovného načítání náhledů.
        items: list[QListWidgetItem] = []
        while self._list.count():
            items.append(self._list.takeItem(0))

        def sort_key(item: QListWidgetItem):
            path = Path(str(item.data(_ROLE_PATH) or ""))
            mtime = float(item.data(_ROLE_MTIME) or 0) / 1_000_000_000.0
            name = path.name.casefold()
            if self._sort_mode == SORT_DATE_NEWEST:
                return (-mtime, name)
            if self._sort_mode == SORT_DATE_OLDEST:
                return (mtime, name)
            return (name,)

        for item in sorted(items, key=sort_key):
            self._list.addItem(item)

    def _on_selection_changed(self) -> None:
        item = self._list.currentItem()
        self._sync_selected_paths()
        self._update_preview_for_item(item)

    def _item_is_selectable(self, item: QListWidgetItem) -> bool:
        path = Path(str(item.data(_ROLE_PATH) or ""))
        if not path.is_file():
            return False
        suffix = path.suffix.lower()
        if suffix in _HEIC_EXTENSIONS:
            return True
        if bool(item.data(_ROLE_PREVIEW_OK)):
            return True
        pixmap = QPixmap(str(path))
        return not pixmap.isNull()

    def _sync_selected_paths(self) -> None:
        paths: list[Path] = []
        for item in self._list.selectedItems():
            if not self._item_is_selectable(item):
                continue
            path = Path(str(item.data(_ROLE_PATH) or "")).resolve()
            paths.append(path)
        self._selected_paths = paths
        self._selected_path = paths[0] if paths else None

    def _update_preview_for_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            self._sync_selected_paths()
            self._select_btn.setEnabled(bool(self._selected_paths))
            self._clear_preview()
            return

        path = Path(str(item.data(_ROLE_PATH) or ""))
        preview_ok = bool(item.data(_ROLE_PREVIEW_OK))
        suffix = path.suffix.lower()
        heic = suffix in _HEIC_EXTENSIONS

        self._info_name.setText(path.name)
        try:
            size = int(item.data(_ROLE_SIZE) or path.stat().st_size)
        except OSError:
            size = 0
        self._info_size.setText(f"Velikost: {_format_size(size)}")
        self._info_mtime.setText(f"Změněno: {_format_mtime(path)}")
        taken = _try_capture_date(path)
        self._info_taken.setText(
            f"Pořízeno: {taken}" if taken else "Pořízeno: —"
        )

        pixmap = QPixmap(str(path)) if path.is_file() and not heic else QPixmap()
        if not pixmap.isNull():
            self._info_dims.setText(
                f"Rozměry: {pixmap.width()} × {pixmap.height()} px"
            )
            target = self._preview.size()
            if target.width() < 40 or target.height() < 40:
                target = QSize(360, 360)
            scaled = pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Nezvětšovat malé fotografie.
            if scaled.width() > pixmap.width() or scaled.height() > pixmap.height():
                scaled = pixmap
            self._preview.setPixmap(scaled)
            self._preview.setText("")
            self._sync_selected_paths()
            self._select_btn.setEnabled(bool(self._selected_paths))
            self._update_rotate_controls(path)
            return

        self._info_dims.setText("Rozměry: —")
        self._preview.setPixmap(QPixmap())
        if heic or preview_ok:
            self._preview.setText(PHOTO_PICKER_PREVIEW_UNAVAILABLE)
        else:
            self._preview.setText(PHOTO_PICKER_PREVIEW_BROKEN)
        self._sync_selected_paths()
        self._select_btn.setEnabled(bool(self._selected_paths))
        self._update_rotate_controls(
            path if path.is_file() and (heic or preview_ok or self._item_is_selectable(item)) else None
        )

    def _update_rotate_controls(self, path: Path | None) -> None:
        supported = bool(path is not None and path.is_file() and is_rotation_supported(path))
        self._rotate_left_btn.setEnabled(supported)
        self._rotate_right_btn.setEnabled(supported)
        if path is not None and path.is_file() and not supported:
            self._rotate_hint.setText(PHOTO_PICKER_ROTATE_UNSUPPORTED)
            self._rotate_hint.show()
        else:
            self._rotate_hint.hide()
            self._rotate_hint.clear()

    def _clear_preview(self) -> None:
        self._preview.setPixmap(QPixmap())
        self._preview.setText("Vyberte fotografii")
        self._info_name.setText("—")
        self._info_dims.setText("Rozměry: —")
        self._info_size.setText("Velikost: —")
        self._info_mtime.setText("Změněno: —")
        self._info_taken.setText("Pořízeno: —")
        self._update_rotate_controls(None)

    def _confirm_rotate(self) -> bool:
        if get_skip_rotate_confirm():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(PHOTO_PICKER_ROTATE_CONFIRM_TITLE)
        box.setText(PHOTO_PICKER_ROTATE_CONFIRM_TEXT)
        checkbox = QCheckBox(PHOTO_PICKER_ROTATE_DONT_ASK)
        box.setCheckBox(checkbox)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        answer = box.exec()
        if answer != QMessageBox.StandardButton.Yes:
            return False
        if checkbox.isChecked():
            set_skip_rotate_confirm(True)
        return True

    def _rotate_selected(self, degrees: int) -> None:
        path = self._selected_path
        if path is None or not path.is_file():
            return
        if not is_rotation_supported(path):
            QMessageBox.information(
                self,
                PHOTO_PICKER_ROTATE_ERROR_TITLE,
                PHOTO_PICKER_ROTATE_UNSUPPORTED,
            )
            return
        if not self._confirm_rotate():
            return

        try:
            rotate_photo_file(path, degrees)
        except PhotoRotateError as exc:
            QMessageBox.warning(
                self,
                PHOTO_PICKER_ROTATE_ERROR_TITLE,
                str(exc),
            )
            return

        self._refresh_item_after_rotate(path)

    def _invalidate_thumb_cache_for_path(self, path_text: str) -> None:
        stale = [key for key in self._thumb_cache if key.path == path_text]
        for key in stale:
            del self._thumb_cache[key]

    def _refresh_item_after_rotate(self, path: Path) -> None:
        """Obnoví miniaturu a náhled bez změny výběru / pozice ve výpisu."""
        path_text = str(path.resolve())
        self._invalidate_thumb_cache_for_path(path_text)

        item: QListWidgetItem | None = None
        for index in range(self._list.count()):
            candidate = self._list.item(index)
            if candidate is not None and candidate.data(_ROLE_PATH) == path_text:
                item = candidate
                break
        if item is None:
            return

        try:
            stat = path.stat()
        except OSError:
            self._update_preview_for_item(item)
            return

        item.setData(_ROLE_MTIME, int(stat.st_mtime_ns))
        item.setData(_ROLE_SIZE, int(stat.st_size))

        # Okamžitá obnova miniatury (bez workeru – jen vybraná fotografie).
        pixmap: QPixmap | None = None
        preview_ok = False
        suffix = path.suffix.lower()
        if suffix in _HEIC_EXTENSIONS:
            preview_ok = True
        else:
            loaded = QImage(str(path))
            if not loaded.isNull():
                pixmap = QPixmap.fromImage(fit_image_on_canvas(loaded, _THUMB_SIZE))
                preview_ok = True

        key = _CacheKey(path_text, int(stat.st_mtime_ns), int(stat.st_size))
        self._thumb_cache[key] = (pixmap, preview_ok)
        item.setData(_ROLE_PREVIEW_OK, preview_ok)
        if pixmap is not None and not pixmap.isNull():
            item.setIcon(QIcon(pixmap))
        else:
            item.setIcon(self._placeholder_icon)

        # Zachovat výběr a scroll – jen obnovit náhled.
        if self._list.currentItem() is not item:
            self._list.setCurrentItem(item)
        self._selected_path = path.resolve()
        self._update_preview_for_item(item)
        self._list.scrollToItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._list.setCurrentItem(item)
        if not item.isSelected():
            if not self._allow_multiple:
                self._list.clearSelection()
            item.setSelected(True)
        self._update_preview_for_item(item)
        self._accept_selection()

    def _accept_selection(self) -> None:
        self._sync_selected_paths()
        paths = self.selected_paths()
        if not paths:
            return
        self._selected_paths = paths
        self._selected_path = paths[0]
        set_last_photo_directory(self._directory)
        self.accept()

    def reject(self) -> None:
        self._generation += 1
        self._selected_path = None
        self._selected_paths = []
        super().reject()

    def closeEvent(self, event) -> None:
        self._generation += 1
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        item = self._list.currentItem()
        if item is not None:
            self._update_preview_for_item(item)

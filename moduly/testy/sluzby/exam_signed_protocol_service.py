"""Aktuální podepsaný protokol dokončené zkoušky.

Ukládá se vlastní kopie do příloh. Ke zkoušce vede nejvýše jedna
aktuální vazba. Starší soubory se při výměně ani odebrání nemažou.

Na Unixu drží zápis popisovač adresáře a nesleduje symbolický odkaz.
Na Windows stejný únik zachytí odmítnutí reparse pointů a ověření
skutečné cesty otevřeného souboru.
"""

from __future__ import annotations

import os
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from core.database.session import get_session
from core.models.attachment import Attachment
from core.services.storage_service import storage_service
from core.utils.confined_path import require_confined_path
from moduly.testy.constants import EXAM_STATUS_COMPLETED
from moduly.testy.modely.test_exam import TestExam

ENTITY_TYPE = "test_exam_protocol"
_PDF_HEADER = b"%PDF-"
_PDF_EOF = b"%%EOF"
_TAIL_BYTES = 8192
_MAX_PROTOCOL_BYTES = 20 * 1024 * 1024
_MAX_TRAILING_AFTER_EOF = 1024
_PDF_WHITESPACE = b"\x00\t\n\f\r "
_SIZE_MESSAGE = "Podepsaný protokol nesmí být větší než 20 MB."
_INVALID_PDF_MESSAGE = (
    "Soubor není platné PDF. Nestačí změnit příponu, "
    "dokument musí mít platný formát PDF."
)


class ExamSignedProtocolError(Exception):
    """Srozumitelná chyba pro uživatele. Zkoušku ani její výsledek nemění."""


@dataclass(frozen=True)
class SignedProtocolState:
    attached: bool
    attachment_id: int | None


class ExamSignedProtocolService:
    def describe(self, exam_id: int) -> SignedProtocolState:
        exam = self._exam(exam_id)
        attachment_id = exam.signed_protocol_attachment_id
        if not attachment_id:
            return SignedProtocolState(attached=False, attachment_id=None)
        attachment = self._attachment(int(attachment_id))
        if attachment is None or not self._belongs_to_exam(attachment, exam.id):
            return SignedProtocolState(attached=False, attachment_id=None)
        return SignedProtocolState(attached=True, attachment_id=int(attachment.id))

    def attach(self, exam_id: int, source_path: str | Path) -> int:
        """Připojí PDF. Zkouška už protokol mít nesmí."""
        return self._assign(exam_id, source_path, replace=False)

    def replace(self, exam_id: int, source_path: str | Path) -> int:
        """Uloží a ověří novou kopii, teprve potom změní vazbu."""
        return self._assign(exam_id, source_path, replace=True)

    def detach(self, exam_id: int) -> None:
        """Zruší jen aktuální vazbu. Soubor ani řádek přílohy nemaže."""
        exam = self._exam(exam_id)
        if not exam.signed_protocol_attachment_id:
            raise ExamSignedProtocolError("K této zkoušce není připojen žádný protokol.")
        with get_session() as session:
            stored = session.get(TestExam, int(exam.id))
            if stored is None:
                raise ExamSignedProtocolError("Zkouška nebyla nalezena.")
            stored.signed_protocol_attachment_id = None
            session.commit()

    def validated_copy_path(self, exam_id: int) -> Path:
        """Cesta k uložené kopii. Ověří, že soubor existuje a je čitelné PDF."""
        exam = self._exam(exam_id)
        attachment_id = exam.signed_protocol_attachment_id
        if not attachment_id:
            raise ExamSignedProtocolError("K této zkoušce není připojen žádný protokol.")
        attachment = self._attachment(int(attachment_id))
        if attachment is None or not self._belongs_to_exam(attachment, exam.id):
            raise ExamSignedProtocolError("Uložený protokol nebyl nalezen.")
        try:
            path = require_confined_path(
                storage_service.attachments_dir,
                attachment.stored_path,
                message="Uložený protokol nebyl nalezen.",
            )
        except ValueError as exc:
            raise ExamSignedProtocolError("Uložený protokol nebyl nalezen.") from exc
        if not path.is_file():
            raise ExamSignedProtocolError(
                "Uložený protokol nebyl nalezen. Soubor v úložišti chybí."
            )
        try:
            _assert_pdf(path)
        except ExamSignedProtocolError as exc:
            raise ExamSignedProtocolError(
                "Uložený protokol je poškozený a nelze ho otevřít."
            ) from exc
        return path

    def _assign(self, exam_id: int, source_path: str | Path, *, replace: bool) -> int:
        exam = self._exam(exam_id)
        self._require_completed(exam)
        previous_id = (
            int(exam.signed_protocol_attachment_id)
            if exam.signed_protocol_attachment_id
            else None
        )
        if replace and previous_id is None:
            raise ExamSignedProtocolError("K této zkoušce není připojen žádný protokol.")
        if not replace and previous_id is not None:
            raise ExamSignedProtocolError(
                "K této zkoušce je už podepsaný protokol připojen."
            )
        source = _require_source_pdf(source_path)
        copied = self._copy_into_storage(int(exam.id), source)
        try:
            _assert_stored_pdf(copied)
            attachment_id = self._link(int(exam.id), source, copied, replace=replace)
        except ExamSignedProtocolError:
            copied.discard()
            raise
        except Exception:
            copied.discard()
            if replace and previous_id is not None:
                raise ExamSignedProtocolError(
                    "Nový protokol se nepodařilo přiřadit. "
                    "Původní protokol zůstal dostupný."
                ) from None
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from None
        copied.close()
        return attachment_id

    def _copy_into_storage(self, exam_id: int, source: Path) -> "_NewProtocolFile":
        """Uloží PDF do příloh, aniž by sledovalo symbolický odkaz."""
        if _directory_fds_available():
            return self._copy_into_storage_fds(exam_id, source)
        return self._copy_into_storage_paths(exam_id, source)

    def _copy_into_storage_fds(self, exam_id: int, source: Path) -> "_NewProtocolFile":
        filename = _safe_component(f"protokol-{uuid.uuid4().hex}.pdf")
        entity = _safe_component(ENTITY_TYPE)
        exam_part = _safe_component(str(int(exam_id)))
        relative = f"{entity}/{exam_part}/{filename}"
        root_fd = _open_directory(storage_service.attachments_dir)
        entity_fd = None
        exam_fd = None
        try:
            entity_fd = _open_or_make_directory(root_fd, entity)
            exam_fd = _open_or_make_directory(entity_fd, exam_part)
            dev, ino = _create_protocol_file(exam_fd, filename, source)
            stored = _NewProtocolFile(
                relative=relative,
                name=filename,
                directory=_FdDirectory(exam_fd),
                dev=dev,
                ino=ino,
            )
            exam_fd = None
            return stored
        except ExamSignedProtocolError:
            raise
        except OSError as exc:
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
        finally:
            if exam_fd is not None:
                os.close(exam_fd)
            if entity_fd is not None:
                os.close(entity_fd)
            os.close(root_fd)

    def _copy_into_storage_paths(self, exam_id: int, source: Path) -> "_NewProtocolFile":
        """Zápis bez dir_fd. Reparse point ani cesta mimo přílohy neprojde."""
        filename = _safe_component(f"protokol-{uuid.uuid4().hex}.pdf")
        entity = _safe_component(ENTITY_TYPE)
        exam_part = _safe_component(str(int(exam_id)))
        relative = f"{entity}/{exam_part}/{filename}"
        root = storage_service.attachments_dir
        try:
            if not _components_are_real(root, root):
                raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
            entity_dir = _make_real_directory(root, entity, root)
            exam_dir = _make_real_directory(entity_dir, exam_part, root)
            dev, ino = _create_protocol_file_at(
                exam_dir, filename, source, root, relative
            )
        except ExamSignedProtocolError:
            raise
        except OSError as exc:
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
        return _NewProtocolFile(
            relative=relative,
            name=filename,
            directory=_PathDirectory(exam_dir, root, f"{entity}/{exam_part}"),
            dev=dev,
            ino=ino,
        )

    def _link(
        self,
        exam_id: int,
        source: Path,
        copied: "_NewProtocolFile",
        *,
        replace: bool,
    ) -> int:
        relative = copied.relative
        require_confined_path(
            storage_service.attachments_dir,
            relative,
            message="Protokol se nepodařilo uložit.",
        )
        original = str(source)
        if len(original) > 500:
            original = original[:500]
        with get_session() as session:
            stored = session.get(TestExam, exam_id)
            if stored is None:
                raise ExamSignedProtocolError("Zkouška nebyla nalezena.")
            if stored.status != EXAM_STATUS_COMPLETED:
                raise ExamSignedProtocolError(
                    "Podepsaný protokol lze připojit jen k dokončené zkoušce."
                )
            current = stored.signed_protocol_attachment_id
            if replace and not current:
                raise ExamSignedProtocolError(
                    "K této zkoušce není připojen žádný protokol."
                )
            if not replace and current:
                raise ExamSignedProtocolError(
                    "K této zkoušce je už podepsaný protokol připojen."
                )
            attachment = Attachment(
                entity_type=ENTITY_TYPE,
                entity_id=exam_id,
                original_path=original,
                stored_path=relative,
                filename=copied.name,
            )
            session.add(attachment)
            session.flush()
            stored.signed_protocol_attachment_id = int(attachment.id)
            session.commit()
            return int(attachment.id)

    def _exam(self, exam_id: int) -> TestExam:
        with get_session() as session:
            exam = session.get(TestExam, int(exam_id))
            if exam is None:
                raise ExamSignedProtocolError("Zkouška nebyla nalezena.")
            session.expunge(exam)
            return exam

    def _attachment(self, attachment_id: int) -> Attachment | None:
        with get_session() as session:
            attachment = session.get(Attachment, int(attachment_id))
            if attachment is not None:
                session.expunge(attachment)
            return attachment

    def _belongs_to_exam(self, attachment: Attachment, exam_id: int) -> bool:
        return (
            attachment.entity_type == ENTITY_TYPE
            and int(attachment.entity_id) == int(exam_id)
        )

    def _require_completed(self, exam: TestExam) -> None:
        if exam.status != EXAM_STATUS_COMPLETED:
            raise ExamSignedProtocolError(
                "Podepsaný protokol lze připojit jen k dokončené zkoušce."
            )


def _require_source_pdf(source_path: str | Path) -> Path:
    source = Path(source_path)
    try:
        info = source.lstat()
    except FileNotFoundError as exc:
        raise ExamSignedProtocolError("Vybraný soubor neexistuje.") from exc
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    if stat.S_ISLNK(info.st_mode):
        raise ExamSignedProtocolError("Symbolický odkaz nelze použít jako protokol.")
    if stat.S_ISDIR(info.st_mode):
        raise ExamSignedProtocolError("Vyberte soubor PDF, ne adresář.")
    if not stat.S_ISREG(info.st_mode):
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.")
    if info.st_size > _MAX_PROTOCOL_BYTES:
        raise ExamSignedProtocolError(_SIZE_MESSAGE)
    try:
        _assert_new_pdf(source)
    except ExamSignedProtocolError:
        raise
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    return source


def _assert_pdf(path: Path) -> None:
    """Kontrola už uloženého protokolu. Nová přísnější pravidla se tu neaplikují."""
    try:
        with path.open("rb") as handle:
            header = handle.read(len(_PDF_HEADER))
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - _TAIL_BYTES))
            tail = handle.read()
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    if not header.startswith(_PDF_HEADER) or _PDF_EOF not in tail:
        raise ExamSignedProtocolError(_INVALID_PDF_MESSAGE)


def _assert_new_pdf(path: Path) -> None:
    """Hlavička, konec a velikost nově připojovaného PDF. Obsah se nespouští."""
    try:
        with path.open("rb") as handle:
            header = handle.read(len(_PDF_HEADER))
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size > _MAX_PROTOCOL_BYTES:
                raise ExamSignedProtocolError(_SIZE_MESSAGE)
            window = len(_PDF_EOF) + _MAX_TRAILING_AFTER_EOF
            handle.seek(max(0, size - window), os.SEEK_SET)
            tail = handle.read(window)
    except ExamSignedProtocolError:
        raise
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    _require_strict_pdf(header, tail, size)


def _require_strict_pdf(header: bytes, tail: bytes, size: int) -> None:
    if size <= 0 or not header.startswith(_PDF_HEADER):
        raise ExamSignedProtocolError(_INVALID_PDF_MESSAGE)
    index = tail.rfind(_PDF_EOF)
    if index < 0:
        raise ExamSignedProtocolError(_INVALID_PDF_MESSAGE)
    trailing = tail[index + len(_PDF_EOF) :]
    if any(byte not in _PDF_WHITESPACE for byte in trailing):
        raise ExamSignedProtocolError(_INVALID_PDF_MESSAGE)


@dataclass
class _NewProtocolFile:
    """Nový soubor držený adresářem, ve kterém vznikl."""

    relative: str
    name: str
    directory: "_FdDirectory | _PathDirectory"
    dev: int
    ino: int
    closed: bool = False

    def discard(self) -> None:
        """Smaže jen tento inode. Symbolický odkaz ani cizí soubor ne."""
        try:
            if not self.closed:
                self.directory.unlink_matching(self.name, self.dev, self.ino)
        finally:
            self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.directory.close()


def _nofollow_available() -> bool:
    return hasattr(os, "O_NOFOLLOW")


# Původní funkce. Testy obalují os.open a členství v supports_dir_fd
# se pak nesmí vyhodnotit podle obalu.
_OS_OPEN = os.open
_OS_MKDIR = os.mkdir
_OS_UNLINK = os.unlink


def _directory_fds_available() -> bool:
    """Unixový openat s O_DIRECTORY a O_NOFOLLOW. Na Windows je False."""
    if not _nofollow_available():
        return False
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_CLOEXEC"):
        return False
    supported = getattr(os, "supports_dir_fd", ())
    return _OS_OPEN in supported and _OS_MKDIR in supported and _OS_UNLINK in supported


def _cloexec_flag() -> int:
    return getattr(os, "O_CLOEXEC", 0) or getattr(os, "O_NOINHERIT", 0)


def _readonly_flags() -> int:
    flags = os.O_RDONLY | _cloexec_flag() | getattr(os, "O_BINARY", 0)
    if _nofollow_available():
        flags |= os.O_NOFOLLOW
    return flags


def _create_flags() -> int:
    flags = (
        os.O_CREAT
        | os.O_EXCL
        | os.O_WRONLY
        | _cloexec_flag()
        | getattr(os, "O_BINARY", 0)
    )
    if _nofollow_available():
        flags |= os.O_NOFOLLOW
    return flags


def _dir_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _is_reparse_point(info: os.stat_result) -> bool:
    """Symbolický odkaz i windowsový junction / mount point."""
    if stat.S_ISLNK(getattr(info, "st_mode", 0)):
        return True
    attributes = getattr(info, "st_file_attributes", 0) or 0
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(int(attributes) & int(marker))


def _safe_component(name: str) -> str:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
    return name


class _FdDirectory:
    """Adresář držený popisovačem. Výměna názvu za odkaz zápis nepřesměruje."""

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self.closed = False

    def open_read(self, name: str) -> int:
        return os.open(name, _readonly_flags(), dir_fd=self._fd)

    def unlink_matching(self, name: str, dev: int, ino: int) -> None:
        _unlink_matching(self._fd, name, dev, ino)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            os.close(self._fd)
        except OSError:
            return


class _PathDirectory:
    """Adresář podle cesty. Každá složka musí být skutečný adresář v přílohách."""

    def __init__(self, path: Path, root: Path, relative_dir: str) -> None:
        self.path = path
        self.root = root
        self.relative_dir = relative_dir
        self.closed = False

    def open_read(self, name: str) -> int:
        _safe_component(name)
        if not _components_are_real(self.path, self.root):
            raise OSError(self.path)
        full = self.path / name
        before = full.lstat()
        if _is_reparse_point(before) or not stat.S_ISREG(before.st_mode) or before.st_ino == 0:
            raise OSError(full)
        fd = os.open(full, _readonly_flags())
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_ino == 0
                or info.st_dev != before.st_dev
                or info.st_ino != before.st_ino
                or not _descriptor_is_relative(fd, self.root, f"{self.relative_dir}/{name}")
            ):
                raise OSError(full)
        except Exception:
            os.close(fd)
            raise
        return fd

    def unlink_matching(self, name: str, dev: int, ino: int) -> None:
        try:
            _safe_component(name)
        except ExamSignedProtocolError:
            return
        _unlink_matching_inodes([self.path / name], dev, ino)

    def close(self) -> None:
        self.closed = True


def _open_directory(path: Path) -> int:
    try:
        return os.open(path, _dir_flags())
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc


def _open_or_make_directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, dir_fd=parent_fd)
    except FileExistsError:
        pass
    try:
        return os.open(name, _dir_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc


def _create_protocol_file(dir_fd: int, name: str, source: Path) -> tuple[int, int]:
    try:
        fd = os.open(name, _create_flags(), 0o644, dir_fd=dir_fd)
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    info = None
    try:
        info = os.fstat(fd)
        _stream_regular_file(source, fd)
    except ExamSignedProtocolError:
        os.close(fd)
        if info is not None:
            _unlink_matching(dir_fd, name, info.st_dev, info.st_ino)
        raise
    except OSError as exc:
        os.close(fd)
        if info is not None:
            _unlink_matching(dir_fd, name, info.st_dev, info.st_ino)
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    os.close(fd)
    return info.st_dev, info.st_ino


def _components_are_real(path: Path, root: Path) -> bool:
    """Každá složka od kořene příloh je adresář a není to reparse point."""
    try:
        relative = Path() if path == root else path.relative_to(root)
    except ValueError:
        return False
    current = root
    for part in (relative.parts if relative.parts != (".",) else ()):
        if part in {".", ".."}:
            return False
        try:
            info = current.lstat()
        except OSError:
            return False
        if _is_reparse_point(info) or not stat.S_ISDIR(info.st_mode):
            return False
        current = current / part
    try:
        info = current.lstat()
        if _is_reparse_point(info) or not stat.S_ISDIR(info.st_mode):
            return False
        current.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _make_real_directory(parent: Path, name: str, root: Path) -> Path:
    _safe_component(name)
    if not _components_are_real(parent, root):
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
    target = parent / name
    created = False
    try:
        target.lstat()
    except FileNotFoundError:
        try:
            os.mkdir(target)
            created = True
        except FileExistsError:
            created = False
        except OSError as exc:
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    if not _components_are_real(target, root):
        if created:
            _remove_empty_directory(target)
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
    return target


def _remove_empty_directory(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError:
        return
    if _is_reparse_point(info) or not stat.S_ISDIR(info.st_mode):
        return
    try:
        os.rmdir(path)
    except OSError:
        return


def _create_protocol_file_at(
    directory: Path,
    name: str,
    source: Path,
    root: Path,
    relative: str,
) -> tuple[int, int]:
    _safe_component(name)
    if not _components_are_real(directory, root):
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
    full = directory / name
    try:
        fd = os.open(full, _create_flags(), 0o644)
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    info = None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_ino == 0:
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
        if not _descriptor_is_relative(fd, root, relative):
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
        _stream_regular_file(source, fd)
        if not _descriptor_is_relative(fd, root, relative):
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
    except ExamSignedProtocolError:
        located = _descriptor_path(fd) if info is not None else None
        os.close(fd)
        if info is not None:
            _unlink_matching_inodes([full, located], info.st_dev, info.st_ino)
        raise
    except OSError as exc:
        located = _descriptor_path(fd) if info is not None else None
        os.close(fd)
        if info is not None:
            _unlink_matching_inodes([full, located], info.st_dev, info.st_ino)
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    os.close(fd)
    return info.st_dev, info.st_ino


def _descriptor_path(fd: int) -> Path | None:
    """Skutečná cesta otevřeného popisovače. Nové vyhledání názvu nedělá."""
    if os.name == "nt":
        return _windows_final_path(fd)
    try:
        target = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return None
    suffix = " (deleted)"
    if target.endswith(suffix):
        target = target[: -len(suffix)]
    if not target:
        return None
    return Path(os.path.normpath(target))


def _windows_final_path(fd: int) -> Path | None:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    try:
        handle = msvcrt.get_osfhandle(fd)
    except OSError:
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    size = 32768
    buffer = ctypes.create_unicode_buffer(size)
    length = kernel32.GetFinalPathNameByHandleW(handle, buffer, size, 0)
    if length == 0 or length >= size:
        return None
    raw = buffer.value
    if raw.startswith("\\\\?\\UNC\\"):
        raw = "\\\\" + raw[8:]
    elif raw.startswith("\\\\?\\"):
        raw = raw[4:]
    if not raw:
        return None
    return Path(os.path.normpath(raw))


def _descriptor_is_relative(fd: int, root: Path, relative: str) -> bool:
    """Popisovač musí být přesně ``root/relative``, ne cíl odkazu."""
    located = _descriptor_path(fd)
    if located is None:
        return False
    try:
        root_real = Path(os.path.realpath(root))
        actual = Path(os.path.normpath(located)).relative_to(root_real)
    except (OSError, ValueError):
        return False
    expected = Path(relative).as_posix()
    return os.path.normcase(actual.as_posix()) == os.path.normcase(expected)


def _unlink_matching_inodes(candidates: list[Path | None], dev: int, ino: int) -> None:
    """Smaže jen inode právě vytvořeného běžného souboru."""
    if ino == 0:
        return
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = os.path.normcase(os.path.normpath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        try:
            info = os.lstat(candidate)
        except OSError:
            continue
        if _is_reparse_point(info) or not stat.S_ISREG(info.st_mode):
            continue
        if info.st_dev != dev or info.st_ino != ino:
            continue
        try:
            os.unlink(candidate)
        except OSError:
            continue
        return


def _stream_regular_file(source: Path, destination_fd: int) -> None:
    try:
        src = _open_source_fd(source)
    except ExamSignedProtocolError:
        raise
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    try:
        total = 0
        while True:
            chunk = os.read(src, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_PROTOCOL_BYTES:
                raise ExamSignedProtocolError(_SIZE_MESSAGE)
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                if written <= 0:
                    raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
                view = view[written:]
        if total <= 0:
            raise ExamSignedProtocolError(_INVALID_PDF_MESSAGE)
    except ExamSignedProtocolError:
        raise
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    finally:
        os.close(src)


def _read_exact(fd: int, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = os.read(fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _open_source_fd(source: Path) -> int:
    if _nofollow_available():
        return os.open(source, _readonly_flags())
    try:
        before = source.lstat()
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    if _is_reparse_point(before) or not stat.S_ISREG(before.st_mode) or before.st_ino == 0:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.")
    try:
        fd = os.open(source, _readonly_flags())
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    try:
        opened = os.fstat(fd)
        after = source.lstat()
    except OSError as exc:
        os.close(fd)
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    if (
        _is_reparse_point(after)
        or not stat.S_ISREG(opened.st_mode)
        or opened.st_ino == 0
        or opened.st_dev != before.st_dev
        or opened.st_ino != before.st_ino
        or after.st_dev != before.st_dev
        or after.st_ino != before.st_ino
    ):
        os.close(fd)
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.")
    return fd


def _unlink_matching(dir_fd: int, name: str, dev: int, ino: int) -> None:
    """Smaže název jen tehdy, když je to běžný soubor se stejným inode."""
    try:
        fd = os.open(name, _readonly_flags(), dir_fd=dir_fd)
    except OSError:
        return
    try:
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode) and info.st_dev == dev and info.st_ino == ino:
            os.unlink(name, dir_fd=dir_fd)
    except OSError:
        return
    finally:
        os.close(fd)


def _assert_stored_pdf(copied: _NewProtocolFile) -> None:
    try:
        fd = copied.directory.open_read(copied.name)
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    try:
        info = os.fstat(fd)
        if (
            info.st_dev != copied.dev
            or info.st_ino != copied.ino
            or not stat.S_ISREG(info.st_mode)
        ):
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.")
        if info.st_size > _MAX_PROTOCOL_BYTES:
            raise ExamSignedProtocolError(_SIZE_MESSAGE)
        header = os.read(fd, len(_PDF_HEADER))
        window = len(_PDF_EOF) + _MAX_TRAILING_AFTER_EOF
        os.lseek(fd, max(0, info.st_size - window), os.SEEK_SET)
        tail = _read_exact(fd, min(info.st_size, window))
    except ExamSignedProtocolError:
        raise
    except OSError as exc:
        raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
    finally:
        os.close(fd)
    _require_strict_pdf(header, tail, info.st_size)


exam_signed_protocol_service = ExamSignedProtocolService()

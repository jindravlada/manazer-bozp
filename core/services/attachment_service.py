from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

import shutil

from sqlalchemy.orm import Session

from core.database.session import get_session
from core.models.attachment import Attachment
from core.models.attachment_staging import (
    AttachmentStagingError,
    AttachmentStagingState,
    PreparedAttachmentChanges,
)
from core.repositories.attachment_repository import AttachmentRepository
from core.services.photo_optimization import optimize_image_bytes
from core.services.storage_service import storage_service
from core.utils.confined_path import resolve_confined_path

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

_FILENAME_DB_LIMIT = 255
_FILENAME_BYTE_LIMIT = 255
_ORIGINAL_PATH_LIMIT = 500
_STORED_PATH_LIMIT = 500


class AttachmentService:
    def __init__(self):
        self.repository = AttachmentRepository()

    def get_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        *,
        session: Session | None = None,
    ):
        if not entity_id:
            return []
        return self.repository.get_for_entity(
            entity_type, entity_id, session=session
        )

    def add_file(self, entity_type: str, entity_id: int, source_path: str):
        source = Path(source_path)
        return self.add_file_as(entity_type, entity_id, source_path, source.name)

    def add_file_as(self, entity_type: str, entity_id: int, source_path: str, target_filename: str):
        source = Path(source_path)

        if not source.exists() or not entity_id:
            return None

        try:
            type_value = _require_entity_type(entity_type)
            ident = _require_entity_id(entity_id)
        except AttachmentStagingError:
            return None

        safe_name = _safe_filename(target_filename)
        target_dir = storage_service.attachment_dir(type_value, ident)
        try:
            _assert_under_attachments_root(target_dir)
        except AttachmentStagingError:
            return None

        target = self._unique_target(target_dir / safe_name)
        try:
            _assert_under_attachments_root(target)
        except AttachmentStagingError:
            return None

        target, stored_name = self._store_source_file(source, target)
        try:
            _assert_under_attachments_root(target)
            relative_path = target.resolve().relative_to(_attachments_root()).as_posix()
        except (AttachmentStagingError, ValueError):
            return None

        attachment = Attachment(
            entity_type=type_value,
            entity_id=ident,
            original_path=str(source),
            stored_path=relative_path,
            filename=stored_name,
        )

        return self.repository.add(attachment)

    def resolve_path(self, attachment) -> Path:
        return storage_service.attachment_absolute(attachment.stored_path)

    def delete(self, attachment_id: int):
        """Okamžitý DELETE DB řádku. Fyzický soubor se nemaže."""
        return self.repository.delete(attachment_id)

    def rebind_entity(
        self,
        old_entity_type: str,
        old_entity_id: int,
        new_entity_type: str,
        new_entity_id: int,
    ) -> int:
        """Přesune přílohy na jinou entitu (DB + soubory). Vrací počet přesunů."""
        if not old_entity_id or not new_entity_id:
            return 0
        if (
            old_entity_type == new_entity_type
            and int(old_entity_id) == int(new_entity_id)
        ):
            return 0

        try:
            new_type = _require_entity_type(new_entity_type)
            new_ident = _require_entity_id(new_entity_id)
        except AttachmentStagingError:
            return 0

        moved = 0
        for attachment in list(
            self.repository.get_for_entity(old_entity_type, old_entity_id)
        ):
            old_path = resolve_confined_path(
                _attachments_root(), attachment.stored_path
            )
            if old_path is None:
                logger.warning(
                    "Příloha %s má cestu mimo prilohy, přesun se přeskočil: %s",
                    attachment.id,
                    attachment.stored_path,
                )
                continue
            target_dir = storage_service.attachment_dir(new_type, new_ident)
            try:
                _assert_under_attachments_root(target_dir)
            except AttachmentStagingError:
                continue
            filename = _safe_filename(
                attachment.filename or old_path.name or f"attachment-{attachment.id}"
            )
            target = self._unique_target(target_dir / filename)
            try:
                _assert_under_attachments_root(target)
            except AttachmentStagingError:
                continue
            if old_path.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(target))
            try:
                relative_path = target.resolve().relative_to(_attachments_root()).as_posix()
            except ValueError:
                continue
            attachment.entity_type = new_type
            attachment.entity_id = new_ident
            attachment.stored_path = relative_path
            attachment.filename = target.name
            self.repository.update(attachment)
            moved += 1
        return moved

    def prepare_attachment_staging(
        self,
        entity_type: str,
        entity_id: int,
        staging: AttachmentStagingState,
        session: Session,
    ) -> PreparedAttachmentChanges:
        """Zkopíruje nové soubory a zapíše DB změny do caller-owned session.

        Fyzické soubory odebíraných příloh se ještě nemažou. Session se
        necommituje. Při chybě uklidí už zkopírované soubory této dávky
        a původní výjimku znovu vyhodí.
        """
        type_value = _require_entity_type(entity_type)
        ident = _require_entity_id(entity_id)
        if session is None:
            raise AttachmentStagingError("prepare_attachment_staging vyžaduje session.")

        pending_unlink: list[Path] = []
        for attachment_id in list(staging.pending_remove_ids):
            record = self.repository.get_by_id(int(attachment_id), session=session)
            if record is None:
                raise AttachmentStagingError(
                    f"Příloha {attachment_id} neexistuje."
                )
            if (
                str(record.entity_type) != type_value
                or int(record.entity_id) != ident
            ):
                raise AttachmentStagingError(
                    "Příloha nepatří k ukládanému záznamu."
                )
            confined = resolve_confined_path(_attachments_root(), record.stored_path)
            if confined is None:
                logger.warning(
                    "Příloha %s má cestu mimo prilohy, soubor se nesmaže: %s",
                    record.id,
                    record.stored_path,
                )
            else:
                pending_unlink.append(confined)

        sources = [_validate_source_file(path) for path in staging.pending_add_paths]

        copied_paths: list[Path] = []
        created: list[Attachment] = []
        try:
            if sources:
                target_dir = storage_service.attachment_dir(type_value, ident)
                _assert_under_attachments_root(target_dir)
                for source in sources:
                    safe_name = _safe_filename(source.name)
                    target = self._unique_safe_target(target_dir / safe_name)
                    _assert_under_attachments_root(target)
                    if target.exists():
                        raise AttachmentStagingError(
                            f"Cílový soubor přílohy už existuje: {target.name}"
                        )
                    shutil.copy2(source, target)
                    copied_paths.append(target)

            for source, target in zip(sources, copied_paths, strict=True):
                relative = target.resolve().relative_to(_attachments_root()).as_posix()
                if len(relative) > _STORED_PATH_LIMIT:
                    relative = relative[:_STORED_PATH_LIMIT]
                original = str(source)
                if len(original) > _ORIGINAL_PATH_LIMIT:
                    original = original[-_ORIGINAL_PATH_LIMIT:]
                attachment = Attachment(
                    entity_type=type_value,
                    entity_id=ident,
                    original_path=original,
                    stored_path=relative,
                    filename=target.name,
                )
                self.repository.add(attachment, session=session)
                created.append(attachment)

            for attachment_id in list(staging.pending_remove_ids):
                self.repository.delete(
                    int(attachment_id),
                    session=session,
                    entity_type=type_value,
                    entity_id=ident,
                )
        except Exception:
            _unlink_copied_quietly(copied_paths)
            raise

        return PreparedAttachmentChanges(
            entity_type=type_value,
            entity_id=ident,
            created_attachments=created,
            copied_paths=copied_paths,
            pending_unlink_paths=pending_unlink,
        )

    def finalize_attachment_changes(
        self,
        prepared: PreparedAttachmentChanges,
    ) -> list[str]:
        """Po úspěšném DB commitu smaže fyzické soubory odebraných příloh.

        Nové kopie ponechá. DB nemění. Selhání unlink se zaloguje jako
        varování a nevrací commit.
        """
        if prepared.rolled_back:
            raise AttachmentStagingError(
                "Nelze dokončit změny příloh po rollback_cleanup."
            )
        if prepared.finalized:
            return list(prepared.unlink_warnings)

        warnings: list[str] = []
        for path in list(prepared.pending_unlink_paths):
            if not _is_under_attachments_root(path):
                message = f"Cesta k odebrání přílohy je mimo adresář prilohy: {path}"
                logger.warning(message)
                warnings.append(message)
                continue
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink()
            except OSError as exc:
                message = f"Nepodařilo se odstranit soubor přílohy {path}: {exc}"
                logger.warning(message)
                warnings.append(message)
                break
        prepared.unlink_warnings.extend(warnings)
        prepared.finalized = True
        return warnings

    def rollback_attachment_changes(
        self,
        prepared: PreparedAttachmentChanges,
    ) -> None:
        """Uklidí jen nové kopie této přípravy. Původní odebírané soubory nechá.

        Idempotentní: chybějící už uklizený soubor není chyba.
        """
        if prepared.finalized:
            return
        _unlink_copied_quietly(prepared.copied_paths)
        prepared.rolled_back = True

    def commit_attachment_staging(
        self,
        entity_type: str,
        entity_id: int,
        staging: AttachmentStagingState,
        *,
        session: Session | None = None,
    ) -> PreparedAttachmentChanges:
        """Vlastní session: prepare → commit → finalize. Při chybě rollback + cleanup.

        Caller-owned session sem nepatří — použijte ``prepare_attachment_staging``
        a po commitu ``finalize_attachment_changes``.
        """
        if session is not None:
            raise AttachmentStagingError(
                "commit_attachment_staging používá vlastní session; "
                "pro caller-owned použijte prepare/finalize."
            )
        sess = get_session()
        sess.expire_on_commit = False
        prepared: PreparedAttachmentChanges | None = None
        try:
            prepared = self.prepare_attachment_staging(
                entity_type, entity_id, staging, sess
            )
            sess.commit()
            for attachment in prepared.created_attachments:
                sess.expunge(attachment)
        except Exception:
            sess.rollback()
            if prepared is not None:
                try:
                    self.rollback_attachment_changes(prepared)
                except Exception:
                    logger.exception("Úklid připravených příloh selhal.")
            sess.close()
            raise
        try:
            self.finalize_attachment_changes(prepared)
        except Exception:
            logger.exception("Dokončení odstranění starých příloh selhalo.")
        sess.close()
        return prepared

    def _store_source_file(self, source: Path, target: Path) -> tuple[Path, str]:
        if source.suffix.lower() in _IMAGE_SUFFIXES:
            try:
                optimized = optimize_image_bytes(source)
                target = self._unique_target(target.with_suffix(".jpg"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(optimized)
                return target, target.name
            except Exception:
                pass

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target, target.name

    def _unique_target(self, target: Path) -> Path:
        if not target.exists():
            return target

        counter = 2

        while True:
            candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _unique_safe_target(self, target: Path) -> Path:
        safe = target.with_name(_safe_filename(target.name))
        if not safe.exists():
            return safe
        counter = 2
        suffix = safe.suffix
        base_stem = Path(safe.name).stem
        while True:
            extra = f"_{counter}"
            reserved = len((extra + suffix).encode("utf-8"))
            stem = _utf8_prefix(base_stem, max(1, _FILENAME_BYTE_LIMIT - reserved))
            candidate = safe.with_name(_safe_filename(f"{stem}{extra}{suffix}"))
            if not candidate.exists():
                return candidate
            counter += 1


def _attachments_root() -> Path:
    return storage_service.attachments_dir.resolve()


def _require_entity_type(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AttachmentStagingError("Typ entity přílohy je povinný.")
    if "/" in text or "\\" in text or (os.sep not in {"/", "\\"} and os.sep in text):
        raise AttachmentStagingError("Typ entity přílohy obsahuje oddělovač cesty.")
    if ".." in text or text in {".", "~"}:
        raise AttachmentStagingError("Typ entity přílohy obsahuje nepovolenou cestu.")
    return text


def _require_entity_id(value: int) -> int:
    try:
        ident = int(value)
    except (TypeError, ValueError) as exc:
        raise AttachmentStagingError("ID entity přílohy musí být kladné celé číslo.") from exc
    if ident <= 0:
        raise AttachmentStagingError("ID entity přílohy musí být kladné celé číslo.")
    return ident


def _assert_under_attachments_root(path: Path) -> None:
    if not _is_under_attachments_root(path):
        raise AttachmentStagingError(
            "Cílová cesta přílohy musí zůstat v adresáři prilohy."
        )


def _is_under_attachments_root(path: Path) -> bool:
    root = _attachments_root()
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return False
    return resolved != root


def _utf8_prefix(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    clipped = encoded[:max_bytes]
    while clipped:
        try:
            return clipped.decode("utf-8")
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return ""


def _safe_filename(name: str) -> str:
    base = Path(str(name or "")).name.replace("\x00", "").strip()
    if not base or base in {".", ".."}:
        base = "priloha"
    suffix = Path(base).suffix
    stem = Path(base).stem or "priloha"
    suffix_bytes = suffix.encode("utf-8")
    max_stem_bytes = max(1, _FILENAME_BYTE_LIMIT - len(suffix_bytes))
    stem = _utf8_prefix(stem, max_stem_bytes) or "priloha"
    candidate = f"{stem}{suffix}"
    if len(candidate) > _FILENAME_DB_LIMIT:
        overflow = len(candidate) - _FILENAME_DB_LIMIT
        stem = stem[:-overflow] if overflow < len(stem) else "p"
        candidate = f"{stem}{suffix}"[:_FILENAME_DB_LIMIT]
    if not candidate or candidate in {".", ".."}:
        return "priloha"
    return candidate


def _validate_source_file(path: str | Path) -> Path:
    source = Path(str(path or "").strip())
    try:
        info = source.lstat()
    except FileNotFoundError as exc:
        raise AttachmentStagingError(f"Soubor přílohy neexistuje: {source}") from exc
    except OSError as exc:
        raise AttachmentStagingError(f"Soubor přílohy nelze číst: {source}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise AttachmentStagingError(f"Symbolický odkaz jako příloha není povolen: {source}")
    if stat.S_ISDIR(info.st_mode):
        raise AttachmentStagingError(f"Adresář nelze uložit jako přílohu: {source}")
    if not stat.S_ISREG(info.st_mode):
        raise AttachmentStagingError(f"Příloha musí být běžný soubor: {source}")
    try:
        with source.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise AttachmentStagingError(f"Soubor přílohy nelze číst: {source}") from exc
    return source


def _unlink_copied_quietly(paths: list[Path]) -> None:
    for path in paths:
        if not _is_under_attachments_root(path):
            logger.warning(
                "Úklid přílohy mimo prilohy se přeskočil: %s", path
            )
            continue
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            logger.exception("Nepodařilo se uklidit připravenou přílohu %s.", path)


attachment_service = AttachmentService()

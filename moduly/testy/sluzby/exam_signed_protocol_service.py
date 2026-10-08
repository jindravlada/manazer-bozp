"""Aktuální podepsaný protokol dokončené zkoušky.

Ukládá se vlastní kopie do příloh. Ke zkoušce vede nejvýše jedna
aktuální vazba. Starší soubory se při výměně ani odebrání nemažou.
"""

from __future__ import annotations

import shutil
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
        target = self._copy_into_storage(int(exam.id), source)
        try:
            _assert_pdf(target)
            return self._link(int(exam.id), source, target, replace=replace)
        except ExamSignedProtocolError:
            _discard_unlinked_copy(target)
            raise
        except Exception:
            _discard_unlinked_copy(target)
            if replace and previous_id is not None:
                raise ExamSignedProtocolError(
                    "Nový protokol se nepodařilo přiřadit. "
                    "Původní protokol zůstal dostupný."
                ) from None
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from None

    def _copy_into_storage(self, exam_id: int, source: Path) -> Path:
        directory = storage_service.attachment_dir(ENTITY_TYPE, exam_id)
        target = directory / f"protokol-{uuid.uuid4().hex}.pdf"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except OSError as exc:
            _discard_unlinked_copy(target)
            raise ExamSignedProtocolError("Protokol se nepodařilo uložit.") from exc
        return target

    def _link(
        self,
        exam_id: int,
        source: Path,
        target: Path,
        *,
        replace: bool,
    ) -> int:
        relative = target.resolve().relative_to(
            storage_service.attachments_dir.resolve()
        ).as_posix()
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
                filename=target.name,
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
    try:
        _assert_pdf(source)
    except ExamSignedProtocolError:
        raise
    except OSError as exc:
        raise ExamSignedProtocolError("Vybraný soubor nelze přečíst.") from exc
    return source


def _assert_pdf(path: Path) -> None:
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
        raise ExamSignedProtocolError(
            "Soubor není platné PDF. Nestačí změnit příponu, "
            "dokument musí mít platný formát PDF."
        )


def _discard_unlinked_copy(path: Path) -> None:
    try:
        resolved = path.resolve()
        resolved.relative_to(storage_service.attachments_dir.resolve())
    except (OSError, ValueError):
        return
    try:
        if resolved.is_file():
            resolved.unlink()
    except OSError:
        return


exam_signed_protocol_service = ExamSignedProtocolService()

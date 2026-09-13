from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import select

from core.database.session import get_session
from core.models.attachment import Attachment
from core.services.attachment_service import attachment_service
from core.services.control_result_photo_service import control_result_photo_service
from core.services.storage_service import storage_service
from core.shared.modely.control_result import ControlResult


@dataclass(frozen=True)
class AttachmentDirectoryInfo:
    relative_path: str
    absolute_path: str
    file_count: int


@dataclass
class AttachmentBackupDiagnostic:
    """Read-only přehled příloh a jejich pokrytí kompletní zálohou."""

    attachments_db_count: int = 0
    attachment_files_found: int = 0
    attachment_files_missing: int = 0
    attachment_orphan_files: int = 0
    attachment_absolute_stored_paths: int = 0
    attachment_absolute_original_paths: int = 0
    control_result_photo_db_count: int = 0
    control_result_photos_found: int = 0
    control_result_photos_missing: int = 0
    directories: list[AttachmentDirectoryInfo] = field(default_factory=list)
    missing_attachment_samples: list[str] = field(default_factory=list)
    orphan_file_samples: list[str] = field(default_factory=list)
    storage_mode: str = "filesystem_with_db_paths"
    workspace_root: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class AttachmentBackupDiagnosticService:
    """Diagnostika příloh ve workspace (read-only)."""

    def diagnose_workspace(self) -> AttachmentBackupDiagnostic:
        storage_service.ensure_structure()
        result = AttachmentBackupDiagnostic(
            storage_mode="filesystem_with_db_paths",
            workspace_root=str(storage_service.base.resolve()),
        )

        attachments = self._load_attachments()
        result.attachments_db_count = len(attachments)

        referenced_paths: set[str] = set()
        for attachment in attachments:
            stored = str(attachment.stored_path or "").strip()
            if not stored:
                result.attachment_files_missing += 1
                result.missing_attachment_samples.append(
                    f"attachments#{attachment.id}: prázdná stored_path"
                )
                continue

            if Path(stored).is_absolute():
                result.attachment_absolute_stored_paths += 1

            if attachment.original_path and Path(str(attachment.original_path)).is_absolute():
                result.attachment_absolute_original_paths += 1

            normalized = stored.replace("\\", "/")
            referenced_paths.add(normalized)
            try:
                absolute = attachment_service.resolve_path(attachment)
            except ValueError:
                result.attachment_files_missing += 1
                if len(result.missing_attachment_samples) < 10:
                    result.missing_attachment_samples.append(
                        f"attachments#{attachment.id}: {normalized}"
                    )
                continue
            if absolute.is_file():
                result.attachment_files_found += 1
            else:
                result.attachment_files_missing += 1
                if len(result.missing_attachment_samples) < 10:
                    result.missing_attachment_samples.append(
                        f"attachments#{attachment.id}: {normalized}"
                    )

        orphan_files = self._orphan_attachment_files(referenced_paths)
        result.attachment_orphan_files = len(orphan_files)
        result.orphan_file_samples = orphan_files[:10]

        control_stats = self._diagnose_control_result_photos()
        result.control_result_photo_db_count = control_stats["db_count"]
        result.control_result_photos_found = control_stats["found"]
        result.control_result_photos_missing = control_stats["missing"]

        result.directories = self._directory_overview()
        return result

    def _load_attachments(self) -> list[Attachment]:
        with get_session() as session:
            return list(session.scalars(select(Attachment).order_by(Attachment.id)))

    def _orphan_attachment_files(self, referenced_paths: set[str]) -> list[str]:
        attachments_dir = storage_service.attachments_dir
        if not attachments_dir.exists():
            return []

        orphans: list[str] = []
        for path in attachments_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(attachments_dir).as_posix()
            if relative not in referenced_paths:
                orphans.append(relative)
        return orphans

    def _diagnose_control_result_photos(self) -> dict[str, int]:
        stats = {"db_count": 0, "found": 0, "missing": 0}
        with get_session() as session:
            rows = list(
                session.scalars(
                    select(ControlResult).where(ControlResult.photo_path != "")
                )
            )

        stats["db_count"] = len(rows)
        for row in rows:
            absolute = control_result_photo_service.absolute_photo_path(row.photo_path)
            if absolute.is_file():
                stats["found"] += 1
            else:
                stats["missing"] += 1
        return stats

    def _directory_overview(self) -> list[AttachmentDirectoryInfo]:
        base = storage_service.base.resolve()
        tracked_dirs = [
            storage_service.attachments_dir,
            base / "control_results",
            storage_service.ciselniky_dir / "audity" / "fotografie",
            storage_service.ciselniky_dir / "proverky" / "fotografie",
            storage_service.exports_dir,
        ]

        overview: list[AttachmentDirectoryInfo] = []
        for directory in tracked_dirs:
            file_count = 0
            if directory.exists():
                file_count = sum(1 for path in directory.rglob("*") if path.is_file())
            overview.append(
                AttachmentDirectoryInfo(
                    relative_path=directory.relative_to(base).as_posix()
                    if directory.is_relative_to(base)
                    else directory.name,
                    absolute_path=str(directory.resolve()),
                    file_count=file_count,
                )
            )
        return overview

    def format_workspace_report(self, diagnostic: AttachmentBackupDiagnostic | None = None) -> str:
        data = diagnostic or self.diagnose_workspace()
        lines = [
            "Kontrola příloh a fotografií",
            "=" * 40,
            f"Kořen workspace: {data.workspace_root}",
            f"Režim ukládání: {data.storage_mode}",
            "",
            "Přílohy (tabulka attachments)",
            f"  Evidované v DB: {data.attachments_db_count}",
            f"  Nalezené soubory: {data.attachment_files_found}",
            f"  Chybějící soubory: {data.attachment_files_missing}",
            f"  Osiřelé soubory v prilohy/: {data.attachment_orphan_files}",
            "",
            "Fotografie kontrolních bodů (control_results)",
            f"  Evidované v DB: {data.control_result_photo_db_count}",
            f"  Nalezené: {data.control_result_photos_found}",
            f"  Chybějící: {data.control_result_photos_missing}",
            "",
            "Používané adresáře:",
        ]

        for directory in data.directories:
            lines.append(
                f"  {directory.relative_path}: {directory.file_count} souborů"
            )
            lines.append(f"    {directory.absolute_path}")

        if data.missing_attachment_samples:
            lines.extend(["", "Ukázky chybějících příloh:"])
            lines.extend(f"  - {item}" for item in data.missing_attachment_samples)

        if data.orphan_file_samples:
            lines.extend(["", "Ukázky osiřelých souborů:"])
            lines.extend(f"  - {item}" for item in data.orphan_file_samples)

        return "\n".join(lines)


attachment_backup_diagnostic_service = AttachmentBackupDiagnosticService()

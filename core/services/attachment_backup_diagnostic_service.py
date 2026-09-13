from __future__ import annotations

import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import func, select

from core.database.session import get_session
from core.models.attachment import Attachment
from core.services.attachment_service import attachment_service
from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
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


@dataclass
class BackupAttachmentCoverageDiagnostic:
    backup_path: str = ""
    zip_readable: bool = False
    zip_crc_ok: bool = False
    integrity_verified: bool = False
    attachment_files_in_zip: int = 0
    control_result_files_in_zip: int = 0
    reference_photo_files_in_zip: int = 0
    export_files_in_zip: int = 0
    version_obsah: list[str] = field(default_factory=list)
    version_root_absolute: str = ""
    attachment_zip_samples: list[str] = field(default_factory=list)
    uses_relative_zip_paths: bool = True
    manifest_reports_attachment_count: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class AttachmentBackupDiagnosticService:
    """Diagnostika příloh a jejich zahrnutí do kompletní zálohy."""

    _REFERENCE_PHOTO_MARKERS = (
        "ciselniky/audity/fotografie/",
        "ciselniky/proverky/fotografie/",
    )

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

    def diagnose_backup_zip(self, zip_path: Path | str) -> BackupAttachmentCoverageDiagnostic:
        source = Path(zip_path)
        result = BackupAttachmentCoverageDiagnostic(backup_path=str(source.resolve()))

        if not source.is_file():
            return result

        try:
            with zipfile.ZipFile(source, "r") as zf:
                result.zip_readable = True
                result.zip_crc_ok = zf.testzip() is None
                names = [name for name in zf.namelist() if not name.endswith("/")]

                attachment_names = [name for name in names if name.startswith("prilohy/")]
                control_names = [name for name in names if name.startswith("control_results/")]
                reference_names = [
                    name
                    for name in names
                    if any(marker in name for marker in self._REFERENCE_PHOTO_MARKERS)
                ]
                export_names = [name for name in names if name.startswith("export/")]

                result.attachment_files_in_zip = len(attachment_names)
                result.control_result_files_in_zip = len(control_names)
                result.reference_photo_files_in_zip = len(reference_names)
                result.export_files_in_zip = len(export_names)
                result.attachment_zip_samples = attachment_names[:10]
                result.uses_relative_zip_paths = all(not name.startswith("/") for name in names)

                if backup_service.VERSION_FILE in names:
                    import json

                    version_info = json.loads(zf.read(backup_service.VERSION_FILE).decode("utf-8"))
                    result.version_obsah = list(version_info.get("obsah") or [])
                    result.version_root_absolute = str(version_info.get("root") or "")

                manifest = backup_service.verify_backup_integrity(source, backup_type=BACKUP_TYPE_FULL)
                result.integrity_verified = bool(manifest.get("verified"))
                result.manifest_reports_attachment_count = "attachments_db_count" in manifest
        except (OSError, zipfile.BadZipFile):
            return result

        return result

    def summarize_phase_92a(self, *, backup_path: Path | str | None = None) -> dict:
        workspace = self.diagnose_workspace()
        backup = (
            self.diagnose_backup_zip(backup_path)
            if backup_path is not None
            else BackupAttachmentCoverageDiagnostic()
        )

        attachments_fully_backed_up = (
            workspace.attachments_db_count == 0
            or (
                workspace.attachment_files_missing == 0
                and backup.attachment_files_in_zip >= workspace.attachment_files_found
            )
        )
        attachments_fully_restorable = workspace.attachment_files_missing == 0

        return {
            "workspace": workspace.to_dict(),
            "backup": backup.to_dict(),
            "conclusions": {
                "attachments_fully_backed_up": attachments_fully_backed_up,
                "attachments_fully_restorable": attachments_fully_restorable,
                "covered_attachment_types": [
                    "attachments.prilohy (accident, mu_investigation, task, ...)",
                    "control_results (audit/inspection control-point photos)",
                    "ciselniky/*/fotografie (reference methodology photos)",
                    "export/ (generated protocols and reports, path-only)",
                ],
                "gaps": self._known_gaps(workspace, backup),
                "absolute_path_transfer_risk": (
                    workspace.attachment_absolute_stored_paths > 0
                    or bool(backup.version_root_absolute)
                    or workspace.attachment_absolute_original_paths > 0
                ),
                "smallest_safe_fix_suggestion": self._smallest_safe_fix(workspace, backup),
            },
        }

    def _known_gaps(
        self,
        workspace: AttachmentBackupDiagnostic,
        backup: BackupAttachmentCoverageDiagnostic,
    ) -> list[str]:
        gaps: list[str] = []
        if workspace.attachment_files_missing:
            gaps.append("Některé záznamy v tabulce attachments nemají soubor na disku.")
        if workspace.attachment_orphan_files:
            gaps.append("Ve složce prilohy/ jsou soubory bez odpovídajícího DB záznamu.")
        if not backup.manifest_reports_attachment_count:
            gaps.append("Manifest integrity neobsahuje počty příloh a fotografií.")
        if "control_results" not in backup.version_obsah:
            gaps.append("VERSION.json obsah neuvádí explicitně adresář control_results/.")
        if workspace.attachment_absolute_stored_paths:
            gaps.append("Některé attachments.stored_path jsou absolutní cesty.")
        if backup.version_root_absolute:
            gaps.append("VERSION.json ukládá absolutní root původního počítače.")
        if workspace.attachments_db_count and backup.attachment_files_in_zip == 0:
            gaps.append("ZIP neobsahuje žádné soubory pod prilohy/.")
        return gaps

    def _smallest_safe_fix(
        self,
        workspace: AttachmentBackupDiagnostic,
        backup: BackupAttachmentCoverageDiagnostic,
    ) -> str:
        if workspace.attachment_files_missing or workspace.attachment_orphan_files:
            return (
                "Nejdřív sjednotit DB a filesystem příloh; teprve potom rozšířit manifest "
                "o počet a kontrolu příloh při záloze."
            )
        if not backup.manifest_reports_attachment_count:
            return (
                "Rozšířit backup_manifest_service o read-only počty souborů v prilohy/ "
                "a control_results/ a porovnat je s tabulkou attachments."
            )
        return "Bez nutné opravy; pouze doplnit reporting do manifestu."

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

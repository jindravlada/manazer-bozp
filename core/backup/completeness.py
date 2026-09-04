"""Porovnání úplnosti instance a kontrola souborových odkazů (BACKUP-2d)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from core.backup.hashing import sha256_file
from core.backup.sqlite_snapshot import read_sqlite_user_version, sqlite_integrity_check
from core.backup.workspace_roots import (
    BACKUP_WORKSPACE_ROOTS,
    NON_BACKUP_WORKSPACE_ROOTS,
    SNAPSHOT_SUPPORT_PHOTOS_DIR,
    classify_workspace_roots,
)

# Sloupce, které typicky odkazují na soubory (relativní nebo absolutní).
FILE_REFERENCE_COLUMNS: dict[str, tuple[str, ...]] = {
    "attachments": ("stored_path", "original_path"),
    "control_results": ("photo_path",),
    "hazard_identification_photos": ("relative_path",),
    "ai_peer_reviews": ("export_file_path",),
    "legal_documents": ("local_file_path",),
    "legal_document_versions": ("local_file_path",),
}

VERDICT_COMPLETE = "COMPLETE"
VERDICT_COMPLETE_WITH_LIMITATIONS = "COMPLETE_WITH_LIMITATIONS"
VERDICT_INCOMPLETE = "INCOMPLETE"


@dataclass
class FileInventoryEntry:
    relative_path: str
    size: int
    sha256: str


@dataclass
class AbsolutePathFinding:
    table: str
    column: str
    value: str
    classification: str  # history | external | must_remap | architecture_issue
    note: str


@dataclass
class CompletenessCompareResult:
    database_integrity_source: str
    database_integrity_restored: str
    user_version_source: int | str | None
    user_version_restored: int | str | None
    tables_source: list[str]
    tables_restored: list[str]
    row_counts_source: dict[str, int]
    row_counts_restored: dict[str, int]
    row_count_mismatches: list[str] = field(default_factory=list)
    missing_files_in_restored: list[str] = field(default_factory=list)
    hash_mismatches: list[str] = field(default_factory=list)
    broken_file_references: list[str] = field(default_factory=list)
    absolute_paths: list[AbsolutePathFinding] = field(default_factory=list)
    settings_match: bool | None = None
    unknown_workspace_roots: list[str] = field(default_factory=list)
    verdict: str = VERDICT_COMPLETE_WITH_LIMITATIONS
    limitations: list[str] = field(default_factory=list)

    @property
    def ok_for_critical_data(self) -> bool:
        return (
            not self.row_count_mismatches
            and not self.missing_files_in_restored
            and not self.hash_mismatches
            and not self.broken_file_references
            and not self.unknown_workspace_roots
            and self.database_integrity_restored == "ok"
            and self.user_version_source == self.user_version_restored
            and self.settings_match is not False
        )


def inventory_workspace_files(workspace_root: Path) -> dict[str, FileInventoryEntry]:
    """Inventář souborů A+B pod workspace (relativní POSIX cesty)."""
    root = Path(workspace_root)
    result: dict[str, FileInventoryEntry] = {}
    for dirname in BACKUP_WORKSPACE_ROOTS:
        base = root / dirname
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            result[rel] = FileInventoryEntry(
                relative_path=rel,
                size=path.stat().st_size,
                sha256=sha256_file(path),
            )
    return result


def list_user_tables(db_path: Path) -> list[str]:
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [str(r[0]) for r in rows]


def count_table_rows(db_path: Path, tables: list[str] | None = None) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        if tables is None:
            tables = list_user_tables(db_path)
        counts: dict[str, int] = {}
        for table in tables:
            # bezpečné jméno tabulky z sqlite_master
            if not table.replace("_", "").isalnum():
                continue
            counts[table] = int(
                conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        return counts
    finally:
        conn.close()


def _is_absolute_path(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    path = Path(text)
    return path.is_absolute() or (len(text) > 1 and text[1] == ":" and text[0].isalpha())


def classify_absolute_path(table: str, column: str, value: str) -> AbsolutePathFinding:
    """Rozhodnutí o absolutní cestě dle známých sloupců."""
    if table == "attachments" and column == "original_path":
        return AbsolutePathFinding(
            table,
            column,
            value,
            "history",
            "Historie původního importu; soubor není potřeba pro provoz.",
        )
    if table == "ai_peer_reviews" and column == "export_file_path":
        return AbsolutePathFinding(
            table,
            column,
            value,
            "external",
            "Externí AI export ZIP mimo workspace – v defaultní záloze není soubor.",
        )
    if table in {"legal_documents", "legal_document_versions"} and column == "local_file_path":
        return AbsolutePathFinding(
            table,
            column,
            value,
            "external",
            "Lokální právní soubor mimo workspace – cesta se zálohuje, soubor ne.",
        )
    if table == "attachments" and column == "stored_path":
        return AbsolutePathFinding(
            table,
            column,
            value,
            "architecture_issue",
            "stored_path má být relativní k prilohy/; absolutní cesta je chyba.",
        )
    return AbsolutePathFinding(
        table,
        column,
        value,
        "must_remap",
        "Absolutní cesta – po přesunu na jiný počítač pravděpodobně neplatí.",
    )


def scan_absolute_paths(db_path: Path) -> list[AbsolutePathFinding]:
    findings: list[AbsolutePathFinding] = []
    tables = set(list_user_tables(db_path))
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        for table, columns in FILE_REFERENCE_COLUMNS.items():
            if table not in tables:
                continue
            # ověř existující sloupce
            info = {
                row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            for column in columns:
                if column not in info:
                    continue
                rows = conn.execute(
                    f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL '
                    f'AND TRIM("{column}") != \'\''
                ).fetchall()
                for (value,) in rows:
                    text = str(value)
                    if _is_absolute_path(text):
                        findings.append(classify_absolute_path(table, column, text))
    finally:
        conn.close()
    return findings


def resolve_db_file_reference(
    workspace_root: Path,
    table: str,
    column: str,
    value: str,
) -> Path | None:
    """Vrátí očekávanou cestu souboru v obnovené instanci, nebo None pokud není souborový odkaz."""
    text = (value or "").strip()
    if not text:
        return None
    root = Path(workspace_root)
    if table == "attachments" and column == "stored_path":
        if _is_absolute_path(text):
            return Path(text)
        return root / "prilohy" / text
    if table == "attachments" and column == "original_path":
        return None  # historie – neověřovat existenci
    if table == "control_results" and column == "photo_path":
        if _is_absolute_path(text):
            return Path(text)
        return root / text
    if table == "hazard_identification_photos" and column == "relative_path":
        if _is_absolute_path(text):
            return Path(text)
        return root / "prilohy" / text
    if table in {"ai_peer_reviews", "legal_documents", "legal_document_versions"}:
        # externí – neověřovat jako povinné soubory workspace
        return None
    return None


def _support_snapshot_photo_rels(payload_text: str) -> list[str]:
    try:
        payload = json.loads(payload_text or "{}")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    section = payload.get("section")
    photos = section.get("referencni_fotografie") if isinstance(section, dict) else None
    if not isinstance(photos, list):
        return []
    rels: list[str] = []
    for photo in photos:
        if not isinstance(photo, dict) or photo.get("missing"):
            continue
        rel = str(photo.get("soubor") or "").strip()
        if rel.startswith(f"{SNAPSHOT_SUPPORT_PHOTOS_DIR}/"):
            rels.append(rel)
    return rels


def check_db_file_references(workspace_root: Path, db_path: Path) -> list[str]:
    """Vrátí seznam rozbitých povinných souborových odkazů (relativní workspace soubory)."""
    broken: list[str] = []
    tables = set(list_user_tables(db_path))
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        for table, columns in FILE_REFERENCE_COLUMNS.items():
            if table not in tables:
                continue
            info = {
                row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            for column in columns:
                if column not in info:
                    continue
                rows = conn.execute(
                    f'SELECT rowid, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL '
                    f'AND TRIM("{column}") != \'\''
                ).fetchall()
                for rowid, value in rows:
                    target = resolve_db_file_reference(
                        workspace_root, table, column, str(value)
                    )
                    if target is None:
                        continue
                    if _is_absolute_path(str(value)):
                        # absolutní stored/photo – po přesunu často rozbité
                        if not target.is_file():
                            broken.append(
                                f"{table}.{column}#{rowid} abs-missing:{value}"
                            )
                        continue
                    if not target.is_file():
                        broken.append(
                            f"{table}.{column}#{rowid} missing:{target.relative_to(workspace_root).as_posix()}"
                        )
        if "audit_question_support_snapshots" in tables:
            info = {
                row[1]
                for row in conn.execute(
                    'PRAGMA table_info("audit_question_support_snapshots")'
                ).fetchall()
            }
            if "support_payload_json" in info:
                rows = conn.execute(
                    "SELECT rowid, support_payload_json "
                    "FROM audit_question_support_snapshots "
                    "WHERE support_payload_json IS NOT NULL "
                    "AND TRIM(support_payload_json) != ''"
                ).fetchall()
                root = Path(workspace_root)
                for rowid, payload in rows:
                    for rel in _support_snapshot_photo_rels(str(payload)):
                        target = root / rel
                        if not target.is_file():
                            broken.append(
                                f"audit_question_support_snapshots.support_payload_json"
                                f"#{rowid} missing:{rel}"
                            )
    finally:
        conn.close()
    return broken


def compare_instances(
    *,
    source_workspace: Path,
    source_db: Path,
    restored_workspace: Path,
    restored_db: Path,
    source_settings: Path | None = None,
    restored_settings: Path | None = None,
) -> CompletenessCompareResult:
    """Porovná zdrojovou a obnovenou instance (kritická data A+B)."""
    src_integrity = sqlite_integrity_check(source_db)
    dst_integrity = sqlite_integrity_check(restored_db)
    src_user_version = read_sqlite_user_version(source_db)
    dst_user_version = read_sqlite_user_version(restored_db)

    src_tables = list_user_tables(source_db)
    dst_tables = list_user_tables(restored_db)
    src_counts = count_table_rows(source_db, src_tables)
    dst_counts = count_table_rows(restored_db, dst_tables)

    mismatches: list[str] = []
    if src_user_version != dst_user_version:
        mismatches.append(
            f"user_version: {src_user_version} → {dst_user_version}"
        )
    for table, count in src_counts.items():
        other = dst_counts.get(table)
        if other is None:
            mismatches.append(f"chybí tabulka {table}")
        elif other != count:
            mismatches.append(f"{table}: {count} → {other}")
    for table in dst_counts:
        if table not in src_counts:
            mismatches.append(f"navíc tabulka {table}")

    src_files = inventory_workspace_files(source_workspace)
    dst_files = inventory_workspace_files(restored_workspace)
    missing: list[str] = []
    hash_bad: list[str] = []
    for rel, entry in src_files.items():
        other = dst_files.get(rel)
        if other is None:
            missing.append(rel)
            continue
        if other.size != entry.size or other.sha256 != entry.sha256:
            hash_bad.append(rel)

    broken_refs = check_db_file_references(restored_workspace, restored_db)
    abs_paths = scan_absolute_paths(restored_db)
    source_scan = classify_workspace_roots(source_workspace)
    restored_scan = classify_workspace_roots(restored_workspace)
    unknown_roots = sorted(set(source_scan.unknown) | set(restored_scan.unknown))

    settings_match: bool | None = None
    if source_settings is not None and restored_settings is not None:
        if source_settings.is_file() and restored_settings.is_file():
            settings_match = (
                sha256_file(source_settings) == sha256_file(restored_settings)
            )
        else:
            settings_match = False

    limitations: list[str] = []
    external = [f for f in abs_paths if f.classification == "external"]
    if external:
        limitations.append(
            "Absolutní cesty na externí soubory (AI exporty / právní PDF) "
            "se zálohují jen jako text v DB; soubory mimo workspace nejsou v balíčku."
        )
    history = [f for f in abs_paths if f.classification == "history"]
    if history:
        limitations.append(
            "attachments.original_path zůstává absolutní (historie importu)."
        )
    limitations.append(
        "export/, zalohy/, import/, logy/ nejsou součástí defaultní úplné zálohy."
    )
    limitations.append(
        "konfigurace/sprava_dat.json může obsahovat absolutní cesty k minulým zálohám."
    )
    if unknown_roots:
        listed = ", ".join(unknown_roots)
        limitations.append(
            f"Neznámé datové kořeny workspace nejsou v úplné záloze: {listed}."
        )

    result = CompletenessCompareResult(
        database_integrity_source=src_integrity,
        database_integrity_restored=dst_integrity,
        user_version_source=src_user_version,
        user_version_restored=dst_user_version,
        tables_source=src_tables,
        tables_restored=dst_tables,
        row_counts_source=src_counts,
        row_counts_restored=dst_counts,
        row_count_mismatches=mismatches,
        missing_files_in_restored=missing,
        hash_mismatches=hash_bad,
        broken_file_references=broken_refs,
        absolute_paths=abs_paths,
        settings_match=settings_match,
        unknown_workspace_roots=unknown_roots,
        limitations=limitations,
    )

    if not result.ok_for_critical_data:
        result.verdict = VERDICT_INCOMPLETE
    elif limitations:
        result.verdict = VERDICT_COMPLETE_WITH_LIMITATIONS
    else:
        result.verdict = VERDICT_COMPLETE
    return result

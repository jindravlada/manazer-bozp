"""FULL-BACKUP-SNAPSHOT-PHOTOS-1: snapshot_support_photos a neznámé kořeny."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.backup import (
    BACKUP_EXTENSION,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    INTEGRITY_VALID_WITH_WARNINGS,
    METADATA_FILENAME,
    RESTORE_ERR_FAILED_BEFORE_SWAP,
    SNAPSHOT_SUPPORT_PHOTOS_DIR,
    SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
    VERDICT_COMPLETE,
    VERDICT_COMPLETE_WITH_LIMITATIONS,
    VERDICT_INCOMPLETE,
    InstanceRestoreError,
    classify_workspace_roots,
    compare_instances,
    create_instance_backup,
    inspect_backup_integrity,
    restore_instance_backup,
    sha256_bytes,
    sha256_file,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_photo(workspace: Path, payload: bytes, suffix: str = ".jpg") -> Path:
    digest = _sha256(payload)
    target = (
        workspace
        / SNAPSHOT_SUPPORT_PHOTOS_DIR
        / digest[:2]
        / f"{digest}{suffix}"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def _make_workspace(root: Path, *, with_photos: bool = True) -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"

    photo = None
    if with_photos:
        photo = _write_photo(workspace, b"\xff\xd8ssp-one")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO demo(note) VALUES ('ok')")
        conn.execute(
            """
            CREATE TABLE attachments (
                id INTEGER PRIMARY KEY,
                entity_type TEXT,
                entity_id INTEGER,
                stored_path TEXT,
                original_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE audit_question_support_snapshots (
                id INTEGER PRIMARY KEY,
                support_payload_json TEXT
            )
            """
        )
        if photo is not None:
            rel = photo.relative_to(workspace).as_posix()
            payload = {
                "section": {
                    "referencni_fotografie": [
                        {"soubor": rel, "file_sha256": sha256_file(photo)}
                    ]
                }
            }
            conn.execute(
                "INSERT INTO audit_question_support_snapshots(support_payload_json) "
                "VALUES (?)",
                (json.dumps(payload, ensure_ascii=False),),
            )
            att_dir = workspace / "prilohy" / "state_supervision" / "1"
            att_dir.mkdir(parents=True)
            att_file = att_dir / "protokol.bin"
            att_file.write_bytes(b"SS-DOC")
            conn.execute(
                "INSERT INTO attachments(entity_type, entity_id, stored_path, original_path) "
                "VALUES (?,?,?,?)",
                (
                    "state_supervision",
                    1,
                    "state_supervision/1/protokol.bin",
                    str(root / "origin.pdf"),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    for name in ("prilohy", "control_results", "ciselniky", "templates", "konfigurace"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    (workspace / "prilohy").mkdir(parents=True, exist_ok=True)
    (workspace / "ciselniky" / "c.json").write_text("{}", encoding="utf-8")
    (workspace / "templates" / "t.odt").write_bytes(b"PK")
    (workspace / "konfigurace" / "sprava_dat.json").write_text("{}", encoding="utf-8")
    (workspace / "zalohy").mkdir(parents=True)
    (workspace / "zalohy" / "old.zip").write_bytes(b"ZIP")
    (workspace / "logy").mkdir(parents=True)
    (workspace / "logy" / "app.log").write_text("log\n", encoding="utf-8")
    (workspace / "import").mkdir(parents=True)
    (workspace / "export").mkdir(parents=True)
    (workspace / "export" / "out.pdf").write_bytes(b"%PDF")

    settings = root / "settings.json"
    settings.write_text('{"theme":"default"}', encoding="utf-8")
    return workspace, db_path, settings


def _strip_coverage_fields(source: Path, target: Path) -> None:
    """Simuluje starší balíček bez deklarovaného pokrytí kořenů."""
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == METADATA_FILENAME:
                meta = json.loads(data.decode("utf-8"))
                meta.pop("included_workspace_roots", None)
                meta.pop("unknown_workspace_roots", None)
                files = [
                    entry
                    for entry in meta.get("files", [])
                    if SNAPSHOT_SUPPORT_PHOTOS_DIR not in str(entry.get("path", ""))
                ]
                meta["files"] = files
                meta["total_content_size"] = sum(int(e["size"]) for e in files)
                data = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
            elif SNAPSHOT_SUPPORT_PHOTOS_DIR in info.filename:
                continue
            dst.writestr(info, data)


def test_photo_in_new_mbbackup_with_manifest_hash(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    package = tmp_path / f"photos{BACKUP_EXTENSION}"
    result = create_instance_backup(
        package,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )
    assert result.coverage_verdict == VERDICT_COMPLETE
    photo = next((workspace / SNAPSHOT_SUPPORT_PHOTOS_DIR).rglob("*.jpg"))
    archive_path = f"workspace/{photo.relative_to(workspace).as_posix()}"
    entry = next(e for e in result.metadata.files if e.path == archive_path)
    assert entry.size == photo.stat().st_size
    assert entry.sha256 == sha256_file(photo)
    with zipfile.ZipFile(package, "r") as zf:
        data = zf.read(archive_path)
    assert len(data) == entry.size
    assert sha256_bytes(data) == entry.sha256
    assert SNAPSHOT_SUPPORT_PHOTOS_DIR in (result.metadata.included_workspace_roots or [])


def test_roundtrip_restores_photo_and_snapshot_link(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    package = tmp_path / f"rt{BACKUP_EXTENSION}"
    create_instance_backup(
        package,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )
    dest = tmp_path / "dest"
    dest.mkdir()
    dest_settings = tmp_path / "dest-settings.json"
    dest_settings.write_text("{}", encoding="utf-8")
    restore_instance_backup(
        package, workspace_root=dest, settings_path=dest_settings
    )

    source_photo = next((workspace / SNAPSHOT_SUPPORT_PHOTOS_DIR).rglob("*.jpg"))
    restored_photo = dest / source_photo.relative_to(workspace)
    assert restored_photo.is_file()
    assert sha256_file(restored_photo) == sha256_file(source_photo)

    conn = sqlite3.connect(str(dest / "databaze" / "manager_bozp.db"))
    try:
        payload = json.loads(
            conn.execute(
                "SELECT support_payload_json FROM audit_question_support_snapshots"
            ).fetchone()[0]
        )
        rel = payload["section"]["referencni_fotografie"][0]["soubor"]
        assert (dest / rel).is_file()
        att = dest / "prilohy" / "state_supervision" / "1" / "protokol.bin"
        assert att.is_file()
        assert att.read_bytes() == b"SS-DOC"
    finally:
        conn.close()

    compared = compare_instances(
        source_workspace=workspace,
        source_db=db_path,
        restored_workspace=dest,
        restored_db=dest / "databaze" / "manager_bozp.db",
        source_settings=settings,
        restored_settings=dest_settings,
    )
    assert compared.broken_file_references == []
    assert compared.missing_files_in_restored == []
    assert compared.unknown_workspace_roots == []
    assert compared.ok_for_critical_data is True
    assert compared.verdict == VERDICT_COMPLETE_WITH_LIMITATIONS


def test_multiple_content_addressed_photos(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path, with_photos=True)
    second = _write_photo(workspace, b"\xff\xd8ssp-two", suffix=".png")
    third = _write_photo(workspace, b"\xff\xd8ssp-three", suffix=".webp")
    package = tmp_path / f"multi{BACKUP_EXTENSION}"
    create_instance_backup(
        package, workspace_root=workspace, database_path=db_path, settings_path=settings
    )
    dest = tmp_path / "dest-multi"
    dest.mkdir()
    dest_settings = tmp_path / "s.json"
    dest_settings.write_text("{}", encoding="utf-8")
    restore_instance_backup(
        package, workspace_root=dest, settings_path=dest_settings
    )
    for source in (second, third):
        restored = dest / source.relative_to(workspace)
        assert restored.is_file()
        assert sha256_file(restored) == sha256_file(source)


def test_empty_or_missing_root_does_not_block(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path, with_photos=False)
    empty_dir = workspace / SNAPSHOT_SUPPORT_PHOTOS_DIR
    empty_dir.mkdir(parents=True)
    package = tmp_path / f"empty{BACKUP_EXTENSION}"
    result = create_instance_backup(
        package, workspace_root=workspace, database_path=db_path, settings_path=settings
    )
    assert result.coverage_verdict == VERDICT_COMPLETE
    paths = {e.path for e in result.metadata.files}
    assert not any(SNAPSHOT_SUPPORT_PHOTOS_DIR in p for p in paths)

    missing_ws, missing_db, missing_settings = _make_workspace(
        tmp_path / "missing", with_photos=False
    )
    ssp = missing_ws / SNAPSHOT_SUPPORT_PHOTOS_DIR
    if ssp.exists():
        ssp.rmdir()
    result_missing = create_instance_backup(
        tmp_path / f"missing{BACKUP_EXTENSION}",
        workspace_root=missing_ws,
        database_path=missing_db,
        settings_path=missing_settings,
    )
    assert result_missing.coverage_verdict == VERDICT_COMPLETE
    assert SNAPSHOT_SUPPORT_PHOTOS_DIR in (
        result_missing.metadata.included_workspace_roots or []
    )


def test_unknown_root_marks_incomplete_and_is_not_archived(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    workspace, db_path, settings = _make_workspace(tmp_path, with_photos=False)
    (workspace / "nova_slozka_modulu").mkdir()
    (workspace / "nova_slozka_modulu" / "tajne.bin").write_bytes(b"secret")
    package = tmp_path / f"unknown{BACKUP_EXTENSION}"
    with caplog.at_level(logging.WARNING):
        result = create_instance_backup(
            package,
            workspace_root=workspace,
            database_path=db_path,
            settings_path=settings,
        )
    assert result.coverage_verdict == VERDICT_INCOMPLETE
    assert "nova_slozka_modulu" in result.unknown_workspace_roots
    assert any("nova_slozka_modulu" in rec.message for rec in caplog.records)
    paths = {e.path for e in result.metadata.files}
    assert not any("nova_slozka_modulu" in p for p in paths)

    dest = tmp_path / "dest-unknown"
    dest.mkdir()
    dest_settings = tmp_path / "u.json"
    dest_settings.write_text("{}", encoding="utf-8")
    restore_instance_backup(
        package, workspace_root=dest, settings_path=dest_settings
    )
    assert not (dest / "nova_slozka_modulu").exists()

    compared = compare_instances(
        source_workspace=workspace,
        source_db=db_path,
        restored_workspace=dest,
        restored_db=dest / "databaze" / "manager_bozp.db",
        source_settings=settings,
        restored_settings=tmp_path / "u.json",
    )
    assert compared.verdict == VERDICT_INCOMPLETE
    assert "nova_slozka_modulu" in compared.unknown_workspace_roots


def test_known_operational_roots_do_not_worsen_and_export_stays_optional(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path, with_photos=False)
    scan = classify_workspace_roots(workspace)
    assert scan.verdict == VERDICT_COMPLETE
    assert "zalohy" in scan.excluded
    assert "logy" in scan.excluded
    assert "import" in scan.excluded
    assert "export" in scan.excluded

    package = tmp_path / f"ops{BACKUP_EXTENSION}"
    result = create_instance_backup(
        package, workspace_root=workspace, database_path=db_path, settings_path=settings
    )
    assert result.coverage_verdict == VERDICT_COMPLETE
    paths = {e.path for e in result.metadata.files}
    assert not any(p.startswith("workspace/export/") for p in paths)

    with_export = tmp_path / f"export{BACKUP_EXTENSION}"
    exported = create_instance_backup(
        with_export,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
        include_exports=True,
    )
    export_paths = {e.path for e in exported.metadata.files}
    assert any(p.startswith("workspace/export/") for p in export_paths)
    assert "export" in (exported.metadata.included_workspace_roots or [])
    assert exported.coverage_verdict == VERDICT_COMPLETE


def test_legacy_package_restores_with_coverage_limitation(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    modern = tmp_path / f"modern{BACKUP_EXTENSION}"
    create_instance_backup(
        modern, workspace_root=workspace, database_path=db_path, settings_path=settings
    )
    legacy = tmp_path / f"legacy{BACKUP_EXTENSION}"
    _strip_coverage_fields(modern, legacy)

    report = inspect_backup_integrity(legacy)
    assert report.ok is True
    assert report.status == INTEGRITY_VALID_WITH_WARNINGS
    assert report.status != INTEGRITY_INVALID
    assert any(
        issue.code == "snapshot_support_photos_uncovered" for issue in report.warnings
    )
    assert SNAPSHOT_SUPPORT_PHOTOS_LIMITATION in " ".join(
        issue.message for issue in report.warnings
    )
    assert not any("poškozen" in issue.message.lower() for issue in report.errors)

    dest = tmp_path / "legacy-dest"
    dest.mkdir()
    dest_settings = tmp_path / "legacy-settings.json"
    dest_settings.write_text("{}", encoding="utf-8")
    restore_instance_backup(
        legacy, workspace_root=dest, settings_path=dest_settings
    )
    assert (dest / "databaze" / "manager_bozp.db").is_file()
    assert (dest / "ciselniky" / "c.json").is_file()
    assert not list((dest / SNAPSHOT_SUPPORT_PHOTOS_DIR).rglob("*"))


def test_corrupt_photo_hash_rejected_before_swap(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    package = tmp_path / f"ok{BACKUP_EXTENSION}"
    create_instance_backup(
        package, workspace_root=workspace, database_path=db_path, settings_path=settings
    )
    photo_entry = next(
        e
        for e in inspect_backup_integrity(package).metadata.files
        if SNAPSHOT_SUPPORT_PHOTOS_DIR in e.path
    )
    broken = tmp_path / f"broken{BACKUP_EXTENSION}"
    with zipfile.ZipFile(package, "r") as src, zipfile.ZipFile(
        broken, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == photo_entry.path:
                data = data + b"tamper"
            dst.writestr(info, data)

    dest = tmp_path / "keep-me"
    dest.mkdir()
    canary = dest / "prilohy"
    canary.mkdir()
    marker = canary / "CANARY.txt"
    marker.write_text("keep", encoding="utf-8")
    dest_settings = tmp_path / "x.json"
    dest_settings.write_text("{}", encoding="utf-8")
    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            broken, workspace_root=dest, settings_path=dest_settings
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "keep"
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(issue.code == "hash_mismatch" for issue in report.errors)


def test_new_package_without_unknown_roots_is_integrity_valid(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    package = tmp_path / f"valid{BACKUP_EXTENSION}"
    create_instance_backup(
        package, workspace_root=workspace, database_path=db_path, settings_path=settings
    )
    report = inspect_backup_integrity(package)
    assert report.status == INTEGRITY_VALID
    assert not any(
        issue.code == "snapshot_support_photos_uncovered" for issue in report.warnings
    )

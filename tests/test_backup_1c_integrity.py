"""BACKUP-1c: ověření integrity *.mbbackup."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from core.backup import (
    BACKUP_EXTENSION,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    METADATA_FILENAME,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_KIND_RISK_CATALOG_EXPORT,
    PACKAGE_STATUS_COMPLETE,
    PACKAGE_STATUS_CREATING,
    create_instance_backup,
    inspect_backup_integrity,
    sha256_bytes,
    verify_instance_backup_package,
)


def _make_workspace(root: Path) -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO demo(note) VALUES ('ok')")
        conn.commit()
    finally:
        conn.close()

    (workspace / "prilohy").mkdir(parents=True)
    (workspace / "prilohy" / "a.txt").write_text("x", encoding="utf-8")
    (workspace / "ciselniky").mkdir(parents=True)
    (workspace / "ciselniky" / "c.json").write_text("{}", encoding="utf-8")
    (workspace / "templates").mkdir(parents=True)
    (workspace / "templates" / "t.odt").write_bytes(b"PK")
    (workspace / "konfigurace").mkdir(parents=True)
    (workspace / "konfigurace" / "sprava_dat.json").write_text("{}", encoding="utf-8")
    (workspace / "control_results").mkdir(parents=True)

    settings = root / "settings.json"
    settings.write_text('{"theme":"default"}', encoding="utf-8")
    return workspace, db_path, settings


def _create_backup(tmp_path: Path) -> Path:
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"ok{BACKUP_EXTENSION}"
    create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )
    return target


def _rewrite_package(source: Path, target: Path, mutate_meta, mutate_members=None) -> None:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst:
        meta = json.loads(src.read(METADATA_FILENAME).decode("utf-8"))
        members = {name: src.read(name) for name in src.namelist() if name != METADATA_FILENAME}
        if mutate_members is not None:
            mutate_members(members, meta)
        mutate_meta(meta)
        for name, data in members.items():
            dst.writestr(name, data)
        dst.writestr(METADATA_FILENAME, json.dumps(meta, ensure_ascii=False, indent=2))


def test_successful_integrity_of_complete_backup(tmp_path: Path):
    target = _create_backup(tmp_path)
    report = inspect_backup_integrity(target)

    assert report.status == INTEGRITY_VALID
    assert report.ok is True
    assert report.errors == []
    assert report.database_integrity == "ok"
    assert report.database_quick_check == "ok"
    assert report.database_empty is False
    assert report.database_size and report.database_size > 0
    assert report.files_checked >= 1
    assert report.metadata is not None
    assert report.metadata.package_kind == PACKAGE_KIND_INSTANCE_BACKUP
    assert report.metadata.package_status == PACKAGE_STATUS_COMPLETE
    assert report.metadata.database_quick_check == "ok"
    assert report.metadata.database_size == report.database_size

    verify_instance_backup_package(target)


def test_corrupted_zip(tmp_path: Path):
    target = _create_backup(tmp_path)
    target.write_bytes(b"toto neni zip")
    report = inspect_backup_integrity(target)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "bad_zip" for i in report.errors)


def test_missing_metadata(tmp_path: Path):
    target = _create_backup(tmp_path)
    broken = tmp_path / f"nometa{BACKUP_EXTENSION}"
    with zipfile.ZipFile(target, "r") as src, zipfile.ZipFile(broken, "w") as dst:
        for name in src.namelist():
            if name == METADATA_FILENAME:
                continue
            dst.writestr(name, src.read(name))

    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "missing_metadata" for i in report.errors)


def test_wrong_format_version(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"ver{BACKUP_EXTENSION}"

    def mutate(meta):
        meta["format_version"] = 999

    _rewrite_package(source, broken, mutate)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "unsupported_format_version" for i in report.errors)


def test_missing_database(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"nodb{BACKUP_EXTENSION}"

    def mutate_members(members, meta):
        for key in list(members):
            if key.startswith("database/"):
                del members[key]
        meta["files"] = [f for f in meta["files"] if f["component"] != "database"]
        meta["total_content_size"] = sum(f["size"] for f in meta["files"])

    _rewrite_package(source, broken, lambda m: None, mutate_members)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(
        i.code in {"missing_database", "missing_database_dir"} for i in report.errors
    )


def test_corrupted_database(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"baddb{BACKUP_EXTENSION}"
    garbage = b"not-a-sqlite-database-at-all!!!!"

    def mutate_members(members, meta):
        path = "database/manager_bozp.db"
        members[path] = garbage
        for entry in meta["files"]:
            if entry["path"] == path:
                entry["size"] = len(garbage)
                entry["sha256"] = sha256_bytes(garbage)
        meta["database_size"] = len(garbage)
        meta["database_integrity"] = "ok"
        meta["total_content_size"] = sum(f["size"] for f in meta["files"])

    _rewrite_package(source, broken, lambda m: None, mutate_members)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(
        i.code
        in {
            "database_integrity_failed",
            "database_quick_check_failed",
            "database_unreadable",
        }
        for i in report.errors
    )


def test_missing_file_from_manifest(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"missing{BACKUP_EXTENSION}"

    def mutate_members(members, meta):
        del members["workspace/prilohy/a.txt"]

    _rewrite_package(source, broken, lambda m: None, mutate_members)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "missing_file" for i in report.errors)


def test_wrong_hash(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"hash{BACKUP_EXTENSION}"

    def mutate(meta):
        meta["files"][0]["sha256"] = "0" * 64

    _rewrite_package(source, broken, mutate)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "hash_mismatch" for i in report.errors)


def test_invalid_package_status(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"status{BACKUP_EXTENSION}"

    def mutate(meta):
        meta["package_status"] = PACKAGE_STATUS_CREATING

    _rewrite_package(source, broken, mutate)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "incomplete_package" for i in report.errors)


def test_invalid_package_kind(tmp_path: Path):
    source = _create_backup(tmp_path)
    broken = tmp_path / f"kind{BACKUP_EXTENSION}"

    def mutate(meta):
        meta["package_kind"] = PACKAGE_KIND_RISK_CATALOG_EXPORT

    _rewrite_package(source, broken, mutate)
    report = inspect_backup_integrity(broken)
    assert report.status == INTEGRITY_INVALID
    assert any(i.code == "bad_package_kind" for i in report.errors)


def test_report_to_dict_shape(tmp_path: Path):
    target = _create_backup(tmp_path)
    data = inspect_backup_integrity(target).to_dict()
    assert data["status"] == INTEGRITY_VALID
    assert data["ok"] is True
    assert "issues" in data
    assert data["metadata"]["package_status"] == PACKAGE_STATUS_COMPLETE

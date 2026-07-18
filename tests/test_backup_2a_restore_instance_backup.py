"""BACKUP-2a: bezpečná obnova *.mbbackup."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.backup import (
    BACKUP_EXTENSION,
    METADATA_FILENAME,
    PACKAGE_STATUS_CREATING,
    RESTORE_ERR_BAD_ARCHIVE,
    RESTORE_ERR_FAILED_BEFORE_SWAP,
    RESTORE_ERR_INTERRUPTED,
    RESTORE_ERR_INVALID_DATABASE,
    RESTORE_ERR_INVALID_METADATA,
    RESTORE_ERR_MISSING_COMPONENT,
    InstanceRestoreError,
    create_instance_backup,
    restore_instance_backup,
    sha256_bytes,
)


def _make_workspace(root: Path, *, note: str = "original") -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO demo(note) VALUES (?)", (note,))
        conn.commit()
    finally:
        conn.close()

    (workspace / "prilohy").mkdir(parents=True)
    (workspace / "prilohy" / "a.txt").write_text(f"file-{note}", encoding="utf-8")
    (workspace / "ciselniky").mkdir(parents=True)
    (workspace / "ciselniky" / "c.json").write_text("{}", encoding="utf-8")
    (workspace / "templates").mkdir(parents=True)
    (workspace / "templates" / "t.odt").write_bytes(b"PK")
    (workspace / "konfigurace").mkdir(parents=True)
    (workspace / "konfigurace" / "sprava_dat.json").write_text("{}", encoding="utf-8")
    (workspace / "control_results").mkdir(parents=True)
    (workspace / "zalohy").mkdir(parents=True)
    (workspace / "zalohy" / "keep-me.zip").write_bytes(b"ZIPKEEP")

    settings = root / "settings.json"
    settings.write_text(
        json.dumps({"theme": "default", "marker": note}, ensure_ascii=False),
        encoding="utf-8",
    )
    return workspace, db_path, settings


def _backup_from(tmp_path: Path, note: str = "backup-data") -> tuple[Path, Path, Path, Path]:
    """Vytvoří workspace + balíček. Vrací package, workspace, db, settings."""
    src_root = tmp_path / f"src-{note}"
    workspace, db_path, settings = _make_workspace(src_root, note=note)
    package = tmp_path / f"{note}{BACKUP_EXTENSION}"
    create_instance_backup(
        package,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )
    return package, workspace, db_path, settings


def _rewrite_package(source: Path, target: Path, mutate_meta, mutate_members=None) -> None:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst:
        meta = json.loads(src.read(METADATA_FILENAME).decode("utf-8"))
        members = {
            name: src.read(name) for name in src.namelist() if name != METADATA_FILENAME
        }
        if mutate_members is not None:
            mutate_members(members, meta)
        mutate_meta(meta)
        for name, data in members.items():
            dst.writestr(name, data)
        dst.writestr(METADATA_FILENAME, json.dumps(meta, ensure_ascii=False, indent=2))


def test_successful_restore(tmp_path: Path):
    package, _, _, _ = _backup_from(tmp_path, note="from-backup")
    live_root = tmp_path / "live"
    live_ws, _, live_settings = _make_workspace(live_root, note="live-old")
    # marker, který musí zmizet
    (live_ws / "prilohy" / "only-live.txt").write_text("gone", encoding="utf-8")

    result = restore_instance_backup(
        package,
        workspace_root=live_ws,
        settings_path=live_settings,
    )

    assert result.database_integrity == "ok"
    assert result.database_path.is_file()
    assert not (live_ws / "prilohy" / "only-live.txt").exists()
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == "file-from-backup"

    conn = sqlite3.connect(str(result.database_path))
    try:
        assert conn.execute("SELECT note FROM demo").fetchone()[0] == "from-backup"
    finally:
        conn.close()

    # zalohy z live zachovány
    assert (live_ws / "zalohy" / "keep-me.zip").read_bytes() == b"ZIPKEEP"
    assert result.preserved_backups_dir is True
    assert result.restored is True
    assert result.post_check_ok is True
    assert result.rollback_copy_removed is True
    assert result.recovery_marker_removed is True

    settings_data = json.loads(live_settings.read_text(encoding="utf-8"))
    assert settings_data["marker"] == "from-backup"

    # žádné orphan staging adresáře / markery
    leftovers = [
        p
        for p in live_ws.parent.iterdir()
        if "mbrestore" in p.name
    ]
    assert leftovers == []


def test_corrupted_archive(tmp_path: Path):
    package, _, _, _ = _backup_from(tmp_path)
    package.write_bytes(b"not-a-zip")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")
    marker = live_ws / "prilohy" / "a.txt"
    before = marker.read_text(encoding="utf-8")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package, workspace_root=live_ws, settings_path=live_settings
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code == RESTORE_ERR_BAD_ARCHIVE
    assert marker.read_text(encoding="utf-8") == before


def test_corrupted_database_in_package(tmp_path: Path):
    source, _, _, _ = _backup_from(tmp_path)
    broken = tmp_path / f"baddb{BACKUP_EXTENSION}"
    garbage = b"not-sqlite!!!!"

    def mutate_members(members, meta):
        path = "database/manager_bozp.db"
        members[path] = garbage
        for entry in meta["files"]:
            if entry["path"] == path:
                entry["size"] = len(garbage)
                entry["sha256"] = sha256_bytes(garbage)
        meta["database_size"] = len(garbage)
        meta["total_content_size"] = sum(f["size"] for f in meta["files"])

    _rewrite_package(source, broken, lambda m: None, mutate_members)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")
    before = (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            broken, workspace_root=live_ws, settings_path=live_settings
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code == RESTORE_ERR_INVALID_DATABASE
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == before


def test_missing_database(tmp_path: Path):
    source, _, _, _ = _backup_from(tmp_path)
    broken = tmp_path / f"nodb{BACKUP_EXTENSION}"

    def mutate_members(members, meta):
        for key in list(members):
            if key.startswith("database/"):
                del members[key]
        meta["files"] = [f for f in meta["files"] if f["component"] != "database"]
        meta["total_content_size"] = sum(f["size"] for f in meta["files"])

    _rewrite_package(source, broken, lambda m: None, mutate_members)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            broken, workspace_root=live_ws, settings_path=live_settings
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code in {
        RESTORE_ERR_INVALID_DATABASE,
        RESTORE_ERR_MISSING_COMPONENT,
    }


def test_missing_component_file(tmp_path: Path):
    source, _, _, _ = _backup_from(tmp_path)
    broken = tmp_path / f"missing{BACKUP_EXTENSION}"

    def mutate_members(members, meta):
        del members["workspace/prilohy/a.txt"]

    _rewrite_package(source, broken, lambda m: None, mutate_members)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            broken, workspace_root=live_ws, settings_path=live_settings
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code == RESTORE_ERR_MISSING_COMPONENT


def test_invalid_metadata(tmp_path: Path):
    source, _, _, _ = _backup_from(tmp_path)
    broken = tmp_path / f"meta{BACKUP_EXTENSION}"

    def mutate(meta):
        meta["package_status"] = PACKAGE_STATUS_CREATING

    _rewrite_package(source, broken, mutate)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            broken, workspace_root=live_ws, settings_path=live_settings
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code == RESTORE_ERR_INVALID_METADATA


def test_interrupted_restore_leaves_original(tmp_path: Path):
    package, _, _, _ = _backup_from(tmp_path, note="pkg")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="live")
    before_db = (live_ws / "databaze" / "manager_bozp.db").read_bytes()
    before_file = (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8")

    def boom(stage: str) -> None:
        if stage == "before_swap":
            raise RuntimeError("stop")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package,
            workspace_root=live_ws,
            settings_path=live_settings,
            interrupt_hook=boom,
        )
    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code == RESTORE_ERR_INTERRUPTED
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == before_file
    assert (live_ws / "databaze" / "manager_bozp.db").read_bytes() == before_db
    leftovers = [p for p in live_ws.parent.iterdir() if "mbrestore" in p.name]
    assert leftovers == []


def test_atomic_switch_replaces_workspace(tmp_path: Path):
    package, _, _, _ = _backup_from(tmp_path, note="new")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="old")
    old_only = live_ws / "OLD_MARKER"
    old_only.write_text("old", encoding="utf-8")

    seen = {"before_swap_exists": False, "after_prepare_new": False}

    def hook(stage: str) -> None:
        if stage == "after_prepare":
            news = list(live_ws.parent.glob(".workspace.mbrestore-new-*"))
            assert len(news) == 1
            assert (news[0] / "prilohy" / "a.txt").exists()
            assert live_ws.exists()
            assert old_only.exists()
            seen["after_prepare_new"] = True
        if stage == "before_swap":
            seen["before_swap_exists"] = live_ws.exists()

    restore_instance_backup(
        package,
        workspace_root=live_ws,
        settings_path=live_settings,
        interrupt_hook=hook,
    )

    assert seen["after_prepare_new"] is True
    assert seen["before_swap_exists"] is True
    assert not old_only.exists()
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == "file-new"
    assert list(live_ws.parent.glob(".workspace.mbrestore-*")) == []

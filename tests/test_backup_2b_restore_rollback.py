"""BACKUP-2b: rollback při selhání obnovy *.mbbackup."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.backup import (
    BACKUP_EXTENSION,
    RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
    RESTORE_ERR_FAILED_BEFORE_SWAP,
    RESTORE_ERR_INTERRUPTED,
    RESTORE_ERR_POSTCHECK,
    RESTORE_ERR_ROLLBACK_FAILED,
    RESTORE_ERR_WRITE_ERROR,
    InstanceRestoreError,
    create_instance_backup,
    restore_instance_backup,
)
from core.backup import package_restore as restore_mod
from core.backup.recovery_marker import read_recovery_marker


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

    settings = root / "settings.json"
    settings.write_text(
        json.dumps({"theme": "default", "marker": note}, ensure_ascii=False),
        encoding="utf-8",
    )
    return workspace, db_path, settings


def _backup_from(tmp_path: Path, note: str = "backup-data") -> Path:
    src_root = tmp_path / f"src-{note}"
    workspace, db_path, settings = _make_workspace(src_root, note=note)
    package = tmp_path / f"{note}{BACKUP_EXTENSION}"
    create_instance_backup(
        package,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )
    return package


def test_successful_restore_removes_rollback_and_marker(tmp_path: Path):
    package = _backup_from(tmp_path, note="new")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="old")

    result = restore_instance_backup(
        package, workspace_root=live_ws, settings_path=live_settings
    )

    assert result.restored is True
    assert result.post_check_ok is True
    assert result.rollback_copy_removed is True
    assert result.recovery_marker_removed is True
    assert result.warnings == []
    assert not list(live_ws.parent.glob(".mbrestore-in-progress-*.json"))
    assert not list(live_ws.parent.glob(".workspace.mbrestore-prev-*"))
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == "file-new"


def test_failure_before_swap_keeps_original(tmp_path: Path):
    package = _backup_from(tmp_path)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="live")
    before = (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8")
    before_settings = live_settings.read_text(encoding="utf-8")

    def boom(stage: str) -> None:
        if stage == "before_swap":
            raise RuntimeError("abort")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package,
            workspace_root=live_ws,
            settings_path=live_settings,
            interrupt_hook=boom,
        )

    assert exc.value.code == RESTORE_ERR_FAILED_BEFORE_SWAP
    assert exc.value.cause_code == RESTORE_ERR_INTERRUPTED
    assert exc.value.rolled_back is False
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == before
    assert live_settings.read_text(encoding="utf-8") == before_settings
    assert not list(live_ws.parent.glob(".mbrestore-in-progress-*.json"))


def test_postcheck_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    package = _backup_from(tmp_path, note="pkg")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="live")
    before_file = (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8")
    before_settings = live_settings.read_text(encoding="utf-8")

    def fail_postcheck(*args, **kwargs):
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK, "simulovaný post-check fail", phase="post_check"
        )

    monkeypatch.setattr(restore_mod, "_verify_live_workspace", fail_postcheck)

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package, workspace_root=live_ws, settings_path=live_settings
        )

    assert exc.value.code == RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK
    assert exc.value.rolled_back is True
    assert exc.value.cause_code == RESTORE_ERR_POSTCHECK
    assert "Původní data byla obnovena" in str(exc.value)
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == before_file
    assert live_settings.read_text(encoding="utf-8") == before_settings
    assert not list(live_ws.parent.glob(".mbrestore-in-progress-*.json"))


def test_settings_failure_rolls_back_workspace_and_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    package = _backup_from(tmp_path, note="pkg")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="live")
    before_file = (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8")
    before_settings = live_settings.read_text(encoding="utf-8")

    original_replace = restore_mod._atomic_replace_file
    writes = {"settings": 0}

    def fail_settings_write(source: Path, destination: Path) -> None:
        if destination == live_settings:
            writes["settings"] += 1
            if writes["settings"] == 1:
                raise OSError("settings write denied")
        return original_replace(source, destination)

    monkeypatch.setattr(restore_mod, "_atomic_replace_file", fail_settings_write)

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package, workspace_root=live_ws, settings_path=live_settings
        )

    assert exc.value.code == RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK
    assert exc.value.cause_code == RESTORE_ERR_WRITE_ERROR
    assert exc.value.rolled_back is True
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == before_file
    assert live_settings.read_text(encoding="utf-8") == before_settings


def test_rollback_failure_preserves_data_and_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    package = _backup_from(tmp_path, note="pkg")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="live")

    def fail_postcheck(*args, **kwargs):
        raise InstanceRestoreError(
            RESTORE_ERR_POSTCHECK, "force rollback", phase="post_check"
        )

    monkeypatch.setattr(restore_mod, "_verify_live_workspace", fail_postcheck)

    real_rename = __import__("os").rename

    def flaky_rename(src, dst):
        # Po post-check fail: první rename v rollbacku (workspace→failed) projde,
        # druhý (rollback→workspace) selže.
        src_p = Path(src)
        if "mbrestore-prev-" in src_p.name:
            raise OSError("rollback rename denied")
        return real_rename(src, dst)

    monkeypatch.setattr(restore_mod.os, "rename", flaky_rename)

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package, workspace_root=live_ws, settings_path=live_settings
        )

    assert exc.value.code == RESTORE_ERR_ROLLBACK_FAILED
    assert exc.value.marker_path is not None
    assert Path(exc.value.marker_path).is_file()
    marker = read_recovery_marker(Path(exc.value.marker_path))
    assert marker["phase"] == "rolling_back"
    assert exc.value.preserved_paths
    # Marker i pracovní adresáře zůstaly
    assert list(live_ws.parent.glob(".mbrestore-in-progress-*.json"))
    assert list(live_ws.parent.glob(".workspace.mbrestore-*"))


def test_recovery_marker_created_and_removed(tmp_path: Path):
    package = _backup_from(tmp_path)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")
    seen_marker = {"path": None}

    def hook(stage: str) -> None:
        if stage == "before_swap":
            markers = list(live_ws.parent.glob(".mbrestore-in-progress-*.json"))
            assert len(markers) == 1
            data = read_recovery_marker(markers[0])
            assert data["kind"] == "instance_restore"
            assert data["phase"] == "before_swap"
            assert data["workspace_root"] == str(live_ws)
            assert data["rollback_workspace"]
            assert data["new_workspace"]
            assert data["backup_format_version"] == 1
            seen_marker["path"] = markers[0]

    restore_instance_backup(
        package,
        workspace_root=live_ws,
        settings_path=live_settings,
        interrupt_hook=hook,
    )
    assert seen_marker["path"] is not None
    assert not Path(seen_marker["path"]).exists()


def test_marker_kept_on_unresolved_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    package = _backup_from(tmp_path)
    live_ws, _, live_settings = _make_workspace(tmp_path / "live")

    monkeypatch.setattr(
        restore_mod,
        "_verify_live_workspace",
        lambda *a, **k: (_ for _ in ()).throw(
            InstanceRestoreError(RESTORE_ERR_POSTCHECK, "x", phase="post_check")
        ),
    )

    def boom_during_rollback(stage: str) -> None:
        if stage == "during_rollback":
            raise RuntimeError("crash during rollback")

    with pytest.raises(InstanceRestoreError) as exc:
        restore_instance_backup(
            package,
            workspace_root=live_ws,
            settings_path=live_settings,
            interrupt_hook=boom_during_rollback,
        )

    assert exc.value.code == RESTORE_ERR_ROLLBACK_FAILED
    assert exc.value.marker_path
    assert Path(exc.value.marker_path).is_file()


def test_cleanup_failure_after_success_is_warning_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    package = _backup_from(tmp_path, note="new")
    live_ws, _, live_settings = _make_workspace(tmp_path / "live", note="old")

    original_cleanup = restore_mod._cleanup_tree

    def selective_cleanup(path):
        if path is not None and "mbrestore-prev-" in Path(path).name:
            return False
        return original_cleanup(path)

    monkeypatch.setattr(restore_mod, "_cleanup_tree", selective_cleanup)

    result = restore_instance_backup(
        package, workspace_root=live_ws, settings_path=live_settings
    )

    assert result.restored is True
    assert result.post_check_ok is True
    assert result.rollback_copy_removed is False
    assert any("rollback kopii" in w for w in result.warnings)
    # Obnovená data jsou nová
    assert (live_ws / "prilohy" / "a.txt").read_text(encoding="utf-8") == "file-new"
    # Nadbytečná kopie zůstala
    assert list(live_ws.parent.glob(".workspace.mbrestore-prev-*"))

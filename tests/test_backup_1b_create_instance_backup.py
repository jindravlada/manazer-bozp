"""BACKUP-1b: vytvoření úplné zálohy *.mbbackup."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.backup import (
    BACKUP_EXTENSION,
    BACKUP_FORMAT_VERSION,
    METADATA_FILENAME,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_STATUS_COMPLETE,
    SNAPSHOT_SUPPORT_PHOTOS_DIR,
    BackupPackageVerificationError,
    InstanceBackupError,
    create_instance_backup,
    create_sqlite_snapshot,
    sha256_bytes,
    verify_instance_backup_package,
)
from core.backup.package_create import PARTIAL_SUFFIX
from core.version import APP_VERSION


def _make_workspace(root: Path) -> tuple[Path, Path, Path]:
    """Vytvoří mini workspace s DB, přílohou, konfigurací a settings."""
    workspace = root / "workspace"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO demo(note) VALUES ('česká poznámka')")
        conn.commit()
    finally:
        conn.close()

    (workspace / "prilohy" / "ukol" / "1").mkdir(parents=True)
    (workspace / "prilohy" / "ukol" / "1" / "soubor.txt").write_text(
        "příloha", encoding="utf-8"
    )
    (workspace / "control_results").mkdir(parents=True)
    (workspace / "control_results" / "foto.jpg").write_bytes(b"\xff\xd8fake")
    (workspace / "ciselniky").mkdir(parents=True)
    (workspace / "ciselniky" / "metodika.json").write_text("{}", encoding="utf-8")
    (workspace / "templates").mkdir(parents=True)
    (workspace / "templates" / "sablona.odt").write_bytes(b"PK\x03\x04")
    (workspace / "konfigurace").mkdir(parents=True)
    (workspace / "konfigurace" / "sprava_dat.json").write_text(
        '{"last_backup": null}', encoding="utf-8"
    )

    # Kategorie D – nesmí se dostat do balíčku
    (workspace / "zalohy").mkdir(parents=True)
    (workspace / "zalohy" / "stara.zip").write_bytes(b"zip")
    (workspace / "import").mkdir(parents=True)
    (workspace / "import" / "tmp.csv").write_text("a;b\n", encoding="utf-8")
    (workspace / "logy").mkdir(parents=True)
    (workspace / "logy" / "app.log").write_text("log\n", encoding="utf-8")
    (workspace / "export").mkdir(parents=True)
    (workspace / "export" / "out.pdf").write_bytes(b"%PDF")

    settings = root / "data" / "nastaveni" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"theme": "default", "language": "cs"}, ensure_ascii=False),
        encoding="utf-8",
    )

    return workspace, db_path, settings


def test_create_valid_mbbackup(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"zaloha{BACKUP_EXTENSION}"

    result = create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )

    assert result.path == target
    assert target.is_file()
    assert not target.with_name(target.name + PARTIAL_SUFFIX).exists()
    assert result.verified is True
    assert result.database_integrity == "ok"
    assert result.metadata.package_status == PACKAGE_STATUS_COMPLETE

    meta = verify_instance_backup_package(target)
    assert meta.format_version == BACKUP_FORMAT_VERSION
    assert meta.package_kind == PACKAGE_KIND_INSTANCE_BACKUP
    assert meta.app_version == APP_VERSION


def test_metadata_and_manifest_content(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"meta{BACKUP_EXTENSION}"

    result = create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )
    meta = result.metadata
    paths = {entry.path for entry in meta.files}

    assert "database/manager_bozp.db" in paths
    assert "workspace/prilohy/ukol/1/soubor.txt" in paths
    assert "workspace/ciselniky/metodika.json" in paths
    assert "workspace/templates/sablona.odt" in paths
    assert "workspace/konfigurace/sprava_dat.json" in paths
    assert "workspace/control_results/foto.jpg" in paths
    assert "settings/settings.json" in paths
    assert SNAPSHOT_SUPPORT_PHOTOS_DIR in (result.metadata.included_workspace_roots or [])

    # Kategorie D mimo balíček
    assert not any("zalohy" in p for p in paths)
    assert not any("import/" in p for p in paths)
    assert not any("logy/" in p for p in paths)
    assert not any("export/" in p for p in paths)

    assert set(meta.included_components) >= {"database", "workspace", "settings"}
    assert meta.database_integrity == "ok"
    assert meta.total_content_size == sum(e.size for e in meta.files)

    with zipfile.ZipFile(target, "r") as zf:
        raw = json.loads(zf.read(METADATA_FILENAME).decode("utf-8"))
    assert raw["package_status"] == PACKAGE_STATUS_COMPLETE
    assert "zaměstnavatel" not in json.dumps(raw, ensure_ascii=False).lower()


def test_checksums_match_archive_bytes(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"hash{BACKUP_EXTENSION}"
    meta = create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    ).metadata

    with zipfile.ZipFile(target, "r") as zf:
        for entry in meta.files:
            data = zf.read(entry.path)
            assert len(data) == entry.size
            assert sha256_bytes(data) == entry.sha256


def test_partial_file_used_then_atomic_finish(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"atomic{BACKUP_EXTENSION}"
    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    seen_partial = {"value": False}

    def hook(stage: str) -> None:
        if stage == "before_rename":
            assert partial.is_file()
            assert not target.exists()
            seen_partial["value"] = True

    create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
        interrupt_hook=hook,
    )

    assert seen_partial["value"] is True
    assert target.is_file()
    assert not partial.exists()


def test_interrupted_creation_leaves_no_complete_package(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"abort{BACKUP_EXTENSION}"
    partial = target.with_name(target.name + PARTIAL_SUFFIX)

    def boom(stage: str) -> None:
        if stage == "before_rename":
            raise RuntimeError("simulované přerušení")

    with pytest.raises(RuntimeError, match="přerušení"):
        create_instance_backup(
            target,
            workspace_root=workspace,
            database_path=db_path,
            settings_path=settings,
            interrupt_hook=boom,
        )

    assert not target.exists()
    assert not partial.exists()


def test_interrupted_before_zip_no_artifacts(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"early{BACKUP_EXTENSION}"

    def boom(stage: str) -> None:
        if stage == "before_zip":
            raise RuntimeError("stop před zip")

    with pytest.raises(RuntimeError, match="před zip"):
        create_instance_backup(
            target,
            workspace_root=workspace,
            database_path=db_path,
            settings_path=settings,
            interrupt_hook=boom,
        )

    assert not target.exists()
    assert not target.with_name(target.name + PARTIAL_SUFFIX).exists()


def test_corrupted_package_fails_verification(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"corrupt{BACKUP_EXTENSION}"
    create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )

    raw = bytearray(target.read_bytes())
    # Přepiš data uprostřed ZIP (mimo lokální hlavičku na začátku)
    mid = len(raw) // 2
    raw[mid] = (raw[mid] + 1) % 256
    target.write_bytes(raw)

    with pytest.raises(BackupPackageVerificationError):
        verify_instance_backup_package(target)


def test_package_completeness_requires_database(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    target = tmp_path / f"complete{BACKUP_EXTENSION}"
    create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    )

    # Odstraň DB ze ZIPu a přepiš metadata – ověření musí selhat
    broken = tmp_path / f"broken{BACKUP_EXTENSION}"
    with zipfile.ZipFile(target, "r") as src, zipfile.ZipFile(
        broken, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst:
        meta = json.loads(src.read(METADATA_FILENAME).decode("utf-8"))
        meta["files"] = [
            f for f in meta["files"] if f["component"] != "database"
        ]
        meta["total_content_size"] = sum(f["size"] for f in meta["files"])
        for name in src.namelist():
            if name == "database/manager_bozp.db":
                continue
            if name == METADATA_FILENAME:
                continue
            dst.writestr(name, src.read(name))
        dst.writestr(METADATA_FILENAME, json.dumps(meta, ensure_ascii=False, indent=2))

    with pytest.raises(BackupPackageVerificationError, match="database"):
        verify_instance_backup_package(broken)


def test_sqlite_snapshot_not_plain_copy(tmp_path: Path):
    source = tmp_path / "source.db"
    dest = tmp_path / "dest.db"
    conn = sqlite3.connect(str(source))
    try:
        conn.execute("CREATE TABLE t(x INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
    finally:
        conn.close()

    integrity = create_sqlite_snapshot(source, dest)
    assert integrity == "ok"
    assert dest.is_file()

    check = sqlite3.connect(str(dest))
    try:
        assert check.execute("SELECT x FROM t").fetchone()[0] == 42
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()


def test_missing_database_fails(tmp_path: Path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = tmp_path / f"nodb{BACKUP_EXTENSION}"
    with pytest.raises(InstanceBackupError, match="Databáze neexistuje"):
        create_instance_backup(
            target,
            workspace_root=workspace,
            database_path=tmp_path / "missing.db",
        )


def test_wrong_extension_rejected(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    with pytest.raises(InstanceBackupError, match="příponu"):
        create_instance_backup(
            tmp_path / "zaloha.zip",
            workspace_root=workspace,
            database_path=db_path,
            settings_path=settings,
        )


def test_czech_paths_in_archive(tmp_path: Path):
    workspace, db_path, settings = _make_workspace(tmp_path)
    folder = workspace / "prilohy" / "úrazy"
    folder.mkdir(parents=True)
    (folder / "Protokol úrazu.pdf").write_bytes(b"%PDF-czech")

    target = tmp_path / f"cz{BACKUP_EXTENSION}"
    meta = create_instance_backup(
        target,
        workspace_root=workspace,
        database_path=db_path,
        settings_path=settings,
    ).metadata

    expected = "workspace/prilohy/úrazy/Protokol úrazu.pdf"
    assert any(e.path == expected for e in meta.files)
    with zipfile.ZipFile(target, "r") as zf:
        assert expected in zf.namelist()

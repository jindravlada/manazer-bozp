"""BACKUP-2d: end-to-end ověření úplnosti zálohy a čisté obnovy."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.backup import (
    BACKUP_EXTENSION,
    VERDICT_COMPLETE_WITH_LIMITATIONS,
    VERDICT_INCOMPLETE,
    compare_instances,
    create_instance_backup,
    inventory_workspace_files,
    restore_instance_backup,
    scan_absolute_paths,
    sha256_file,
)
from core.backup.completeness import BACKUP_WORKSPACE_ROOTS


def _build_rich_source(root: Path) -> tuple[Path, Path, Path]:
    """Reprezentativní zdrojová instance (DB + soubory A/B + settings)."""
    workspace = root / "manazer-bozp-source"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"

    # Soubory
    att_dir = workspace / "prilohy" / "accident" / "1"
    att_dir.mkdir(parents=True)
    att_file = att_dir / "Protokol úrazu.pdf"
    att_file.write_bytes(b"%PDF-czech-accident")

    photo_dir = workspace / "prilohy" / "rizeni_rizik" / "RID-1" / "fotografie"
    photo_dir.mkdir(parents=True)
    risk_photo = photo_dir / "zdroj_rizika.jpg"
    risk_photo.write_bytes(b"\xff\xd8risk")

    cr_dir = workspace / "control_results" / "audity" / "7"
    cr_dir.mkdir(parents=True)
    cr_photo = cr_dir / "a_b_c_photo.jpg"
    cr_photo.write_bytes(b"\xff\xd8audit")

    cis = workspace / "ciselniky" / "modulove"
    cis.mkdir(parents=True)
    (cis / "vlastni_ciselnik.json").write_text(
        json.dumps({"polozky": ["A", "B"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    ref = workspace / "ciselniky" / "audity" / "fotografie" / "proc" / "krit"
    ref.mkdir(parents=True)
    (ref / "reference.jpg").write_bytes(b"\xff\xd8ref")

    templates = workspace / "templates" / "kniha_urazu"
    templates.mkdir(parents=True)
    (templates / "sablona_uživatelská.odt").write_bytes(b"PK\x03\x04user-template")

    cfg = workspace / "konfigurace"
    cfg.mkdir(parents=True)
    (cfg / "sprava_dat.json").write_text(
        json.dumps(
            {
                "last_backup": {
                    "path": str(root / "old-machine" / "zaloha.mbbackup"),
                    "created_at": "2026-01-01T00:00:00",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Dočasné / provozní – nesmí být nutná pro COMPLETE kritických dat
    (workspace / "zalohy").mkdir(parents=True)
    (workspace / "zalohy" / "stara.zip").write_bytes(b"ZIP")
    (workspace / "export").mkdir(parents=True)
    (workspace / "export" / "out.pdf").write_bytes(b"%PDF")
    (workspace / "import").mkdir(parents=True)
    (workspace / "logy").mkdir(parents=True)

    # Externí AI export mimo workspace (omezení)
    external_ai = root / "external" / "ai_export.zip"
    external_ai.parent.mkdir(parents=True)
    external_ai.write_bytes(b"PKAI")
    external_legal = root / "external" / "predpis.pdf"
    external_legal.write_bytes(b"%PDF-legal")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE employers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL
            );
            CREATE TABLE accidents (
                id INTEGER PRIMARY KEY,
                description TEXT
            );
            CREATE TABLE attachments (
                id INTEGER PRIMARY KEY,
                entity_type TEXT,
                entity_id INTEGER,
                stored_path TEXT,
                original_path TEXT,
                filename TEXT
            );
            CREATE TABLE control_results (
                id INTEGER PRIMARY KEY,
                entity_type TEXT,
                entity_id INTEGER,
                photo_path TEXT
            );
            CREATE TABLE hazard_identification_photos (
                id INTEGER PRIMARY KEY,
                relative_path TEXT,
                filename TEXT
            );
            CREATE TABLE ai_peer_reviews (
                id INTEGER PRIMARY KEY,
                export_file_path TEXT
            );
            CREATE TABLE legal_documents (
                id INTEGER PRIMARY KEY,
                title TEXT,
                local_file_path TEXT
            );
            CREATE TABLE processes (
                id INTEGER PRIMARY KEY,
                name TEXT
            );
            """
        )
        conn.execute("INSERT INTO employers(name) VALUES (?)", ("Testovací firma s.r.o.",))
        conn.execute("INSERT INTO tasks(title) VALUES (?)", ("Úkol BOZP",))
        conn.execute("INSERT INTO accidents(description) VALUES (?)", ("Úraz – pád",))
        conn.execute(
            "INSERT INTO attachments(entity_type, entity_id, stored_path, original_path, filename) "
            "VALUES (?,?,?,?,?)",
            (
                "accident",
                1,
                "accident/1/Protokol úrazu.pdf",
                str(root / "imports" / "originál.pdf"),
                "Protokol úrazu.pdf",
            ),
        )
        conn.execute(
            "INSERT INTO control_results(entity_type, entity_id, photo_path) VALUES (?,?,?)",
            ("audity", 7, "control_results/audity/7/a_b_c_photo.jpg"),
        )
        conn.execute(
            "INSERT INTO hazard_identification_photos(relative_path, filename) VALUES (?,?)",
            ("rizeni_rizik/RID-1/fotografie/zdroj_rizika.jpg", "zdroj_rizika.jpg"),
        )
        conn.execute(
            "INSERT INTO ai_peer_reviews(export_file_path) VALUES (?)",
            (str(external_ai.resolve()),),
        )
        conn.execute(
            "INSERT INTO legal_documents(title, local_file_path) VALUES (?,?)",
            ("NV 361/2007", str(external_legal.resolve())),
        )
        conn.execute("INSERT INTO processes(name) VALUES (?)", ("Svařování",))
        conn.commit()
    finally:
        conn.close()

    settings = root / "data" / "nastaveni" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps(
            {"theme": "default", "language": "cs", "window_maximized": True},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return workspace, db_path, settings


def test_e2e_clean_restore_between_different_roots(tmp_path: Path):
    source_root = tmp_path / "machine-A"
    target_root = tmp_path / "machine-B-clean"
    source_ws, source_db, source_settings = _build_rich_source(source_root)

    package = tmp_path / f"uplnost{BACKUP_EXTENSION}"
    create_instance_backup(
        package,
        workspace_root=source_ws,
        database_path=source_db,
        settings_path=source_settings,
    )

    # Čistá instalace: prázdný workspace + prázdné settings
    target_ws = target_root / "manazer-bozp"
    target_ws.mkdir(parents=True)
    target_settings = target_root / "data" / "nastaveni" / "settings.json"
    target_settings.parent.mkdir(parents=True)
    target_settings.write_text("{}", encoding="utf-8")

    restore_instance_backup(
        package,
        workspace_root=target_ws,
        settings_path=target_settings,
    )

    target_db = target_ws / "databaze" / "manager_bozp.db"
    assert target_db.is_file()

    result = compare_instances(
        source_workspace=source_ws,
        source_db=source_db,
        restored_workspace=target_ws,
        restored_db=target_db,
        source_settings=source_settings,
        restored_settings=target_settings,
    )

    assert result.database_integrity_restored == "ok"
    assert result.user_version_source == result.user_version_restored
    assert result.row_count_mismatches == []
    assert result.missing_files_in_restored == []
    assert result.hash_mismatches == []
    assert result.broken_file_references == []
    assert result.settings_match is True
    assert result.ok_for_critical_data is True
    assert result.verdict == VERDICT_COMPLETE_WITH_LIMITATIONS
    assert result.row_counts_restored["employers"] == 1
    assert result.row_counts_restored["tasks"] == 1
    assert result.row_counts_restored["accidents"] == 1
    assert result.row_counts_restored["attachments"] == 1
    assert result.row_counts_restored["processes"] == 1

    # České názvy
    czech = target_ws / "prilohy" / "accident" / "1" / "Protokol úrazu.pdf"
    assert czech.is_file()
    assert sha256_file(czech) == sha256_file(
        source_ws / "prilohy" / "accident" / "1" / "Protokol úrazu.pdf"
    )

    # Vlastní číselník + šablona
    assert (target_ws / "ciselniky" / "modulove" / "vlastni_ciselnik.json").is_file()
    assert (
        target_ws / "templates" / "kniha_urazu" / "sablona_uživatelská.odt"
    ).is_file()

    # Settings obnovena
    assert json.loads(target_settings.read_text(encoding="utf-8"))["language"] == "cs"

    # export/ není v defaultní záloze
    assert not (target_ws / "export" / "out.pdf").exists()

    # Absolutní cesty detekovány jako omezení
    abs_findings = scan_absolute_paths(target_db)
    kinds = {f.classification for f in abs_findings}
    assert "external" in kinds
    assert "history" in kinds


def test_inventory_covers_backup_roots_only(tmp_path: Path):
    source_ws, _, _ = _build_rich_source(tmp_path / "inv")
    inv = inventory_workspace_files(source_ws)
    assert any(p.startswith("prilohy/") for p in inv)
    assert any(p.startswith("ciselniky/") for p in inv)
    assert not any(p.startswith("export/") for p in inv)
    assert not any(p.startswith("zalohy/") for p in inv)
    for root in BACKUP_WORKSPACE_ROOTS:
        # alespoň konfigurace existuje
        if root == "konfigurace":
            assert any(p.startswith(f"{root}/") for p in inv)


def test_missing_attachment_file_marks_incomplete(tmp_path: Path):
    source_ws, source_db, source_settings = _build_rich_source(tmp_path / "src")
    package = tmp_path / f"gap{BACKUP_EXTENSION}"
    create_instance_backup(
        package,
        workspace_root=source_ws,
        database_path=source_db,
        settings_path=source_settings,
    )

    target_ws = tmp_path / "dst" / "ws"
    target_ws.mkdir(parents=True)
    target_settings = tmp_path / "dst" / "settings.json"
    target_settings.write_text("{}", encoding="utf-8")
    restore_instance_backup(
        package, workspace_root=target_ws, settings_path=target_settings
    )

    # Simulace chybějícího souboru po obnově (poškození)
    victim = target_ws / "prilohy" / "accident" / "1" / "Protokol úrazu.pdf"
    victim.unlink()

    result = compare_instances(
        source_workspace=source_ws,
        source_db=source_db,
        restored_workspace=target_ws,
        restored_db=target_ws / "databaze" / "manager_bozp.db",
        source_settings=source_settings,
        restored_settings=target_settings,
    )
    assert result.verdict == VERDICT_INCOMPLETE
    assert result.missing_files_in_restored or result.broken_file_references

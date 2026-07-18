"""BACKUP-1a: formát *.mbbackup, metadata, cesty a SHA-256."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.backup import (
    BACKUP_FORMAT_VERSION,
    PACKAGE_KIND_INSTANCE_BACKUP,
    PACKAGE_KIND_RISK_CATALOG_EXPORT,
    PACKAGE_STATUS_COMPLETE,
    PACKAGE_STATUS_CREATING,
    BackupMetadata,
    BackupMetadataError,
    BackupPathError,
    build_file_entry,
    create_backup_metadata,
    hashes_equal,
    is_safe_archive_path,
    mark_package_complete,
    normalize_archive_path,
    sha256_bytes,
    sha256_file,
    validate_backup_metadata,
)
from core.version import APP_VERSION


def _sha(text: bytes) -> str:
    return sha256_bytes(text)


def _sample_files() -> list:
    payload = b"sqlite-snapshot"
    return [
        build_file_entry(
            "database/manager_bozp.db",
            component="database",
            size=len(payload),
            sha256=_sha(payload),
        ),
        build_file_entry(
            "workspace/prilohy/.gitkeep",
            component="workspace",
            size=0,
            sha256=_sha(b""),
            required=False,
        ),
        build_file_entry(
            "settings/app_settings.json",
            component="settings",
            size=2,
            sha256=_sha(b"{}"),
        ),
    ]


def test_create_valid_metadata_complete():
    files = _sample_files()
    meta = create_backup_metadata(
        files=files,
        package_status=PACKAGE_STATUS_COMPLETE,
        database_integrity="ok",
        schema_version=None,
    )
    assert meta.format_version == BACKUP_FORMAT_VERSION
    assert meta.package_kind == PACKAGE_KIND_INSTANCE_BACKUP
    assert meta.package_status == PACKAGE_STATUS_COMPLETE
    assert meta.app_version == APP_VERSION
    assert "database" in meta.included_components
    assert meta.total_content_size == sum(f.size for f in files)
    validate_backup_metadata(meta)


def test_json_round_trip():
    meta = create_backup_metadata(
        files=_sample_files(),
        package_status=PACKAGE_STATUS_COMPLETE,
        database_integrity="ok",
    )
    text = meta.to_json()
    loaded = BackupMetadata.from_json(text)
    assert loaded.to_dict() == meta.to_dict()
    assert "zaměstnavatel" not in text.lower()
    assert "employer" not in text.lower()


def test_missing_required_field():
    meta = create_backup_metadata(
        files=_sample_files(),
        package_status=PACKAGE_STATUS_COMPLETE,
    )
    data = meta.to_dict()
    del data["package_kind"]
    with pytest.raises(BackupMetadataError, match="package_kind"):
        BackupMetadata.from_dict(data)


def test_unsupported_format_version():
    meta = create_backup_metadata(
        files=_sample_files(),
        package_status=PACKAGE_STATUS_COMPLETE,
        validate=False,
    )
    meta.format_version = 999
    with pytest.raises(BackupMetadataError, match="Nepodporovaná verze"):
        validate_backup_metadata(meta)


def test_wrong_package_kind():
    meta = create_backup_metadata(
        files=_sample_files(),
        package_status=PACKAGE_STATUS_COMPLETE,
        package_kind=PACKAGE_KIND_RISK_CATALOG_EXPORT,
        validate=False,
    )
    with pytest.raises(BackupMetadataError, match="typ balíčku"):
        validate_backup_metadata(meta)


def test_reject_absolute_path():
    with pytest.raises(BackupPathError):
        normalize_archive_path("/tmp/evil.db")
    assert not is_safe_archive_path("/etc/passwd")


def test_reject_parent_segment():
    with pytest.raises(BackupPathError, match=r"\.\."):
        normalize_archive_path("workspace/../database/x.db")
    with pytest.raises(BackupPathError):
        normalize_archive_path("../outside.txt")


def test_reject_windows_path_outside_root():
    with pytest.raises(BackupPathError):
        normalize_archive_path(r"C:\Windows\system32\evil.dll")
    with pytest.raises(BackupPathError):
        normalize_archive_path("C:/Users/Public/evil.db")
    with pytest.raises(BackupPathError):
        normalize_archive_path(r"\\server\share\file.db")


def test_duplicate_path_rejected():
    files = _sample_files()
    dup = build_file_entry(
        files[0].path,
        component="database",
        size=1,
        sha256=_sha(b"x"),
    )
    meta = create_backup_metadata(
        files=files + [dup],
        package_status=PACKAGE_STATUS_COMPLETE,
        validate=False,
    )
    with pytest.raises(BackupMetadataError, match="Duplicitní"):
        validate_backup_metadata(meta)


def test_sha256_file(tmp_path: Path):
    path = tmp_path / "chunk.bin"
    # větší než jeden malý chunk – ověří streamované čtení
    data = b"A" * 3000 + "české".encode("utf-8") + b"B" * 2000
    path.write_bytes(data)
    assert sha256_file(path, chunk_size=1024) == sha256_bytes(data)


def test_sha256_bytes_and_compare():
    digest = sha256_bytes(b"hello")
    assert len(digest) == 64
    assert hashes_equal(digest, digest.upper())
    assert not hashes_equal(digest, "0" * 64)
    assert not hashes_equal(None, digest)


def test_incomplete_status_rejected_as_valid_backup():
    meta = create_backup_metadata(
        files=_sample_files(),
        package_status=PACKAGE_STATUS_CREATING,
    )
    assert meta.package_status == PACKAGE_STATUS_CREATING
    with pytest.raises(BackupMetadataError, match="dokončený"):
        validate_backup_metadata(meta)
    with pytest.raises(BackupMetadataError, match="dokončený"):
        BackupMetadata.from_json(meta.to_json())


def test_valid_completed_manifest():
    creating = create_backup_metadata(files=_sample_files())
    complete = mark_package_complete(creating)
    assert complete.package_status == PACKAGE_STATUS_COMPLETE
    validate_backup_metadata(complete)
    loaded = BackupMetadata.from_json(complete.to_json())
    assert loaded.package_status == PACKAGE_STATUS_COMPLETE


def test_czech_filenames_and_directories():
    path = normalize_archive_path("workspace/přílohy/Úraz zaměstnance.pdf")
    assert path == "workspace/přílohy/Úraz zaměstnance.pdf"
    entry = build_file_entry(
        "workspace\\zálohy\\kopie.db",
        component="workspace",
        size=1,
        sha256=_sha(b"1"),
    )
    assert entry.path == "workspace/zálohy/kopie.db"


def test_path_separator_normalization():
    assert normalize_archive_path(r"database\manager_bozp.db") == "database/manager_bozp.db"
    assert normalize_archive_path("settings//app.json") == "settings/app.json"
    assert normalize_archive_path("./workspace/a.txt") == "workspace/a.txt"
    with pytest.raises(BackupPathError):
        normalize_archive_path("")


def test_empty_and_dangerous_paths_in_manifest_json():
    meta = create_backup_metadata(
        files=_sample_files(),
        package_status=PACKAGE_STATUS_COMPLETE,
    )
    data = meta.to_dict()
    data["files"][0]["path"] = "../escape.db"
    with pytest.raises(BackupMetadataError):
        BackupMetadata.from_dict(data)

    data = meta.to_dict()
    data["files"][0]["path"] = "/abs/path.db"
    with pytest.raises(BackupMetadataError):
        BackupMetadata.from_dict(data)

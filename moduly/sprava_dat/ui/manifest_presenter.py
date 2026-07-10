from pathlib import Path

STATUS_OK = "V pořádku"
STATUS_WARNING = "Vytvořena s upozorněním"
STATUS_ATTENTION = "Vyžaduje pozornost"


def _status_label(condition: bool) -> str:
    return STATUS_OK if condition else "Problém"


def _warning_label(condition: bool) -> str:
    return STATUS_OK if condition else "Upozornění"


def _backup_health_value(manifest: dict) -> str:
    if not manifest.get("verified"):
        return "Neúspěšné"
    if manifest.get("backup_health") == "warning":
        return STATUS_WARNING
    return STATUS_OK


def _backup_health_status(manifest: dict) -> str:
    if not manifest.get("verified"):
        return "Problém"
    if manifest.get("backup_health") == "warning":
        return STATUS_WARNING
    return STATUS_OK


def rows_from_backup_manifest(manifest: dict | None) -> list[tuple[str, str, str]]:
    if not manifest:
        return []

    dash = "—"
    database_path = str(manifest.get("database_path") or "databaze/manager_bozp.db")
    database_name = Path(database_path).name
    db_counts = manifest.get("database_counts") or {}
    missing_attachments = int(manifest.get("attachment_files_missing") or 0)
    missing_photos = int(manifest.get("control_result_photos_missing") or 0)
    orphan_files = int(manifest.get("attachment_orphan_files") or 0)

    rows = [
        ("Databáze aplikace", database_name, _status_label(bool(manifest.get("database_included")))),
        ("Počet souborů", str(manifest.get("file_count", 0)), dash),
        ("Globální číselníky", str(manifest.get("global_catalogs", 0)), STATUS_OK),
        ("Modulové číselníky", str(manifest.get("module_catalogs", 0)), STATUS_OK),
        ("Auditní metodiky", str(manifest.get("audit_methodologies", 0)), STATUS_OK),
        ("Metodiky prověrek", str(manifest.get("proverky_methodologies", 0)), STATUS_OK),
        ("Právní předpisy", str(db_counts.get("legal_documents", 0)), dash),
        ("Řídicí procesy", str(db_counts.get("control_processes", 0)), dash),
        ("Úkoly", str(db_counts.get("tasks", 0)), dash),
        ("Pracovní úrazy", str(db_counts.get("accidents", 0)), dash),
        ("Audity", str(db_counts.get("audits", 0)), dash),
        ("Prověrky", str(db_counts.get("inspections", 0)), dash),
    ]

    if "attachments_db_count" in manifest:
        rows.extend(
            [
                (
                    "Přílohy evidované v DB",
                    str(manifest.get("attachments_db_count", 0)),
                    dash,
                ),
                (
                    "Přílohy nalezené",
                    str(manifest.get("attachment_files_found", 0)),
                    _status_label(missing_attachments == 0),
                ),
                (
                    "Chybějící přílohy",
                    str(missing_attachments),
                    _status_label(missing_attachments == 0),
                ),
                (
                    "Soubory příloh bez DB záznamu",
                    str(orphan_files),
                    _warning_label(orphan_files == 0),
                ),
                (
                    "Fotografie kontrolních bodů evidované",
                    str(manifest.get("control_result_photo_db_count", 0)),
                    dash,
                ),
                (
                    "Fotografie nalezené",
                    str(manifest.get("control_result_photos_found", 0)),
                    _status_label(missing_photos == 0),
                ),
                (
                    "Chybějící fotografie",
                    str(missing_photos),
                    _status_label(missing_photos == 0),
                ),
                (
                    "Referenční fotografie metodik",
                    str(manifest.get("reference_photo_files", 0)),
                    dash,
                ),
                (
                    "Generované exporty",
                    str(manifest.get("export_files_count", 0)),
                    dash,
                ),
                (
                    "Adresář control_results",
                    "Ano" if manifest.get("control_results_included") else "Ne",
                    _status_label(bool(manifest.get("control_results_included"))),
                ),
            ]
        )

    rows.extend(
        [
            (
                "CRC ZIP",
                "Ověřeno" if manifest.get("zip_crc_ok") else "Chyba",
                _status_label(bool(manifest.get("zip_crc_ok"))),
            ),
            (
                "Ověření zálohy",
                _backup_health_value(manifest),
                _backup_health_status(manifest),
            ),
        ]
    )
    return rows


def rows_from_integrity_manifest(manifest: dict | None) -> list[tuple[str, str, str]]:
    if not manifest:
        return []

    return [
        (
            "ZIP lze otevřít",
            "Ano" if manifest.get("zip_readable") else "Ne",
            _status_label(bool(manifest.get("zip_readable"))),
        ),
        (
            "Databáze v záloze",
            "Ano" if manifest.get("database_included") else "Ne",
            _status_label(bool(manifest.get("database_included"))),
        ),
        (
            "CRC ZIP",
            "Ověřeno" if manifest.get("zip_crc_ok") else "Chyba",
            _status_label(bool(manifest.get("zip_crc_ok"))),
        ),
        (
            "Kontrola integrity",
            "Úspěšná" if manifest.get("verified") else "Neúspěšná",
            _status_label(bool(manifest.get("verified"))),
        ),
    ]

from pathlib import Path

STATUS_OK = "V pořádku"
STATUS_ATTENTION = "Vyžaduje pozornost"


def _status_label(condition: bool) -> str:
    return "V pořádku" if condition else "Problém"


def rows_from_backup_manifest(manifest: dict | None) -> list[tuple[str, str, str]]:
    if not manifest:
        return []

    dash = "—"
    database_path = str(manifest.get("database_path") or "databaze/manager_bozp.db")
    database_name = Path(database_path).name
    db_counts = manifest.get("database_counts") or {}

    return [
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
        (
            "CRC ZIP",
            "Ověřeno" if manifest.get("zip_crc_ok") else "Chyba",
            _status_label(bool(manifest.get("zip_crc_ok"))),
        ),
        (
            "Ověření zálohy",
            "Úspěšné" if manifest.get("verified") else "Neúspěšné",
            _status_label(bool(manifest.get("verified"))),
        ),
    ]


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

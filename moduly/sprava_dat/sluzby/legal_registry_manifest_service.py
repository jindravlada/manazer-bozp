import json
from pathlib import Path

from core.version import app_display_name, is_compatible_application_name

_REGISTRY_EXPORT_VERSIONS = {1, 2}


class LegalRegistryManifestService:
    """Ověření exportního JSON registru a sestavení manifestu."""

    INCLUDED_ITEMS: tuple[str, ...] = (
        "Právní předpisy",
        "Verze předpisů",
        "Ustanovení",
        "Řídicí procesy",
        "Právní podklady procesů",
        "Sankce",
        "Kontroly změn",
        "Zjištěné změny",
        "Změněná ustanovení",
    )

    EXCLUDED_ITEMS: tuple[str, ...] = (
        "Auditní metodiky",
        "Metodiky prověrek",
        "Registr rizik",
        "Ostatní databáze programu",
    )

    LINKS_WARNING = (
        "Import registru zachovává původní ID řídicích procesů.\n\n"
        "Pokud nejsou přeneseny auditní metodiky, budou procesy existovat, "
        "ale jejich použití v auditech nebude obnoveno.\n\n"
        "Po importu auditních metodik se vazby automaticky obnoví."
    )

    DESCRIPTION = (
        "Slouží k přenosu Registru právních požadavků mezi dvěma instalacemi Manažera BOZP."
    )

    COUNT_LABELS: tuple[tuple[str, str], ...] = (
        ("documents", "Právní předpisy"),
        ("versions", "Verze"),
        ("sections", "Ustanovení"),
        ("requirements", "Řídicí procesy"),
        ("sources", "Právní podklady"),
        ("sanctions", "Sankce"),
        ("check_runs", "Kontroly změn"),
        ("changes", "Zjištěné změny"),
        ("change_sections", "Změněná ustanovení"),
    )

    def verify_export_file(self, path: str | Path) -> dict:
        source = Path(path)
        manifest: dict = {
            "path": str(source.resolve()),
            "verified": False,
            "verification_errors": [],
            "record_counts": {},
        }

        if not source.is_file():
            manifest["verification_errors"].append("Exportní soubor neexistuje.")
            return manifest

        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            manifest["verification_errors"].append(f"Exportní JSON nelze načíst: {exc}")
            return manifest

        if not isinstance(payload, dict):
            manifest["verification_errors"].append("Exportní soubor má neplatný formát.")
            return manifest

        export_version = payload.get("export_version")
        if export_version not in _REGISTRY_EXPORT_VERSIONS:
            manifest["verification_errors"].append("Exportní soubor má nepodporovanou verzi.")

        application = str(payload.get("application") or "").strip()
        if application and not is_compatible_application_name(application):
            manifest["verification_errors"].append(
                f"Exportní soubor nepochází z {app_display_name()}."
            )

        record_counts = payload.get("record_counts")
        if not isinstance(record_counts, dict):
            manifest["verification_errors"].append("Exportní soubor neobsahuje record_counts.")
        else:
            expected_keys = {key for key, _ in self.COUNT_LABELS}
            manifest["record_counts"] = {
                key: int(record_counts.get(key, 0)) for key in expected_keys
            }
            for array_key in (
                "documents",
                "versions",
                "sections",
                "requirements",
                "sources",
                "sanctions",
                "check_runs",
                "changes",
                "change_sections",
            ):
                array_value = payload.get(array_key, [])
                if isinstance(array_value, list) and array_key in manifest["record_counts"]:
                    if manifest["record_counts"][array_key] != len(array_value):
                        manifest["verification_errors"].append(
                            f"Počet v record_counts.{array_key} neodpovídá obsahu souboru."
                        )

        manifest["export_version"] = export_version
        manifest["verified"] = not manifest["verification_errors"]
        return manifest

    def format_counts_manifest(self, record_counts: dict | None) -> str:
        if not record_counts:
            return "—"
        lines = []
        for key, label in self.COUNT_LABELS:
            lines.append(f"{label}: {record_counts.get(key, 0)}")
        return "\n".join(lines)

    def rows_from_record_counts(
        self,
        record_counts: dict | None,
        *,
        verified: bool = True,
    ) -> list[tuple[str, str, str]]:
        if not record_counts:
            return []

        status = "V pořádku" if verified else "Problém"
        dash = "—"
        return [
            (label, str(record_counts.get(key, 0)), status if verified else dash)
            for key, label in self.COUNT_LABELS
        ]

    def import_result_to_counts(self, result) -> dict[str, int]:
        return {
            "documents": result.document_count,
            "versions": result.version_count,
            "sections": result.section_count,
            "requirements": result.requirement_count,
            "sources": result.source_count,
            "sanctions": result.sanction_count,
            "check_runs": result.check_run_count,
            "changes": result.change_count,
            "change_sections": result.change_section_count,
        }


legal_registry_manifest_service = LegalRegistryManifestService()

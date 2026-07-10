from __future__ import annotations

from dataclasses import dataclass

from moduly.sprava_dat.sluzby.codebook_catalog_service import (
    STORAGE_BUNDLED_JSON,
    STORAGE_DATABASE,
    STORAGE_HARDCODED,
    CodebookEntry,
    _KIND_DATABASE,
    _KIND_HARDCODED,
    _KIND_JSON_BUNDLED,
)


@dataclass(frozen=True)
class CodebookCapabilities:
    """Schopnosti číselníku pro UX Správy dat a budoucí rozšíření."""

    export_supported: bool
    import_supported: bool
    internet_update_supported: bool = False
    import_unavailable_headline: str = ""
    import_unavailable_reason: str = ""

    @property
    def shows_import_action(self) -> bool:
        return self.import_supported

    @property
    def shows_import_info(self) -> bool:
        return self.export_supported and not self.import_supported


def capabilities_for(entry: CodebookEntry) -> CodebookCapabilities:
    if entry.importable:
        return CodebookCapabilities(
            export_supported=entry.exportable,
            import_supported=True,
        )

    headline, reason = _non_importable_messages(entry)
    return CodebookCapabilities(
        export_supported=entry.exportable,
        import_supported=False,
        import_unavailable_headline=headline,
        import_unavailable_reason=reason,
    )


def _non_importable_messages(entry: CodebookEntry) -> tuple[str, str]:
    profile = _distribution_profile(entry)
    return _IMPORT_UNAVAILABLE_MESSAGES[profile]


def _distribution_profile(entry: CodebookEntry) -> str:
    if entry.kind == _KIND_JSON_BUNDLED or entry.storage_type == STORAGE_BUNDLED_JSON:
        return "bundled_database"

    if entry.kind == _KIND_HARDCODED or entry.storage_type == STORAGE_HARDCODED:
        if entry.codebook_id.endswith(":zdravotni_pojistovny"):
            return "distributed_reference"
        return "installation_builtin"

    if entry.kind == _KIND_DATABASE or entry.storage_type == STORAGE_DATABASE:
        return "module_managed"

    return "unsupported_import"


_IMPORT_UNAVAILABLE_MESSAGES: dict[str, tuple[str, str]] = {
    "bundled_database": (
        "Import tohoto číselníku není podporován.",
        "Přebírá se z distribuované databáze programu.",
    ),
    "installation_builtin": (
        "Tento číselník je součástí instalace programu a nelze jej importovat samostatně.",
        "Součást instalace programu.",
    ),
    "distributed_reference": (
        "Tento číselník je součástí instalace programu a nelze jej importovat samostatně.",
        "Distribuovaný referenční číselník.",
    ),
    "module_managed": (
        "Import tohoto číselníku není podporován.",
        "Spravuje se v rámci modulu aplikace.",
    ),
    "unsupported_import": (
        "Import tohoto číselníku není podporován.",
        "Samostatný import není k dispozici.",
    ),
}

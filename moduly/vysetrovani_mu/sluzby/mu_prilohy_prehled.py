"""Zařazení příloh vyšetřování MU podle uložených vazeb a názvových předpon."""

from __future__ import annotations

import json

SECTION_ZAJISTENI = "Zajištění důkazů"
SECTION_SVEDCI = "Svědci"
SECTION_OHLEDANI = "Ohledání místa"
SECTION_CASOVA_OSA = "Časová osa"
SECTION_DODRZOVANI = "Dodržování předpisů"
SECTION_SHARED = "Společný seznam příloh"

# Delší předpona musí být dřív. Jde o názvy, které modul sám zapisuje.
_PREFIXES = (
    ("Foto-CasZarizeni-", SECTION_CASOVA_OSA),
    ("Foto-", SECTION_ZAJISTENI),
    ("Ohledani-", SECTION_OHLEDANI),
    ("DodrzovaniPredpisu-", SECTION_DODRZOVANI),
    ("Formular-", SECTION_SVEDCI),
)


def linked_attachment_names(
    *,
    zajisteni_dukazu_json: str = "",
    casova_osa_json: str = "",
    ohledani_mista_json: str = "",
) -> tuple[set[str], set[str], set[str]]:
    """Názvy souborů výslovně uložené ve formulářích spisu."""
    zajisteni = _load_json(zajisteni_dukazu_json)
    casova = _load_json(casova_osa_json)
    ohledani = _load_json(ohledani_mista_json)

    photos = zajisteni.get("fotky") if isinstance(zajisteni, dict) else None
    zajisteni_names = _names(photos.values() if isinstance(photos, dict) else ())

    sync = casova.get("cas_synchronizace") if isinstance(casova, dict) else None
    rows = sync.get("caszarizeni_rows") if isinstance(sync, dict) else None
    casova_names = _names(
        row.get("foto") for row in rows if isinstance(row, dict)
    ) if isinstance(rows, list) else set()

    ohledani_names = _names(
        [ohledani.get("ohledani_priloha")] if isinstance(ohledani, dict) else ()
    )
    return zajisteni_names, casova_names, ohledani_names


def classify_mu_attachment(
    filename: str,
    *,
    zajisteni_names: set[str],
    casova_osa_names: set[str],
    ohledani_names: set[str],
) -> str:
    """Jedno zařazení. Nejednoznačný nebo neznámý původ je společný seznam."""
    name = (filename or "").strip()
    linked: set[str] = set()
    if name and name in zajisteni_names:
        linked.add(SECTION_ZAJISTENI)
    if name and name in casova_osa_names:
        linked.add(SECTION_CASOVA_OSA)
    if name and name in ohledani_names:
        linked.add(SECTION_OHLEDANI)

    prefixed = ""
    for prefix, section in _PREFIXES:
        if name.startswith(prefix):
            prefixed = section
            break

    if len(linked) == 1 and (not prefixed or prefixed == next(iter(linked))):
        return next(iter(linked))
    if not linked and prefixed:
        return prefixed
    return SECTION_SHARED


def _load_json(raw: str) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _names(values) -> set[str]:
    found: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text:
            found.add(text)
    return found

"""Validace JSON znalostní databáze interních auditů."""

from __future__ import annotations

import json
from pathlib import Path

from core.services.editable_catalog_service import editable_catalog_service

TEMPLATE_BASENAME = "_sablona_rizeni_procesu.json"
PROCESY_BASENAME = "procesy.json"

VALID_ZAVAZNOST = frozenset({"kriticka", "vysoka", "stredni", "nizka"})

PROCESS_REQUIRED_FIELDS = (
    "verze",
    "id",
    "nazev",
    "popis",
    "ucel_procesu",
    "proc_je_dulezity",
    "ocekavany_vystup",
    "poradi",
    "aktivni",
    "vazby_procesy",
    "pozadavky_norem",
    "sekce",
)

SECTION_REQUIRED_FIELDS = (
    "id",
    "nazev",
    "popis",
    "cil_overeni",
    "poradi",
    "aktivni",
    "sekce",
    "postup_kontroly",
    "auditni_tvrzeni",
    "kontrolni_body",
    "navodne_otazky",
    "objektivni_dukazy",
    "doporucene_rozhovory",
    "pozorovani_v_provozu",
    "typicke_neshody",
    "typicke_zavady",
    "pkz",
    "pozorovani",
    "doporucene_postupy",
    "legislativa",
    "pozadavky_normy",
    "vazby_procesy",
    "poznamky_auditora",
    "referencni_fotografie",
    "historie",
)

LIST_ITEM_FIELDS = ("id", "nazev", "poradi", "aktivni")
ASSERTION_FIELDS = ("id", "text", "popis", "poradi", "aktivni", "zavaznost")


def default_audity_dir() -> Path:
    return editable_catalog_service.bundled_dir() / "audity"


def load_json_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Kořen JSON musí být objekt: {path}")
    return payload


def _validate_ids(items: list, *, path: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{path}[{index}]: položka není objekt")
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            errors.append(f"{path}[{index}]: chybí id")
            continue
        if item_id in seen:
            errors.append(f"{path}: duplicitní id '{item_id}'")
        seen.add(item_id)


def _validate_list_items(items: list, *, path: str, errors: list[str]) -> None:
    _validate_ids(items, path=path, errors=errors)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_path = f"{path}[{index}]"
        for field in LIST_ITEM_FIELDS:
            if field not in item:
                errors.append(f"{item_path}: chybí pole '{field}'")


def _validate_assertions(items: list, *, path: str, errors: list[str]) -> None:
    _validate_ids(items, path=path, errors=errors)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_path = f"{path}[{index}]"
        for field in ASSERTION_FIELDS:
            if field not in item:
                errors.append(f"{item_path}: chybí pole '{field}'")
        text = str(item.get("text") or item.get("nazev") or "").strip()
        if not text:
            errors.append(f"{item_path}: chybí text tvrzení")
        severity = str(item.get("zavaznost") or "").strip()
        if severity and severity not in VALID_ZAVAZNOST:
            errors.append(f"{item_path}: neplatná závažnost '{severity}'")


def _validate_section(section: dict, *, path: str, errors: list[str]) -> None:
    if not isinstance(section, dict):
        errors.append(f"{path}: oblast není objekt")
        return

    for field in SECTION_REQUIRED_FIELDS:
        if field not in section:
            errors.append(f"{path}: chybí pole '{field}'")

    section_id = str(section.get("id") or "").strip()
    if not section_id:
        errors.append(f"{path}: chybí id oblasti")

    _validate_assertions(
        section.get("auditni_tvrzeni") or [],
        path=f"{path}.auditni_tvrzeni",
        errors=errors,
    )
    for list_field in (
        "postup_kontroly",
        "kontrolni_body",
        "navodne_otazky",
        "objektivni_dukazy",
        "doporucene_rozhovory",
        "pozorovani_v_provozu",
        "typicke_neshody",
        "typicke_zavady",
        "pkz",
        "pozorovani",
        "doporucene_postupy",
        "legislativa",
        "pozadavky_normy",
        "vazby_procesy",
        "poznamky_auditora",
        "referencni_fotografie",
        "historie",
    ):
        _validate_list_items(
            section.get(list_field) or [],
            path=f"{path}.{list_field}",
            errors=errors,
        )

    for index, nested in enumerate(section.get("sekce") or []):
        nested_id = (
            str(nested.get("id") or index).strip()
            if isinstance(nested, dict)
            else str(index)
        )
        _validate_section(nested, path=f"{path}.sekce[{nested_id}]", errors=errors)


def validate_knowledge_data(data: dict, *, source_name: str) -> list[str]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"{source_name}: kořen musí být objekt"]

    for field in PROCESS_REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"{source_name}: chybí pole '{field}'")

    process_id = str(data.get("id") or "").strip()
    if not process_id:
        errors.append(f"{source_name}: chybí id procesu")
    elif source_name.endswith(".json") and source_name != PROCESY_BASENAME:
        if source_name != f"{process_id}.json":
            errors.append(
                f"{source_name}: id '{process_id}' neodpovídá názvu souboru"
            )

    _validate_list_items(
        data.get("vazby_procesy") or [],
        path=f"{source_name}.vazby_procesy",
        errors=errors,
    )
    _validate_list_items(
        data.get("pozadavky_norem") or [],
        path=f"{source_name}.pozadavky_norem",
        errors=errors,
    )

    for index, section in enumerate(data.get("sekce") or []):
        section_id = (
            str(section.get("id") or index).strip()
            if isinstance(section, dict)
            else str(index)
        )
        _validate_section(section, path=f"{source_name}.sekce[{section_id}]", errors=errors)

    return errors


def validate_procesy_registry_data(data: dict, *, source_name: str = PROCESY_BASENAME) -> list[str]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"{source_name}: kořen musí být objekt"]

    processes = data.get("procesy") or []
    if not isinstance(processes, list):
        errors.append(f"{source_name}: pole 'procesy' musí být seznam")
        return errors

    seen_ids: set[str] = set()
    for index, process in enumerate(processes):
        if not isinstance(process, dict):
            errors.append(f"{source_name}[{index}]: proces není objekt")
            continue

        item_path = f"{source_name}[{index}]"
        process_id = str(process.get("id") or "").strip()
        nazev = str(process.get("nazev") or "").strip()
        soubor = str(process.get("soubor_znalosti") or "").strip()

        if not process_id:
            errors.append(f"{item_path}: chybí id")
            continue
        if process_id in seen_ids:
            errors.append(f"{source_name}: duplicitní id '{process_id}'")
        seen_ids.add(process_id)

        if not nazev:
            errors.append(f"{item_path}: chybí název")
        if not soubor:
            errors.append(f"{source_name}: proces '{process_id}' nemá soubor_znalosti")

    return errors


def validate_knowledge_file(path: Path, *, data: dict | None = None) -> list[str]:
    try:
        payload = data if data is not None else load_json_file(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"{path.name}: neplatný JSON ({exc})"]

    if path.name == PROCESY_BASENAME:
        return validate_procesy_registry_data(payload, source_name=path.name)

    return validate_knowledge_data(payload, source_name=path.name)


def validate_all_catalogs(audity_dir: Path | None = None) -> list[str]:
    catalog_dir = audity_dir or default_audity_dir()
    procesy_file = catalog_dir / PROCESY_BASENAME
    errors: list[str] = []

    if not procesy_file.is_file():
        errors.append("Chybí procesy.json")
        return errors

    try:
        registry = load_json_file(procesy_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"procesy.json: neplatný JSON ({exc})")
        return errors

    processes = registry.get("procesy") or []
    if not isinstance(processes, list):
        errors.append("procesy.json: pole 'procesy' musí být seznam")
        return errors

    registered_files: set[str] = set()
    for index, process in enumerate(processes):
        if not isinstance(process, dict):
            errors.append(f"procesy.json[{index}]: proces není objekt")
            continue

        process_id = str(process.get("id") or "").strip()
        soubor = str(process.get("soubor_znalosti") or "").strip()
        if not process_id:
            errors.append(f"procesy.json[{index}]: chybí id")
            continue
        if not soubor:
            errors.append(f"procesy.json: proces '{process_id}' nemá soubor_znalosti")
            continue

        knowledge_path = catalog_dir / soubor
        registered_files.add(soubor)
        if not knowledge_path.is_file():
            errors.append(
                f"procesy.json: chybí soubor '{soubor}' pro proces '{process_id}'"
            )
            continue

        errors.extend(validate_knowledge_file(knowledge_path))

    for path in sorted(catalog_dir.glob("*.json")):
        if path.name in {PROCESY_BASENAME, TEMPLATE_BASENAME}:
            continue
        if path.name.startswith("_"):
            continue
        if path.name not in registered_files:
            errors.append(f"{path.name}: soubor není registrován v procesy.json")

    return errors

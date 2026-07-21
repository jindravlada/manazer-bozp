#!/usr/bin/env python3
"""Jednorázové odstranění osiřelých výsledků auditních tvrzení z celé DB.

Skript NENÍ volán aplikací ani migrací — spouští se ručně.

Výchozí režim: projde všechny řádky ``control_results`` s ``entity_type='audity'``
a odstraní ty, jejichž ``source_control_point_id`` už není mezi aktuálními
auditními tvrzeními dané sekce v metodice (stejné kritérium jako A12.3).

Volitelně lze omezit na jeden audit přes ``--audit``.

Platné výsledky se nemažou jen proto, že mají stav „Není relevantní“
(``nelze_posoudit``).
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.shared.constants import ENTITY_AUDITY, CONTROL_RESULT_LABELS
from core.services.storage_service import storage_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


@dataclass(frozen=True)
class OrphanCandidate:
    id: int
    audit_id: int
    audit_number: str
    assertion_id: str
    assertion_text: str
    result: str
    result_label: str
    area_id: str
    area_label: str
    section_id: str
    section_label: str


def _iter_knowledge_sections(sections: list) -> list[dict]:
    collected: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        collected.append(section)
        nested = section.get("sekce") or []
        if isinstance(nested, list):
            collected.extend(_iter_knowledge_sections(nested))
    return collected


def _section_assertion_ids(
    process_id: str,
    section_id: str,
    *,
    cache: dict[tuple[str, str], set[str] | None],
) -> set[str] | None:
    """Vrátí ID aktuálních tvrzení sekce, nebo None pokud sekce v metodice není."""
    key = (process_id, section_id)
    if key in cache:
        return cache[key]

    if not process_id or not section_id:
        cache[key] = None
        return None

    process = audit_knowledge_service.get_process_by_id(process_id, ensure=False)
    if process is None:
        cache[key] = None
        return None

    knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
    if not knowledge:
        cache[key] = None
        return None

    for section in _iter_knowledge_sections(knowledge.get("sekce") or []):
        if str(section.get("id") or "").strip() != section_id:
            continue
        if not section.get("aktivni", True):
            cache[key] = set()
            return cache[key]
        cache[key] = {
            str(item.get("id") or "").strip()
            for item in audit_knowledge_service.get_audit_questions(section)
            if str(item.get("id") or "").strip()
        }
        return cache[key]

    cache[key] = None
    return None


def resolve_audit_id(connection: sqlite3.Connection, audit_ref: str) -> int:
    """Vrátí ID auditu podle číselného ID nebo čísla auditu (``number``)."""
    audit_ref = audit_ref.strip()
    if not audit_ref:
        raise ValueError("Chybí identifikace auditu (--audit).")

    row = None
    if audit_ref.isdigit():
        row = connection.execute(
            "SELECT id, number FROM audits WHERE id = ?",
            (int(audit_ref),),
        ).fetchone()
    if row is None:
        row = connection.execute(
            "SELECT id, number FROM audits WHERE number = ?",
            (audit_ref,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Audit nebyl nalezen: {audit_ref!r}")
    return int(row[0])


def _load_audit_numbers(connection: sqlite3.Connection) -> dict[int, str]:
    return {
        int(row[0]): str(row[1] or "")
        for row in connection.execute("SELECT id, number FROM audits")
    }


def find_orphaned_candidates(
    connection: sqlite3.Connection,
    *,
    audit_id: int | None = None,
) -> list[OrphanCandidate]:
    """Najde osiřelé výsledky — výchozí: celá DB (všechny audity)."""
    audit_numbers = _load_audit_numbers(connection)

    sql = """
        SELECT
            id,
            entity_id,
            source_area_id,
            source_area_label,
            source_section_id,
            source_section_label,
            source_control_point_id,
            source_control_point_label,
            result
        FROM control_results
        WHERE entity_type = ?
    """
    params: list[object] = [ENTITY_AUDITY]
    if audit_id is not None:
        sql += " AND entity_id = ?"
        params.append(audit_id)
    sql += " ORDER BY entity_id, id"

    rows = connection.execute(sql, params).fetchall()
    section_cache: dict[tuple[str, str], set[str] | None] = {}
    orphans: list[OrphanCandidate] = []

    for row in rows:
        (
            result_id,
            entity_id,
            area_id,
            area_label,
            section_id,
            section_label,
            assertion_id,
            assertion_text,
            result,
        ) = row
        area_id = str(area_id or "").strip()
        section_id = str(section_id or "").strip()
        assertion_id = str(assertion_id or "").strip()
        result = str(result or "").strip()
        entity_id = int(entity_id)

        # Musí odkazovat na konkrétní tvrzení.
        if not assertion_id:
            continue

        assertion_ids = _section_assertion_ids(
            area_id,
            section_id,
            cache=section_cache,
        )
        if assertion_ids is None:
            # Proces/sekce v metodice neexistuje — ponechat (není bezpečně osiřelé).
            continue
        if assertion_id in assertion_ids:
            continue

        orphans.append(
            OrphanCandidate(
                id=int(result_id),
                audit_id=entity_id,
                audit_number=audit_numbers.get(entity_id, ""),
                assertion_id=assertion_id,
                assertion_text=str(assertion_text or "").strip(),
                result=result,
                result_label=CONTROL_RESULT_LABELS.get(result, result or "—"),
                area_id=area_id,
                area_label=str(area_label or "").strip(),
                section_id=section_id,
                section_label=str(section_label or "").strip(),
            )
        )

    return orphans


def print_candidates(
    candidates: list[OrphanCandidate],
    *,
    scope_label: str,
) -> None:
    print(f"Rozsah: {scope_label}")
    print(f"Kandidátů na odstranění: {len(candidates)}")
    if not candidates:
        return

    by_audit: dict[int, list[OrphanCandidate]] = defaultdict(list)
    for item in candidates:
        by_audit[item.audit_id].append(item)

    print(f"Dotčených auditů: {len(by_audit)}")
    print()
    for audit_id in sorted(by_audit):
        group = by_audit[audit_id]
        number = group[0].audit_number or "—"
        print(f"=== Audit {number} (id={audit_id}) — {len(group)} záznam(ů) ===")
        for item in group:
            area = item.section_label or item.area_label or item.section_id or item.area_id
            print(f"- result_id={item.id}")
            print(f"  assertion_id={item.assertion_id}")
            print(f"  text={item.assertion_text or '—'}")
            print(f"  stav={item.result} ({item.result_label})")
            print(f"  oblast/sekce={area} [{item.area_id}/{item.section_id}]")
            print()


def create_backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.cleanup-orphans-{stamp}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def delete_candidates(
    connection: sqlite3.Connection,
    candidates: list[OrphanCandidate],
) -> int:
    if not candidates:
        return 0
    ids = [item.id for item in candidates]
    placeholders = ",".join("?" for _ in ids)
    cursor = connection.execute(
        f"""
        DELETE FROM control_results
        WHERE entity_type = ?
          AND id IN ({placeholders})
        """,
        (ENTITY_AUDITY, *ids),
    )
    return int(cursor.rowcount)


def integrity_ok(connection: sqlite3.Connection) -> tuple[bool, str]:
    row = connection.execute("PRAGMA integrity_check").fetchone()
    message = str(row[0]) if row else "missing"
    return message == "ok", message


def resolve_data_dir(db_path: Path, data_dir: Path | None) -> Path:
    if data_dir is not None:
        return data_dir.resolve()
    if db_path.parent.name == "databaze":
        return db_path.parent.parent.resolve()
    return storage_service.base.resolve()


def configure_knowledge_root(data_dir: Path) -> None:
    """Nasměruje knowledge service na číselníky vedle zvolené databáze."""
    storage_service.base = data_dir
    (data_dir / "ciselniky").mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bezpečné odstranění osiřelých control_results auditních tvrzení "
            "z celé SQLite databáze (jednorázový nástroj)."
        ),
    )
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Cesta k SQLite databázi (např. .../databaze/manager_bozp.db).",
    )
    parser.add_argument(
        "--audit",
        default=None,
        help=(
            "Volitelně omezit na jeden audit (ID nebo číslo, např. 3/2027). "
            "Bez tohoto přepínače se čistí celá databáze."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=(
            "Kořen uživatelských dat s ciselniky/ (výchozí: rodič adresáře databaze/). "
            "Slouží k načtení aktuální metodiky auditu."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pouze vypsat kandidáty, nic neměnit (výchozí chování bez --apply).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Skutečně odstranit kandidáty (nejprve vytvoří zálohu DB).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db_path = args.db.expanduser().resolve()
    if not db_path.is_file():
        print(f"CHYBA: Databáze neexistuje: {db_path}", file=sys.stderr)
        return 2

    if args.apply and args.dry_run:
        print("CHYBA: Zvolte buď --dry-run, nebo --apply, ne obojí.", file=sys.stderr)
        return 2

    apply_changes = bool(args.apply)
    # Bez --apply vždy dry-run (i když uživatel nepřepne --dry-run).
    dry_run = not apply_changes

    data_dir = resolve_data_dir(db_path, args.data_dir)
    configure_knowledge_root(data_dir)

    connection = sqlite3.connect(db_path)
    try:
        audit_id: int | None = None
        if args.audit:
            audit_id = resolve_audit_id(connection, args.audit)
            scope_label = f"jeden audit (id={audit_id})"
        else:
            scope_label = "celá databáze (všechny audity)"

        candidates = find_orphaned_candidates(connection, audit_id=audit_id)
        mode = "APPLY" if apply_changes else "DRY-RUN"
        print(f"Režim: {mode}")
        print(f"Databáze: {db_path}")
        print(f"Metodika (ciselniky): {data_dir / 'ciselniky' / 'audity'}")
        print_candidates(candidates, scope_label=scope_label)

        if dry_run:
            print("Dry-run: žádné změny nebyly provedeny.")
            return 0

        if not candidates:
            print("Není co mazat.")
            return 0

        backup_path = create_backup(db_path)
        print(f"Záloha databáze: {backup_path}")

        try:
            deleted = delete_candidates(connection, candidates)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        ok, integrity_message = integrity_ok(connection)
        print(f"Odstraněno záznamů: {deleted}")
        print(f"PRAGMA integrity_check: {integrity_message}")
        if not ok:
            print("CHYBA: Integrita databáze po změně není OK.", file=sys.stderr)
            return 3
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())

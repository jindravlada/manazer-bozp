"""PERSON-THP-SEPARATION-1: zrcadlové Person→THP, převod vazeb, ověřená záloha."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.backup.constants import BACKUP_EXTENSION
from core.database.upgrade_guard import (
    MigrationGuardError,
    PreMigrationBackupError,
    create_verified_pre_migration_backup,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_failed,
    mark_migration_in_progress,
    read_migration_state,
    sqlite_table_exists,
)

logger = logging.getLogger(__name__)

TRANSITION_ID = "person-thp-separation-1"
BACKUP_NAME_PREFIX = "pre_person_thp_separation"

MIGRATION_MAP_TABLE = "person_thp_separation_migration_map"

STATUS_DELETED = "deleted"
STATUS_SKIPPED_REFS = "skipped_refs"
STATUS_SKIPPED_AMBIGUOUS = "skipped_ambiguous"

SOURCE_PERSON = "person"
SOURCE_THP_WORKER = "thp_worker"
SOURCE_LEGACY_INVALID = "legacy_invalid"

ROLE_INVITED_PERSON = "invited_person"
ROLE_EXTERNAL_AUDITOR = "external_auditor"

EXCLUDED_PERSON_ID_TABLES = frozenset(
    {
        "persons",
        MIGRATION_MAP_TABLE,
    }
)


@dataclass(frozen=True)
class PersonThpSeparationResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None
    stats: dict | None = None


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().split()).casefold()


def _emails_conflict(email_a: str | None, email_b: str | None) -> bool:
    a = _norm(email_a)
    b = _norm(email_b)
    return bool(a and b and a != b)


def _person_name_snapshot(
    title_before: str | None,
    first_name: str | None,
    last_name: str | None,
    title_after: str | None,
) -> str:
    base = " ".join(
        part
        for part in [
            (title_before or "").strip(),
            (first_name or "").strip(),
            (last_name or "").strip(),
        ]
        if part
    ).strip()
    after = (title_after or "").strip()
    if after:
        return f"{base}, {after}".strip()
    return base


def allocate_person_thp_separation_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
    root = Path(backups_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"{BACKUP_NAME_PREFIX}_{stamp}{BACKUP_EXTENSION}"
    candidate = root / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = root / f"{BACKUP_NAME_PREFIX}_{stamp}_{index}{BACKUP_EXTENSION}"
        if not alt.exists():
            return alt
    raise MigrationGuardError(
        "Nelze přidělit unikátní název zálohy PERSON-THP-SEPARATION-1."
    )


def _sqlite_table_exists_conn(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not _sqlite_table_exists_conn(connection, table_name):
        return set()
    rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_ddl: str,
) -> None:
    if not _sqlite_table_exists_conn(connection, table_name):
        return
    if column_name in _table_columns(connection, table_name):
        return
    connection.execute(
        f'ALTER TABLE "{table_name}" ADD COLUMN {column_ddl}'
    )


def apply_person_thp_separation_ddl(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_MAP_TABLE} (
            id INTEGER PRIMARY KEY,
            person_id INTEGER NOT NULL,
            thp_worker_id INTEGER,
            person_name_snapshot VARCHAR(250) NOT NULL DEFAULT '',
            person_email_snapshot VARCHAR(150) NOT NULL DEFAULT '',
            status VARCHAR(40) NOT NULL,
            reason TEXT,
            migrated_at DATETIME
        )
        """
    )
    _ensure_column(
        connection, "meetings", "organizer_source_type", "organizer_source_type VARCHAR(40)"
    )
    _ensure_column(
        connection, "meetings", "organizer_source_id", "organizer_source_id INTEGER"
    )
    _ensure_column(
        connection,
        "meeting_templates",
        "organizer_source_type",
        "organizer_source_type VARCHAR(40)",
    )
    _ensure_column(
        connection,
        "meeting_templates",
        "organizer_source_id",
        "organizer_source_id INTEGER",
    )


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, MIGRATION_MAP_TABLE):
        return False
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        for table in ("meetings", "meeting_templates"):
            if not _sqlite_table_exists_conn(connection, table):
                continue
            cols = _table_columns(connection, table)
            if "organizer_source_type" not in cols or "organizer_source_id" not in cols:
                return False
        return True
    finally:
        connection.close()


def _load_persons(connection: sqlite3.Connection) -> list[dict]:
    if not _sqlite_table_exists_conn(connection, "persons"):
        return []
    cols = _table_columns(connection, "persons")
    needed = {
        "id",
        "title_before",
        "first_name",
        "last_name",
        "title_after",
        "email",
        "is_employee",
    }
    if not needed.issubset(cols):
        return []
    rows = connection.execute(
        """
        SELECT id, title_before, first_name, last_name, title_after, email, is_employee
        FROM persons
        """
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        result.append(
            {
                "id": int(row[0]),
                "title_before": row[1] or "",
                "first_name": row[2] or "",
                "last_name": row[3] or "",
                "title_after": row[4] or "",
                "email": row[5] or "",
                "is_employee": bool(row[6]),
            }
        )
    return result


def _load_thp_workers(connection: sqlite3.Connection) -> list[dict]:
    if not _sqlite_table_exists_conn(connection, "thp_workers"):
        return []
    cols = _table_columns(connection, "thp_workers")
    needed = {"id", "first_name", "last_name", "email"}
    if not needed.issubset(cols):
        return []
    rows = connection.execute(
        "SELECT id, first_name, last_name, email FROM thp_workers"
    ).fetchall()
    return [
        {
            "id": int(row[0]),
            "first_name": row[1] or "",
            "last_name": row[2] or "",
            "email": row[3] or "",
        }
        for row in rows
    ]


def _person_matches_thp(person: dict, worker: dict) -> bool:
    if not _norm(person["first_name"]) or not _norm(person["last_name"]):
        return False
    if _norm(person["first_name"]) != _norm(worker["first_name"]):
        return False
    if _norm(person["last_name"]) != _norm(worker["last_name"]):
        return False
    if _emails_conflict(person.get("email"), worker.get("email")):
        return False
    return True


def preflight_report(connection: sqlite3.Connection) -> dict:
    """Mapa jednoznačných zrcadel + nejednoznačné osoby s důvody + inventura referencí."""
    persons = _load_persons(connection)
    workers = _load_thp_workers(connection)

    convertible: dict[int, int] = {}
    ambiguous: list[dict] = []
    person_by_id = {p["id"]: p for p in persons}

    # person → matching THPs
    person_to_thps: dict[int, list[int]] = {}
    for person in persons:
        first = _norm(person["first_name"])
        last = _norm(person["last_name"])
        if not first or not last:
            continue
        matches = [w["id"] for w in workers if _person_matches_thp(person, w)]
        if matches:
            person_to_thps[person["id"]] = matches

    # thp → matching Persons
    thp_to_persons: dict[int, list[int]] = {}
    for worker in workers:
        first = _norm(worker["first_name"])
        last = _norm(worker["last_name"])
        if not first or not last:
            continue
        matches = [p["id"] for p in persons if _person_matches_thp(p, worker)]
        if matches:
            thp_to_persons[worker["id"]] = matches

    candidate_pairs: list[tuple[int, int]] = []
    for person_id, thp_ids in person_to_thps.items():
        if len(thp_ids) != 1:
            ambiguous.append(
                {
                    "person_id": person_id,
                    "reason": (
                        "více odpovídajících THP"
                        if len(thp_ids) > 1
                        else "žádné odpovídající THP"
                    ),
                    "thp_ids": list(thp_ids),
                    "is_employee": bool(person_by_id[person_id].get("is_employee")),
                }
            )
            continue
        thp_id = thp_ids[0]
        reverse = thp_to_persons.get(thp_id) or []
        if len(reverse) != 1 or reverse[0] != person_id:
            ambiguous.append(
                {
                    "person_id": person_id,
                    "reason": (
                        "THP není jednoznačně navázán na právě tuto Osobu "
                        "(obousměrná jednoznačnost selhala)"
                    ),
                    "thp_ids": [thp_id],
                    "matching_person_ids": list(reverse),
                    "is_employee": bool(person_by_id[person_id].get("is_employee")),
                }
            )
            continue
        candidate_pairs.append((person_id, thp_id))

    # Injektivita: person i thp smí být v mapě jen jednou
    person_counts: dict[int, int] = {}
    thp_counts: dict[int, int] = {}
    for person_id, thp_id in candidate_pairs:
        person_counts[person_id] = person_counts.get(person_id, 0) + 1
        thp_counts[thp_id] = thp_counts.get(thp_id, 0) + 1

    for person_id, thp_id in candidate_pairs:
        if person_counts[person_id] != 1 or thp_counts[thp_id] != 1:
            ambiguous.append(
                {
                    "person_id": person_id,
                    "reason": "kolize mapování (stejná Osoba nebo THP ve více párech)",
                    "thp_ids": [thp_id],
                    "is_employee": bool(person_by_id[person_id].get("is_employee")),
                }
            )
            continue
        convertible[person_id] = thp_id

    references = inventory_person_references(connection, set(convertible.keys()) | set())
    # inventura i pro všechny osoby v ambiguous + convertible
    all_ids = set(convertible.keys()) | {item["person_id"] for item in ambiguous}
    if all_ids:
        references = inventory_person_references(connection, all_ids)

    return {
        "convertible": dict(convertible),
        "ambiguous": ambiguous,
        "references": references,
        "persons_count": len(persons),
        "thp_workers_count": len(workers),
    }


def build_unambiguous_mirror_map(connection: sqlite3.Connection) -> dict[int, int]:
    report = preflight_report(connection)
    return dict(report["convertible"])


def _parse_participant_person_ids(raw: str | None) -> set[int]:
    ids: set[int] = set()
    text = (raw or "").strip()
    if not text:
        return ids
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return ids
    if not isinstance(data, list):
        return ids
    for item in data:
        if isinstance(item, dict):
            source_type = str(item.get("source_type") or "").strip()
            if source_type != SOURCE_PERSON:
                continue
            try:
                source_id = int(item.get("source_id"))
            except (TypeError, ValueError):
                continue
            if source_id > 0:
                ids.add(source_id)
        else:
            try:
                source_id = int(item)
            except (TypeError, ValueError):
                continue
            if source_id > 0:
                ids.add(source_id)
    return ids


def _rewrite_participant_ids_json(
    raw: str | None,
    mirror_map: dict[int, int],
) -> str:
    text = (raw or "").strip() or "[]"
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return text
    if not isinstance(data, list):
        return text
    out: list = []
    for item in data:
        if isinstance(item, dict):
            source_type = str(item.get("source_type") or "").strip()
            try:
                source_id = int(item.get("source_id"))
            except (TypeError, ValueError):
                out.append(item)
                continue
            if source_type == SOURCE_PERSON and source_id in mirror_map:
                out.append(
                    {
                        "source_type": SOURCE_THP_WORKER,
                        "source_id": int(mirror_map[source_id]),
                    }
                )
            else:
                out.append(item)
        else:
            try:
                person_id = int(item)
            except (TypeError, ValueError):
                out.append(item)
                continue
            if person_id in mirror_map:
                out.append(
                    {
                        "source_type": SOURCE_THP_WORKER,
                        "source_id": int(mirror_map[person_id]),
                    }
                )
            else:
                out.append(person_id)
    return json.dumps(out, ensure_ascii=False)


def _tables_with_exact_person_id_column(
    connection: sqlite3.Connection,
) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    found: list[str] = []
    for (name,) in rows:
        table = str(name)
        if table in EXCLUDED_PERSON_ID_TABLES:
            continue
        if "person_id" in _table_columns(connection, table):
            found.append(table)
    return sorted(found)


def inventory_person_references(
    connection: sqlite3.Connection,
    person_ids: set[int] | None = None,
) -> dict[str, list[dict]]:
    """Inventura referencí, které blokují smazání Person.

    Vrací mapu kategorie → seznam záznamů s person_id (a případně row id).
    """
    wanted = set(person_ids) if person_ids is not None else None
    result: dict[str, list[dict]] = {
        "meetings.organizer_person_id": [],
        "meetings.participant_ids_json": [],
        "meeting_templates.organizer_person_id": [],
        "meeting_templates.participant_ids_json": [],
        "external_audit_participants": [],
        "audit_commission_members.person_id": [],
        "bozp_inspection_commission_members.person_id": [],
        "periodic_activity_occurrences": [],
        "generic_person_id": [],
    }

    def _want(pid: int) -> bool:
        return wanted is None or pid in wanted

    if _sqlite_table_exists_conn(connection, "meetings"):
        cols = _table_columns(connection, "meetings")
        if "organizer_person_id" in cols:
            for row in connection.execute(
                "SELECT id, organizer_person_id FROM meetings "
                "WHERE organizer_person_id IS NOT NULL"
            ):
                pid = int(row[1])
                if _want(pid):
                    result["meetings.organizer_person_id"].append(
                        {"meeting_id": int(row[0]), "person_id": pid}
                    )
        if "participant_ids_json" in cols:
            for row in connection.execute(
                "SELECT id, participant_ids_json FROM meetings"
            ):
                for pid in _parse_participant_person_ids(row[1]):
                    if _want(pid):
                        result["meetings.participant_ids_json"].append(
                            {"meeting_id": int(row[0]), "person_id": pid}
                        )

    if _sqlite_table_exists_conn(connection, "meeting_templates"):
        cols = _table_columns(connection, "meeting_templates")
        if "organizer_person_id" in cols:
            for row in connection.execute(
                "SELECT id, organizer_person_id FROM meeting_templates "
                "WHERE organizer_person_id IS NOT NULL"
            ):
                pid = int(row[1])
                if _want(pid):
                    result["meeting_templates.organizer_person_id"].append(
                        {"template_id": int(row[0]), "person_id": pid}
                    )
        if "participant_ids_json" in cols:
            for row in connection.execute(
                "SELECT id, participant_ids_json FROM meeting_templates"
            ):
                for pid in _parse_participant_person_ids(row[1]):
                    if _want(pid):
                        result["meeting_templates.participant_ids_json"].append(
                            {"template_id": int(row[0]), "person_id": pid}
                        )

    if _sqlite_table_exists_conn(connection, "external_audit_participants"):
        cols = _table_columns(connection, "external_audit_participants")
        if {"source_type", "source_id"}.issubset(cols):
            for row in connection.execute(
                """
                SELECT id, role, source_type, source_id
                FROM external_audit_participants
                WHERE source_type = ?
                """,
                (SOURCE_PERSON,),
            ):
                pid = int(row[3])
                if _want(pid):
                    result["external_audit_participants"].append(
                        {
                            "participant_id": int(row[0]),
                            "role": row[1] or "",
                            "person_id": pid,
                        }
                    )

    if _sqlite_table_exists_conn(connection, "audit_commission_members"):
        if "person_id" in _table_columns(connection, "audit_commission_members"):
            for row in connection.execute(
                "SELECT id, person_id FROM audit_commission_members "
                "WHERE person_id IS NOT NULL"
            ):
                pid = int(row[1])
                if _want(pid):
                    result["audit_commission_members.person_id"].append(
                        {"member_id": int(row[0]), "person_id": pid}
                    )

    if _sqlite_table_exists_conn(connection, "bozp_inspection_commission_members"):
        if "person_id" in _table_columns(
            connection, "bozp_inspection_commission_members"
        ):
            for row in connection.execute(
                "SELECT id, person_id FROM bozp_inspection_commission_members "
                "WHERE person_id IS NOT NULL"
            ):
                pid = int(row[1])
                if _want(pid):
                    result["bozp_inspection_commission_members.person_id"].append(
                        {"member_id": int(row[0]), "person_id": pid}
                    )

    if _sqlite_table_exists_conn(connection, "periodic_activity_occurrences"):
        cols = _table_columns(connection, "periodic_activity_occurrences")
        if {"performed_by_kind", "performed_by_id"}.issubset(cols):
            for row in connection.execute(
                """
                SELECT id, performed_by_id
                FROM periodic_activity_occurrences
                WHERE performed_by_kind = ? AND performed_by_id IS NOT NULL
                """,
                (SOURCE_PERSON,),
            ):
                pid = int(row[1])
                if _want(pid):
                    result["periodic_activity_occurrences"].append(
                        {"occurrence_id": int(row[0]), "person_id": pid}
                    )

    known_person_id_tables = {
        "audit_commission_members",
        "bozp_inspection_commission_members",
    }
    for table in _tables_with_exact_person_id_column(connection):
        if table in known_person_id_tables:
            continue
        cols = _table_columns(connection, table)
        id_expr = "id" if "id" in cols else "rowid"
        for row in connection.execute(
            f'SELECT {id_expr}, person_id FROM "{table}" WHERE person_id IS NOT NULL'
        ):
            try:
                pid = int(row[1])
            except (TypeError, ValueError):
                continue
            if _want(pid):
                result["generic_person_id"].append(
                    {"table": table, "row_id": int(row[0]), "person_id": pid}
                )

    return result


def _blocking_ref_person_ids(
    connection: sqlite3.Connection,
    mirror_ids: set[int],
) -> dict[int, list[str]]:
    """Reference, které migrace nepřevádí → přeskočit DELETE (skipped_refs)."""
    blocked: dict[int, list[str]] = {pid: [] for pid in mirror_ids}
    inv = inventory_person_references(connection, mirror_ids)

    for item in inv["audit_commission_members.person_id"]:
        blocked[int(item["person_id"])].append("audit_commission_members")
    for item in inv["bozp_inspection_commission_members.person_id"]:
        blocked[int(item["person_id"])].append("bozp_inspection_commission_members")
    for item in inv["periodic_activity_occurrences"]:
        blocked[int(item["person_id"])].append("periodic_activity_occurrences")
    for item in inv["generic_person_id"]:
        blocked[int(item["person_id"])].append(
            f"generic:{item.get('table') or 'person_id'}"
        )

    # EA role, které nepřevádíme (např. company_representative jako person)
    for item in inv["external_audit_participants"]:
        role = str(item.get("role") or "").strip()
        if role not in {ROLE_INVITED_PERSON, ROLE_EXTERNAL_AUDITOR}:
            blocked[int(item["person_id"])].append(
                f"external_audit_participants:{role or 'unknown'}"
            )

    return {pid: reasons for pid, reasons in blocked.items() if reasons}


def _remaining_refs_for_delete(
    connection: sqlite3.Connection,
    person_ids: set[int],
) -> dict[int, list[str]]:
    """Po převodu: jakékoli zbývající odkazy na mazané ID."""
    if not person_ids:
        return {}
    inv = inventory_person_references(connection, person_ids)
    found: dict[int, list[str]] = {pid: [] for pid in person_ids}
    for category, items in inv.items():
        for item in items:
            pid = int(item["person_id"])
            if pid in found:
                found[pid].append(category)
    return {pid: cats for pid, cats in found.items() if cats}


def _convert_meeting_organizers(
    connection: sqlite3.Connection,
    table: str,
    mirror_map: dict[int, int],
) -> int:
    if not _sqlite_table_exists_conn(connection, table):
        return 0
    cols = _table_columns(connection, table)
    if "organizer_person_id" not in cols:
        return 0
    if "organizer_source_type" not in cols or "organizer_source_id" not in cols:
        return 0
    changed = 0
    for row in connection.execute(
        f'SELECT id, organizer_person_id FROM "{table}" '
        "WHERE organizer_person_id IS NOT NULL"
    ):
        person_id = int(row[1])
        if person_id not in mirror_map:
            continue
        thp_id = int(mirror_map[person_id])
        connection.execute(
            f"""
            UPDATE "{table}"
            SET organizer_source_type = ?,
                organizer_source_id = ?,
                organizer_person_id = NULL
            WHERE id = ?
            """,
            (SOURCE_THP_WORKER, thp_id, int(row[0])),
        )
        changed += 1
    return changed


def _convert_meeting_participants(
    connection: sqlite3.Connection,
    table: str,
    mirror_map: dict[int, int],
) -> int:
    if not _sqlite_table_exists_conn(connection, table):
        return 0
    cols = _table_columns(connection, table)
    if "participant_ids_json" not in cols:
        return 0
    changed = 0
    for row in connection.execute(
        f'SELECT id, participant_ids_json FROM "{table}"'
    ):
        original = row[1] or "[]"
        rewritten = _rewrite_participant_ids_json(original, mirror_map)
        if rewritten != original:
            connection.execute(
                f'UPDATE "{table}" SET participant_ids_json = ? WHERE id = ?',
                (rewritten, int(row[0])),
            )
            changed += 1
    return changed


def _convert_external_audit_participants(
    connection: sqlite3.Connection,
    mirror_map: dict[int, int],
) -> dict[str, int]:
    stats = {"invited_to_thp": 0, "auditor_to_legacy_invalid": 0}
    if not _sqlite_table_exists_conn(connection, "external_audit_participants"):
        return stats
    cols = _table_columns(connection, "external_audit_participants")
    needed = {"id", "role", "source_type", "source_id"}
    if not needed.issubset(cols):
        return stats
    rows = connection.execute(
        """
        SELECT id, role, source_type, source_id
        FROM external_audit_participants
        WHERE source_type = ?
        """,
        (SOURCE_PERSON,),
    ).fetchall()
    for row in rows:
        person_id = int(row[3])
        if person_id not in mirror_map:
            continue
        role = str(row[1] or "").strip()
        thp_id = int(mirror_map[person_id])
        if role == ROLE_INVITED_PERSON:
            connection.execute(
                """
                UPDATE external_audit_participants
                SET source_type = ?, source_id = ?
                WHERE id = ?
                """,
                (SOURCE_THP_WORKER, thp_id, int(row[0])),
            )
            stats["invited_to_thp"] += 1
        elif role == ROLE_EXTERNAL_AUDITOR:
            connection.execute(
                """
                UPDATE external_audit_participants
                SET source_type = ?, source_id = ?
                WHERE id = ?
                """,
                (SOURCE_LEGACY_INVALID, 0, int(row[0])),
            )
            stats["auditor_to_legacy_invalid"] += 1
    return stats


def _insert_migration_map_row(
    connection: sqlite3.Connection,
    *,
    person: dict,
    thp_worker_id: int | None,
    status: str,
    reason: str | None,
    migrated_at: str,
) -> None:
    connection.execute(
        f"""
        INSERT INTO {MIGRATION_MAP_TABLE} (
            person_id,
            thp_worker_id,
            person_name_snapshot,
            person_email_snapshot,
            status,
            reason,
            migrated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(person["id"]),
            thp_worker_id,
            _person_name_snapshot(
                person.get("title_before"),
                person.get("first_name"),
                person.get("last_name"),
                person.get("title_after"),
            )[:250],
            (person.get("email") or "")[:150],
            status,
            reason,
            migrated_at,
        ),
    )


def apply_person_thp_separation_data(connection: sqlite3.Connection) -> dict:
    """DDL + převod vazeb + DELETE bezpečných mirrorů. Bez COMMIT (volající řídí transakci)."""
    apply_person_thp_separation_ddl(connection)

    report = preflight_report(connection)
    mirror_map: dict[int, int] = dict(report["convertible"])
    persons_by_id = {p["id"]: p for p in _load_persons(connection)}
    migrated_at = datetime.now().isoformat(timespec="seconds")

    stats: dict = {
        "convertible_count": len(mirror_map),
        "ambiguous_count": len(report["ambiguous"]),
        "meetings_organizer_converted": 0,
        "meetings_participants_converted": 0,
        "templates_organizer_converted": 0,
        "templates_participants_converted": 0,
        "ea_invited_to_thp": 0,
        "ea_auditor_to_legacy_invalid": 0,
        "deleted_count": 0,
        "skipped_refs_count": 0,
        "skipped_ambiguous_count": 0,
    }

    for item in report["ambiguous"]:
        person = persons_by_id.get(int(item["person_id"]))
        if person is None:
            continue
        _insert_migration_map_row(
            connection,
            person=person,
            thp_worker_id=(item.get("thp_ids") or [None])[0],
            status=STATUS_SKIPPED_AMBIGUOUS,
            reason=str(item.get("reason") or "ambiguous"),
            migrated_at=migrated_at,
        )
        stats["skipped_ambiguous_count"] += 1

    if not mirror_map:
        return stats

    blocked = _blocking_ref_person_ids(connection, set(mirror_map.keys()))
    deletable = {
        pid: thp_id for pid, thp_id in mirror_map.items() if pid not in blocked
    }
    skipped_refs = {
        pid: thp_id for pid, thp_id in mirror_map.items() if pid in blocked
    }

    stats["meetings_organizer_converted"] = _convert_meeting_organizers(
        connection, "meetings", mirror_map
    )
    stats["meetings_participants_converted"] = _convert_meeting_participants(
        connection, "meetings", mirror_map
    )
    stats["templates_organizer_converted"] = _convert_meeting_organizers(
        connection, "meeting_templates", mirror_map
    )
    stats["templates_participants_converted"] = _convert_meeting_participants(
        connection, "meeting_templates", mirror_map
    )
    ea_stats = _convert_external_audit_participants(connection, mirror_map)
    stats["ea_invited_to_thp"] = ea_stats["invited_to_thp"]
    stats["ea_auditor_to_legacy_invalid"] = ea_stats["auditor_to_legacy_invalid"]

    remaining = _remaining_refs_for_delete(connection, set(deletable.keys()))
    if remaining:
        details = "; ".join(
            f"person_id={pid}: {','.join(cats)}" for pid, cats in sorted(remaining.items())
        )
        raise MigrationGuardError(
            "PERSON-THP-SEPARATION-1: po převodu zbývají reference na mazané Osoby. "
            f"Detail: {details}"
        )

    for person_id, thp_id in sorted(deletable.items()):
        person = persons_by_id.get(person_id)
        if person is None:
            continue
        connection.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        _insert_migration_map_row(
            connection,
            person=person,
            thp_worker_id=thp_id,
            status=STATUS_DELETED,
            reason=None,
            migrated_at=migrated_at,
        )
        stats["deleted_count"] += 1

    for person_id, thp_id in sorted(skipped_refs.items()):
        person = persons_by_id.get(person_id)
        if person is None:
            continue
        reasons = blocked.get(person_id) or []
        _insert_migration_map_row(
            connection,
            person=person,
            thp_worker_id=thp_id,
            status=STATUS_SKIPPED_REFS,
            reason=", ".join(sorted(set(reasons))),
            migrated_at=migrated_at,
        )
        stats["skipped_refs_count"] += 1

    return stats


def needs_person_thp_separation(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not schema_is_present(path):
        return True
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        mirrors = build_unambiguous_mirror_map(connection)
        if not mirrors:
            return False
        if _has_pending_convertible_refs(connection, mirrors):
            return True
        blocked = _blocking_ref_person_ids(connection, set(mirrors.keys()))
        deletable = set(mirrors.keys()) - set(blocked.keys())
        return bool(deletable)
    finally:
        connection.close()


def _has_pending_convertible_refs(
    connection: sqlite3.Connection,
    mirrors: dict[int, int],
) -> bool:
    """True, pokud ještě zbývá převést meeting/EA odkazy na mirror Person."""
    mirror_ids = set(mirrors.keys())
    for table in ("meetings", "meeting_templates"):
        if not _sqlite_table_exists_conn(connection, table):
            continue
        cols = _table_columns(connection, table)
        if "organizer_person_id" in cols:
            for row in connection.execute(
                f'SELECT organizer_person_id FROM "{table}" '
                "WHERE organizer_person_id IS NOT NULL"
            ):
                if int(row[0]) in mirror_ids:
                    return True
        if "participant_ids_json" in cols:
            for row in connection.execute(
                f'SELECT participant_ids_json FROM "{table}"'
            ):
                if _parse_participant_person_ids(row[0]) & mirror_ids:
                    return True
    if _sqlite_table_exists_conn(connection, "external_audit_participants"):
        for row in connection.execute(
            """
            SELECT source_id, role FROM external_audit_participants
            WHERE source_type = ?
            """,
            (SOURCE_PERSON,),
        ):
            if int(row[0]) not in mirror_ids:
                continue
            role = str(row[1] or "").strip()
            if role in {ROLE_INVITED_PERSON, ROLE_EXTERNAL_AUDITOR}:
                return True
    return False


def prepare_person_thp_separation(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> PersonThpSeparationResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace PERSON-THP-SEPARATION-1 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and not needs_person_thp_separation(
        database_path
    ):
        return PersonThpSeparationResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return PersonThpSeparationResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_person_thp_separation(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return PersonThpSeparationResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    target = allocate_person_thp_separation_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError:
        raise
    except Exception as exc:  # pragma: no cover - obrana
        raise PreMigrationBackupError(
            "Nepodařilo se vytvořit zálohu před migrací PERSON-THP-SEPARATION-1. "
            "Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )

    connection = sqlite3.connect(str(database_path.resolve()))
    stats: dict | None = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        stats = apply_person_thp_separation_data(connection)
        connection.commit()
    except Exception as exc:
        try:
            connection.rollback()
        except Exception:  # pragma: no cover
            pass
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace PERSON-THP-SEPARATION-1 selhala. Obnovte data ze zálohy."
        ) from exc
    finally:
        connection.close()

    # Úspěšný apply → complete. needs_* zůstane True jen pokud zbývají zrcadla
    # (např. skipped_refs); další běh je idempotentní (převod znovu, DELETE jen volné).
    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )

    logger.info(
        "PERSON-THP-SEPARATION-1: hotovo, záloha %s, stats=%s",
        backup_path,
        stats,
    )
    return PersonThpSeparationResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
        stats=stats,
    )

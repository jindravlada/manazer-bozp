"""AUDIT-METHOD-SUPPORT-SNAPSHOT-1-PERF: rychlý vs úplný integrity guard."""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.database.upgrade_guard import (
    MigrationGuardError,
    is_transition_complete,
)
from moduly.audity.constants import (
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL,
    METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION,
    METHOD_SUPPORT_SOURCE_UNAVAILABLE,
    METHOD_SUPPORT_STATUS_AVAILABLE,
    METHOD_SUPPORT_STATUS_EMPTY,
    METHOD_SUPPORT_STATUS_UNAVAILABLE,
)
from moduly.audity.sluzby.audit_method_support_backfill_service import (
    BACKFILL_TRANSITION_ID,
)
from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
    TRANSITION_ID as SCHEMA_TRANSITION_ID,
    needs_method_support_snapshot_1_schema,
    schema_is_present,
)
from moduly.audity.sluzby.audit_method_support_snapshot_service import (
    compute_audit_support_integrity_hash_from_rows,
)

logger = logging.getLogger(__name__)

INTEGRITY_TRANSITION_ID = "audit-method-support-snapshot-1-integrity"

_VALID_STATUSES = (
    METHOD_SUPPORT_STATUS_AVAILABLE,
    METHOD_SUPPORT_STATUS_EMPTY,
    METHOD_SUPPORT_STATUS_UNAVAILABLE,
)
_VALID_SOURCES = (
    METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION,
    METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL,
    METHOD_SUPPORT_SOURCE_UNAVAILABLE,
)


@dataclass(frozen=True)
class MethodSupportFastIntegrityResult:
    ok: bool
    problems: tuple[str, ...] = ()
    sql_statements: int = 0
    elapsed_ms: float = 0.0
    skipped_reason: str | None = None


@dataclass
class MethodSupportIntegrityGuardResult:
    checked: bool
    fast: MethodSupportFastIntegrityResult | None = None
    full_ran: bool = False
    skipped_reason: str | None = None
    problems: list[str] = field(default_factory=list)


class MethodSupportIntegrityError(MigrationGuardError):
    """Nekonzistence metodické podpory — bez automatické opravy."""


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(Path(db_path).resolve()))


def run_method_support_fast_integrity_check(
    database_path: Path,
) -> MethodSupportFastIntegrityResult:
    """
    Levná DB-only kontrola (agregované SQL + uložené per-row hashe).

    Neparsuje JSON payloady, nehashuje soubory, nenačítá živou metodiku.
    """
    t0 = time.perf_counter()
    path = Path(database_path)
    problems: list[str] = []
    sql_count = 0

    if not path.is_file():
        return MethodSupportFastIntegrityResult(
            ok=False,
            problems=("databáze neexistuje",),
            sql_statements=0,
            elapsed_ms=0.0,
        )

    if needs_method_support_snapshot_1_schema(path):
        return MethodSupportFastIntegrityResult(
            ok=False,
            problems=("chybí schema audit_question_support_snapshots / sloupce",),
            sql_statements=1,
            elapsed_ms=(time.perf_counter() - t0) * 1000,
        )

    connection = _connect(path)
    try:
        sql_count += 1
        missing_markers = connection.execute(
            """
            SELECT COUNT(*)
            FROM audits
            WHERE methodology_source = ?
              AND (
                support_snapshot_count IS NULL
                OR IFNULL(support_integrity_hash, '') = ''
              )
            """,
            (AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,),
        ).fetchone()
        if int(missing_markers[0] or 0) > 0:
            problems.append(
                f"chybí support markery u {int(missing_markers[0])} snapshotových auditů"
            )

        sql_count += 1
        count_mismatch = connection.execute(
            """
            SELECT a.id, a.support_snapshot_count,
                   (SELECT COUNT(*) FROM audit_question_support_snapshots s
                    WHERE s.audit_id = a.id) AS actual
            FROM audits a
            WHERE a.methodology_source = ?
              AND a.support_snapshot_count IS NOT NULL
              AND a.support_snapshot_count != (
                SELECT COUNT(*) FROM audit_question_support_snapshots s
                WHERE s.audit_id = a.id
              )
            LIMIT 20
            """,
            (AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,),
        ).fetchall()
        if count_mismatch:
            sample = ", ".join(
                f"id={row[0]} manifest={row[1]} actual={row[2]}"
                for row in count_mismatch[:5]
            )
            problems.append(f"nesoulad počtu support řádků ({sample})")

        sql_count += 1
        missing_links = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_question_snapshots q
            JOIN audits a ON a.id = q.audit_id
            WHERE a.methodology_source = ?
              AND IFNULL(q.is_in_scope, 1) = 1
              AND IFNULL(q.question_kind, '') != ?
              AND NOT EXISTS (
                SELECT 1 FROM audit_question_support_snapshots s
                WHERE s.audit_question_snapshot_id = q.id
              )
            """,
            (AUDIT_METHODOLOGY_SOURCE_SNAPSHOT, AUDIT_QUESTION_KIND_EXTRAORDINARY),
        ).fetchone()
        if int(missing_links[0] or 0) > 0:
            problems.append(
                f"chybí support u {int(missing_links[0])} in-scope běžných otázek"
            )

        sql_count += 1
        extra_links = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_question_support_snapshots s
            WHERE NOT EXISTS (
                SELECT 1 FROM audit_question_snapshots q
                WHERE q.id = s.audit_question_snapshot_id
            )
            """
        ).fetchone()
        if int(extra_links[0] or 0) > 0:
            problems.append(
                f"osiřelé support řádky bez otázkového snapshotu: {int(extra_links[0])}"
            )

        sql_count += 1
        dupes = connection.execute(
            """
            SELECT audit_question_snapshot_id, COUNT(*) AS c
            FROM audit_question_support_snapshots
            GROUP BY audit_question_snapshot_id
            HAVING c > 1
            LIMIT 5
            """
        ).fetchall()
        if dupes:
            problems.append(
                "duplicitní vazba 1:1 na audit_question_snapshot_id: "
                + ", ".join(f"{row[0]}×{row[1]}" for row in dupes)
            )

        sql_count += 1
        bad_status = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM audit_question_support_snapshots
            WHERE status NOT IN ({",".join("?" for _ in _VALID_STATUSES)})
            """,
            _VALID_STATUSES,
        ).fetchone()
        if int(bad_status[0] or 0) > 0:
            problems.append(
                f"neplatný status u {int(bad_status[0])} support řádků"
            )

        sql_count += 1
        bad_source = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM audit_question_support_snapshots
            WHERE source NOT IN ({",".join("?" for _ in _VALID_SOURCES)})
            """,
            _VALID_SOURCES,
        ).fetchone()
        if int(bad_source[0] or 0) > 0:
            problems.append(
                f"neplatný source u {int(bad_source[0])} support řádků"
            )

        # Audit-level hash z uložených per-row hashů (bez JSON).
        sql_count += 1
        support_rows = connection.execute(
            """
            SELECT s.audit_id, s.audit_question_snapshot_id, s.status, s.source,
                   s.integrity_hash, s.payload_version, IFNULL(s.id, 0)
            FROM audit_question_support_snapshots s
            JOIN audits a ON a.id = s.audit_id
            WHERE a.methodology_source = ?
            ORDER BY s.audit_id, s.audit_question_snapshot_id, s.id
            """,
            (AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,),
        ).fetchall()

        sql_count += 1
        audit_hashes = {
            int(row[0]): str(row[1] or "")
            for row in connection.execute(
                """
                SELECT id, IFNULL(support_integrity_hash, '')
                FROM audits
                WHERE methodology_source = ?
                """,
                (AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,),
            ).fetchall()
        }

        by_audit: dict[int, list[tuple]] = {}
        for row in support_rows:
            by_audit.setdefault(int(row[0]), []).append(
                (
                    int(row[1]),
                    str(row[2] or ""),
                    str(row[3] or ""),
                    str(row[4] or ""),
                    int(row[5] or 0),
                    int(row[6] or 0),
                )
            )

        hash_mismatches = 0
        for audit_id, stored in audit_hashes.items():
            if not stored:
                continue
            actual = compute_audit_support_integrity_hash_from_rows(
                by_audit.get(audit_id, [])
            )
            if actual != stored:
                hash_mismatches += 1
                if hash_mismatches <= 5:
                    problems.append(
                        f"nesoulad support_integrity_hash u auditu id={audit_id}"
                    )
        if hash_mismatches > 5:
            problems.append(
                f"… dalších {hash_mismatches - 5} auditů s vadným support_integrity_hash"
            )

    finally:
        connection.close()

    elapsed = (time.perf_counter() - t0) * 1000
    return MethodSupportFastIntegrityResult(
        ok=not problems,
        problems=tuple(problems),
        sql_statements=sql_count,
        elapsed_ms=elapsed,
    )


def run_method_support_full_integrity_check(database_path: Path) -> list[str]:
    """Úplná kontrola: JSON + payload hash + existence/hash referenčních fotografií."""
    from sqlalchemy import select

    from core.database.session import get_session, reconfigure_database_engine
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.modely.audit_question_support_snapshot import (
        AuditQuestionSupportSnapshot,
    )
    from moduly.audity.sluzby.audit_method_support_snapshot_service import (
        MethodSupportSnapshotError,
        audit_method_support_snapshot_service,
    )

    reconfigure_database_engine(force=True)
    problems: list[str] = []
    with get_session() as session:
        audits = list(
            session.scalars(
                select(Audit).where(
                    Audit.methodology_source == AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                )
            )
        )
        for audit in audits:
            questions = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
            supports = list(
                session.scalars(
                    select(AuditQuestionSupportSnapshot).where(
                        AuditQuestionSupportSnapshot.audit_id == audit.id
                    )
                )
            )
            try:
                audit_method_support_snapshot_service.verify_support_integrity(
                    audit,
                    questions,
                    supports,
                    check_payloads=True,
                    check_photos=True,
                )
            except MethodSupportSnapshotError as exc:
                problems.append(str(exc))
    return problems


def prepare_method_support_integrity_guard(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> MethodSupportIntegrityGuardResult:
    """
    Startup guard: při completed stavu jen rychlá DB kontrola.

    Při nesouladu nic nemaže/nepřepisuje — přesnější diagnostika + chyba.
    """
    del settings_path  # rezervováno pro budoucí diagnostiku/zálohy
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)

    if not schema_is_present(database_path):
        # Schema prepare řeší chybějící tabulku (vč. completed + obnovená DB).
        return MethodSupportIntegrityGuardResult(
            checked=False,
            skipped_reason="schema_missing",
        )

    if not is_transition_complete(workspace_root, BACKFILL_TRANSITION_ID):
        return MethodSupportIntegrityGuardResult(
            checked=False,
            skipped_reason="backfill_not_complete",
        )

    if not is_transition_complete(workspace_root, SCHEMA_TRANSITION_ID):
        return MethodSupportIntegrityGuardResult(
            checked=False,
            skipped_reason="schema_transition_not_complete",
        )

    fast = run_method_support_fast_integrity_check(database_path)
    logger.info(
        "AUDIT-METHOD-SUPPORT integrity fast: ok=%s sql=%s %.1f ms",
        fast.ok,
        fast.sql_statements,
        fast.elapsed_ms,
    )
    if fast.ok:
        return MethodSupportIntegrityGuardResult(
            checked=True,
            fast=fast,
            skipped_reason="fast_ok",
        )

    # Nesoulad → úplná diagnostika (stále bez destruktivní opravy).
    full_problems = run_method_support_full_integrity_check(database_path)
    detail = "; ".join(list(fast.problems) + full_problems)
    raise MethodSupportIntegrityError(
        "AUDIT-METHOD-SUPPORT-SNAPSHOT-1: nekonzistentní metodická podpora.\n"
        "Automatická destruktivní oprava se nespouští.\n"
        f"Detaily: {detail}\n"
        "Obnovte data ze zálohy pre_audit_method_support_snapshot_* "
        "nebo opravte data ručně."
    )

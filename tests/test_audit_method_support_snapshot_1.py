"""AUDIT-METHOD-SUPPORT-SNAPSHOT-1: zmrazení metodické podpory."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-method-support-1-"))
_WS = _TMP / ".local" / "share" / "manazer-bozp"
_DB = _WS / "databaze" / "manager_bozp.db"

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
        apply_method_support_snapshot_1_schema_ddl,
        needs_method_support_snapshot_1_schema,
        schema_is_present,
    )

    apply_method_support_snapshot_1_schema_ddl(_DB)

    from core.database.session import get_session
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_QUESTION_KIND_OPERATION,
        AUDIT_QUESTION_KIND_SYSTEM,
        METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL,
        METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION,
        METHOD_SUPPORT_STATUS_AVAILABLE,
        METHOD_SUPPORT_STATUS_EMPTY,
        METHOD_SUPPORT_STATUS_UNAVAILABLE,
        METHOD_SUPPORT_UNAVAILABLE_MESSAGE,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.modely.audit_question_support_snapshot import (
        AuditQuestionSupportSnapshot,
    )
    from moduly.audity.sluzby.audit_knowledge_service import (
        KnowledgeTreeNode,
        audit_knowledge_service,
    )
    from moduly.audity.sluzby.audit_method_support_backfill_service import (
        run_method_support_backfill,
    )
    from moduly.audity.sluzby.audit_method_support_payload_service import (
        build_support_payload_from_section,
        canonical_json_dumps,
    )
    from moduly.audity.sluzby.audit_method_support_snapshot_service import (
        audit_method_support_snapshot_service,
    )
    from moduly.audity.sluzby.audit_question_source_service import (
        audit_question_source_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_v2_create_service import create_audit_with_v2_snapshot
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.audity.sluzby.system_audit_workplace_service import (
        system_audit_workplace_service,
    )


def _fake_tree() -> list[KnowledgeTreeNode]:
    section = {
        "id": "sec_ms",
        "nazev": "Sekce MS",
        "aktivni": True,
        "cil_overeni": "Ověřit podporu",
        "objektivni_dukazy": [
            {"id": "d1", "nazev": "Důkaz A", "poradi": 10, "aktivni": True}
        ],
        "doporucene_rozhovory": [
            {"id": "r1", "nazev": "Vedoucí", "poradi": 10, "aktivni": True}
        ],
        "pozorovani_v_provozu": [],
        "typicke_neshody": [
            {"id": "n1", "nazev": "Chybí záznam", "poradi": 10, "aktivni": True}
        ],
        "pkz": [],
        "pozorovani": [],
        "vazby_procesy": [],
        "pozadavky_normy": [
            {
                "id": "iso1",
                "nazev": "ISO 45001",
                "popis": "6.1",
                "poradi": 10,
                "aktivni": True,
            }
        ],
        "postup_kontroly": [
            {
                "id": "p1",
                "nazev": "Krok 1",
                "popis": "Zkontrolovat",
                "poradi": 10,
                "aktivni": True,
            }
        ],
        "referencni_fotografie": [],
        "auditni_tvrzeni": [
            {
                "id": "sys_ms",
                "text": "Systémová otázka MS",
                "poradi": 10,
                "aktivni": True,
                "zavaznost": "stredni",
                "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
                "question_kind": AUDIT_QUESTION_KIND_SYSTEM,
            },
            {
                "id": "ops_ms",
                "text": "Provozní otázka MS",
                "poradi": 20,
                "aktivni": True,
                "zavaznost": "stredni",
                "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
                "question_kind": AUDIT_QUESTION_KIND_OPERATION,
            },
        ],
        "sekce": [],
    }
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id="proc_ms",
        process_label="Proces MS",
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id="proc_ms",
            label="Proces MS",
            process_id="proc_ms",
            process_label="Proces MS",
            section=None,
            children=(section_node,),
        )
    ]


class MethodSupportSnapshot1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(text("DELETE FROM audit_question_support_snapshots"))
            session.execute(text("DELETE FROM audit_question_snapshots"))
            session.execute(text("DELETE FROM audits"))
            session.commit()
        self.system = settings_service.save_workplace(
            name=f"MS Systém-{uuid.uuid4().hex[:4]}",
            active=True,
            audit_enabled=True,
        )
        self.wp = settings_service.save_workplace(
            name=f"MS Provoz-{uuid.uuid4().hex[:4]}",
            active=True,
            audit_enabled=True,
        )
        system_audit_workplace_service.set_system_audit_workplace_id(self.system.id)
        self.tree = _fake_tree()

    def test_01_schema_present(self) -> None:
        self.assertTrue(schema_is_present(_DB))
        self.assertFalse(needs_method_support_snapshot_1_schema(_DB))

    def test_02_new_audit_freezes_full_support(self) -> None:
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            wraps=audit_knowledge_service.get_knowledge_tree,
        ) as mocked:
            audit = create_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.wp.id,
                    "workplace_name": self.wp.name,
                    "year": 2026,
                    "started_at": date(2026, 8, 1),
                    "title": "MS new",
                },
                workplace_id=self.wp.id,
                knowledge_tree=self.tree,
                ensure_knowledge=False,
            )
            mocked.assert_not_called()

        with get_session() as session:
            from sqlalchemy import select

            rows = list(
                session.scalars(
                    select(AuditQuestionSupportSnapshot).where(
                        AuditQuestionSupportSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            self.assertGreaterEqual(len(rows), 1)
            for row in rows:
                self.assertEqual(row.source, METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION)
                self.assertIn(
                    row.status,
                    (METHOD_SUPPORT_STATUS_AVAILABLE, METHOD_SUPPORT_STATUS_EMPTY),
                )
                payload = json.loads(row.support_payload_json)
                self.assertIn("objektivni_dukazy", payload["section"])
                self.assertEqual(
                    payload["section"]["objektivni_dukazy"][0]["nazev"], "Důkaz A"
                )
                self.assertEqual(payload["section"]["cil_overeni"], "Ověřit podporu")

        # Live change must not affect frozen support
        self.tree[0].children[0].section["objektivni_dukazy"][0]["nazev"] = "Změněno"
        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(source.is_snapshot)
        section = source.roots[0].children[0].section
        evidence = section.get("objektivni_dukazy") or []
        self.assertEqual(evidence[0]["nazev"], "Důkaz A")

    def test_03_empty_support_is_available_empty(self) -> None:
        payload, status = build_support_payload_from_section(
            section={"id": "s", "nazev": "S", "auditni_tvrzeni": []},
            process_knowledge={},
        )
        self.assertEqual(status, METHOD_SUPPORT_STATUS_EMPTY)
        self.assertEqual(payload["section"]["objektivni_dukazy"], [])

    def test_04_backfill_unavailable_and_single_tree_load(self) -> None:
        # Manuálně vytvoř snapshotovaný audit bez supportu
        audit = audit_service.create_audit(
            workplace_id=self.wp.id,
            workplace_name=self.wp.name,
            year=2026,
            title="Legacy snap",
        )
        with get_session() as session:
            db = session.get(type(audit), audit.id)
            assert db is not None
            db.methodology_source = "snapshot"
            db.methodology_generation = "v2"
            from datetime import datetime

            db.questions_frozen_at = datetime.now()
            session.add(
                AuditQuestionSnapshot(
                    audit_id=audit.id,
                    process_id="gone_proc",
                    process_name="Gone",
                    section_id="gone_sec",
                    section_name="Gone Sec",
                    assertion_id="gone_q",
                    assertion_text="Stará otázka",
                    verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                    severity="stredni",
                    question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                    display_order=10,
                    is_in_scope=True,
                )
            )
            session.add(
                AuditQuestionSnapshot(
                    audit_id=audit.id,
                    process_id="proc_ms",
                    process_name="Proces MS",
                    section_id="sec_ms",
                    section_name="Sekce MS",
                    assertion_id="sys_ms",
                    assertion_text="Systémová",
                    verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                    severity="stredni",
                    question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                    display_order=20,
                    is_in_scope=True,
                )
            )
            # extraordinary — nesmí dostat support
            session.add(
                AuditQuestionSnapshot(
                    audit_id=audit.id,
                    process_id="__extraordinary__",
                    process_name="Mimořádná",
                    section_id="__extraordinary_section__",
                    section_name="Mimořádná",
                    assertion_id="ext_1",
                    assertion_text="Mimořádná",
                    verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                    severity="stredni",
                    question_kind="extraordinary",
                    display_order=9000,
                    is_in_scope=True,
                )
            )
            session.commit()

        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=self.tree,
        ) as mocked:
            stats = run_method_support_backfill()
            self.assertEqual(mocked.call_count, 1)

        self.assertGreaterEqual(stats.supports_unavailable, 1)
        with get_session() as session:
            from sqlalchemy import select

            rows = list(
                session.scalars(
                    select(AuditQuestionSupportSnapshot).where(
                        AuditQuestionSupportSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            # extraordinary excluded
            self.assertEqual(len(rows), 2)
            sources = {row.source for row in rows}
            self.assertTrue(
                METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL in sources
                or METHOD_SUPPORT_STATUS_UNAVAILABLE
                in {row.status for row in rows}
            )
            statuses = {row.status for row in rows}
            self.assertIn(METHOD_SUPPORT_STATUS_UNAVAILABLE, statuses)

        # Idempotentní druhý běh
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            return_value=self.tree,
        ) as mocked2:
            stats2 = run_method_support_backfill()
            self.assertEqual(mocked2.call_count, 1)
        self.assertEqual(stats2.supports_available + stats2.supports_empty + stats2.supports_unavailable, 0)

        source = audit_question_source_service.resolve_for_audit(audit.id)
        self.assertTrue(source.is_snapshot)
        # unavailable sekce
        status = source.section_support_status.get(("gone_proc", "gone_sec"))
        self.assertEqual(status, METHOD_SUPPORT_STATUS_UNAVAILABLE)
        self.assertEqual(METHOD_SUPPORT_UNAVAILABLE_MESSAGE.startswith("Metodická"), True)

    def test_05_snapshot_dialog_source_no_live_tree(self) -> None:
        audit = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp.id,
                "workplace_name": self.wp.name,
                "year": 2026,
                "started_at": date.today(),
                "title": "MS dialog",
            },
            workplace_id=self.wp.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            wraps=audit_knowledge_service.get_knowledge_tree,
        ) as mocked:
            source = audit_question_source_service.resolve_for_audit(audit.id)
            mocked.assert_not_called()
        self.assertTrue(source.is_snapshot)
        section = source.roots[0].children[0].section
        self.assertTrue(section.get("objektivni_dukazy"))
        self.assertIn(("proc_ms", "sec_ms"), source.section_support_status)

    def test_06_out_of_scope_and_integrity(self) -> None:
        from moduly.audity.modely.audit import Audit
        from moduly.audity.sluzby.audit_snapshot_integrity_service import (
            diagnose_frozen_snapshot_db_only,
        )
        from sqlalchemy import select

        audit = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp.id,
                "workplace_name": self.wp.name,
                "year": 2026,
                "started_at": date.today(),
                "title": "MS integrity",
            },
            workplace_id=self.wp.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        with get_session() as session:
            db_audit = session.get(Audit, int(audit.id))
            assert db_audit is not None
            questions = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            supports = list(
                session.scalars(
                    select(AuditQuestionSupportSnapshot).where(
                        AuditQuestionSupportSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            audit_method_support_snapshot_service.verify_support_integrity(
                db_audit, questions, supports
            )
            reasons = diagnose_frozen_snapshot_db_only(
                db_audit,
                snapshot_rows=questions,
                control_results=[],
            )
            self.assertEqual(reasons, [])

            # out-of-scope orphan — bez support řádku
            session.add(
                AuditQuestionSnapshot(
                    audit_id=audit.id,
                    process_id="orphan_p",
                    process_name="Orphan",
                    section_id="orphan_s",
                    section_name="Orphan S",
                    assertion_id="orphan_q",
                    assertion_text="Orphan",
                    verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                    severity="stredni",
                    question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                    display_order=9999,
                    is_in_scope=False,
                )
            )
            session.commit()
            questions2 = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            supports2 = list(
                session.scalars(
                    select(AuditQuestionSupportSnapshot).where(
                        AuditQuestionSupportSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            orphan = next(q for q in questions2 if q.is_in_scope is False)
            support_ids = {int(r.audit_question_snapshot_id) for r in supports2}
            self.assertNotIn(int(orphan.id), support_ids)
            # support integrity stále OK (orphan mimo očekávaný rozsah)
            audit_method_support_snapshot_service.verify_support_integrity(
                db_audit, questions2, supports2
            )

    def test_07_reference_photo_freeze_and_missing(self) -> None:
        from moduly.audity.sluzby.audit_method_support_photo_service import (
            absolute_support_photo_path,
            freeze_reference_photos_in_payload,
            publish_staged_support_photos,
            cleanup_staging,
            SNAPSHOT_SUPPORT_PHOTOS_DIR,
        )
        import tempfile

        src_dir = Path(tempfile.mkdtemp(prefix="ms-photo-src-"))
        src_file = src_dir / "ref.jpg"
        src_file.write_bytes(b"\xff\xd8\xff\xe0" + b"fake-jpeg-content-ms1")

        with patch(
            "moduly.audity.sluzby.audit_method_support_photo_service."
            "audit_reference_photo_service.absolute_photo_path",
            side_effect=lambda rel: src_file if "ref" in str(rel) else Path("/missing"),
        ):
            payload = {
                "schema_version": 1,
                "process": {},
                "section": {
                    "referencni_fotografie": [
                        {"id": "f1", "nazev": "Ref", "soubor": "live/ref.jpg", "aktivni": True},
                        {"id": "f2", "nazev": "Gone", "soubor": "live/missing.jpg", "aktivni": True},
                    ]
                },
            }
            staging = Path(tempfile.mkdtemp(prefix="ms-photo-stage-"))
            try:
                frozen, staged = freeze_reference_photos_in_payload(
                    payload, staging_dir=staging
                )
                photos = frozen["section"]["referencni_fotografie"]
                self.assertTrue(photos[0]["soubor"].startswith(f"{SNAPSHOT_SUPPORT_PHOTOS_DIR}/"))
                self.assertIn("file_sha256", photos[0])
                self.assertTrue(photos[1].get("missing"))
                publish_staged_support_photos(staged, staging)
            finally:
                cleanup_staging(staging)

            frozen_rel = photos[0]["soubor"]
            abs_path = absolute_support_photo_path(frozen_rel)
            self.assertTrue(abs_path.is_file())
            # Zdroj zmizí — zmrazená kopie zůstane
            src_file.unlink()
            self.assertTrue(absolute_support_photo_path(frozen_rel).is_file())


if __name__ == "__main__":
    unittest.main()

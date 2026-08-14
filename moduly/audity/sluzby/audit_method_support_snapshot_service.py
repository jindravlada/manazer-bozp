"""Služba zmrazení / načtení metodické podpory auditních otázek."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    METHOD_SUPPORT_PAYLOAD_VERSION,
    METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION,
    METHOD_SUPPORT_SOURCE_UNAVAILABLE,
    METHOD_SUPPORT_STATUS_AVAILABLE,
    METHOD_SUPPORT_STATUS_EMPTY,
    METHOD_SUPPORT_STATUS_UNAVAILABLE,
)
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.modely.audit_question_support_snapshot import (
    AuditQuestionSupportSnapshot,
)
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode
from moduly.audity.sluzby.audit_method_support_payload_service import (
    build_section_index_with_process_knowledge,
    build_support_payload_from_section,
    canonical_json_dumps,
    load_process_knowledge_map_from_tree,
    payload_integrity_hash,
    process_knowledge_from_payload,
    section_dict_from_payload,
    unavailable_payload,
)
from moduly.audity.sluzby.audit_method_support_photo_service import (
    cleanup_staging,
    freeze_reference_photos_in_payload,
    publish_staged_support_photos,
)

logger = logging.getLogger(__name__)


class MethodSupportSnapshotError(RuntimeError):
    """Chyba při zápisu/ověření metodické podpory."""


def _is_regular_in_scope(row: AuditQuestionSnapshot) -> bool:
    if row.is_in_scope is False:
        return False
    kind = interpret_question_kind(row.question_kind)
    return kind != AUDIT_QUESTION_KIND_EXTRAORDINARY


def compute_audit_support_integrity_hash_from_rows(
    rows: Collection[tuple],
) -> str:
    """
    rows: (audit_question_snapshot_id, status, source, integrity_hash,
           payload_version, id)
    """
    lines: list[str] = []
    ordered = sorted(
        rows,
        key=lambda item: (int(item[0]), int(item[5] if len(item) > 5 else 0)),
    )
    for row in ordered:
        lines.append(
            f"{int(row[0])}|{row[1]}|{row[2]}|{row[3]}|{int(row[4])}"
        )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def compute_audit_support_integrity_hash(
    rows: Collection[AuditQuestionSupportSnapshot],
) -> str:
    return compute_audit_support_integrity_hash_from_rows(
        [
            (
                int(row.audit_question_snapshot_id),
                str(row.status or ""),
                str(row.source or ""),
                str(row.integrity_hash or ""),
                int(row.payload_version or 0),
                int(row.id or 0),
            )
            for row in rows
        ]
    )


class AuditMethodSupportSnapshotService:
    def build_rows_for_new_audit(
        self,
        session: Session,
        *,
        audit: Audit,
        question_rows: list[AuditQuestionSnapshot],
        knowledge_tree: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...],
        source: str = METHOD_SUPPORT_SOURCE_SNAPSHOT_AT_CREATION,
        when: datetime | None = None,
    ) -> list[AuditQuestionSupportSnapshot]:
        """Vytvoří support řádky v session (bez commit). Foto staging publish volající."""
        frozen_at = when or datetime.now()
        process_map = load_process_knowledge_map_from_tree(knowledge_tree)
        section_index = build_section_index_with_process_knowledge(
            knowledge_tree,
            process_knowledge_by_id=process_map,
        )

        staging_root = Path(tempfile.mkdtemp(prefix="method-support-new-"))
        staged_files: list[Path] = []
        created: list[AuditQuestionSupportSnapshot] = []
        try:
            # Cache payload per section (stejná podpora pro otázky v sekci).
            payload_cache: dict[tuple[str, str], tuple[str, str, str]] = {}
            for row in question_rows:
                if not _is_regular_in_scope(row):
                    continue
                key = (str(row.process_id), str(row.section_id))
                if key not in payload_cache:
                    section, process_knowledge = section_index.get(key, ({}, {}))
                    if not section and key not in section_index:
                        payload = unavailable_payload()
                        status = METHOD_SUPPORT_STATUS_UNAVAILABLE
                        src = METHOD_SUPPORT_SOURCE_UNAVAILABLE
                        payload, more_staged = freeze_reference_photos_in_payload(
                            payload, staging_dir=staging_root
                        )
                        staged_files.extend(more_staged)
                    else:
                        payload, status = build_support_payload_from_section(
                            section=section,
                            process_knowledge=process_knowledge,
                        )
                        payload, more_staged = freeze_reference_photos_in_payload(
                            payload, staging_dir=staging_root
                        )
                        staged_files.extend(more_staged)
                        src = source
                    canonical = canonical_json_dumps(payload)
                    payload_cache[key] = (
                        canonical,
                        status,
                        src,
                    )
                canonical, status, src = payload_cache[key]
                support = AuditQuestionSupportSnapshot(
                    audit_id=int(audit.id),
                    audit_question_snapshot_id=int(row.id),
                    payload_version=METHOD_SUPPORT_PAYLOAD_VERSION,
                    support_payload_json=canonical,
                    source=src,
                    status=status,
                    integrity_hash=payload_integrity_hash(canonical),
                    created_at=frozen_at,
                )
                session.add(support)
                created.append(support)

            session.flush()
            publish_staged_support_photos(staged_files, staging_root)
            self.apply_support_integrity_manifest(audit, created)
            return created
        except Exception:
            cleanup_staging(staging_root)
            raise
        finally:
            cleanup_staging(staging_root)

    def apply_support_integrity_manifest(
        self,
        audit: Audit,
        rows: Collection[AuditQuestionSupportSnapshot],
    ) -> None:
        audit.support_snapshot_count = len(list(rows))
        audit.support_integrity_hash = compute_audit_support_integrity_hash(rows)

    def list_for_audit(
        self, session: Session, audit_id: int
    ) -> list[AuditQuestionSupportSnapshot]:
        return list(
            session.scalars(
                select(AuditQuestionSupportSnapshot).where(
                    AuditQuestionSupportSnapshot.audit_id == int(audit_id)
                )
            )
        )

    def delete_for_audit(self, audit_id: int) -> int:
        with get_session() as session:
            rows = self.list_for_audit(session, int(audit_id))
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
            return count

    def map_by_question_snapshot_id(
        self, session: Session, audit_id: int
    ) -> dict[int, AuditQuestionSupportSnapshot]:
        return {
            int(row.audit_question_snapshot_id): row
            for row in self.list_for_audit(session, audit_id)
        }

    def load_payload(self, row: AuditQuestionSupportSnapshot) -> dict[str, Any]:
        try:
            data = json.loads(row.support_payload_json or "{}")
        except json.JSONDecodeError:
            return unavailable_payload()
        return data if isinstance(data, dict) else unavailable_payload()

    def verify_support_integrity(
        self,
        audit: Audit,
        question_rows: list[AuditQuestionSnapshot],
        support_rows: list[AuditQuestionSupportSnapshot],
        *,
        check_payloads: bool = True,
        check_photos: bool = True,
    ) -> None:
        expected_ids = {
            int(row.id)
            for row in question_rows
            if _is_regular_in_scope(row) and row.id is not None
        }
        actual = {
            int(row.audit_question_snapshot_id): row for row in support_rows
        }
        missing = sorted(expected_ids - set(actual))
        extra = sorted(set(actual) - expected_ids)
        if missing or extra:
            raise MethodSupportSnapshotError(
                f"Nekonzistentní metodická podpora auditu {audit.id}: "
                f"chybí={missing[:10]} navíc={extra[:10]}"
            )

        expected_count = len(expected_ids)
        stored_count = getattr(audit, "support_snapshot_count", None)
        if stored_count is not None and int(stored_count) != expected_count:
            raise MethodSupportSnapshotError(
                f"support_snapshot_count={stored_count} != {expected_count}"
            )
        expected_audit_hash = compute_audit_support_integrity_hash(support_rows)
        stored_hash = str(getattr(audit, "support_integrity_hash", None) or "")
        if stored_hash and stored_hash != expected_audit_hash:
            raise MethodSupportSnapshotError(
                f"support_integrity_hash nesouhlasí u auditu {audit.id}"
            )

        if not check_payloads and not check_photos:
            return

        from moduly.audity.sluzby.audit_method_support_photo_service import (
            absolute_support_photo_path,
            _sha256_file,
        )

        for row in support_rows:
            canonical = str(row.support_payload_json or "")
            if check_payloads:
                expected_hash = payload_integrity_hash(canonical)
                if row.integrity_hash != expected_hash:
                    raise MethodSupportSnapshotError(
                        f"Neplatný integrity_hash support id={row.id}"
                    )
                try:
                    payload = json.loads(canonical)
                except json.JSONDecodeError as exc:
                    raise MethodSupportSnapshotError(
                        f"Neplatný JSON support id={row.id}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise MethodSupportSnapshotError(
                        f"Neplatný payload support id={row.id}"
                    )
            else:
                payload = None

            if not check_photos:
                continue
            if payload is None:
                try:
                    payload = json.loads(canonical)
                except json.JSONDecodeError as exc:
                    raise MethodSupportSnapshotError(
                        f"Neplatný JSON support id={row.id}"
                    ) from exc
            if not isinstance(payload, dict):
                continue
            section = payload.get("section")
            photos = (
                section.get("referencni_fotografie")
                if isinstance(section, dict)
                else None
            )
            if not isinstance(photos, list):
                continue
            for photo in photos:
                if not isinstance(photo, dict) or photo.get("missing"):
                    continue
                rel = str(photo.get("soubor") or "").strip()
                if not rel:
                    continue
                abs_path = absolute_support_photo_path(rel)
                if not abs_path.is_file():
                    raise MethodSupportSnapshotError(
                        f"Chybí zmrazená referenční fotografie {rel} "
                        f"(support id={row.id})"
                    )
                expected_photo_hash = str(photo.get("file_sha256") or "").strip()
                if expected_photo_hash and _sha256_file(abs_path) != expected_photo_hash:
                    raise MethodSupportSnapshotError(
                        f"Hash referenční fotografie nesouhlasí {rel} "
                        f"(support id={row.id})"
                    )

    def enrich_section_from_support(
        self,
        *,
        base_section: dict,
        support_row: AuditQuestionSupportSnapshot | None,
    ) -> tuple[dict, dict | None, str]:
        """
        Vrátí (section, process_knowledge|None, status).
        status: available|empty|unavailable|missing
        """
        if support_row is None:
            return dict(base_section), None, "missing"
        status = str(support_row.status or "")
        if status == METHOD_SUPPORT_STATUS_UNAVAILABLE:
            return dict(base_section), None, METHOD_SUPPORT_STATUS_UNAVAILABLE
        payload = self.load_payload(support_row)
        section = section_dict_from_payload(payload, base_section=base_section)
        process_knowledge = process_knowledge_from_payload(payload)
        return section, process_knowledge, status or METHOD_SUPPORT_STATUS_AVAILABLE


audit_method_support_snapshot_service = AuditMethodSupportSnapshotService()

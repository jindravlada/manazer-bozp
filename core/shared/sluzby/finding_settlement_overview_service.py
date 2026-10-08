"""Historické přehledy vypořádání zjištění pro představenstvo.

Řada Auditů a řada Prověrek mají vlastní pořadová čísla. Obě řady berou
jen záznamy ve stavu Dokončeno. Rozhraní a export jsou zatím jen pro Audity.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import transaction
from core.shared.constants import (
    ENTITY_AUDITY,
    ENTITY_PROVERKY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    SETTLEMENT_SOURCE_AUDITY,
    SETTLEMENT_SOURCE_PROVERKY,
    VALID_SETTLEMENT_SOURCES,
)
from core.shared.modely.finding import Finding
from core.shared.modely.finding_settlement_overview import (
    FindingSettlementOverview,
    FindingSettlementOverviewItem,
)
from core.shared.modely.finding_status_event import FindingStatusEvent
from moduly.ukoly.modely.task import Task


class FindingSettlementOverviewError(ValueError):
    """Přehled nelze uložit. Rozpracovaný zápis se při tom neponechá."""


@dataclass(frozen=True)
class FindingSettlementScope:
    """Kolik dokončených záznamů a jejich zjištění by další přehled zahrnul."""

    completed_record_count: int
    finding_count: int


_OPEN_STATUSES = frozenset(
    {
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
    }
)


@dataclass(frozen=True)
class _ParentRecord:
    record_id: int
    number: str
    year: int | None
    workplace_name: str


@dataclass(frozen=True)
class _CollectedFinding:
    finding: Finding
    parent: _ParentRecord
    task_title: str
    task_status: str


class FindingSettlementOverviewService:
    def create_overview(
        self,
        source_type: str,
        *,
        presented_at: date | None = None,
        note: str = "",
    ) -> FindingSettlementOverview:
        """Uloží další přehled řady. První přehled dané řady má číslo 0."""
        source = self._require_source(source_type)
        presented = presented_at or date.today()
        if not isinstance(presented, date) or isinstance(presented, datetime):
            raise FindingSettlementOverviewError("Datum předložení musí být datum.")

        overview_id = 0
        with transaction() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            previous = self._latest(session, source)
            if previous is not None and presented < previous.presented_at:
                raise FindingSettlementOverviewError(
                    "Datum předložení nemůže být dříve než u předchozího přehledu."
                )
            sequence = 0 if previous is None else int(previous.sequence_number) + 1
            collected = self._collect(session, source)
            previous_items = (
                {}
                if previous is None
                else {
                    int(item.finding_id): item
                    for item in self._items(session, int(previous.id))
                }
            )
            events_by_finding = (
                {}
                if previous is None
                else self._events_after(
                    session,
                    [row.finding.id for row in collected],
                    previous.created_at,
                )
            )
            overview = FindingSettlementOverview(
                source_type=source,
                sequence_number=sequence,
                created_at=datetime.now(),
                presented_at=presented,
                period_from=None if previous is None else previous.presented_at,
                period_to=presented,
                note=str(note or ""),
                total_count=0,
                settled_count=0,
                in_process_count=0,
                open_count=0,
                type_counts_json="{}",
            )
            session.add(overview)
            session.flush()

            type_counts: dict[str, int] = defaultdict(int)
            settled = in_process = opened = 0
            for row in collected:
                item = self._build_item(
                    overview_id=int(overview.id),
                    row=row,
                    previous_item=previous_items.get(row.finding.id),
                    events=events_by_finding.get(row.finding.id, ()),
                    has_previous=previous is not None,
                )
                session.add(item)
                type_counts[item.finding_type] += 1
                if item.status == FINDING_STATUS_VYPORADANO:
                    settled += 1
                elif item.status == FINDING_STATUS_V_PROCESU:
                    in_process += 1
                elif item.status == FINDING_STATUS_OTEVRENE:
                    opened += 1
            overview.total_count = len(collected)
            overview.settled_count = settled
            overview.in_process_count = in_process
            overview.open_count = opened
            overview.type_counts_json = json.dumps(
                dict(sorted(type_counts.items())),
                ensure_ascii=False,
            )
            session.flush()
            overview_id = int(overview.id)

        loaded = self.get_overview(overview_id)
        if loaded is None:
            raise FindingSettlementOverviewError("Přehled se nepodařilo znovu načíst.")
        return loaded

    def completed_scope(self, source_type: str) -> FindingSettlementScope:
        """Spočítá rozsah dalšího přehledu. Do databáze nic nezapíše."""
        source = self._require_source(source_type)
        with transaction() as session:
            parents = self._completed_parents(session, source)
            return FindingSettlementScope(
                completed_record_count=len(parents),
                finding_count=len(self._collect(session, source)),
            )

    def list_overviews(self, source_type: str) -> list[FindingSettlementOverview]:
        source = self._require_source(source_type)
        with transaction() as session:
            rows = list(
                session.scalars(
                    select(FindingSettlementOverview)
                    .where(FindingSettlementOverview.source_type == source)
                    .order_by(FindingSettlementOverview.sequence_number)
                )
            )
            for row in rows:
                session.expunge(row)
            return rows

    def get_overview(self, overview_id: int) -> FindingSettlementOverview | None:
        with transaction() as session:
            row = session.get(FindingSettlementOverview, int(overview_id))
            if row is not None:
                session.expunge(row)
            return row

    def items_for(self, overview_id: int) -> list[FindingSettlementOverviewItem]:
        with transaction() as session:
            rows = self._items(session, int(overview_id))
            for row in rows:
                session.expunge(row)
            return rows

    def _latest(
        self,
        session: Session,
        source_type: str,
    ) -> FindingSettlementOverview | None:
        return session.scalar(
            select(FindingSettlementOverview)
            .where(FindingSettlementOverview.source_type == source_type)
            .order_by(FindingSettlementOverview.sequence_number.desc())
            .limit(1)
        )

    def _items(
        self,
        session: Session,
        overview_id: int,
    ) -> list[FindingSettlementOverviewItem]:
        return list(
            session.scalars(
                select(FindingSettlementOverviewItem)
                .where(FindingSettlementOverviewItem.overview_id == int(overview_id))
                .order_by(
                    FindingSettlementOverviewItem.audit_year,
                    FindingSettlementOverviewItem.audit_number,
                    FindingSettlementOverviewItem.finding_id,
                )
            )
        )

    def _collect(self, session: Session, source_type: str) -> list[_CollectedFinding]:
        parents = {
            parent.record_id: parent
            for parent in self._completed_parents(session, source_type)
        }
        if not parents:
            return []
        entity_type = (
            ENTITY_AUDITY if source_type == SETTLEMENT_SOURCE_AUDITY else ENTITY_PROVERKY
        )
        findings = list(
            session.scalars(
                select(Finding)
                .where(
                    Finding.entity_type == entity_type,
                    Finding.entity_id.in_(parents),
                )
                .order_by(Finding.entity_id, Finding.display_order, Finding.id)
            )
        )
        task_ids = [int(row.task_id) for row in findings if row.task_id]
        tasks = {}
        if task_ids:
            tasks = {
                int(task.id): task
                for task in session.scalars(select(Task).where(Task.id.in_(task_ids)))
            }
        collected: list[_CollectedFinding] = []
        for finding in findings:
            parent = parents.get(int(finding.entity_id))
            if parent is None:
                continue
            task = tasks.get(int(finding.task_id)) if finding.task_id else None
            collected.append(
                _CollectedFinding(
                    finding=finding,
                    parent=parent,
                    task_title="" if task is None else str(task.title or ""),
                    task_status="" if task is None else str(task.computed_status or ""),
                )
            )
        return collected

    def _completed_parents(
        self,
        session: Session,
        source_type: str,
    ) -> list[_ParentRecord]:
        if source_type == SETTLEMENT_SOURCE_AUDITY:
            from moduly.audity.constants import AUDIT_STATUS_DOKONCENO
            from moduly.audity.modely.audit import Audit

            rows = session.scalars(
                select(Audit).where(Audit.status == AUDIT_STATUS_DOKONCENO)
            )
            return [
                _ParentRecord(
                    record_id=int(row.id),
                    number=str(row.number or ""),
                    year=row.year,
                    workplace_name=str(row.workplace_name or ""),
                )
                for row in rows
            ]
        if source_type == SETTLEMENT_SOURCE_PROVERKY:
            from moduly.proverky.constants import INSPECTION_STATUS_DOKONCENO
            from moduly.proverky.modely.bozp_inspection import BozpInspection

            rows = session.scalars(
                select(BozpInspection).where(
                    BozpInspection.status == INSPECTION_STATUS_DOKONCENO
                )
            )
            return [
                _ParentRecord(
                    record_id=int(row.id),
                    number=str(row.number or ""),
                    year=row.year,
                    workplace_name=str(row.workplace_name or ""),
                )
                for row in rows
            ]
        return []

    def _events_after(
        self,
        session: Session,
        finding_ids: list[int],
        moment: datetime,
    ) -> dict[int, list[FindingStatusEvent]]:
        if not finding_ids:
            return {}
        rows = session.scalars(
            select(FindingStatusEvent)
            .where(
                FindingStatusEvent.finding_id.in_(finding_ids),
                FindingStatusEvent.changed_at > moment,
            )
            .order_by(FindingStatusEvent.id)
        )
        grouped: dict[int, list[FindingStatusEvent]] = defaultdict(list)
        for row in rows:
            grouped[int(row.finding_id)].append(row)
        return grouped

    def _build_item(
        self,
        *,
        overview_id: int,
        row: _CollectedFinding,
        previous_item: FindingSettlementOverviewItem | None,
        events: tuple[FindingStatusEvent, ...] | list[FindingStatusEvent],
        has_previous: bool,
    ) -> FindingSettlementOverviewItem:
        finding = row.finding
        status = str(finding.status or "")
        previous_status = None if previous_item is None else str(previous_item.status or "")
        settled_now = status == FINDING_STATUS_VYPORADANO
        open_now = status in _OPEN_STATUSES
        was_settled = previous_status == FINDING_STATUS_VYPORADANO
        return FindingSettlementOverviewItem(
            overview_id=overview_id,
            finding_id=int(finding.id),
            audit_id=row.parent.record_id,
            audit_number=row.parent.number,
            audit_year=row.parent.year,
            workplace_name=row.parent.workplace_name,
            finding_type=str(finding.finding_type or ""),
            process_label=str(finding.source_area_label or ""),
            verification_area_label=str(finding.source_section_label or ""),
            description=str(finding.description or ""),
            recommended_action=str(finding.recommended_action or ""),
            status=status,
            resolved_at=finding.resolved_at,
            task_id=int(finding.task_id) if finding.task_id else None,
            task_title=row.task_title,
            task_status=row.task_status,
            settled_since_previous=bool(
                has_previous and settled_now and not was_settled
            ),
            still_unsettled=bool(has_previous and open_now),
            is_new=bool(has_previous and previous_item is None),
            reopened=bool(has_previous and was_settled and open_now),
            resettled=bool(
                has_previous
                and settled_now
                and was_settled
                and self._settled_again(finding, previous_item, events)
            ),
        )

    @staticmethod
    def _settled_again(
        finding: Finding,
        previous_item: FindingSettlementOverviewItem | None,
        events: tuple[FindingStatusEvent, ...] | list[FindingStatusEvent],
    ) -> bool:
        """Opakované vypořádání pozná i stejný kalendářní den díky historii stavů."""
        if previous_item is None:
            return False
        if previous_item.resolved_at != finding.resolved_at:
            return True
        return any(
            event.old_status == FINDING_STATUS_VYPORADANO
            and event.new_status != FINDING_STATUS_VYPORADANO
            for event in events
        )

    @staticmethod
    def _require_source(source_type: str) -> str:
        if source_type not in VALID_SETTLEMENT_SOURCES:
            raise FindingSettlementOverviewError("Neznámý typ přehledu.")
        return source_type


finding_settlement_overview_service = FindingSettlementOverviewService()

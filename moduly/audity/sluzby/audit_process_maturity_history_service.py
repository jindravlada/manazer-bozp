from dataclasses import dataclass

from moduly.audity.modely.audit_process_maturity_snapshot import AuditProcessMaturitySnapshot
from moduly.audity.repository.audit_process_maturity_snapshot_repository import (
    AuditProcessMaturitySnapshotRepository,
)

TREND_IMPROVING = "improving"
TREND_DECLINING = "declining"
TREND_STABLE = "stable"
TREND_UNKNOWN = "unknown"

_MATURITY_SCORES = {
    "kriticky": 1,
    "rizikovy": 2,
    "stabilni": 3,
    "vyspely": 4,
}

_TREND_LABELS = {
    TREND_IMPROVING: "⬆ Zlepšuje se",
    TREND_DECLINING: "⬇ Zhoršuje se",
    TREND_STABLE: "→ Stabilní",
    TREND_UNKNOWN: "— Bez srovnání",
}


@dataclass(frozen=True)
class AuditProcessMaturityTrend:
    process_id: str
    process_name: str
    current_year: int
    current_level: str
    current_emoji: str
    previous_year: int | None
    previous_level: str | None
    previous_emoji: str | None
    direction: str
    label: str

    def to_timeline_line(self) -> str:
        lines = [self.process_name]
        if self.previous_year is not None and self.previous_emoji:
            lines.append(f"{self.previous_year}   {self.previous_emoji}")
        lines.append(f"{self.current_year}   {self.current_emoji}")
        lines.append(f"Trend: {self.label}")
        return "\n".join(lines)


@dataclass(frozen=True)
class AuditProcessMaturityHistoryRecord:
    year: int
    process_id: str
    process_name: str
    maturity_level: str
    maturity_emoji: str
    maturity_label: str
    weighted_score: int
    audits_count: int
    control_points_count: int
    nevyhovuje_count: int
    doporuceni_count: int
    open_measures_count: int
    overdue_measures_count: int
    trend_direction: str
    trend_label: str


class AuditProcessMaturityHistoryService:
    def __init__(self) -> None:
        self.repository = AuditProcessMaturitySnapshotRepository()

    def record_snapshot(
        self,
        *,
        year: int,
        audit_program_id: int | None,
        process_id: str,
        process_name: str,
        maturity_level: str,
        maturity_emoji: str,
        maturity_label: str,
        weighted_score: int,
        audits_count: int,
        control_points_count: int,
        nevyhovuje_count: int,
        doporuceni_count: int,
        open_measures_count: int,
        overdue_measures_count: int,
    ) -> AuditProcessMaturitySnapshot:
        previous = self._find_previous_snapshot(
            year=year,
            audit_program_id=audit_program_id,
            process_id=process_id,
        )
        direction, label = self._resolve_trend(
            current_level=maturity_level,
            previous_level=previous.maturity_level if previous else None,
        )
        snapshot = AuditProcessMaturitySnapshot(
            year=year,
            audit_program_id=audit_program_id,
            process_id=process_id,
            process_name=process_name,
            maturity_level=maturity_level,
            maturity_emoji=maturity_emoji,
            maturity_label=maturity_label,
            weighted_score=weighted_score,
            audits_count=audits_count,
            control_points_count=control_points_count,
            nevyhovuje_count=nevyhovuje_count,
            doporuceni_count=doporuceni_count,
            open_measures_count=open_measures_count,
            overdue_measures_count=overdue_measures_count,
            trend_direction=direction,
            trend_label=label,
        )
        return self.repository.save(snapshot)

    def get_process_history(
        self,
        process_id: str,
        *,
        audit_program_id: int | None = None,
    ) -> list[AuditProcessMaturityHistoryRecord]:
        return [self._to_record(item) for item in self.repository.list_for_process(process_id, audit_program_id=audit_program_id)]

    def get_year_snapshots(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
    ) -> list[AuditProcessMaturityHistoryRecord]:
        return [self._to_record(item) for item in self.repository.list_for_year(year, audit_program_id=audit_program_id)]

    def build_trends_for_year(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
    ) -> list[AuditProcessMaturityTrend]:
        trends: list[AuditProcessMaturityTrend] = []
        for snapshot in self.repository.list_for_year(year, audit_program_id=audit_program_id):
            previous = self._find_previous_snapshot(
                year=year,
                audit_program_id=audit_program_id,
                process_id=snapshot.process_id,
            )
            trends.append(
                AuditProcessMaturityTrend(
                    process_id=snapshot.process_id,
                    process_name=snapshot.process_name,
                    current_year=year,
                    current_level=snapshot.maturity_level,
                    current_emoji=snapshot.maturity_emoji,
                    previous_year=previous.year if previous else None,
                    previous_level=previous.maturity_level if previous else None,
                    previous_emoji=previous.maturity_emoji if previous else None,
                    direction=snapshot.trend_direction,
                    label=snapshot.trend_label,
                )
            )
        return trends

    def trends_text_for_year(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
    ) -> str:
        trends = self.build_trends_for_year(year, audit_program_id=audit_program_id)
        if not trends:
            return "—"
        return "\n\n".join(item.to_timeline_line() for item in trends)

    @staticmethod
    def average_maturity_level(levels: list[str]) -> tuple[str, str, str]:
        mapping = {
            "kriticky": ("kriticky", "🔴", "Kritický"),
            "rizikovy": ("rizikovy", "🟠", "Rizikový"),
            "stabilni": ("stabilni", "🟡", "Stabilní"),
            "vyspely": ("vyspely", "🟢", "Vyspělý"),
        }
        if not levels:
            return mapping["stabilni"]
        average_score = sum(_MATURITY_SCORES.get(level, 2) for level in levels) / len(levels)
        if average_score >= 3.5:
            return mapping["vyspely"]
        if average_score >= 2.5:
            return mapping["stabilni"]
        if average_score >= 1.5:
            return mapping["rizikovy"]
        return mapping["kriticky"]

    def _find_previous_snapshot(
        self,
        *,
        year: int,
        audit_program_id: int | None,
        process_id: str,
    ) -> AuditProcessMaturitySnapshot | None:
        history = self.repository.list_for_process(process_id, audit_program_id=audit_program_id)
        previous_items = [item for item in history if item.year < year]
        if not previous_items:
            return None
        return max(previous_items, key=lambda item: item.year)

    @staticmethod
    def _resolve_trend(
        *,
        current_level: str,
        previous_level: str | None,
    ) -> tuple[str, str]:
        if not previous_level:
            return TREND_UNKNOWN, _TREND_LABELS[TREND_UNKNOWN]
        current_score = _MATURITY_SCORES.get(current_level, 2)
        previous_score = _MATURITY_SCORES.get(previous_level, 2)
        if current_score > previous_score:
            return TREND_IMPROVING, _TREND_LABELS[TREND_IMPROVING]
        if current_score < previous_score:
            return TREND_DECLINING, _TREND_LABELS[TREND_DECLINING]
        return TREND_STABLE, _TREND_LABELS[TREND_STABLE]

    @staticmethod
    def _to_record(snapshot: AuditProcessMaturitySnapshot) -> AuditProcessMaturityHistoryRecord:
        return AuditProcessMaturityHistoryRecord(
            year=snapshot.year,
            process_id=snapshot.process_id,
            process_name=snapshot.process_name,
            maturity_level=snapshot.maturity_level,
            maturity_emoji=snapshot.maturity_emoji,
            maturity_label=snapshot.maturity_label,
            weighted_score=snapshot.weighted_score,
            audits_count=snapshot.audits_count,
            control_points_count=snapshot.control_points_count,
            nevyhovuje_count=snapshot.nevyhovuje_count,
            doporuceni_count=snapshot.doporuceni_count,
            open_measures_count=snapshot.open_measures_count,
            overdue_measures_count=snapshot.overdue_measures_count,
            trend_direction=snapshot.trend_direction,
            trend_label=snapshot.trend_label,
        )


audit_process_maturity_history_service = AuditProcessMaturityHistoryService()

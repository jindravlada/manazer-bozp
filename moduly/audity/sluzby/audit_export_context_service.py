from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from core.export.control_point_appendix import (
    ControlPointAppendixItem,
    build_areas_appendix,
    build_detailed_control_points_appendix,
)
from core.export.odt_engine import OdtRichContent
from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    CONTROL_RESULT_NELZE_POSOUDIT,
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    ENTITY_AUDITY,
    FINDING_TYPE_PRILEZITOST,
)
from core.shared.control_result_display import control_result_label, protocol_evaluation_results
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import (
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.repository.audit_program_repository import AuditProgramRepository
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.nastaveni.sluzby.settings_service import settings_service


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except Exception:
        return text


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _normalize_person_name(value) -> str:
    text = _text(value).casefold()
    return " ".join(text.split())


_AUDIT_TEAM_EXCLUDED_RECORD_TYPES = frozenset(
    {
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_WORKPLACE,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_INVITED,
    }
)


def _format_labeled_block(
    index: int,
    title: str,
    fields: list[tuple[str, str]],
) -> str:
    lines = [f"{index}. {title}"]
    for label, value in fields:
        text = _text(value)
        if text:
            lines.append(f"   {label}: {text}")
    return "\n".join(lines)


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(blocks)


_COMMISSION_ROLE_LABELS = {
    COMMISSION_RECORD_LEADER: "Vedoucí komise",
    COMMISSION_RECORD_WORKPLACE: "Zástupce pracoviště",
    COMMISSION_RECORD_UNION: "Zástupce odborové organizace",
    COMMISSION_RECORD_MEMBER: "Člen komise",
    COMMISSION_RECORD_INVITED: "Přizvaná osoba",
}

_COMMISSION_EXPORT_ORDER = {
    COMMISSION_RECORD_LEADER: 1,
    COMMISSION_RECORD_WORKPLACE: 2,
    COMMISSION_RECORD_UNION: 3,
    COMMISSION_RECORD_MEMBER: 4,
    COMMISSION_RECORD_INVITED: 5,
}

_ASSERTION_RESULT_EMOJI = {
    CONTROL_RESULT_VYHOVUJE: "🟢",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "🟡",
    CONTROL_RESULT_NEVYHOVUJE: "🔴",
    CONTROL_RESULT_NELZE_POSOUDIT: "⚪",
    CONTROL_RESULT_NEKONTROLOVANO: "○",
}

_ASSERTION_RESULT_WORDS = {
    CONTROL_RESULT_VYHOVUJE: "Vyhovuje",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "Vyhovuje s doporučením",
    CONTROL_RESULT_NEVYHOVUJE: "Nevyhovuje",
    CONTROL_RESULT_NELZE_POSOUDIT: "Není relevantní",
    CONTROL_RESULT_NEKONTROLOVANO: "Nekontrolováno",
}


@dataclass(frozen=True)
class AuditExportDocumentConfig:
    """Konfigurace výstupního dokumentu z auditu (protokol vs. podrobná zpráva)."""

    include_signatures: bool = True
    detailed_assertions_appendix: bool = False


PROTOCOL_DOCUMENT_CONFIG = AuditExportDocumentConfig(
    include_signatures=True,
    detailed_assertions_appendix=False,
)

DETAILED_REPORT_DOCUMENT_CONFIG = AuditExportDocumentConfig(
    include_signatures=False,
    detailed_assertions_appendix=True,
)


@dataclass(frozen=True)
class AuditExportContext:
    """Sjednocený kontext exportu protokolu / podrobné zprávy auditu."""

    audit: Audit
    config: AuditExportDocumentConfig = PROTOCOL_DOCUMENT_CONFIG

    @property
    def audit_id(self) -> int:
        return self.audit.id

    def is_completed(self) -> bool:
        return self.audit.finished_at is not None

    def planned_month_label(self) -> str:
        month = self.audit.planned_month
        if month is None or month < 1 or month > 12:
            return PLANNED_MONTH_NOT_SET_LABEL
        return PLANNED_MONTH_NAMES[month - 1]

    def status_label(self) -> str:
        return audit_service.derive_status(
            self.audit.started_at,
            self.audit.finished_at,
        )

    def employer_name(self) -> str:
        employer = settings_service.get_employer()
        if employer is None:
            return ""
        return _text(employer.name)

    def program_name(self) -> str:
        program_id = self.audit.program_id
        if program_id is None:
            return ""
        program = AuditProgramRepository().get_program(program_id)
        if program is None:
            return ""
        return _text(program.name)

    def commission_lines(self) -> list[str]:
        members = audit_commission_service.get_for_audit(self.audit_id)
        if not members:
            return []

        lines: list[str] = []
        for member in sorted(
            members,
            key=lambda item: (
                _COMMISSION_EXPORT_ORDER.get(item.record_type, 99),
                item.display_order,
                item.id,
            ),
        ):
            role = _COMMISSION_ROLE_LABELS.get(member.record_type, member.record_type)
            lines.append(f"• {member.display_name} – {role}")
        return lines

    def commission_text(self) -> str:
        lines = self.commission_lines()
        return "\n".join(lines) if lines else "Nejsou evidováni."

    def commission_members_without_leader_lines(self) -> list[str]:
        """Skuteční členové auditorského týmu (bez vedoucího, zástupců a hostů)."""
        members = audit_commission_service.get_for_audit(self.audit_id)
        if not members:
            return []

        excluded_thp_ids: set[int] = set()
        excluded_person_ids: set[int] = set()
        excluded_names: set[str] = set()
        for member in members:
            if member.record_type not in _AUDIT_TEAM_EXCLUDED_RECORD_TYPES:
                continue
            if member.thp_worker_id is not None:
                excluded_thp_ids.add(int(member.thp_worker_id))
            if member.person_id is not None:
                excluded_person_ids.add(int(member.person_id))
            normalized = _normalize_person_name(member.display_name)
            if normalized:
                excluded_names.add(normalized)

        lines: list[str] = []
        for member in sorted(
            members,
            key=lambda item: (
                _COMMISSION_EXPORT_ORDER.get(item.record_type, 99),
                item.display_order,
                item.id,
            ),
        ):
            if member.record_type != COMMISSION_RECORD_MEMBER:
                continue
            if (
                member.thp_worker_id is not None
                and int(member.thp_worker_id) in excluded_thp_ids
            ):
                continue
            if (
                member.person_id is not None
                and int(member.person_id) in excluded_person_ids
            ):
                continue
            name = _text(member.display_name)
            if not name:
                continue
            if _normalize_person_name(name) in excluded_names:
                continue
            lines.append(name)
        return lines

    def commission_members_without_leader_text(self) -> str:
        return "\n".join(self.commission_members_without_leader_lines())

    def audit_start_date_text(self) -> str:
        return _fmt_date(self.audit.started_at)

    def audit_end_date_text(self) -> str:
        if not self.audit.finished_at:
            return "Dosud neukončen"
        return _fmt_date(self.audit.finished_at)

    def commission_member_name(self, record_type: str) -> str:
        for member in audit_commission_service.get_for_audit(self.audit_id):
            if member.record_type == record_type:
                return _text(member.display_name)
        return "—"

    def leader_auditor_name(self) -> str:
        return self.commission_member_name(COMMISSION_RECORD_LEADER)

    def workplace_representative_name(self) -> str:
        return self.commission_member_name(COMMISSION_RECORD_WORKPLACE)

    def union_representative_raw_name(self) -> str:
        name = self.commission_member_name(COMMISSION_RECORD_UNION)
        if name in {"", "—"}:
            return ""
        return name

    def union_representative_name(self) -> str:
        return self.union_representative_raw_name() or "Neuveden"

    def union_signature_block_text(self) -> str:
        name = self.union_representative_raw_name()
        if not name:
            return ""
        return "\n".join(
            [
                "Zástupce odborové organizace",
                name,
                "........................................",
                "podpis",
            ]
        )

    def planned_process_ids(self) -> tuple[str, ...]:
        visit_id = self.audit.program_visit_id
        if visit_id is None:
            return ()
        visit_context = audit_program_service.get_visit_audit_context(visit_id)
        if visit_context is None:
            return ()
        return visit_context.planned_process_ids

    def processes_lines(self) -> list[str]:
        planned_ids = set(self.planned_process_ids())
        process_names: list[str] = []
        for process in audit_knowledge_service.get_processes():
            if planned_ids and process.id not in planned_ids:
                continue
            process_names.append(process.nazev)
        if process_names:
            return process_names

        seen: set[str] = set()
        for result in control_result_service.get_for_entity(ENTITY_AUDITY, self.audit_id):
            process_id = str(result.source_area_id or "").strip()
            if not process_id or process_id in seen:
                continue
            label = str(result.source_area_label or process_id).strip() or process_id
            seen.add(process_id)
            process_names.append(label)
        return sorted(process_names, key=str.casefold)

    def processes_text(self) -> str:
        lines = self.processes_lines()
        if not lines:
            return "Nejsou evidovány."
        return "\n".join(f"• {line}" for line in lines)

    def appendix_processes_text(self) -> str | OdtRichContent:
        if self.config.detailed_assertions_appendix:
            return self.detailed_appendix_processes()
        return self.processes_text()

    def detailed_appendix_processes(self) -> OdtRichContent:
        """Příloha A podrobné zprávy – názvy procesů tučně, každý jako samostatný odstavec."""
        return build_areas_appendix(self.processes_lines())

    @staticmethod
    def _iter_knowledge_sections(sections: list) -> list[dict]:
        collected: list[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            collected.append(section)
            nested = section.get("sekce") or []
            if isinstance(nested, list):
                collected.extend(AuditExportContext._iter_knowledge_sections(nested))
        return collected

    def _section_assertion_ids(
        self,
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

        for section in self._iter_knowledge_sections(knowledge.get("sekce") or []):
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

    def _assertion_control_results(self):
        """Výsledky ze spisu auditu bez osiřelých tvrzení ze starší metodiky.

        Text tvrzení vždy bere z uloženého ``control_results`` (spis).
        Metodika slouží jen jako filtr platných ID — nikoli jako zdroj textů.
        """
        results = control_result_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        if not results:
            return []

        planned_ids = set(self.planned_process_ids())
        known_process_ids = {
            process.id for process in audit_knowledge_service.get_processes()
        }
        section_cache: dict[tuple[str, str], set[str] | None] = {}
        filtered = []

        for row in results:
            area_id = str(row.source_area_id or "").strip()
            section_id = str(row.source_section_id or "").strip()
            control_point_id = str(row.source_control_point_id or "").strip()

            if (
                planned_ids
                and area_id
                and area_id in known_process_ids
                and area_id not in planned_ids
            ):
                continue

            assertion_ids = self._section_assertion_ids(
                area_id,
                section_id,
                cache=section_cache,
            )
            if assertion_ids is None:
                # Proces/sekce v metodice neexistuje — ponechat uložený výsledek.
                filtered.append(row)
                continue
            if control_point_id in assertion_ids:
                filtered.append(row)
                continue
            # Sekce v metodice je, ale toto tvrzení už ne (osiřelý záznam).

        return filtered

    def appendix_assertions_text(self) -> str | OdtRichContent:
        if self.config.detailed_assertions_appendix:
            return self.detailed_appendix_assertions()
        return self.summary_appendix_assertions_text()

    def summary_appendix_assertions_text(self) -> str:
        results = self._assertion_control_results()
        if not results:
            return ""

        grouped: dict[str, list[str]] = {}
        area_order: list[str] = []
        for row in sorted(
            results,
            key=lambda item: (
                item.source_area_label or "",
                item.source_section_label or "",
                item.source_control_point_label or "",
                item.id,
            ),
        ):
            assertion = _text(row.source_control_point_label)
            if not assertion:
                continue
            area = _text(row.source_section_label) or _text(row.source_area_label)
            if not area:
                continue
            emoji = _ASSERTION_RESULT_EMOJI.get(row.result, "○")
            if area not in grouped:
                grouped[area] = []
                area_order.append(area)
            grouped[area].append(f"{emoji} {assertion}")

        blocks: list[str] = []
        for area in area_order:
            lines = grouped.get(area) or []
            if not lines:
                continue
            blocks.append(f"{area}\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    def detailed_appendix_assertions_text(self) -> str:
        """Textová reprezentace podrobné přílohy B (pro testy)."""
        return self.detailed_appendix_assertions().plain_text()

    def detailed_appendix_assertions(self) -> OdtRichContent:
        """Podrobná příloha B: samostatné odstavce (kritérium, tvrzení, doporučení, poznámka, foto)."""
        results = self._assertion_control_results()
        if not results:
            return OdtRichContent()

        recommendations = self._recommendation_by_control_point()
        items: list[ControlPointAppendixItem] = []
        for row in sorted(
            results,
            key=lambda item: (
                item.source_area_label or "",
                item.source_section_label or "",
                item.source_control_point_label or "",
                item.id,
            ),
        ):
            assertion = _text(row.source_control_point_label)
            if not assertion:
                continue
            area = _text(row.source_section_label) or _text(row.source_area_label)
            if not area:
                continue
            photo_path = control_result_service.resolve_photo_path(row)
            items.append(
                ControlPointAppendixItem(
                    area_label=area,
                    control_point_label=assertion,
                    result=row.result,
                    note=_text(getattr(row, "note", "")),
                    recommendation=recommendations.get(
                        str(row.source_control_point_id or "").strip(),
                        "",
                    ),
                    photo_path=photo_path if photo_path and photo_path.is_file() else None,
                )
            )

        return build_detailed_control_points_appendix(
            items,
            result_emoji=_ASSERTION_RESULT_EMOJI,
            result_words=_ASSERTION_RESULT_WORDS,
            note_label="Poznámka auditora:",
            include_recommendation=True,
        )

    def _recommendation_by_control_point(self) -> dict[str, str]:
        """Doporučení z PKZ / zjištění navázaných na auditní tvrzení."""
        mapping: dict[str, str] = {}
        findings = sorted(
            finding_service.get_for_entity(ENTITY_AUDITY, self.audit_id),
            key=lambda item: (
                0 if item.finding_type == FINDING_TYPE_PRILEZITOST else 1,
                item.display_order,
                item.id,
            ),
        )
        for finding in findings:
            control_point_id = str(finding.source_control_point_id or "").strip()
            if not control_point_id:
                continue
            recommendation = _text(finding.recommended_action)
            if not recommendation:
                continue
            mapping.setdefault(control_point_id, recommendation)
        return mapping

    def appendix_assertions_summary_text(self) -> str:
        results = self._assertion_control_results()
        total = 0
        ok = 0
        partial = 0
        fail = 0
        na = 0
        for row in results:
            if row.result == CONTROL_RESULT_NEKONTROLOVANO:
                continue
            total += 1
            if row.result == CONTROL_RESULT_VYHOVUJE:
                ok += 1
            elif row.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM:
                partial += 1
            elif row.result == CONTROL_RESULT_NEVYHOVUJE:
                fail += 1
            elif row.result == CONTROL_RESULT_NELZE_POSOUDIT:
                na += 1
        return "\n".join(
            [
                f"Celkem auditních tvrzení: {total}",
                f"🟢 Splněno: {ok}",
                f"🟡 Částečně splněno: {partial}",
                f"🔴 Nesplněno: {fail}",
                f"⚪ Není relevantní: {na}",
            ]
        )

    def _activity_statistics(self):
        return control_activity_statistics_service.compute(ENTITY_AUDITY, self.audit_id)

    def audited_system_label(self) -> str:
        program = self.program_name()
        if program:
            return program
        audit_type = _text(self.audit.audit_type)
        return audit_type or "Systém managementu BOZP"

    def overall_rating_label(self) -> str:
        stats = self._activity_statistics()
        if stats.ratings_nevyhovuje:
            return "🔴 Nevyhovující"
        if stats.ratings_vyhovuje_s_doporucenim:
            return "🟡 Vyhovuje s výhradami"
        return "🟢 Vyhovující"

    def overall_assessment_text(self) -> str:
        stats = self._activity_statistics()
        if stats.ratings_nevyhovuje:
            first_sentence = "Systém řízení vykazuje neshody vyžadující nápravu."
        elif stats.ratings_vyhovuje_s_doporucenim:
            first_sentence = "Systém řízení je funkční s doporučeními ke zlepšení."
        else:
            first_sentence = "Systém řízení plní požadavky bez závažných výhrad."

        detail_parts: list[str] = []
        if stats.ratings_nevyhovuje == 1:
            detail_parts.append("1 neshoda")
        elif stats.ratings_nevyhovuje > 1:
            detail_parts.append(f"{stats.ratings_nevyhovuje} neshody")
        if stats.ratings_vyhovuje_s_doporucenim == 1:
            detail_parts.append("1 příležitost ke zlepšení")
        elif stats.ratings_vyhovuje_s_doporucenim > 1:
            detail_parts.append(
                f"{stats.ratings_vyhovuje_s_doporucenim} příležitosti ke zlepšení"
            )

        if detail_parts:
            if len(detail_parts) == 2:
                second_sentence = (
                    f"Během auditu byla zjištěna {detail_parts[0]} a {detail_parts[1]}. "
                )
            else:
                second_sentence = f"Během auditu byla zjištěna {detail_parts[0]}. "
        else:
            second_sentence = "Během auditu nebyla zjištěna významná zjištění. "

        if stats.ratings_nevyhovuje >= 3:
            second_sentence += "Bylo prokázáno systémové selhání v některých oblastech."
        else:
            second_sentence += "Audit neprokázal systémové selhání."
        return f"{first_sentence}\n{second_sentence}"

    def strengths_text(self) -> str:
        raw = _text(getattr(self.audit, "silne_stranky", ""))
        if not raw:
            return "—"
        lines: list[str] = []
        for line in raw.split("\n"):
            text = line.strip()
            if not text:
                continue
            if text.startswith("✔"):
                lines.append(text)
            else:
                lines.append(f"✔ {text}")
        return "\n".join(lines) if lines else "—"

    def attention_areas_text(self) -> str:
        results = control_result_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        lines: list[str] = []
        for row in sorted(
            results,
            key=lambda item: (
                0 if item.result == CONTROL_RESULT_NEVYHOVUJE else 1,
                item.source_area_label,
                item.source_section_label,
                item.source_control_point_label,
                item.id,
            ),
        ):
            label = self._attention_area_label(row)
            if row.result == CONTROL_RESULT_NEVYHOVUJE:
                lines.append(f"🔴 {label}")
            elif row.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM:
                lines.append(f"🟡 {label}")
        return "\n".join(lines) if lines else "—"

    @staticmethod
    def _attention_area_label(row) -> str:
        for attr in ("source_control_point_label", "note", "source_section_label"):
            value = _text(getattr(row, attr, ""))
            if value:
                return value
        return "—"

    def audit_scope_text(self) -> str:
        return (
            "Audit byl proveden podle schváleného programu interních auditů.\n"
            "Auditované procesy jsou uvedeny v příloze této zprávy."
        )

    def auditor_recommendation_text(self) -> str:
        stats = self._activity_statistics()
        summary = audit_service.get_conclusion_summary(self.audit_id)
        sentences: list[str] = []

        if stats.ratings_nevyhovuje:
            sentences.append(
                f"Audit identifikoval {stats.ratings_nevyhovuje} neshod "
                "vyžadujících bezodkladné řešení."
            )
        if stats.ratings_vyhovuje_s_doporucenim:
            sentences.append(
                f"V {stats.ratings_vyhovuje_s_doporucenim} oblastech byla "
                "doporučena preventivní zlepšení."
            )
        if not sentences:
            sentences.append(
                "Audit potvrdil účinnost systému managementu BOZP "
                "bez závažných nedostatků."
            )
        if summary["findings_open"] > 0 or summary["tasks_active"] > 0:
            sentences.append(
                f"Organizaci doporučujeme prioritně dokončit "
                f"{summary['findings_open']} otevřených zjištění "
                f"a {summary['tasks_active']} aktivních úkolů."
            )
        else:
            sentences.append(
                "Doporučujeme průběžně sledovat plnění přijatých opatření "
                "a udržovat zavedené kontroly."
            )
        return " ".join(sentences[:4])

    def executive_summary_text(self) -> str:
        stats = self._activity_statistics()
        lines = [
            f"Celkové hodnocení: {self.overall_rating_label()}",
            f"Auditovaný provoz: {_text(self.audit.workplace_name) or '—'}",
            f"Auditovaný systém: {self.audited_system_label()}",
            f"Datum auditu: {_fmt_date(self.audit.audit_date) or '—'}",
            f"Počet auditních tvrzení: {stats.control_points_checked}",
            f"Počet neshod: {stats.ratings_nevyhovuje}",
            f"Počet doporučení: {stats.ratings_vyhovuje_s_doporucenim}",
            "",
            "Stručné doporučení auditora:",
            self.auditor_recommendation_text(),
        ]
        return "\n".join(lines)

    def results_overview_text(self) -> str:
        stats = self._activity_statistics()
        summary = audit_service.get_conclusion_summary(self.audit_id)
        return "\n".join(
            [
                f"Auditovaných procesů: {len(self.processes_lines())}",
                f"Auditních tvrzení: {stats.control_points_checked}",
                f"Vyhovuje: {stats.ratings_vyhovuje}",
                f"Vyhovuje s doporučením: {stats.ratings_vyhovuje_s_doporucenim}",
                f"Nevyhovuje: {stats.ratings_nevyhovuje}",
                f"Zjištění: {stats.findings_total}",
                f"Otevřené úkoly: {summary['tasks_active']}",
            ]
        )

    def signatures_text(self) -> str:
        blocks = [
            "\n".join(
                [
                    "Vedoucí auditor",
                    self.leader_auditor_name(),
                    "........................................",
                    "podpis",
                ]
            ),
            "\n".join(
                [
                    "Zástupce auditovaného provozu",
                    self.workplace_representative_name(),
                    "........................................",
                    "podpis",
                ]
            ),
        ]
        union_block = self.union_signature_block_text()
        if union_block:
            blocks.append(union_block)
        return "\n\n".join(blocks)

    def evaluation_lines(self) -> list[str]:
        results = control_result_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        if not results:
            return []

        included_results = protocol_evaluation_results()
        lines: list[str] = []
        for index, row in enumerate(
            sorted(
                (
                    item
                    for item in results
                    if item.result in included_results
                ),
                key=lambda item: (
                    item.source_area_label,
                    item.source_section_label,
                    item.source_control_point_label,
                    item.id,
                ),
            ),
            start=1,
        ):
            lines.append(
                _format_labeled_block(
                    index,
                    control_result_label(row.result),
                    [
                        ("Proces", row.source_area_label),
                        ("Kritérium", row.source_section_label),
                        ("Tvrzení", row.source_control_point_label),
                        ("Poznámka", row.note),
                    ],
                )
            )
        return lines

    def evaluation_text(self) -> str:
        lines = self.evaluation_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována významná zjištění."

    def significant_findings_text(self) -> str:
        return self.evaluation_text()

    def findings_lines(self) -> list[str]:
        findings = finding_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
        if not findings:
            return []

        lines: list[str] = []
        for index, finding in enumerate(
            sorted(findings, key=lambda item: (item.display_order, item.id)),
            start=1,
        ):
            lines.append(
                _format_labeled_block(
                    index,
                    finding_type_label(finding.finding_type),
                    [
                        ("Proces", finding.source_area_label),
                        ("Kritérium", finding.source_section_label),
                        ("Popis", finding.description),
                        ("Doporučení", finding.recommended_action),
                        ("Termín", _fmt_date(finding.due_date)),
                        ("Odpovědná osoba", finding.responsible_person_name),
                        ("Stav", finding_status_label(finding.status)),
                    ],
                )
            )
        return lines

    def findings_text(self) -> str:
        lines = self.findings_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována."

    def findings_detail_text(self) -> str:
        return self.findings_text()

    def tasks_lines(self) -> list[str]:
        tasks = audit_service.get_tasks_for_audit(self.audit_id)
        if not tasks:
            return []

        lines: list[str] = []
        for index, task in enumerate(tasks, start=1):
            lines.append(
                _format_labeled_block(
                    index,
                    task.title or "Úkol",
                    [
                        ("Odpovídá", task.responsible_person),
                        ("Termín", _fmt_date(task.due_date)),
                        ("Stav", task.computed_status),
                        ("Splněno", _fmt_date(task.completed_date)),
                    ],
                )
            )
        return lines

    def tasks_text(self) -> str:
        lines = self.tasks_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována."

    def accepted_measures_text(self) -> str:
        return self.tasks_text()

    def statistics_text(self) -> str:
        return self.results_overview_text()

    def summary_text(self) -> str:
        return self.executive_summary_text()

    def conclusion_text(self) -> str:
        summary = audit_service.get_conclusion_summary(self.audit_id)
        stats = self._activity_statistics()

        evaluation_parts: list[str] = []
        if stats.ratings_nevyhovuje:
            evaluation_parts.append(f"{stats.ratings_nevyhovuje} neshod")
        if stats.ratings_vyhovuje_s_doporucenim:
            evaluation_parts.append(
                f"{stats.ratings_vyhovuje_s_doporucenim} oblastí s doporučením"
            )

        if evaluation_parts:
            sentence = (
                "Na základě provedeného interního auditu bylo zjištěno "
                + " a ".join(evaluation_parts)
                + "."
            )
        else:
            sentence = (
                "Na základě provedeného interního auditu nebyly zjištěny "
                "neshody ani doporučení k nápravě."
            )

        if summary["findings_open"] > 0 or summary["tasks_active"] > 0:
            sentence += (
                f" K uzavření zbývá {summary['findings_open']} otevřených zjištění"
                f" a {summary['tasks_active']} aktivních úkolů."
            )
        else:
            sentence += (
                " Zjištěné nedostatky byly zaznamenány a byla přijata "
                "odpovídající nápravná opatření."
            )
        return sentence

    def placeholder_values(self) -> dict[str, Any]:
        executive_summary = self.executive_summary_text()
        results_overview = self.results_overview_text()
        significant_findings = self.significant_findings_text()
        accepted_measures = self.accepted_measures_text()
        findings_detail = self.findings_detail_text()
        conclusion = self.conclusion_text()
        if self.config.include_signatures:
            signatures = self.signatures_text()
            union_signature = self.union_signature_block_text()
        else:
            signatures = ""
            union_signature = ""

        return {
            "cislo_auditu": _text(self.audit.number),
            "zamestnavatel_nazev": self.employer_name(),
            "pracoviste": _text(self.audit.workplace_name),
            "provoz": _text(self.audit.workplace_name),
            "program_nazev": self.program_name(),
            "rok": str(self.audit.year or ""),
            "planovany_mesic": self.planned_month_label(),
            "typ_auditu": _text(self.audit.audit_type),
            "datum_auditu": _fmt_date(self.audit.audit_date),
            "datum_zahajeni": self.audit_start_date_text(),
            "datum_ukonceni": self.audit_end_date_text(),
            "datum_zahajeni_auditu": self.audit_start_date_text(),
            "datum_ukonceni_auditu": self.audit_end_date_text(),
            "stav": self.status_label(),
            "komise_text": self.commission_text(),
            "auditni_tym_text": self.commission_text(),
            "clenove_komise_text": self.commission_members_without_leader_text(),
            "procesy_text": self.processes_text(),
            "priloha_procesy_text": self.appendix_processes_text(),
            "priloha_auditni_tvrzeni_text": self.appendix_assertions_text(),
            "priloha_auditni_tvrzeni_souhrn": self.appendix_assertions_summary_text(),
            "celkove_hodnoceni": self.overall_rating_label(),
            "celkove_hodnoceni_text": self.overall_assessment_text(),
            "auditovany_provoz": _text(self.audit.workplace_name),
            "auditovany_system": self.audited_system_label(),
            "vedouci_auditor": self.leader_auditor_name(),
            "zastupce_provozu": self.workplace_representative_name(),
            "zastupce_odborove_organizace": self.union_representative_name(),
            "podpis_odboru_blok": union_signature,
            "doporuceni_auditora": self.auditor_recommendation_text(),
            "silne_stranky_text": self.strengths_text(),
            "oblasti_pozornosti_text": self.attention_areas_text(),
            "rozsah_auditu_text": self.audit_scope_text(),
            "executive_summary_text": executive_summary,
            "prehled_vysledku_text": results_overview,
            "vyznamna_zjisteni_text": significant_findings,
            "prijata_opatreni_text": accepted_measures,
            "detail_zjisteni_text": findings_detail,
            "podpisy_text": signatures,
            "hodnoceni_text": significant_findings,
            "zjisteni_text": findings_detail,
            "ukoly_text": accepted_measures,
            "zaver_text": conclusion,
            "statistika_text": results_overview,
            "souhrn_text": executive_summary,
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
        }


class AuditExportContextService:
    def build(
        self,
        audit: Audit,
        config: AuditExportDocumentConfig | None = None,
    ) -> AuditExportContext:
        if audit is None or not getattr(audit, "id", None):
            raise ValueError("Není vybraný uložený audit.")
        return AuditExportContext(
            audit=audit,
            config=config or PROTOCOL_DOCUMENT_CONFIG,
        )

    def is_completed(self, audit: Audit) -> bool:
        return AuditExportContext(audit=audit).is_completed()


audit_export_context_service = AuditExportContextService()

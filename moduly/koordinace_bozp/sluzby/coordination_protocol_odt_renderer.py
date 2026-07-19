"""Vykreslení koordinačního protokolu do ODT (COORD-011b).

Renderer nepřistupuje k databázi, nepočítá data, nevytváří varování ani PBP.
Vstupem jsou již připravená ``protocol_data``, ``warnings`` a ``summary``.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.export.odt_engine import _sync_written_file
from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
    ATTACHMENT_TYPE_OTHER,
    PROTOCOL_WARNING_SEVERITY_CRITICAL,
    PROTOCOL_WARNING_SEVERITY_INFO,
    PROTOCOL_WARNING_SEVERITY_WARNING,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
    ProtocolBuildResult,
    ProtocolSummary,
    ProtocolWarning,
    flatten_protocol_measure_bullets,
)


class CoordinationProtocolOdtRendererError(ValueError):
    pass


# Pořadí kapitol (bez volitelné „Upozornění“ a závěrečného „Souhrn“).
PROTOCOL_ODT_CHAPTER_TITLES = (
    "Titulní strana",
    "Základní údaje koordinace",
    "Zúčastnění zaměstnavatelé",
    "Účastníci",
    "Koordinátor BOZP",
    "Místa výkonu práce",
    "Činnosti na pracovišti",
    "Organizační opatření",
    "Kontakty",
    "Postupy při mimořádných událostech",
    "Informace o předání rizik",
    "Přehled příloh",
    "Příloha A – Pravidla bezpečné práce (PBP)",
    "Příloha B – Přehled předaných rizik zaměstnavatelů",
    "Příloha C+ – Další přiložené dokumenty",
)


def _format_date(value: str | None) -> str:
    if not value:
        return "—"
    parts = str(value).split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return str(value)


def _as_warning_dicts(warnings: Sequence[Any] | None) -> list[dict]:
    if not warnings:
        return []
    result = []
    for item in warnings:
        if isinstance(item, ProtocolWarning):
            result.append(item.to_dict())
        elif isinstance(item, Mapping):
            result.append(dict(item))
        else:
            result.append(
                {
                    "code": getattr(item, "code", ""),
                    "severity": getattr(item, "severity", ""),
                    "message": getattr(item, "message", str(item)),
                }
            )
    return result


def _as_summary_dict(summary: Any | None) -> dict:
    if summary is None:
        return {}
    if isinstance(summary, ProtocolSummary):
        return summary.to_dict()
    if isinstance(summary, Mapping):
        data = dict(summary)
        if "warnings_total" not in data:
            data["warnings_total"] = (
                int(data.get("warnings_info") or 0)
                + int(data.get("warnings_warning") or 0)
                + int(data.get("warnings_critical") or 0)
            )
        return data
    return {}


class CoordinationProtocolOdtRenderer:
    """Vykreslí ODT výhradně z připravených dat protokolu."""

    DOCUMENT_TITLE = "Koordinační protokol BOZP"

    def render(
        self,
        output_path: str | Path,
        *,
        protocol_data: Mapping[str, Any],
        warnings: Sequence[Any] | None = None,
        summary: Any | None = None,
    ) -> Path:
        if protocol_data is None:
            raise CoordinationProtocolOdtRendererError("protocol_data je povinné.")
        data = dict(protocol_data)
        warning_rows = _as_warning_dicts(warnings)
        summary_data = _as_summary_dict(summary)
        lines = self._build_document_lines(
            data,
            warnings=warning_rows,
            summary=summary_data,
        )
        return self._write_odt(Path(output_path), lines=lines)

    def render_from_result(
        self,
        output_path: str | Path,
        result: ProtocolBuildResult | Mapping[str, Any],
    ) -> Path:
        if isinstance(result, ProtocolBuildResult):
            return self.render(
                output_path,
                protocol_data=result.protocol_data,
                warnings=result.warnings,
                summary=result.summary,
            )
        if not isinstance(result, Mapping):
            raise CoordinationProtocolOdtRendererError(
                "Výsledek sestavení protokolu má neplatný tvar."
            )
        return self.render(
            output_path,
            protocol_data=result.get("protocol_data") or {},
            warnings=result.get("warnings") or [],
            summary=result.get("summary"),
        )

    def _build_document_lines(
        self,
        data: dict,
        *,
        warnings: list[dict],
        summary: dict,
    ) -> list[str]:
        basics = data.get("basics") or {}
        lines: list[str] = []

        # Volitelná kapitola Upozornění na začátku dokumentu
        if warnings:
            lines.append("Upozornění")
            lines.append("")
            for item in warnings:
                severity = item.get("severity") or ""
                prefix = {
                    PROTOCOL_WARNING_SEVERITY_CRITICAL: "[kritické]",
                    PROTOCOL_WARNING_SEVERITY_WARNING: "[varování]",
                    PROTOCOL_WARNING_SEVERITY_INFO: "[info]",
                }.get(severity, "")
                message = (item.get("message") or "").strip() or "—"
                lines.append(f"{prefix} {message}".strip())
            lines.append("")

        # 1. Titulní strana
        lines.extend(
            [
                "Titulní strana",
                "",
                self.DOCUMENT_TITLE,
                "",
                f"Číslo: {basics.get('coordination_number') or '—'}",
                f"Název akce: {basics.get('subject') or '—'}",
                f"Datum schůzky: {_format_date(basics.get('meeting_date'))}",
                f"Místo: {basics.get('place') or '—'}",
                "",
            ]
        )

        # 2. Základní údaje
        lines.extend(
            [
                "Základní údaje koordinace",
                "",
                f"Číslo: {basics.get('coordination_number') or '—'}",
                f"Datum schůzky: {_format_date(basics.get('meeting_date'))}",
                f"Místo: {basics.get('place') or '—'}",
                f"Název akce: {basics.get('subject') or '—'}",
                f"Stav: {basics.get('status_label') or basics.get('status') or '—'}",
                (
                    f"Platnost: {_format_date(basics.get('valid_from'))}"
                    f" – {_format_date(basics.get('valid_to'))}"
                ),
                f"Poznámka: {basics.get('note') or '—'}",
                "",
            ]
        )

        # 3. Zaměstnavatelé
        lines.append("Zúčastnění zaměstnavatelé")
        lines.append("")
        employers = data.get("employers") or []
        if employers:
            for employer in employers:
                role = "hlavní" if employer.get("is_main") else "zúčastněný"
                ico = employer.get("ico") or ""
                ico_part = f", IČO {ico}" if ico else ""
                lines.append(
                    f"• {employer.get('display_name') or '—'} ({role}{ico_part})"
                )
        else:
            lines.append("—")
        lines.append("")

        # 4. Účastníci
        lines.append("Účastníci")
        lines.append("")
        participants_groups = data.get("participants_by_employer") or []
        has_participants = False
        for group in participants_groups:
            employer = group.get("employer") or {}
            participants = group.get("participants") or []
            if not participants:
                continue
            has_participants = True
            lines.append(f"{employer.get('display_name') or '—'}:")
            for participant in participants:
                detail = participant.get("full_name") or "—"
                if participant.get("role"):
                    detail = f"{detail} – {participant['role']}"
                extras = []
                if participant.get("phone"):
                    extras.append(participant["phone"])
                if participant.get("email"):
                    extras.append(participant["email"])
                if extras:
                    detail = f"{detail} ({', '.join(extras)})"
                lines.append(f"  • {detail}")
        if not has_participants:
            lines.append("—")
        lines.append("")

        # 5. Koordinátor
        lines.append("Koordinátor BOZP")
        lines.append("")
        coordinator = data.get("coordinator")
        if not coordinator:
            lines.append("Koordinátor není určen.")
        else:
            lines.append(f"Jméno: {coordinator.get('full_name') or '—'}")
            lines.append(f"Role: {coordinator.get('role') or '—'}")
            lines.append(f"Zaměstnavatel: {coordinator.get('employer_name') or '—'}")
            if coordinator.get("phone"):
                lines.append(f"Telefon: {coordinator['phone']}")
            if coordinator.get("email"):
                lines.append(f"E-mail: {coordinator['email']}")
            if coordinator.get("note"):
                lines.append(f"Poznámka: {coordinator['note']}")
        lines.append("")

        # 6. Místa
        lines.append("Místa výkonu práce")
        lines.append("")
        workplaces = data.get("workplaces") or []
        if workplaces:
            for item in workplaces:
                line = f"• {item.get('label') or '—'}"
                if item.get("note"):
                    line = f"{line} – {item['note']}"
                lines.append(line)
        else:
            lines.append("—")
        lines.append("")

        # 7. Činnosti
        lines.append("Činnosti na pracovišti")
        lines.append("")
        activity_groups = data.get("activities_by_employer") or []
        has_activities = False
        for group in activity_groups:
            employer = group.get("employer") or {}
            activities = group.get("activities") or []
            lines.append(f"{employer.get('display_name') or '—'}:")
            if not activities:
                lines.append("  — bez aktivní činnosti")
                continue
            has_activities = True
            for activity in activities:
                place = activity.get("workplace_label") or ""
                suffix = f" ({place})" if place else ""
                lines.append(
                    f"  • {activity.get('activity_name') or '—'}{suffix}"
                )
                if activity.get("description"):
                    lines.append(f"    {activity['description']}")
        if not activity_groups and not has_activities:
            lines.append("—")
        lines.append("")

        # 8. Opatření
        lines.append("Organizační opatření")
        lines.append("")
        measure_lines = flatten_protocol_measure_bullets(
            data.get("measures_by_category") or []
        )
        if measure_lines:
            lines.extend(measure_lines)
        else:
            lines.append("—")
        lines.append("")

        # 9. Kontakty
        lines.append("Kontakty")
        lines.append("")
        contacts = data.get("contacts") or []
        if contacts:
            for contact in contacts:
                detail = contact.get("custom_name") or "—"
                type_label = contact.get("contact_type_label") or ""
                if type_label:
                    detail = f"{detail} ({type_label})"
                if contact.get("role"):
                    detail = f"{detail} – {contact['role']}"
                extras = []
                if contact.get("phone"):
                    extras.append(contact["phone"])
                if contact.get("email"):
                    extras.append(contact["email"])
                if extras:
                    detail = f"{detail}: {', '.join(extras)}"
                lines.append(f"• {detail}")
        else:
            lines.append("—")
        lines.append("")

        # 10. Postupy
        procedures = data.get("emergency_procedures") or {}
        lines.extend(
            [
                "Postupy při mimořádných událostech",
                "",
                f"Mimořádná událost: {procedures.get('emergency_reporting') or '—'}",
                f"Pracovní úraz: {procedures.get('accident_reporting') or '—'}",
                f"Požár: {procedures.get('fire_reporting') or '—'}",
                f"Evakuace: {procedures.get('evacuation_instructions') or '—'}",
                "",
            ]
        )

        # 11. Předání rizik
        lines.append("Informace o předání rizik")
        lines.append("")
        risk_rows = data.get("risk_handovers") or []
        if risk_rows:
            for row in risk_rows:
                employer = row.get("employer") or {}
                status = row.get("handover_status_label") or row.get("handover_status") or "—"
                lines.append(f"• {employer.get('display_name') or '—'}: {status}")
                submission = row.get("submission") or {}
                if submission:
                    method = submission.get("submission_method") or ""
                    if method:
                        lines.append(f"  Způsob: {method}")
                    if submission.get("submission_date"):
                        lines.append(
                            "  Datum: "
                            f"{_format_date(submission.get('submission_date'))}"
                        )
                    if submission.get("document_reference"):
                        lines.append(
                            f"  Reference: {submission['document_reference']}"
                        )
        else:
            lines.append("—")
        lines.append("")

        # 12. Přehled příloh
        lines.append("Přehled příloh")
        lines.append("")
        lines.append("Dokument odkazuje na následující přílohy:")
        lines.append("• A – Pravidla bezpečné práce (PBP)")
        lines.append("• B – Přehled předaných rizik zaměstnavatelů")
        lines.append("• C+ – Další přiložené dokumenty (pouze seznam)")
        lines.append("")

        # Příloha A
        lines.append("Příloha A – Pravidla bezpečné práce (PBP)")
        lines.append("")
        pbp = data.get("pbp_snapshot")
        if pbp:
            lines.append(f"Název: {pbp.get('title') or 'Pravidla bezpečné práce'}")
            lines.append(f"Revize: {pbp.get('revision_number') or '—'}")
            lines.append(f"Počet pravidel: {pbp.get('rules_count') or 0}")
            lines.append(f"Soubor: {pbp.get('stored_filename') or '—'}")
            if pbp.get("created_at"):
                lines.append(f"Vytvořeno: {pbp['created_at']}")
            if pbp.get("created_by"):
                lines.append(f"Vytvořil: {pbp['created_by']}")
        else:
            lines.append("Příloha PBP (snapshot) není k dispozici.")
        lines.append("")

        # Příloha B
        lines.append("Příloha B – Přehled předaných rizik zaměstnavatelů")
        lines.append("")
        if risk_rows:
            for row in risk_rows:
                employer = row.get("employer") or {}
                status = row.get("handover_status_label") or row.get("handover_status") or "—"
                lines.append(f"• {employer.get('display_name') or '—'}: {status}")
        else:
            lines.append("—")
        contractor_files = self._attachments_of_type(
            data.get("attachments_by_group") or [],
            ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        )
        if contractor_files:
            lines.append("")
            lines.append("Soubory (seznam):")
            for attachment in contractor_files:
                name = (
                    attachment.get("original_filename")
                    or attachment.get("description")
                    or "—"
                )
                lines.append(f"  • {name}")
        lines.append("")

        # Příloha C+
        lines.append("Příloha C+ – Další přiložené dokumenty")
        lines.append("")
        lines.append(
            "Samotné soubory se k tomuto protokolu nepřipojují; níže je pouze seznam."
        )
        other_files = self._attachments_of_type(
            data.get("attachments_by_group") or [],
            ATTACHMENT_TYPE_OTHER,
        )
        # Explicitní „other“ + případné neklasifikované mimo A/B
        extra = []
        for group in data.get("attachments_by_group") or []:
            type_id = group.get("attachment_type")
            if type_id in (
                ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
                ATTACHMENT_TYPE_CONTRACTOR_RISKS,
            ):
                continue
            for attachment in group.get("attachments") or []:
                if attachment not in other_files and attachment not in extra:
                    extra.append(attachment)
        listed = other_files or extra
        if listed:
            for attachment in listed:
                name = (
                    attachment.get("original_filename")
                    or attachment.get("description")
                    or "—"
                )
                lines.append(f"• {name}")
        else:
            lines.append("—")
        lines.append("")

        # Souhrn
        lines.extend(
            [
                "Souhrn",
                "",
                f"Počet zaměstnavatelů: {summary.get('active_employers', 0)}",
                f"Počet účastníků: {summary.get('active_participants', 0)}",
                f"Počet míst: {summary.get('active_workplaces', 0)}",
                f"Počet činností: {summary.get('active_activities', 0)}",
                (
                    "Počet organizačních opatření: "
                    f"{summary.get('active_measures', 0)}"
                ),
                f"Počet kontaktů: {summary.get('active_contacts', 0)}",
                f"Počet pravidel PBP: {summary.get('pbp_rules_count', 0)}",
                f"Počet příloh: {summary.get('active_attachments', 0)}",
                f"Počet upozornění: {summary.get('warnings_total', 0)}",
            ]
        )
        return lines

    @staticmethod
    def _attachments_of_type(groups: list, attachment_type: str) -> list[dict]:
        for group in groups:
            if group.get("attachment_type") == attachment_type:
                return list(group.get("attachments") or [])
        return []

    def _write_odt(self, output_path: Path, *, lines: list[str]) -> Path:
        paragraphs_xml = "".join(
            (
                f'<text:p text:style-name="Standard">{self._escape_xml(line)}</text:p>'
                if line
                else '<text:p text:style-name="Standard"/>'
            )
            for line in lines
        )
        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-content '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
            'office:version="1.2">'
            "<office:body><office:text>"
            f"{paragraphs_xml}"
            "</office:text></office:body></office:document-content>"
        )
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-styles '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'office:version="1.2">'
            "<office:styles/>"
            "</office:document-styles>"
        )
        meta_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-meta '
            'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'office:version="1.2">'
            "<office:meta/>"
            "</office:document-meta>"
        )
        manifest_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<manifest:manifest '
            'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2">'
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:version="1.2" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="styles.xml" '
            'manifest:media-type="text/xml"/>'
            '<manifest:file-entry manifest:full-path="meta.xml" '
            'manifest:media-type="text/xml"/>'
            "</manifest:manifest>"
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w") as zout:
            info = zipfile.ZipInfo("mimetype")
            info.compress_type = zipfile.ZIP_STORED
            zout.writestr(info, "application/vnd.oasis.opendocument.text")
            zout.writestr("content.xml", content_xml.encode("utf-8"))
            zout.writestr("styles.xml", styles_xml.encode("utf-8"))
            zout.writestr("meta.xml", meta_xml.encode("utf-8"))
            zout.writestr("META-INF/manifest.xml", manifest_xml.encode("utf-8"))
        _sync_written_file(output_path)
        return output_path

    @staticmethod
    def _escape_xml(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


coordination_protocol_odt_renderer = CoordinationProtocolOdtRenderer()

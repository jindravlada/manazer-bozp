"""Formátování detailu návrhového balíku AI (R20b)."""

from __future__ import annotations

from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_LABELS
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from moduly.rizeni_rizik.constants import RISK_SEVERITY_LABELS


def format_proposal_package_detail(
    package: AiProposalPackage,
    *,
    resolved_target_event_name: str | None = None,
) -> str:
    lines: list[str] = []
    type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
        package.package_type,
        package.package_type,
    )
    lines.append(f"Balík: {package.package_id}")
    lines.append(f"Typ: {type_label}")

    if package.is_measure_recommendation:
        if package.target_export_id:
            lines.append(f"Cíl (exportní ID): {package.target_export_id}")
        lines.append("")
        lines.append("NAVRHOVANÉ ZNĚNÍ")
        lines.append("-" * 40)
        if package.package_type == "beze_zmen":
            lines.append("(beze změn – stávající opatření jsou dostatečná)")
        else:
            lines.append(package.proposed_text.strip() or "—")
        lines.append("")
        lines.append("ZDŮVODNĚNÍ AI")
        lines.append("-" * 40)
        lines.append(package.reasoning.strip() or "—")
        return "\n".join(lines).rstrip() + "\n"

    if package.target_event_export_id:
        target_name = (resolved_target_event_name or "").strip()
        if target_name:
            lines.append(f"Cílová událost: {target_name}")
        else:
            lines.append("Cílová událost: Doplnění události")
    lines.append("")

    lines.append("UDÁLOST")
    lines.append("-" * 40)
    if package.event is None:
        target_name = (resolved_target_event_name or "").strip()
        if target_name:
            lines.append(f"Doplnění události: {target_name}")
        else:
            lines.append("(doplnění existující události – bez nové události)")
    else:
        lines.append(package.event.name or "—")
        if package.event.description.strip():
            lines.append(package.event.description.strip())
        if package.event.note.strip():
            lines.append(f"Poznámka: {package.event.note.strip()}")
    lines.append("")

    for index, assessment in enumerate(package.assessments, start=1):
        lines.append(f"POSOUZENÍ {index}")
        lines.append("-" * 40)
        groups = assessment.exposed_groups or (
            (assessment.exposed_group,) if assessment.exposed_group else ()
        )
        if groups:
            for group_name in groups:
                lines.append(f"Ohrožená skupina: {group_name}")
        else:
            lines.append("Ohrožená skupina: —")
        severity_label = RISK_SEVERITY_LABELS.get(
            assessment.severity,
            assessment.severity or "—",
        )
        lines.append(f"Závažnost: {severity_label}")
        if assessment.conclusion.strip():
            lines.append(f"Závěr: {assessment.conclusion.strip()}")
        lines.append("")
        lines.append("Zásady bezpečné práce:")
        if assessment.existing_measures:
            for measure in assessment.existing_measures:
                lines.append(f"- {measure.description}")
                if measure.note.strip():
                    lines.append(f"  Poznámka: {measure.note.strip()}")
        else:
            lines.append("- (žádná)")
        lines.append("")
        lines.append("Kontrolní otázky pro revizi rizik:")
        if assessment.required_measures:
            for measure in assessment.required_measures:
                lines.append(f"- {measure.description}")
                if measure.note.strip():
                    lines.append(f"  Poznámka: {measure.note.strip()}")
        else:
            lines.append("- (žádná)")
        lines.append("")

    lines.append("PRÁVNÍ VAZBY")
    lines.append("-" * 40)
    if package.legal_links:
        for link in package.legal_links:
            lines.append(f"- {link.reference}")
            if link.reasoning.strip():
                lines.append(f"  Zdůvodnění: {link.reasoning.strip()}")
    else:
        lines.append("- (žádné)")
    lines.append("")

    lines.append("ZDŮVODNĚNÍ AI")
    lines.append("-" * 40)
    lines.append(package.reasoning.strip() or "—")
    return "\n".join(lines).rstrip() + "\n"

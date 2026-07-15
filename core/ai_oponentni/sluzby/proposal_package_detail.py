"""Formátování detailu návrhového balíku AI (R20b)."""

from __future__ import annotations

from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_LABELS
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from moduly.rizeni_rizik.constants import RISK_SEVERITY_LABELS


def format_proposal_package_detail(package: AiProposalPackage) -> str:
    lines: list[str] = []
    type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
        package.package_type,
        package.package_type,
    )
    lines.append(f"Balík: {package.package_id}")
    lines.append(f"Typ: {type_label}")
    if package.target_event_export_id:
        lines.append(f"Cílová událost: {package.target_event_export_id}")
    lines.append("")

    lines.append("UDÁLOST")
    lines.append("-" * 40)
    if package.event is None:
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
        lines.append(f"Ohrožená skupina: {assessment.exposed_group or '—'}")
        lines.append(f"Možný následek: {assessment.consequence or '—'}")
        severity_label = RISK_SEVERITY_LABELS.get(
            assessment.severity,
            assessment.severity or "—",
        )
        lines.append(f"Závažnost: {severity_label}")
        if assessment.conclusion.strip():
            lines.append(f"Závěr: {assessment.conclusion.strip()}")
        lines.append("")
        lines.append("Existující opatření:")
        if assessment.existing_measures:
            for measure in assessment.existing_measures:
                lines.append(f"- {measure.description}")
                if measure.note.strip():
                    lines.append(f"  Poznámka: {measure.note.strip()}")
        else:
            lines.append("- (žádná)")
        lines.append("")
        lines.append("Potřebná opatření:")
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

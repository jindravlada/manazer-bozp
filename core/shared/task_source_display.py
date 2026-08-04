from core.shared.constants import (
    ENTITY_ACCIDENT,
    ENTITY_AUDITY,
    ENTITY_FINDING,
    ENTITY_LEGAL_REQUIREMENT,
    ENTITY_MEETING,
    ENTITY_MU_INVESTIGATION,
    ENTITY_PROVERKY,
)
from core.shared.sluzby.finding_service import finding_service


def task_type_label(task) -> str:
    from moduly.ukoly.task_display import task_type_table_label

    return task_type_table_label(task)


def task_source_short_label(task) -> str:
    from moduly.rizeni_rizik.constants import ENTITY_RISK_MEASURE_REVIEW

    source_module = task.source_module or ""
    if source_module == ENTITY_LEGAL_REQUIREMENT:
        return "Právní pož."
    if source_module == ENTITY_MU_INVESTIGATION:
        return _entity_source_short_label(ENTITY_MU_INVESTIGATION)
    if source_module == ENTITY_ACCIDENT:
        return _entity_source_short_label(ENTITY_ACCIDENT)
    if source_module == ENTITY_MEETING:
        return "Schůzka"
    if source_module == ENTITY_RISK_MEASURE_REVIEW:
        return "Přezkoumání"
    if source_module == ENTITY_FINDING and task.source_record_id:
        finding = finding_service.get_by_id(task.source_record_id)
        if finding is not None:
            return _entity_source_short_label(finding.entity_type)
        return "Zjištění"

    return _legacy_source_short_label(source_module)


def _entity_source_short_label(entity_type: str) -> str:
    labels = {
        ENTITY_AUDITY: "Audit",
        ENTITY_ACCIDENT: "Úraz",
        ENTITY_MU_INVESTIGATION: "MU",
        ENTITY_PROVERKY: "Prověrka",
        ENTITY_MEETING: "Schůzka",
    }
    return labels.get(entity_type, entity_type or "—")


def _legacy_source_short_label(source: str) -> str:
    from moduly.rizeni_rizik.constants import ENTITY_RISK_MEASURE_REVIEW

    mapping = {
        "manual": "Ručně",
        "uraz": "Úrazy",
        "kniha_urazu": "Úrazy",
        "kniha_urazu_opatreni": "Úrazy",
        "audit": "Audit",
        "audity": "Audit",
        "proverka": "Prověrka",
        "proverky": "Prověrka",
        "kontrola": "Kontrola",
        ENTITY_ACCIDENT: "Úraz",
        ENTITY_FINDING: "Zjištění",
        ENTITY_MU_INVESTIGATION: "MU",
        ENTITY_LEGAL_REQUIREMENT: "Právní pož.",
        ENTITY_MEETING: "Schůzka",
        ENTITY_RISK_MEASURE_REVIEW: "Přezkoumání",
    }
    return mapping.get(source or "", source or "—")


def task_source_label(task) -> str:
    from moduly.rizeni_rizik.constants import ENTITY_RISK_MEASURE_REVIEW

    source_module = task.source_module or ""
    if source_module == ENTITY_LEGAL_REQUIREMENT and task.source_record_id:
        return _legal_requirement_source_label(task.source_record_id)
    if source_module == ENTITY_MU_INVESTIGATION and task.source_record_id:
        return _finding_entity_source_label(ENTITY_MU_INVESTIGATION, task.source_record_id)
    if source_module == ENTITY_ACCIDENT and task.source_record_id:
        return _finding_entity_source_label(ENTITY_ACCIDENT, task.source_record_id)
    if source_module == ENTITY_MEETING and task.source_record_id:
        return _meeting_source_label(task.source_record_id)
    if source_module == ENTITY_RISK_MEASURE_REVIEW and task.source_record_id:
        return _risk_measure_review_source_label(task.source_record_id)
    if source_module == ENTITY_FINDING and task.source_record_id:
        finding = finding_service.get_by_id(task.source_record_id)
        if finding is not None:
            return _finding_entity_source_label(finding.entity_type, finding.entity_id)

    return _legacy_source_label(source_module)


def _risk_measure_review_source_label(review_id: int) -> str:
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )

    review = risk_measure_review_service.get_by_id(review_id)
    if review is None:
        return "Přezkoumání opatření"
    if review.review_number:
        return f"Přezkoumání opatření {review.review_number}"
    return f"Přezkoumání opatření #{review_id}"


def _meeting_source_label(meeting_id: int) -> str:
    from moduly.schuzky.sluzby.meeting_service import meeting_service

    meeting = meeting_service.get_by_id(meeting_id)
    if meeting is None:
        return "Schůzka"
    title = (meeting.title or "").strip()
    if title:
        return f"Schůzka – {title}"
    return f"Schůzka #{meeting_id}"


def _legal_requirement_source_label(requirement_id: int) -> str:
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

    requirement = legal_requirement_service.get_by_id(requirement_id)
    if requirement is None:
        return "Právní požadavek"
    if requirement.regulation_name.strip():
        return f"Právní požadavek – {requirement.regulation_name.strip()}"
    return f"Právní požadavek #{requirement_id}"


def _finding_entity_source_label(entity_type: str, entity_id: int) -> str:
    labels = {
        ENTITY_AUDITY: "Audit systému řízení",
        ENTITY_ACCIDENT: "Úraz",
        ENTITY_MU_INVESTIGATION: "Vyšetřování MU",
        ENTITY_PROVERKY: "Prověrka BOZP",
    }
    base = labels.get(entity_type, entity_type or "—")
    detail = _entity_record_detail(entity_type, entity_id)
    if detail:
        return f"{base} {detail}"
    return base


def _entity_record_detail(entity_type: str, entity_id: int) -> str:
    if entity_type == ENTITY_AUDITY:
        from moduly.audity.sluzby.audit_service import audit_service

        audit = audit_service.get_by_id(entity_id)
        if audit is not None and audit.number:
            return audit.number
    elif entity_type == ENTITY_ACCIDENT:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(entity_id)
        if accident is not None and accident.number:
            return accident.number
    elif entity_type == ENTITY_MU_INVESTIGATION:
        from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service

        investigation = mu_investigation_service.get_by_id(entity_id)
        if investigation is not None and investigation.number:
            return investigation.number

    return ""


def _legacy_source_label(source: str) -> str:
    from moduly.rizeni_rizik.constants import ENTITY_RISK_MEASURE_REVIEW

    mapping = {
        "manual": "Ručně",
        "uraz": "Kniha úrazů",
        "kniha_urazu": "Kniha úrazů",
        "kniha_urazu_opatreni": "Kniha úrazů – opatření",
        "audit": "Audit",
        "audity": "Audit systému řízení",
        "proverka": "Prověrka",
        "proverky": "Prověrka BOZP",
        "kontrola": "Kontrola",
        ENTITY_ACCIDENT: "Úraz",
        ENTITY_FINDING: "Zjištění",
        ENTITY_MU_INVESTIGATION: "Vyšetřování MU",
        ENTITY_LEGAL_REQUIREMENT: "Právní požadavek",
        ENTITY_MEETING: "Schůzka",
        ENTITY_RISK_MEASURE_REVIEW: "Přezkoumání opatření",
    }
    return mapping.get(source or "", source or "—")

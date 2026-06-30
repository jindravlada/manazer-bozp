from core.shared.constants import (
    ENTITY_ACCIDENT,
    ENTITY_AUDITY,
    ENTITY_FINDING,
    ENTITY_MU_INVESTIGATION,
    ENTITY_PROVERKY,
)
from core.shared.sluzby.finding_service import finding_service


def task_type_label(task) -> str:
    from moduly.ukoly.task_display import task_type_table_label

    return task_type_table_label(task)


def task_source_short_label(task) -> str:
    source_module = task.source_module or ""
    if source_module == ENTITY_MU_INVESTIGATION:
        return _entity_source_short_label(ENTITY_MU_INVESTIGATION)
    if source_module == ENTITY_FINDING and task.source_record_id:
        finding = finding_service.get_by_id(task.source_record_id)
        if finding is not None:
            return _entity_source_short_label(finding.entity_type)
        return "Zjištění"

    return _legacy_source_short_label(source_module)


def _entity_source_short_label(entity_type: str) -> str:
    labels = {
        ENTITY_AUDITY: "Audit",
        ENTITY_ACCIDENT: "Administrace",
        ENTITY_MU_INVESTIGATION: "MU",
        ENTITY_PROVERKY: "Prověrka",
    }
    return labels.get(entity_type, entity_type or "—")


def _legacy_source_short_label(source: str) -> str:
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
        ENTITY_FINDING: "Zjištění",
        ENTITY_MU_INVESTIGATION: "MU",
    }
    return mapping.get(source or "", source or "—")


def task_source_label(task) -> str:
    source_module = task.source_module or ""
    if source_module == ENTITY_MU_INVESTIGATION and task.source_record_id:
        return _finding_entity_source_label(ENTITY_MU_INVESTIGATION, task.source_record_id)
    if source_module == ENTITY_FINDING and task.source_record_id:
        finding = finding_service.get_by_id(task.source_record_id)
        if finding is not None:
            return _finding_entity_source_label(finding.entity_type, finding.entity_id)

    return _legacy_source_label(source_module)


def _finding_entity_source_label(entity_type: str, entity_id: int) -> str:
    labels = {
        ENTITY_AUDITY: "Audit IMS",
        ENTITY_ACCIDENT: "Administrace úrazu",
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
        from moduly.audity.sluzby.internal_audit_service import internal_audit_service

        audit = internal_audit_service.get_by_id(entity_id)
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
    mapping = {
        "manual": "Ručně",
        "uraz": "Kniha úrazů",
        "kniha_urazu": "Kniha úrazů",
        "kniha_urazu_opatreni": "Kniha úrazů – opatření",
        "audit": "Audit",
        "audity": "Audit IMS",
        "proverka": "Prověrka",
        "proverky": "Prověrka BOZP",
        "kontrola": "Kontrola",
        ENTITY_FINDING: "Zjištění",
        ENTITY_MU_INVESTIGATION: "Vyšetřování MU",
    }
    return mapping.get(source or "", source or "—")

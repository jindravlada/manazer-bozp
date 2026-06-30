"""Kontrola úplnosti a logiky vyšetřovacího spisu MU."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.utils.casove_rozdily import datetime_from_date_and_time, format_od_udalosti_rozdil
from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_LEVEL_SYSTEMOVA,
    ISHIKAWA_LEVEL_ZAKLADNI,
    ISHIKAWA_STATUS_POTVRZENO,
    ISHIKAWA_STATUSES,
    MU_STATUS_DOKONCENO,
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_CONTROL,
    SOURCE_TYPE_MANUAL,
)
from moduly.vysetrovani_mu.sluzby.mu_chronologie_events import build_system_chronologie_events
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain import (
    build_rejected_cause_chain_warnings,
    chain_cause_label,
)

CHECK_SEVERITY_OK = "ok"
CHECK_SEVERITY_WARNING = "warning"
CHECK_SEVERITY_RECOMMENDATION = "recommendation"
CHECK_SEVERITY_ERROR = "error"

SEVERITY_ORDER = (
    CHECK_SEVERITY_ERROR,
    CHECK_SEVERITY_WARNING,
    CHECK_SEVERITY_RECOMMENDATION,
    CHECK_SEVERITY_OK,
)

SEVERITY_LABELS = {
    CHECK_SEVERITY_OK: "OK",
    CHECK_SEVERITY_WARNING: "Upozornění",
    CHECK_SEVERITY_RECOMMENDATION: "Doporučení",
    CHECK_SEVERITY_ERROR: "Chyba",
}


@dataclass(frozen=True)
class InvestigationCheckResult:
    severity: str
    title: str
    message: str
    tab_name: str
    check_code: str
    suggested_task_title: str = ""
    suggested_task_description: str = ""


def _collect_issue_checks(snapshot: dict) -> list[InvestigationCheckResult]:
    return (
        _check_spis(snapshot)
        + _check_oznameni(snapshot)
        + _check_zajisteni(snapshot)
        + _check_svedci(snapshot)
        + _check_casova_osa(snapshot)
        + _check_ishikawa(snapshot)
        + _check_findings(snapshot)
        + _check_zaver(snapshot)
    )


def run_investigation_checks(snapshot: dict) -> list[InvestigationCheckResult]:
    results = _collect_issue_checks(snapshot)
    results.extend(_check_closed_with_errors(snapshot, results))
    return sorted(results, key=lambda item: (SEVERITY_ORDER.index(item.severity), item.tab_name, item.title))


def _result(
    severity: str,
    *,
    title: str,
    message: str,
    tab_name: str,
    check_code: str,
    suggested_task_title: str = "",
    suggested_task_description: str = "",
) -> InvestigationCheckResult:
    return InvestigationCheckResult(
        severity=severity,
        title=title,
        message=message,
        tab_name=tab_name,
        check_code=check_code,
        suggested_task_title=suggested_task_title,
        suggested_task_description=suggested_task_description,
    )


def _text(value) -> str:
    return str(value or "").strip()


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _has_photo_documentation(zajisteni: dict, casova_osa: dict | None = None) -> bool:
    fotky = zajisteni.get("fotky") or {}
    if any(_text(path) for path in fotky.values()):
        return True
    if zajisteni.get("nacrt_porizen"):
        return True
    if _parse_date(zajisteni.get("datum_fotek")):
        return True
    cas_sync = ((casova_osa or {}).get("cas_synchronizace") or {}) if isinstance(casova_osa, dict) else {}
    return _text(cas_sync.get("caszarizeni_fotodokumentace")) == "Pořízena"


def _check_spis(snapshot: dict) -> list[InvestigationCheckResult]:
    results: list[InvestigationCheckResult] = []
    lead_id = snapshot.get("lead_thp_worker_id")
    lead_name = _text(snapshot.get("lead_thp_worker_name"))
    status = _text(snapshot.get("status"))
    event_character = _text(snapshot.get("event_character"))
    source_type = _text(snapshot.get("source_type"))

    if lead_id or lead_name:
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Vedoucí vyšetřování",
                message="Vedoucí šetření je uveden.",
                tab_name="Spis",
                check_code="spis.lead_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí vedoucí vyšetřování",
                message="Ve spisu není vyplněn vedoucí šetření.",
                tab_name="Spis",
                check_code="spis.lead_missing",
                suggested_task_title="Doplnit vedoucího vyšetřování MU",
                suggested_task_description="Určit a zapsat vedoucího šetření do spisu MU.",
            )
        )

    if status:
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Stav šetření",
                message=f"Stav šetření je uveden ({status}).",
                tab_name="Spis",
                check_code="spis.status_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí stav šetření",
                message="Ve spisu není uveden stav vyšetřování.",
                tab_name="Spis",
                check_code="spis.status_missing",
            )
        )

    if not event_character:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí charakter události",
                message="Ve spisu není uveden charakter události.",
                tab_name="Spis",
                check_code="spis.event_character_missing",
            )
        )

    source_ok = False
    if source_type == SOURCE_TYPE_MANUAL:
        source_ok = bool(_text(snapshot.get("source_label")))
    elif source_type in (SOURCE_TYPE_ACCIDENT, SOURCE_TYPE_AUDIT, SOURCE_TYPE_CONTROL):
        source_ok = isinstance(snapshot.get("source_id"), int) and snapshot.get("source_id", 0) > 0
    else:
        source_ok = bool(source_type)

    if source_ok and event_character:
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Zdroj a charakter události",
                message="Zdroj podnětu a charakter události jsou uvedeny.",
                tab_name="Spis",
                check_code="spis.source_present",
            )
        )
    elif not source_ok:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí vazba zdroje",
                message="Ve spisu chybí zdroj podnětu nebo jeho vazba na záznam.",
                tab_name="Spis",
                check_code="spis.source_missing",
                suggested_task_title="Doplnit zdroj vyšetřování MU",
                suggested_task_description="Doplnit zdroj podnětu a propojení se zdrojovým záznamem.",
            )
        )

    return results


def _check_oznameni(snapshot: dict) -> list[InvestigationCheckResult]:
    oznameni = snapshot.get("oznameni") or {}
    results: list[InvestigationCheckResult] = []

    if oznameni.get("oznameni_datum"):
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Datum oznámení",
                message="Datum oznámení je vyplněno.",
                tab_name="Oznámení",
                check_code="oznameni.date_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí datum oznámení",
                message="Na kartě Oznámení chybí datum oznámení události.",
                tab_name="Oznámení",
                check_code="oznameni.date_missing",
                suggested_task_title="Doplnit datum oznámení MU",
                suggested_task_description="Doplnit datum oznámení události zaměstnavateli.",
            )
        )

    if _text(oznameni.get("oznameni_cas")):
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Čas oznámení",
                message="Čas oznámení je vyplněn.",
                tab_name="Oznámení",
                check_code="oznameni.time_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Chybí čas oznámení",
                message="Na kartě Oznámení chybí čas oznámení události.",
                tab_name="Oznámení",
                check_code="oznameni.time_missing",
                suggested_task_title="Doplnit čas oznámení MU",
                suggested_task_description="Doplnit čas oznámení události a ověřit návaznost v časové ose.",
            )
        )

    opatreni_keys = (
        "opatreni_prvni_pomoc",
        "opatreni_zzs",
        "opatreni_policie",
        "opatreni_hzs",
        "opatreni_zastavena_cinnost",
        "opatreni_zajisteno_misto",
        "opatreni_zabraneno_manipulaci",
        "opatreni_informovan_nadrizeny",
        "opatreni_informovan_bozp",
        "opatreni_informovany_dalsi",
    )
    if any(_text(oznameni.get(key)) == "ANO" for key in opatreni_keys):
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Okamžitá opatření",
                message="Alespoň jedno okamžité opatření je zaznamenáno.",
                tab_name="Oznámení",
                check_code="oznameni.measures_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_RECOMMENDATION,
                title="Okamžitá opatření nejsou vyplněna",
                message="Na kartě Oznámení není zaškrtnuto žádné okamžité opatření.",
                tab_name="Oznámení",
                check_code="oznameni.measures_missing",
                suggested_task_title="Doplnit okamžitá opatření po události",
                suggested_task_description="Projít průběh události a zaznamenat provedená okamžitá opatření.",
            )
        )

    return results


def _check_zajisteni(snapshot: dict) -> list[InvestigationCheckResult]:
    zajisteni = snapshot.get("zajisteni") or {}
    oznameni = snapshot.get("oznameni") or {}
    casova_osa = snapshot.get("casova_osa") or {}
    results: list[InvestigationCheckResult] = []

    site_secured = (
        _text(oznameni.get("opatreni_zajisteno_misto")) == "ANO"
        or _parse_date(zajisteni.get("datum")) is not None
        or bool(_text(zajisteni.get("presne_misto")))
    )
    if site_secured:
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Zajištění místa",
                message="Zajištění místa události je zaznamenáno.",
                tab_name="Zajištění důkazů",
                check_code="zajisteni.site_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí záznam o zajištění místa",
                message="Není zaznamenáno zajištění místa události ani v Oznámení, ani v Zajištění důkazů.",
                tab_name="Zajištění důkazů",
                check_code="zajisteni.site_missing",
                suggested_task_title="Doplnit zajištění místa události",
                suggested_task_description="Zaznamenat, kdo a kdy zajistil místo události a jaká opatření byla provedena.",
            )
        )

    if _has_photo_documentation(zajisteni, casova_osa):
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Fotodokumentace",
                message="Fotodokumentace je v spisu uvedena.",
                tab_name="Zajištění důkazů",
                check_code="zajisteni.photo_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Fotodokumentace není uvedena",
                message="Ve spisu není zaznamenáno, zda byla pořízena fotodokumentace.",
                tab_name="Zajištění důkazů",
                check_code="zajisteni.photo_missing",
                suggested_task_title="Prověřit fotodokumentaci místa události",
                suggested_task_description="Ověřit, zda byla pořízena fotodokumentace, a doplnit údaje v Zajištění důkazů.",
            )
        )

    if _has_photo_documentation(zajisteni, casova_osa) and _parse_date(zajisteni.get("datum_fotek")) and not _text(zajisteni.get("cas_fotek")):
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Chybí čas fotodokumentace",
                message="Fotodokumentace je uvedena, ale chybí čas pořízení.",
                tab_name="Zajištění důkazů",
                check_code="zajisteni.photo_time_missing",
                suggested_task_title="Doplnit čas fotodokumentace",
                suggested_task_description="Doplnit čas pořízení fotodokumentace a ověřit návaznost v časové ose.",
            )
        )

    if _text(oznameni.get("opatreni_policie")) == "ANO" or _text(oznameni.get("opatreni_hzs")) == "ANO":
        chronologie = (snapshot.get("casova_osa") or {}).get("chronologie") or []
        has_emergency_entry = any(
            "polic" in _text(entry.get("typ")).lower()
            or "hzs" in _text(entry.get("typ")).lower()
            or "hasič" in _text(entry.get("typ")).lower()
            or "zzs" in _text(entry.get("typ")).lower()
            for entry in chronologie
        )
        if not has_emergency_entry:
            results.append(
                _result(
                    CHECK_SEVERITY_RECOMMENDATION,
                    title="Přivolána složka IZS bez záznamu v časové ose",
                    message="V Oznámení je uvedena Policie nebo HZS, doporučuje se doplnit čas příjezdu nebo záznam do časové osy.",
                    tab_name="Zajištění důkazů",
                    check_code="zajisteni.emergency_timeline_missing",
                    suggested_task_title="Doplnit záznam příjezdu Policie/HZS",
                    suggested_task_description="Doplnit do časové osy čas příjezdu nebo další údaje o zásahu složky IZS.",
                )
            )

    return results


def _check_svedci(snapshot: dict) -> list[InvestigationCheckResult]:
    svedci = snapshot.get("svedci") or {}
    results: list[InvestigationCheckResult] = []
    witness_names = [_text(name) for name in (svedci.get("svedci") or []) if _text(name)]
    pocet = int(svedci.get("pocet_svedku") or 0)

    if pocet <= 0 and not witness_names:
        results.append(
            _result(
                CHECK_SEVERITY_RECOMMENDATION,
                title="Nejsou uvedeni svědci",
                message="Na kartě Svědci není uveden žádný svědek.",
                tab_name="Svědci",
                check_code="svedci.none",
                suggested_task_title="Prověřit a doplnit svědky události",
                suggested_task_description="Ověřit, zda existují svědci události, a doplnit jejich identifikaci do spisu.",
            )
        )
        return results

    results.append(
        _result(
            CHECK_SEVERITY_OK,
            title="Svědci uvedeni",
            message="Ve spisu jsou uvedeni svědci.",
            tab_name="Svědci",
            check_code="svedci.present",
        )
    )

    obsah = _text(svedci.get("obsah"))
    if not obsah and not svedci.get("vyjadreni_vracena"):
        label = witness_names[0] if witness_names else "svědka"
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Chybí vyjádření svědka",
                message=f"Svědek „{label}“ nemá doplněné vyjádření ani výslech.",
                tab_name="Svědci",
                check_code="svedci.statement_missing",
                suggested_task_title=f"Vyslechnout svědka {label}",
                suggested_task_description=(
                    f"Domluvit termín výslechu, ověřit dostupnost svědka a doplnit vyjádření do spisu MU."
                ),
            )
        )

    for index, name in enumerate(witness_names, start=1):
        if len(name.split()) < 2:
            results.append(
                _result(
                    CHECK_SEVERITY_RECOMMENDATION,
                    title="Neúplná identifikace svědka",
                    message=f"Svědek „{name}“ nemusí být dostatečně identifikován.",
                    tab_name="Svědci",
                    check_code=f"svedci.identity_{index}",
                    suggested_task_title=f"Doplnit identifikaci svědka {name}",
                    suggested_task_description="Doplnit jméno, pracovní zařazení nebo kontakt svědka.",
                )
            )

    return results


def _check_casova_osa(snapshot: dict) -> list[InvestigationCheckResult]:
    results: list[InvestigationCheckResult] = []
    oznameni = snapshot.get("oznameni") or {}
    zajisteni = snapshot.get("zajisteni") or {}
    casova_osa = snapshot.get("casova_osa") or {}

    system_events = build_system_chronologie_events(
        started_at=snapshot.get("started_at"),
        source_type=_text(snapshot.get("source_type")),
        source_id=snapshot.get("source_id"),
        oznameni_datum=oznameni.get("oznameni_datum"),
        oznameni_cas=_text(oznameni.get("oznameni_cas")),
    )
    manual_events = casova_osa.get("chronologie") or []
    if not system_events and not manual_events:
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Chybí základní události v časové ose",
                message="Časová osa neobsahuje systémové ani ručně zadané události.",
                tab_name="Časová osa",
                check_code="casova_osa.events_missing",
                suggested_task_title="Doplnit časovou osu vyšetřování",
                suggested_task_description="Doplnit klíčové události do časové osy MU.",
            )
        )

    reference_dt = datetime_from_date_and_time(snapshot.get("event_datum"), _text(snapshot.get("event_cas")))
    oznameni_dt = datetime_from_date_and_time(oznameni.get("oznameni_datum"), _text(oznameni.get("oznameni_cas")))
    zajisteni_dt = datetime_from_date_and_time(_parse_date(zajisteni.get("datum")), _text(zajisteni.get("cas")))
    foto_dt = datetime_from_date_and_time(_parse_date(zajisteni.get("datum_fotek")), _text(zajisteni.get("cas_fotek")))

    timeline_issues: list[str] = []
    for label, target_dt, pred_text in (
        ("Oznámení události", oznameni_dt, "Čas oznámení je před vznikem události."),
        ("Zajištění důkazů", zajisteni_dt, "Zajištění důkazů je před vznikem události."),
        ("Fotodokumentace", foto_dt, "Fotodokumentace je před vznikem události."),
    ):
        formatted = format_od_udalosti_rozdil(reference_dt, target_dt, pred_udalosti_text=pred_text)
        if formatted is not None and formatted[1] == "#c62828":
            timeline_issues.append(f"{label}: {formatted[0]}")

    if zajisteni_dt and foto_dt and foto_dt < zajisteni_dt:
        timeline_issues.append("Fotodokumentace byla pořízena před zajištěním důkazů.")

    if timeline_issues:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Problém v časové návaznosti",
                message=" ".join(timeline_issues),
                tab_name="Časová osa",
                check_code="casova_osa.sequence_error",
                suggested_task_title="Prověřit časovou návaznost událostí",
                suggested_task_description="Zkontrolovat datum a čas události, oznámení, zajištění důkazů a fotodokumentace.",
            )
        )
    elif reference_dt and (oznameni_dt or zajisteni_dt or foto_dt):
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Časová návaznost",
                message="Základní časová návaznost neobsahuje zjevný rozpor.",
                tab_name="Časová osa",
                check_code="casova_osa.sequence_ok",
            )
        )

    return results


def _check_ishikawa(snapshot: dict) -> list[InvestigationCheckResult]:
    causes: list[dict] = snapshot.get("causes") or []
    results: list[InvestigationCheckResult] = []

    if not causes:
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Nejsou zadány příčiny",
                message="V Ishikawa+ není zadána žádná příčina.",
                tab_name="Zjištění",
                check_code="ishikawa.none",
                suggested_task_title="Zpracovat analýzu příčin Ishikawa+",
                suggested_task_description="Doplnit příčiny události v Ishikawa+.",
            )
        )
        return results

    for cause in causes:
        status = _text(cause.get("status")).lower()
        if status and status not in ISHIKAWA_STATUSES:
            label = chain_cause_label(cause)
            results.append(
                _result(
                    CHECK_SEVERITY_WARNING,
                    title="Neplatný stav příčiny",
                    message=f"Příčina „{label}“ má neplatný nebo chybějící stav.",
                    tab_name="Zjištění",
                    check_code=f"ishikawa.status_{cause.get('id', '')}",
                )
            )
        elif not status:
            label = chain_cause_label(cause)
            results.append(
                _result(
                    CHECK_SEVERITY_WARNING,
                    title="Chybí stav příčiny",
                    message=f"Příčina „{label}“ nemá uveden stav.",
                    tab_name="Zjištění",
                    check_code=f"ishikawa.status_missing_{cause.get('id', '')}",
                )
            )

        if status == ISHIKAWA_STATUS_POTVRZENO and not _text(cause.get("evidence")):
            label = chain_cause_label(cause)
            results.append(
                _result(
                    CHECK_SEVERITY_WARNING,
                    title="Potvrzená příčina bez důkazů",
                    message=f"Příčina „{label}“ je potvrzena, ale chybí popis důkazů.",
                    tab_name="Zjištění",
                    check_code=f"ishikawa.evidence_{cause.get('id', '')}",
                    suggested_task_title=f"Doplnit důkazy k příčině {label}",
                    suggested_task_description="Doplnit důkazní materiál nebo popis důkazů u potvrzené příčiny.",
                )
            )

    for warning in build_rejected_cause_chain_warnings(causes):
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Navazující příčina na vyvrácené",
                message=warning,
                tab_name="Zjištění",
                check_code="ishikawa.rejected_chain",
            )
        )

    findings = snapshot.get("findings") or []
    for cause in causes:
        if _text(cause.get("status")) != ISHIKAWA_STATUS_POTVRZENO:
            continue
        if _text(cause.get("cause_level")) not in (ISHIKAWA_LEVEL_ZAKLADNI, ISHIKAWA_LEVEL_SYSTEMOVA):
            continue
        label = chain_cause_label(cause)
        if not findings:
            results.append(
                _result(
                    CHECK_SEVERITY_RECOMMENDATION,
                    title="Kořenová příčina bez zjištění",
                    message=f"Potvrzená příčina „{label}“ nemá navázané zjištění ani opatření.",
                    tab_name="Zjištění",
                    check_code=f"ishikawa.root_no_finding_{cause.get('id', '')}",
                    suggested_task_title=f"Vytvořit zjištění k příčině {label}",
                    suggested_task_description="Z potvrzené kořenové příčiny vytvořit zjištění a navrhnout opatření.",
                )
            )

    return results


def _check_findings(snapshot: dict) -> list[InvestigationCheckResult]:
    findings = snapshot.get("findings") or []
    results: list[InvestigationCheckResult] = []
    investigation_id = snapshot.get("investigation_id")

    if investigation_id is None:
        results.append(
            _result(
                CHECK_SEVERITY_RECOMMENDATION,
                title="Spis není uložen",
                message="Zjištění a navázaná opatření lze plně kontrolovat až po uložení vyšetřování.",
                tab_name="Zjištění",
                check_code="findings.unsaved",
            )
        )
        return results

    if not findings:
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Nejsou vytvořena zjištění",
                message="Vyšetřování neobsahuje žádné zjištění.",
                tab_name="Zjištění",
                check_code="findings.none",
                suggested_task_title="Vytvořit zjištění z vyšetřování MU",
                suggested_task_description="Zpracovat zjištění z analýzy příčin a dalších zdrojů.",
            )
        )
        return results

    results.append(
        _result(
            CHECK_SEVERITY_OK,
            title="Zjištění existují",
            message=f"Ve spisu je {len(findings)} zjištění.",
            tab_name="Zjištění",
            check_code="findings.present",
        )
    )

    for finding in findings:
        finding_id = getattr(finding, "id", None)
        reference = _text(getattr(finding, "reference_label", "")) or f"ID {finding_id}"
        if not getattr(finding, "task_id", None):
            results.append(
                _result(
                    CHECK_SEVERITY_RECOMMENDATION,
                    title="Zjištění bez navázaného úkolu",
                    message=f"Zjištění „{reference}“ nemá navázané opatření / úkol.",
                    tab_name="Zjištění",
                    check_code=f"findings.task_missing_{finding_id}",
                    suggested_task_title=f"Vytvořit úkol k zjištění {reference}",
                    suggested_task_description="Navázat na zjištění nápravné opatření nebo úkol.",
                )
            )

        if not _text(getattr(finding, "responsible_person_name", "")) and not getattr(
            finding, "responsible_person_id", None
        ):
            results.append(
                _result(
                    CHECK_SEVERITY_WARNING,
                    title="Opatření bez odpovědné osoby",
                    message=f"U zjištění „{reference}“ chybí odpovědná osoba.",
                    tab_name="Zjištění",
                    check_code=f"findings.responsible_missing_{finding_id}",
                    suggested_task_title=f"Určit odpovědnou osobu k zjištění {reference}",
                    suggested_task_description="Doplnit odpovědnou osobu pro realizaci opatření.",
                )
            )

        if getattr(finding, "due_date", None) is None:
            results.append(
                _result(
                    CHECK_SEVERITY_WARNING,
                    title="Opatření bez termínu",
                    message=f"U zjištění „{reference}“ chybí termín splnění.",
                    tab_name="Zjištění",
                    check_code=f"findings.due_missing_{finding_id}",
                    suggested_task_title=f"Stanovit termín opatření {reference}",
                    suggested_task_description="Doplnit termín pro realizaci opatření.",
                )
            )

    return results


def _check_zaver(snapshot: dict) -> list[InvestigationCheckResult]:
    zaver = snapshot.get("zaver") or {}
    results: list[InvestigationCheckResult] = []
    conclusion = _text(snapshot.get("conclusion"))

    if conclusion:
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Závěr vyšetřování",
                message="Závěrečné shrnutí je vyplněno.",
                tab_name="Závěr",
                check_code="zaver.conclusion_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_ERROR,
                title="Chybí závěr vyšetřování",
                message="Na kartě Závěr chybí závěrečné shrnutí vyšetřování.",
                tab_name="Závěr",
                check_code="zaver.conclusion_missing",
                suggested_task_title="Doplnit závěr vyšetřování MU",
                suggested_task_description="Sepsat závěrečné shrnutí vyšetřování mimořádné události.",
            )
        )

    if _text(zaver.get("vysledek_hlavni_priciny")):
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Shrnutí příčin",
                message="Hlavní příčiny jsou ve Závěru uvedeny.",
                tab_name="Závěr",
                check_code="zaver.causes_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_WARNING,
                title="Chybí shrnutí příčin",
                message="Ve Závěru chybí shrnutí hlavních příčin.",
                tab_name="Závěr",
                check_code="zaver.causes_missing",
                suggested_task_title="Doplnit shrnutí hlavních příčin",
                suggested_task_description="Doplnit hlavní příčiny do závěru vyšetřování.",
            )
        )

    findings = snapshot.get("findings") or []
    if findings:
        results.append(
            _result(
                CHECK_SEVERITY_OK,
                title="Preventivní opatření",
                message="Ve spisu existují zjištění, ze kterých lze odvodit nápravná opatření.",
                tab_name="Závěr",
                check_code="zaver.measures_present",
            )
        )
    else:
        results.append(
            _result(
                CHECK_SEVERITY_RECOMMENDATION,
                title="Chybí návrh preventivních opatření",
                message="Ve spisu zatím nejsou zjištění, ze kterých by šlo odvodit preventivní opatření.",
                tab_name="Závěr",
                check_code="zaver.measures_missing",
                suggested_task_title="Navrhnout preventivní opatření",
                suggested_task_description="Na základě analýzy příčin navrhnout preventivní opatření.",
            )
        )

    return results


def _check_closed_with_errors(
    snapshot: dict,
    existing_results: list[InvestigationCheckResult],
) -> list[InvestigationCheckResult]:
    if _text(snapshot.get("status")) != MU_STATUS_DOKONCENO:
        return []

    issues = [
        item
        for item in existing_results
        if item.severity in (CHECK_SEVERITY_ERROR, CHECK_SEVERITY_WARNING)
    ]
    if not issues:
        return []

    return [
        _result(
            CHECK_SEVERITY_ERROR,
            title="Spis je uzavřen, ale obsahuje nedostatky",
            message=f"Vyšetřování je ve stavu Dokončeno, ale kontrola našla {len(issues)} problém(ů).",
            tab_name="Závěr",
            check_code="zaver.closed_with_issues",
            suggested_task_title="Prověřit nedostatky před uzavřením spisu",
            suggested_task_description="Projít kontrolní nálezy a doplnit chybějící části spisu.",
        )
    ]

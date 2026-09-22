"""Generování dokumentu Pravidla bezpečné práce (PBP).

PBP-2: sběr platných (realizovaných) opatření z Registru rizik.
PBP-3: export do ODT podle šablony.
PBP-4: normalizace textů a kontrola vhodnosti pro zaměstnance.
PBP-4b: řazení podle závažnosti rizika.
PBP-5a: evidence vydání (snapshot) po úspěšném exportu.
PBP-5b: porovnání s předchozím vydáním před uložením.
PBP-5c: generování pro profesi (sjednocení ohrožených skupin).
PBP-5d: zobrazení změn v ODT dokumentu.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from core.export import OdtExportEngine, open_export_file
from core.export.odt_engine import _sync_written_file
from core.services.storage_service import storage_service
from core.utils.czech_sort import czech_sort_key
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
)
from moduly.rizeni_rizik.sluzby.existing_measure_relevance import refs_match_targets
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    SOURCE_TYPE_HAZARD_GROUP,
    SOURCE_TYPE_ROLE,
    effective_target_refs,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.sluzby.profession_service import profession_service

# Infinitivy / formulace typu „zajistit…“ – nevhodné jako přímé pokyny zaměstnanci.
_UNSUITABLE_EMPLOYEE_PREFIXES = (
    "zajistit",
    "provést",
    "kontrolovat",
    "zabezpečit",
    "ověřit",
    "dodržování",
    "není potřeba",
    "není nutné",
    "bez opatření",
)

_UNSUITABLE_PHRASES = (
    "není potřeba opatření",
    "není potřeba žádných opatření",
    "není potřeba žádné opatření",
    "není nutné opatření",
    "není nutné žádné opatření",
    "bez opatření",
    "riziko je zřejmé",
    "riziko je zrejme",
    "zřejmé riziko",
    "zrejme riziko",
    "není potřeba dalších opatření",
    "není nutná žádná opatření",
)

# Imperativy / 2. osoba – typické pokyny pro zaměstnance (kladné i záporné).
_IMPERATIVE_STEMS = (
    "používej",
    "používejte",
    "použij",
    "použijte",
    "dodržuj",
    "dodržujte",
    "oznam",
    "oznamuj",
    "oznamujte",
    "oznamte",
    "přeruš",
    "přerušte",
    "přerušuj",
    "přerušujte",
    "ukonč",
    "ukončete",
    "ukonči",
    "ukončuj",
    "ukončujte",
    "vstupuj",
    "vstupujte",
    "vstoup",
    "vstupte",
    "prováděj",
    "provádějte",
    "odstraňuj",
    "odstraňujte",
    "podléhej",
    "podléhejte",
    "nastupuj",
    "nastupujte",
    "noste",
    "nos",
    "zkontroluj",
    "zkontrolujte",
    "kontroluj",
    "kontrolujte",
    "vypni",
    "vypněte",
    "zapni",
    "zapněte",
    "odpoj",
    "odpojte",
    "připoj",
    "připojte",
    "ohlás",
    "ohlaste",
    "ohláš",
    "ujisti",
    "ujistěte",
    "přesvědči",
    "přesvědčete",
)

# Jmenné začátky bez slovesného pokynu (např. „Kontrola stavu…“, „Evidence závad.“).
_UNSUITABLE_NOUN_STARTERS = (
    "kontrola",
    "evidence",
    "provádění",
    "zajištění",
    "poučení",
    "používání",
    "dodržování",
    "umístění",
)

# Imperativy / 2. osoba – typické pokyny pro zaměstnance.
_EMPLOYEE_VERB_RE = re.compile(
    r"\b(" + "|".join(re.escape(stem) for stem in _IMPERATIVE_STEMS) + r")\w*\b",
    re.IGNORECASE,
)

# Česká slovesná jména (dějová podstatná): poučení, používání, umístění…
_VERBAL_NOUN_RE = re.compile(
    r"\b\w*(ání|ení|ění|ití|utí|nutí)\b",
    re.IGNORECASE,
)

_TRAILING_END_PUNCT_RE = re.compile(r"[.!?…]+$")

_EMPTY_INFO_ROW_RE = re.compile(
    r"<table:table-row>\s*"
    r"<table:table-cell[^>]*>\s*<text:p[^>]*>(?P<label>Pracoviště|Část pracoviště)</text:p>\s*</table:table-cell>\s*"
    r"<table:table-cell[^>]*>\s*<text:p[^>]*>\s*</text:p>\s*</table:table-cell>\s*"
    r"</table:table-row>",
    re.DOTALL,
)

_EMPTY_ZMENY_PARAGRAPH_RE = re.compile(
    r"<text:p[^>]*>\s*</text:p>\s*"
    r"(?=<text:p[^>]*>DODRŽUJTE TATO PRAVIDLA</text:p>)",
)



def normalize_rule_text(text: str) -> str:
    """Normalizuje každý řádek zvlášť a zachová zalomení (RISK-RULES-1b).

    Enter (``\\n`` / ``\\r\\n`` / ``\\r``) zůstává hranicí mezi samostatnými
    pravidly. Prázdné řádky se vynechají. Každý neprázdný řádek dostane
    sjednocené mezery a jednu tečku na konci.
    """
    if not text:
        return ""

    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        collapsed = " ".join(raw_line.split())
        if not collapsed:
            continue
        collapsed = _TRAILING_END_PUNCT_RE.sub("", collapsed).rstrip()
        if collapsed:
            lines.append(f"{collapsed}.")

    return "\n".join(lines)


def _first_word(lowered: str) -> str:
    body = _TRAILING_END_PUNCT_RE.sub("", lowered).strip()
    if not body:
        return ""
    return body.split()[0]


def _starts_with_employee_imperative(lowered: str) -> bool:
    """True, pokud věta začíná kladným nebo záporným rozkazovacím způsobem."""
    first = _first_word(lowered)
    if not first:
        return False

    if first.startswith("ne") and len(first) > 2:
        without_ne = first[2:]
        for stem in _IMPERATIVE_STEMS:
            if without_ne.startswith(stem.casefold()):
                return True

    for stem in _IMPERATIVE_STEMS:
        if first.startswith(stem.casefold()):
            return True
    return False


def _starts_with_unsuitable_noun_form(lowered: str) -> bool:
    """True, pokud věta začíná jmennou / slovesnou jmennou formulací."""
    first = _first_word(lowered)
    if not first:
        return False
    if first in _UNSUITABLE_NOUN_STARTERS:
        return True
    return bool(_VERBAL_NOUN_RE.search(first))


def is_unsuitable_employee_rule(text: str) -> bool:
    """True, pokud text není vhodně formulován jako pravidlo pro zaměstnance."""
    lowered = (text or "").casefold().lstrip()
    if not lowered:
        return False

    for phrase in _UNSUITABLE_PHRASES:
        if phrase.casefold() in lowered:
            return True

    for prefix in _UNSUITABLE_EMPLOYEE_PREFIXES:
        needle = prefix.casefold()
        if not lowered.startswith(needle):
            continue
        rest = lowered[len(needle) :]
        if not rest or not rest[0].isalnum():
            return True

    if _starts_with_employee_imperative(lowered):
        return False

    if _starts_with_unsuitable_noun_form(lowered):
        return True

    if _is_short_noun_phrase_without_verb(lowered):
        return True
    return False


UNSUITABLE_EMPLOYEE_RULE_REASON = (
    "Formulace není vhodná jako pravidlo bezpečné práce pro zaměstnance."
)


def unsuitable_employee_rule_reason(text: str) -> str:
    """Důvod nevhodnosti – bez změny detekčních pravidel."""
    if not is_unsuitable_employee_rule(text):
        return ""
    return UNSUITABLE_EMPLOYEE_RULE_REASON


def rule_text_is_unsuitable(text: str) -> bool:
    """Stejná logika jako při generování: jakýkoli nevhodný řádek → True."""
    normalized = normalize_rule_text(text)
    if not normalized:
        return False
    return any(
        is_unsuitable_employee_rule(line)
        for line in normalized.split("\n")
        if line.strip()
    )


def severity_rank(severity: str | None) -> int:
    """Pořadí závažnosti z Registru rizik: vyšší číslo = vyšší závažnost."""
    code = severity or DEFAULT_RISK_SEVERITY
    try:
        return RISK_SEVERITIES.index(code)
    except ValueError:
        return -1


def _is_short_noun_phrase_without_verb(lowered: str) -> bool:
    """Detekuje krátké jmenné fráze bez slovesného pokynu (např. „Poučení obsluhy.“)."""
    if _starts_with_employee_imperative(lowered):
        return False
    body = _TRAILING_END_PUNCT_RE.sub("", lowered).strip()
    words = body.split()
    if len(words) < 2 or len(words) > 10:
        return False
    if _EMPLOYEE_VERB_RE.search(body):
        return False
    return bool(_VERBAL_NOUN_RE.search(body))


@dataclass(frozen=True)
class PravidloBezpecnePraceSource:
    """Jedna zdrojová vazba pravidla na posouzení / opatření."""

    measure_id: int
    source_hazard_id: int | None = None
    source_event_id: int | None = None
    severity: str = DEFAULT_RISK_SEVERITY


@dataclass(frozen=True)
class PravidloBezpecnePrace:
    """Jedno pravidlo bezpečné práce odvozené z existujícího opatření."""

    measure_id: int
    text: str
    source_hazard_id: int | None = None
    source_event_id: int | None = None
    unsuitable_for_employee: bool = False
    severity: str = DEFAULT_RISK_SEVERITY
    severity_rank: int = 0
    sources: tuple[PravidloBezpecnePraceSource, ...] = ()


class PravidlaBezpecnePraceService:
    """Služba pro sestavení a export Pravidel bezpečné práce."""

    TEMPLATE_NAME = "PravidlaBezpecnePrace.odt"
    TEMPLATE_SUBDIR = "exporty"
    EXPORT_SUBDIR = "pravidla_bezpecne_prace"

    def __init__(self) -> None:
        self.engine = OdtExportEngine()
        self.last_comparison = None

    def template_path(self) -> Path:
        storage_service.ensure_structure()
        return storage_service.resolve_editable_template(
            self.TEMPLATE_SUBDIR,
            self.TEMPLATE_NAME,
        )

    def generate(
        self,
        endangered_group_id: int | None = None,
        operation_id: int | None = None,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        *,
        profession_id: int | None = None,
        role_ids: list[int] | tuple[int, ...] | None = None,
        endangered_group_ids: list[int] | tuple[int, ...] | None = None,
    ) -> list[PravidloBezpecnePrace]:
        """Vrátí platná pravidla pro vybrané cíle a rozsah pracoviště.

        Platná = aktivní **existující** opatření (realizovaná).
        Potřebná další / neaktivní opatření se nezahrnují.
        Texty se normalizují; nevhodné formulace zůstávají ve výsledku
        a mají ``unsuitable_for_employee=True``.

        Cíle mohou být kombinací:
        - rolí/profesí (vazby typu ``role`` v posouzení),
        - ohrožených skupin (vazby typu ``hazard_group``),
        - legacy ``profession_id`` (rozvine se na přiřazené skupiny).
        """
        if operation_id is None:
            raise ValueError("operation_id je povinný.")
        if workplace_id is None:
            workplace_part_id = None

        resolved_role_ids, resolved_group_ids = self._resolve_target_ids(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
            role_ids=role_ids,
            endangered_group_ids=endangered_group_ids,
        )
        if not resolved_role_ids and not resolved_group_ids:
            raise ValueError(
                "Je nutné zadat alespoň jednu roli, ohroženou skupinu nebo profesi."
            )

        return self._generate_for_targets(
            role_ids=resolved_role_ids,
            group_ids=resolved_group_ids,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

    @staticmethod
    def _resolve_target_ids(
        *,
        endangered_group_id: int | None,
        profession_id: int | None,
        role_ids: list[int] | tuple[int, ...] | None,
        endangered_group_ids: list[int] | tuple[int, ...] | None,
    ) -> tuple[list[int], list[int]]:
        roles: list[int] = []
        seen_roles: set[int] = set()
        for role_id in role_ids or ():
            value = int(role_id)
            if value in seen_roles:
                continue
            seen_roles.add(value)
            roles.append(value)

        groups: list[int] = []
        seen_groups: set[int] = set()

        def _add_group(group_id: int | None) -> None:
            if group_id is None:
                return
            value = int(group_id)
            if value in seen_groups:
                return
            seen_groups.add(value)
            groups.append(value)

        for group_id in endangered_group_ids or ():
            _add_group(group_id)
        _add_group(endangered_group_id)

        if profession_id is not None:
            for group_id in profession_service.get_active_exposed_group_ids(profession_id):
                _add_group(group_id)

        return roles, groups

    def _generate_for_targets(
        self,
        *,
        role_ids: list[int],
        group_ids: list[int],
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> list[PravidloBezpecnePrace]:
        target_roles = set(role_ids)
        target_groups = set(group_ids)
        collected: list[PravidloBezpecnePrace] = []
        for identification in hazard_identification_service.get_all(
            include_inactive=False
        ):
            if not self._identification_in_scope(
                identification,
                operation_id=operation_id,
                workplace_id=workplace_id,
                workplace_part_id=workplace_part_id,
            ):
                continue

            for row in hazard_risk_assessment_service.get_for_identification(
                identification.id,
                include_inactive=False,
            ):
                if not self._assessment_matches_targets(
                    row.assessment.id,
                    role_ids=target_roles,
                    group_ids=target_groups,
                    legacy_exposed_group_id=row.assessment.exposed_group_id,
                ):
                    continue

                measures = hazard_existing_measure_service.get_for_assessment(
                    row.assessment.id,
                    include_inactive=False,
                )
                refs_by_measure = (
                    hazard_existing_measure_service.relevance_repository.list_refs_for_measures(
                        [measure.id for measure in measures],
                    )
                )
                for measure in measures:
                    if not refs_match_targets(
                        refs_by_measure.get(measure.id, []),
                        role_ids=target_roles,
                        group_ids=target_groups,
                    ):
                        continue
                    text = normalize_rule_text(measure.description or "")
                    if not text:
                        continue
                    severity = row.assessment.severity or DEFAULT_RISK_SEVERITY
                    if severity not in RISK_SEVERITIES:
                        severity = DEFAULT_RISK_SEVERITY
                    rank = severity_rank(severity)
                    source = PravidloBezpecnePraceSource(
                        measure_id=measure.id,
                        source_hazard_id=identification.id,
                        source_event_id=row.assessment.hazard_event_id,
                        severity=severity,
                    )
                    unsuitable = any(
                        is_unsuitable_employee_rule(line)
                        for line in text.replace("\r\n", "\n")
                        .replace("\r", "\n")
                        .split("\n")
                        if line.strip()
                    )
                    collected.append(
                        PravidloBezpecnePrace(
                            measure_id=measure.id,
                            text=text,
                            source_hazard_id=identification.id,
                            source_event_id=row.assessment.hazard_event_id,
                            unsuitable_for_employee=unsuitable,
                            severity=severity,
                            severity_rank=rank,
                            sources=(source,),
                        )
                    )

        collected.sort(key=lambda item: item.measure_id)
        return self._dedupe_and_sort(collected)

    def _generate_for_groups(
        self,
        *,
        group_ids: list[int],
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> list[PravidloBezpecnePrace]:
        """Zpětná kompatibilita – generování jen podle ohrožených skupin."""
        return self._generate_for_targets(
            role_ids=[],
            group_ids=group_ids,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

    def quality_warnings(
        self,
        rules: list[PravidloBezpecnePrace],
        *,
        include_approved: bool = False,
    ) -> list[PravidloBezpecnePrace]:
        """Vrátí pravidla označená jako nevhodně formulovaná pro zaměstnance.

        Platná uživatelská schválení (stejné znění + stejné validační pravidlo)
        se ve výchozím režimu vynechají.
        """
        from moduly.rizeni_rizik.sluzby.pbp_validation_approval_service import (
            pbp_validation_approval_service,
        )

        result: list[PravidloBezpecnePrace] = []
        for rule in rules:
            if not rule.unsuitable_for_employee:
                continue
            if pbp_validation_approval_service.is_rule_approved(rule):
                if include_approved:
                    result.append(rule)
                continue
            result.append(rule)
        return result

    def apply_rule_text(
        self,
        rule: PravidloBezpecnePrace,
        new_text: str,
    ) -> PravidloBezpecnePrace:
        """Přepíše popis zdrojových opatření a vrátí aktualizované pravidlo."""
        from dataclasses import replace

        normalized = normalize_rule_text(new_text)
        if not normalized:
            raise ValueError("Text pravidla nesmí být prázdný.")

        measure_ids = [int(source.measure_id) for source in rule.sources]
        if not measure_ids:
            measure_ids = [int(rule.measure_id)]

        for measure_id in measure_ids:
            measure = hazard_existing_measure_service.get_by_id(measure_id)
            if measure is None:
                raise ValueError(f"Opatření #{measure_id} nebylo nalezeno.")
            identification_id = rule.source_hazard_id
            for source in rule.sources:
                if int(source.measure_id) == measure_id and source.source_hazard_id:
                    identification_id = source.source_hazard_id
                    break
            if identification_id is None:
                from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
                    hazard_inventory_item_service,
                )

                assessment = hazard_risk_assessment_service.get_by_id(
                    int(measure.hazard_risk_assessment_id)
                )
                if assessment is None:
                    raise ValueError(
                        f"Posouzení pro opatření #{measure_id} nebylo nalezeno."
                    )
                event = hazard_event_service.get_by_id(assessment.hazard_event_id)
                if event is None:
                    raise ValueError(
                        f"Událost pro opatření #{measure_id} nebyla nalezena."
                    )
                inventory_item = hazard_inventory_item_service.get_by_id(
                    event.inventory_item_id
                )
                if inventory_item is None:
                    raise ValueError(
                        f"Zdroj rizika pro opatření #{measure_id} nebyl nalezen."
                    )
                identification_id = inventory_item.hazard_identification_id
            hazard_existing_measure_service.update_measure(
                measure_id,
                hazard_identification_id=int(identification_id),
                hazard_risk_assessment_id=int(measure.hazard_risk_assessment_id),
                description=normalized,
                note=measure.note or "",
                active=bool(measure.active),
            )

        return replace(
            rule,
            text=normalized,
            unsuitable_for_employee=rule_text_is_unsuitable(normalized),
        )

    def export_document(
        self,
        *,
        operation_id: int,
        endangered_group_id: int | None = None,
        profession_id: int | None = None,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        rules: list[PravidloBezpecnePrace] | None = None,
        issued_at: date | datetime | None = None,
        role_ids: list[int] | tuple[int, ...] | None = None,
        endangered_group_ids: list[int] | tuple[int, ...] | None = None,
    ) -> Path | None:
        """Vytvoří ODT dokument. Při prázdném seznamu pravidel nic nevytváří."""
        if workplace_id is None:
            workplace_part_id = None

        resolved_role_ids, resolved_group_ids = self._resolve_target_ids(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
            role_ids=role_ids,
            endangered_group_ids=endangered_group_ids,
        )

        if rules is None:
            rules = self.generate(
                endangered_group_id=endangered_group_id,
                profession_id=profession_id,
                role_ids=role_ids,
                endangered_group_ids=endangered_group_ids,
                operation_id=operation_id,
                workplace_id=workplace_id,
                workplace_part_id=workplace_part_id,
            )
        if not rules:
            self.last_comparison = None
            return None

        template = self.template_path()
        if not template.exists():
            raise FileNotFoundError(
                f"Šablona Pravidel bezpečné práce nebyla nalezena: {template}"
            )

        from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
            pravidla_bezpecne_prace_edition_service,
        )

        edition_group_id, edition_profession_id = self._edition_scope_ids(
            profession_id=profession_id,
            role_ids=resolved_role_ids,
            group_ids=resolved_group_ids,
            endangered_group_id=endangered_group_id,
        )

        if edition_group_id is not None or edition_profession_id is not None:
            self.last_comparison = (
                pravidla_bezpecne_prace_edition_service.compare_to_latest(
                    endangered_group_id=edition_group_id,
                    profession_id=edition_profession_id,
                    operation_id=operation_id,
                    workplace_id=workplace_id,
                    workplace_part_id=workplace_part_id,
                    rules=rules,
                )
            )
        else:
            self.last_comparison = None

        values = self._placeholder_values(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
            role_ids=resolved_role_ids,
            group_ids=resolved_group_ids,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            rules=rules,
            issued_at=issued_at or date.today(),
        )
        output_path = storage_service.export_file(
            self.EXPORT_SUBDIR,
            self._output_filename(
                endangered_group_id=endangered_group_id,
                profession_id=profession_id,
                role_ids=resolved_role_ids,
                group_ids=resolved_group_ids,
                operation_id=operation_id,
            ),
        )
        rendered = self.engine.render(template, output_path, values)
        self._strip_empty_workplace_rows(rendered)
        self._strip_empty_change_section_paragraph(rendered)
        self._ensure_rules_heading(rendered)

        issued_dt: datetime
        if issued_at is None:
            issued_dt = datetime.now()
        elif isinstance(issued_at, datetime):
            issued_dt = issued_at
        else:
            issued_dt = datetime.combine(issued_at, datetime.min.time())

        if edition_group_id is not None or edition_profession_id is not None:
            pravidla_bezpecne_prace_edition_service.record_edition(
                endangered_group_id=edition_group_id,
                profession_id=edition_profession_id,
                operation_id=operation_id,
                workplace_id=workplace_id,
                workplace_part_id=workplace_part_id,
                rules=rules,
                export_path=rendered,
                issued_at=issued_dt,
            )
        return rendered

    @staticmethod
    def _edition_scope_ids(
        *,
        profession_id: int | None,
        role_ids: list[int],
        group_ids: list[int],
        endangered_group_id: int | None,
    ) -> tuple[int | None, int | None]:
        """Evidence vydání jen pro jednoznačný legacy rozsah (1 skupina / 1 profese)."""
        if profession_id is not None and not role_ids:
            return None, profession_id
        if not role_ids and len(group_ids) == 1:
            return group_ids[0], None
        if (
            not role_ids
            and not group_ids
            and endangered_group_id is not None
        ):
            return endangered_group_id, None
        return None, None

    @staticmethod
    def _strip_empty_workplace_rows(odt_path: Path) -> None:
        """Odstraní řádky Pracoviště / Část pracoviště s prázdnou hodnotou."""
        PravidlaBezpecnePraceService._rewrite_odt_content(
            odt_path,
            lambda content_xml: _EMPTY_INFO_ROW_RE.sub("", content_xml),
        )

    @staticmethod
    def _strip_empty_change_section_paragraph(odt_path: Path) -> None:
        """Odstraní prázdný odstavec změnových sekcí před DODRŽUJTE TATO PRAVIDLA."""
        PravidlaBezpecnePraceService._rewrite_odt_content(
            odt_path,
            lambda content_xml: _EMPTY_ZMENY_PARAGRAPH_RE.sub("", content_xml),
        )

    @staticmethod
    def _ensure_rules_heading(odt_path: Path) -> None:
        """Sjednotí nadpis sekce pravidel na DODRŽUJTE TATO PRAVIDLA."""
        PravidlaBezpecnePraceService._rewrite_odt_content(
            odt_path,
            lambda content_xml: content_xml.replace(
                "PLATNÁ PRAVIDLA BEZPEČNÉ PRÁCE",
                "DODRŽUJTE TATO PRAVIDLA",
            ),
        )

    @staticmethod
    def _rewrite_odt_content(odt_path: Path, transform) -> None:
        with zipfile.ZipFile(odt_path, "r") as zin:
            entries = {
                info.filename: (info, zin.read(info.filename)) for info in zin.infolist()
            }

        content_info, content_data = entries["content.xml"]
        content_xml = content_data.decode("utf-8")
        cleaned = transform(content_xml)
        if cleaned == content_xml:
            return

        entries["content.xml"] = (content_info, cleaned.encode("utf-8"))
        tmp_path = odt_path.with_suffix(odt_path.suffix + ".tmp")
        with zipfile.ZipFile(tmp_path, "w") as zout:
            for filename, (info, data) in entries.items():
                new_item = zipfile.ZipInfo(filename=filename, date_time=info.date_time)
                new_item.compress_type = info.compress_type
                new_item.comment = info.comment
                new_item.extra = info.extra
                new_item.internal_attr = info.internal_attr
                new_item.external_attr = info.external_attr
                zout.writestr(new_item, data)
        tmp_path.replace(odt_path)
        _sync_written_file(odt_path)

    def open_document(
        self,
        *,
        operation_id: int,
        endangered_group_id: int | None = None,
        profession_id: int | None = None,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        rules: list[PravidloBezpecnePrace] | None = None,
        role_ids: list[int] | tuple[int, ...] | None = None,
        endangered_group_ids: list[int] | tuple[int, ...] | None = None,
    ) -> Path | None:
        path = self.export_document(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
            role_ids=role_ids,
            endangered_group_ids=endangered_group_ids,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            rules=rules,
        )
        if path is None:
            return None
        open_export_file(path, title="Pravidla bezpečné práce")
        return path

    def _placeholder_values(
        self,
        *,
        endangered_group_id: int | None,
        profession_id: int | None,
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
        rules: list[PravidloBezpecnePrace],
        issued_at: date | datetime,
        role_ids: list[int] | None = None,
        group_ids: list[int] | None = None,
    ) -> dict[str, object]:
        rozsah_label, rozsah_nazev = self._format_scope_label(
            profession_id=profession_id,
            endangered_group_id=endangered_group_id,
            role_ids=role_ids or [],
            group_ids=group_ids or [],
        )
        comparison = self.last_comparison
        from core.export.odt_engine import OdtParagraph, OdtRichContent
        from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_document_format import (
            format_bullet_valid_rules,
            format_change_sections,
        )

        bullet_lines = format_bullet_valid_rules(rules, comparison)
        platna_pravidla_text: object
        if bullet_lines:
            platna_pravidla_text = OdtRichContent(
                paragraphs=[
                    OdtParagraph.text(line, style="PbpRuleBullet")
                    for line in bullet_lines
                ]
            )
        else:
            platna_pravidla_text = ""

        return {
            "rozsah_label": rozsah_label,
            "ohrozena_skupina": rozsah_nazev,
            "provoz": self._workplace_name(operation_id),
            "pracoviste": self._workplace_name(workplace_id),
            "cast_pracoviste": self._workplace_name(workplace_part_id),
            "datum_vydani": self._fmt_date(issued_at),
            "zmeny_text": format_change_sections(
                comparison,
                current_issued_at=issued_at,
                date_formatter=self._fmt_date,
            ),
            "platna_pravidla_text": platna_pravidla_text,
        }

    @staticmethod
    def _format_scope_label(
        *,
        profession_id: int | None,
        endangered_group_id: int | None,
        role_ids: list[int],
        group_ids: list[int],
    ) -> tuple[str, str]:
        # Legacy číselník profesí (PBP-5c): vždy zobrazit název profese,
        # i když se interně rozvine na více ohrožených skupin.
        if profession_id is not None and not role_ids:
            return "Profese", profession_service.display_name(profession_id)

        role_names = [
            responsibility_role_service.display_name(role_id) or f"#{role_id}"
            for role_id in role_ids
        ]
        group_names = [
            exposed_group_service.display_name(group_id) or f"#{group_id}"
            for group_id in group_ids
        ]
        if not role_names and not group_names and endangered_group_id is not None:
            return (
                "Ohrožená skupina",
                exposed_group_service.display_name(endangered_group_id),
            )
        if role_names and not group_names:
            return "Profese", ", ".join(role_names)
        if group_names and not role_names:
            # RISK-RULES-1a: i samotné ohrožené skupiny mají popisek „Profese“.
            return "Profese", ", ".join(group_names)
        parts = []
        if role_names:
            parts.append(", ".join(role_names))
        if group_names:
            parts.append(", ".join(group_names))
        return "Profese", "; ".join(parts)

    @staticmethod
    def _workplace_name(workplace_id: int | None) -> str:
        if workplace_id is None:
            return ""
        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            return ""
        return (workplace.name or "").strip()

    @staticmethod
    def _fmt_date(value: date | datetime) -> str:
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        return value.strftime("%d.%m.%Y")

    @staticmethod
    def _output_filename(
        *,
        operation_id: int,
        endangered_group_id: int | None = None,
        profession_id: int | None = None,
        role_ids: list[int] | None = None,
        group_ids: list[int] | None = None,
    ) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if profession_id is not None and not (role_ids or []):
            scope = f"p{profession_id}"
        elif role_ids and not (group_ids or []):
            scope = "r" + "-".join(str(role_id) for role_id in role_ids[:5])
        elif (group_ids or []) and not (role_ids or []):
            if len(group_ids) == 1:
                scope = f"g{group_ids[0]}"
            else:
                scope = "g" + "-".join(str(group_id) for group_id in group_ids[:5])
        elif endangered_group_id is not None:
            scope = f"g{endangered_group_id}"
        else:
            scope = "multi"
        return f"PravidlaBezpecnePrace-{scope}-o{operation_id}_{stamp}.odt"

    @staticmethod
    def _identification_in_scope(
        identification,
        *,
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> bool:
        if identification.operation_id != operation_id:
            return False
        if workplace_part_id is not None:
            return identification.workplace_part_id == workplace_part_id
        if workplace_id is not None:
            return identification.workplace_id == workplace_id
        return True

    @staticmethod
    def _assessment_matches_group(
        assessment_id: int,
        endangered_group_id: int,
        *,
        legacy_exposed_group_id: int | None,
    ) -> bool:
        return PravidlaBezpecnePraceService._assessment_matches_targets(
            assessment_id,
            role_ids=set(),
            group_ids={endangered_group_id},
            legacy_exposed_group_id=legacy_exposed_group_id,
        )

    @staticmethod
    def _assessment_matches_any_group(
        assessment_id: int,
        endangered_group_ids: set[int],
        *,
        legacy_exposed_group_id: int | None,
    ) -> bool:
        return PravidlaBezpecnePraceService._assessment_matches_targets(
            assessment_id,
            role_ids=set(),
            group_ids=endangered_group_ids,
            legacy_exposed_group_id=legacy_exposed_group_id,
        )

    @staticmethod
    def _assessment_matches_targets(
        assessment_id: int,
        *,
        role_ids: set[int],
        group_ids: set[int],
        legacy_exposed_group_id: int | None,
    ) -> bool:
        if not role_ids and not group_ids:
            return False
        refs = effective_target_refs(
            hazard_risk_assessment_service.get_target_refs(assessment_id),
            legacy_exposed_group_id=legacy_exposed_group_id,
        )
        for ref in refs:
            if ref.source_type == SOURCE_TYPE_ROLE and ref.source_id in role_ids:
                return True
            if (
                ref.source_type == SOURCE_TYPE_HAZARD_GROUP
                and ref.source_id in group_ids
            ):
                return True
        return False

    @staticmethod
    def _dedupe_and_sort(
        items: list[PravidloBezpecnePrace],
    ) -> list[PravidloBezpecnePrace]:
        """Sloučí duplicity: primárně measure_id, poté shoda normalizovaného textu."""

        def _merge_pair(
            existing: PravidloBezpecnePrace,
            item: PravidloBezpecnePrace,
        ) -> PravidloBezpecnePrace:
            sources = existing.sources + tuple(
                source
                for source in item.sources
                if source.measure_id
                not in {s.measure_id for s in existing.sources}
            )
            if item.severity_rank > existing.severity_rank:
                return PravidloBezpecnePrace(
                    measure_id=existing.measure_id,
                    text=existing.text,
                    source_hazard_id=item.source_hazard_id,
                    source_event_id=item.source_event_id,
                    unsuitable_for_employee=existing.unsuitable_for_employee,
                    severity=item.severity,
                    severity_rank=item.severity_rank,
                    sources=sources,
                )
            return PravidloBezpecnePrace(
                measure_id=existing.measure_id,
                text=existing.text,
                source_hazard_id=existing.source_hazard_id,
                source_event_id=existing.source_event_id,
                unsuitable_for_employee=existing.unsuitable_for_employee,
                severity=existing.severity,
                severity_rank=existing.severity_rank,
                sources=sources,
            )

        by_measure: dict[int, PravidloBezpecnePrace] = {}
        for item in items:
            measure_id = int(item.measure_id)
            existing = by_measure.get(measure_id)
            if existing is None:
                by_measure[measure_id] = item
                continue
            by_measure[measure_id] = _merge_pair(existing, item)

        by_text: dict[str, PravidloBezpecnePrace] = {}
        for item in by_measure.values():
            key = item.text.casefold()
            if not key:
                continue
            existing = by_text.get(key)
            if existing is None:
                by_text[key] = item
                continue
            by_text[key] = _merge_pair(existing, item)

        return sorted(
            by_text.values(),
            key=lambda item: (-item.severity_rank, czech_sort_key(item.text)),
        )


pravidla_bezpecne_prace_service = PravidlaBezpecnePraceService()

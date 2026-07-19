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
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
)
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

# Imperativy / 2. osoba – typické pokyny pro zaměstnance.
_EMPLOYEE_VERB_RE = re.compile(
    r"\b("
    r"používej|používejte|použij|použijte|"
    r"noste|nos|"
    r"vstupuj|vstupujte|vstoup|"
    r"dodržuj|dodržujte|"
    r"zkontroluj|zkontrolujte|kontroluj|kontrolujte|"
    r"vypni|vypněte|zapni|zapněte|"
    r"odpoj|odpojte|připoj|připojte|"
    r"ohlás|ohlaste|ohláš|"
    r"ujisti|ujistěte|přesvědči|přesvědčete"
    r")\w*\b",
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
    r"(?=<text:p[^>]*>PLATNÁ PRAVIDLA BEZPEČNÉ PRÁCE</text:p>)",
)



def normalize_rule_text(text: str) -> str:
    """Sjednotí mezery, odstraní prázdné řádky a zajistí jednu tečku na konci."""
    if not text:
        return ""

    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        collapsed = " ".join(raw_line.split())
        if collapsed:
            lines.append(collapsed)

    body = " ".join(lines).strip()
    if not body:
        return ""

    body = _TRAILING_END_PUNCT_RE.sub("", body).rstrip()
    if not body:
        return ""
    return f"{body}."


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

    if _is_short_noun_phrase_without_verb(lowered):
        return True
    return False


def severity_rank(severity: str | None) -> int:
    """Pořadí závažnosti z Registru rizik: vyšší číslo = vyšší závažnost."""
    code = severity or DEFAULT_RISK_SEVERITY
    try:
        return RISK_SEVERITIES.index(code)
    except ValueError:
        return -1


def _is_short_noun_phrase_without_verb(lowered: str) -> bool:
    """Detekuje krátké jmenné fráze bez slovesného pokynu (např. „Poučení obsluhy.“)."""
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
    ) -> list[PravidloBezpecnePrace]:
        """Vrátí platná pravidla pro ohroženou skupinu nebo profesi a rozsah pracoviště.

        Platná = aktivní **existující** opatření (realizovaná).
        Potřebná další / neaktivní opatření se nezahrnují.
        Texty se normalizují; nevhodné formulace zůstávají ve výsledku
        a mají ``unsuitable_for_employee=True``.

        Při výběru profese se sjednotí pravidla ze všech jejích aktivních
        ohrožených skupin (deduplikace, nejvyšší závažnost, všechny zdroje).
        """
        if operation_id is None:
            raise ValueError("operation_id je povinný.")
        if workplace_id is None:
            workplace_part_id = None

        if profession_id is not None:
            group_ids = profession_service.get_active_exposed_group_ids(profession_id)
            if not group_ids:
                return []
            return self._generate_for_groups(
                group_ids=group_ids,
                operation_id=operation_id,
                workplace_id=workplace_id,
                workplace_part_id=workplace_part_id,
            )

        if endangered_group_id is None:
            raise ValueError("Je nutné zadat endangered_group_id nebo profession_id.")

        return self._generate_for_groups(
            group_ids=[endangered_group_id],
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

    def _generate_for_groups(
        self,
        *,
        group_ids: list[int],
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> list[PravidloBezpecnePrace]:
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
                if not self._assessment_matches_any_group(
                    row.assessment.id,
                    target_groups,
                    legacy_exposed_group_id=row.assessment.exposed_group_id,
                ):
                    continue

                for measure in hazard_existing_measure_service.get_for_assessment(
                    row.assessment.id,
                    include_inactive=False,
                ):
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
                    collected.append(
                        PravidloBezpecnePrace(
                            measure_id=measure.id,
                            text=text,
                            source_hazard_id=identification.id,
                            source_event_id=row.assessment.hazard_event_id,
                            unsuitable_for_employee=is_unsuitable_employee_rule(text),
                            severity=severity,
                            severity_rank=rank,
                            sources=(source,),
                        )
                    )

        # Stabilní „první nalezená“ = nejnižší measure_id (dřívější záznam).
        collected.sort(key=lambda item: item.measure_id)
        return self._dedupe_and_sort(collected)

    def quality_warnings(
        self, rules: list[PravidloBezpecnePrace]
    ) -> list[PravidloBezpecnePrace]:
        """Vrátí pravidla označená jako nevhodně formulovaná pro zaměstnance."""
        return [rule for rule in rules if rule.unsuitable_for_employee]

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
    ) -> Path | None:
        """Vytvoří ODT dokument. Při prázdném seznamu pravidel nic nevytváří."""
        if workplace_id is None:
            workplace_part_id = None

        if rules is None:
            rules = self.generate(
                endangered_group_id=endangered_group_id,
                profession_id=profession_id,
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

        # Porovnání s posledním vydáním (PBP-5b) – před ODT i před uložením evidence.
        from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
            pravidla_bezpecne_prace_edition_service,
        )

        self.last_comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            rules=rules,
        )

        values = self._placeholder_values(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
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
                operation_id=operation_id,
            ),
        )
        rendered = self.engine.render(template, output_path, values)
        self._strip_empty_workplace_rows(rendered)
        self._strip_empty_change_section_paragraph(rendered)

        # Evidence vydání až po úspěšném porovnání i ODT (PBP-5a/5b).
        issued_dt: datetime
        if issued_at is None:
            issued_dt = datetime.now()
        elif isinstance(issued_at, datetime):
            issued_dt = issued_at
        else:
            issued_dt = datetime.combine(issued_at, datetime.min.time())

        pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            rules=rules,
            export_path=rendered,
            issued_at=issued_dt,
        )
        return rendered

    @staticmethod
    def _strip_empty_workplace_rows(odt_path: Path) -> None:
        """Odstraní řádky Pracoviště / Část pracoviště s prázdnou hodnotou."""
        PravidlaBezpecnePraceService._rewrite_odt_content(
            odt_path,
            lambda content_xml: _EMPTY_INFO_ROW_RE.sub("", content_xml),
        )

    @staticmethod
    def _strip_empty_change_section_paragraph(odt_path: Path) -> None:
        """Odstraní prázdný odstavec změnových sekcí před PLATNÁ PRAVIDLA."""
        PravidlaBezpecnePraceService._rewrite_odt_content(
            odt_path,
            lambda content_xml: _EMPTY_ZMENY_PARAGRAPH_RE.sub("", content_xml),
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
    ) -> Path | None:
        path = self.export_document(
            endangered_group_id=endangered_group_id,
            profession_id=profession_id,
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
    ) -> dict[str, str]:
        if profession_id is not None:
            rozsah_label = "Profese"
            rozsah_nazev = profession_service.display_name(profession_id)
        else:
            rozsah_label = "Ohrožená skupina"
            rozsah_nazev = exposed_group_service.display_name(endangered_group_id)
        comparison = self.last_comparison
        from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_document_format import (
            format_change_sections,
            format_numbered_valid_rules,
        )

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
            "platna_pravidla_text": format_numbered_valid_rules(rules, comparison),
        }

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
    ) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if profession_id is not None:
            scope = f"p{profession_id}"
        else:
            scope = f"g{endangered_group_id}"
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
        return PravidlaBezpecnePraceService._assessment_matches_any_group(
            assessment_id,
            {endangered_group_id},
            legacy_exposed_group_id=legacy_exposed_group_id,
        )

    @staticmethod
    def _assessment_matches_any_group(
        assessment_id: int,
        endangered_group_ids: set[int],
        *,
        legacy_exposed_group_id: int | None,
    ) -> bool:
        if not endangered_group_ids:
            return False
        group_ids = hazard_risk_assessment_service.get_group_ids(assessment_id)
        if group_ids:
            return bool(endangered_group_ids.intersection(group_ids))
        if legacy_exposed_group_id is not None:
            return legacy_exposed_group_id in endangered_group_ids
        return False

    @staticmethod
    def _dedupe_and_sort(
        items: list[PravidloBezpecnePrace],
    ) -> list[PravidloBezpecnePrace]:
        """Sloučí duplicity, vezme nejvyšší závažnost a seřadí severity → abeceda."""
        merged: dict[str, PravidloBezpecnePrace] = {}
        for item in items:
            key = item.text.casefold()
            if not key:
                continue
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue

            sources = existing.sources + tuple(
                source
                for source in item.sources
                if source.measure_id
                not in {s.measure_id for s in existing.sources}
            )
            if item.severity_rank > existing.severity_rank:
                merged[key] = PravidloBezpecnePrace(
                    measure_id=existing.measure_id,
                    text=existing.text,
                    source_hazard_id=item.source_hazard_id,
                    source_event_id=item.source_event_id,
                    unsuitable_for_employee=existing.unsuitable_for_employee,
                    severity=item.severity,
                    severity_rank=item.severity_rank,
                    sources=sources,
                )
            else:
                merged[key] = PravidloBezpecnePrace(
                    measure_id=existing.measure_id,
                    text=existing.text,
                    source_hazard_id=existing.source_hazard_id,
                    source_event_id=existing.source_event_id,
                    unsuitable_for_employee=existing.unsuitable_for_employee,
                    severity=existing.severity,
                    severity_rank=existing.severity_rank,
                    sources=sources,
                )

        unique = list(merged.values())
        return sorted(
            unique,
            key=lambda item: (-item.severity_rank, czech_sort_key(item.text)),
        )


pravidla_bezpecne_prace_service = PravidlaBezpecnePraceService()

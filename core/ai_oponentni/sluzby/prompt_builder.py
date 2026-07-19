"""Sestavení pokynu pro AI oponentní posouzení (R11.8)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from core.ai_oponentni.constants import (
    AI_CATALOG_PEER_REVIEW_DEFAULT_OBJECTIVES,
    AI_CATALOG_PEER_REVIEW_OBJECTIVES,
    AI_PEER_REVIEW_DEFAULT_OBJECTIVES,
    AI_PEER_REVIEW_DEFAULT_ROLE,
    AI_PEER_REVIEW_FOCUS_AREA_LABELS,
    AI_PEER_REVIEW_FOCUS_AREAS,
    AI_PEER_REVIEW_OBJECTIVE_LABELS,
    AI_PEER_REVIEW_OBJECTIVES,
    AI_PEER_REVIEW_ROLE_LABELS,
    AI_PEER_REVIEW_ROLES,
)

# Kapitola AI-RISK-OP-2 – společná pro identifikaci i katalog.
MEASURE_FORMULATION_STYLE_HEADING = "=== Styl formulace opatření ==="


def measure_formulation_style_section() -> list[str]:
    """Samostatná kapitola o stylu formulace opatření (AI-RISK-OP-2)."""
    return [
        MEASURE_FORMULATION_STYLE_HEADING,
        "",
        "1. Každé opatření formulujte jako jednoznačný pokyn zaměstnanci.",
        "",
        "Preferovaný styl:",
        "- Používejte...",
        "- Dodržujte...",
        "- Udržujte...",
        "- Zajistěte...",
        "- Před zahájením práce...",
        "- Při práci...",
        "- Po skončení práce...",
        "- Nevstupujte...",
        "- Nepoužívejte...",
        "- Neprovádějte...",
        "",
        "2. Opatření musí být srozumitelné samo o sobě.",
        "Nesmí vyžadovat znalost kontextu ani předchozí věty.",
        "",
        "3. Každé opatření musí být možné beze změny použít",
        "v dokumentu „Pravidla bezpečné práce“.",
        "",
        "4. Nepoužívejte pouze jmenné fráze.",
        "",
        "Nevhodné:",
        "- Poučení zaměstnanců.",
        "- Používání OOPP.",
        "- Kontrola zařízení.",
        "- Stabilní umístění zařízení.",
        "- Zajištění bezpečného přístupu.",
        "",
        "5. Nepoužívejte administrativní formulace bez určení adresáta.",
        "",
        "Nevhodné:",
        "- Zajistit...",
        "- Provést...",
        "- Kontrolovat...",
        "- Ověřit...",
        "- Dodržování...",
        "",
        "6. Nepište hodnotící věty.",
        "",
        "Zakázané formulace:",
        "- Riziko je zřejmé.",
        "- Není potřeba přijímat zvláštní opatření.",
        "- Opatření nejsou nutná.",
        "- Bez opatření.",
        "",
        "7. Preferujte aktivní věty.",
        "",
        "Místo:",
        "\"Nábytek musí být stabilně umístěn.\"",
        "",
        "Použijte:",
        "\"Umísťujte nábytek na rovný a stabilní podklad.\"",
        "",
        "8. Nepoužívejte neurčitá slova:",
        "- vhodně",
        "- přiměřeně",
        "- dostatečně",
        "- správně",
        "- podle potřeby",
        "",
        "pokud lze napsat konkrétní pokyn.",
        "",
        "9. Nepopisujte organizaci práce zaměstnavatele.",
        "Opatření mají popisovat bezpečné chování osoby, které jsou určena.",
        "",
        "10. Pokud nelze vytvořit konkrétní pokyn zaměstnanci,",
        "raději opatření vůbec nenavrhujte.",
    ]


def normalize_opponent_role(role: str | None) -> str:
    value = (role or "").strip()
    if value in AI_PEER_REVIEW_ROLES:
        return value
    return AI_PEER_REVIEW_DEFAULT_ROLE


def normalize_objectives(objectives: Iterable[str] | None) -> list[str]:
    if objectives is None:
        return list(AI_PEER_REVIEW_DEFAULT_OBJECTIVES)
    allowed = set(AI_PEER_REVIEW_OBJECTIVES)
    result = [key for key in AI_PEER_REVIEW_OBJECTIVES if key in objectives and key in allowed]
    return result if result else list(AI_PEER_REVIEW_DEFAULT_OBJECTIVES)


def normalize_catalog_objectives(objectives: Iterable[str] | None) -> list[str]:
    if objectives is None:
        return list(AI_CATALOG_PEER_REVIEW_DEFAULT_OBJECTIVES)
    allowed = set(AI_CATALOG_PEER_REVIEW_OBJECTIVES)
    result = [
        key for key in AI_CATALOG_PEER_REVIEW_OBJECTIVES if key in objectives and key in allowed
    ]
    return result if result else list(AI_CATALOG_PEER_REVIEW_DEFAULT_OBJECTIVES)


def normalize_focus_areas(focus_areas: Iterable[str] | None) -> list[str]:
    if not focus_areas:
        return []
    allowed = set(AI_PEER_REVIEW_FOCUS_AREAS)
    return [key for key in AI_PEER_REVIEW_FOCUS_AREAS if key in focus_areas and key in allowed]


def opponent_role_label(role: str | None) -> str:
    normalized = normalize_opponent_role(role)
    return AI_PEER_REVIEW_ROLE_LABELS[normalized]


def build_ai_peer_review_prompt(
    *,
    role: str | None = None,
    objectives: Sequence[str] | None = None,
    focus_areas: Sequence[str] | None = None,
    workplace_characteristics: str = "",
    identification_kind_note: str = "",
    risk_assessment_note: str = "",
) -> str:
    """Sestaví obsah souboru pokyn_pro_AI.txt."""
    role_id = normalize_opponent_role(role)
    role_label = AI_PEER_REVIEW_ROLE_LABELS[role_id]
    objective_ids = normalize_objectives(objectives)
    focus_ids = normalize_focus_areas(focus_areas)
    characteristics = " ".join((workplace_characteristics or "").split()).strip()

    lines: list[str] = []
    lines.append("ROLE ODBORNÉHO OPONENTA")
    lines.append("-" * 40)
    lines.append(f"Jsi: {role_label}.")
    lines.append(
        "Proveď odborné oponentní posouzení poskytnutých podkladů přesně z této "
        "odborné pozice. Drž se jejího úhlu pohledu, zkušeností a typických "
        "priorit, aniž bys měnil strukturu odpovědi."
    )
    lines.append("")

    lines.append("KONTEXT IDENTIFIKACE")
    lines.append("-" * 40)
    if characteristics:
        lines.append(f"Charakteristika pracoviště: {characteristics}")
    else:
        lines.append(
            "Charakteristika pracoviště nebyla samostatně zadána – "
            "vycházej pouze z exportovaných podkladů."
        )
    if identification_kind_note:
        lines.append(identification_kind_note)
    if risk_assessment_note:
        lines.append(risk_assessment_note)
    lines.append("")

    lines.append("PRÁVNÍ RÁMEC")
    lines.append("-" * 40)
    lines.append(
        "Posuzuj podle aktuálně platných právních předpisů České republiky "
        "v oblasti BOZP."
    )
    lines.append("")

    lines.append("CÍL OPONENTURY")
    lines.append("-" * 40)
    lines.append("Zaměř se zejména na:")
    for objective_id in objective_ids:
        lines.append(f"- {AI_PEER_REVIEW_OBJECTIVE_LABELS[objective_id]}")
    if focus_ids:
        lines.append("")
        lines.append("Doplňující zaměření:")
        for focus_id in focus_ids:
            lines.append(f"- {AI_PEER_REVIEW_FOCUS_AREA_LABELS[focus_id]}")
    lines.append("")

    lines.append("STRUKTURA PODKLADŮ")
    lines.append("-" * 40)
    lines.append(
        "Podklady jsou hierarchické:\n"
        "\n"
        "Analýza pracoviště → Nežádoucí události → Posouzení\n"
        "→ Existující opatření → Potřebná opatření\n"
        "\n"
        "Každý objekt má stabilní exportní ID (ITEM-…, EVENT-…, ASSESSMENT-…).\n"
        "Při návrhu doplnění uveď rodiče pomocí tohoto ID (pole Rodič)."
    )
    lines.append("")

    lines.append("PRAVIDLA")
    lines.append("-" * 40)
    rules = [
        "Nehodnoť závažnost rizik.",
        "Neměň existující položky.",
        "Neopakuj již existující položky z exportu.",
        "Nenavrhuj zjevně nereálné scénáře.",
        "Nevymýšlej technologie, zařízení ani činnosti, které nejsou z exportu "
        "ani z charakteristiky pracoviště patrné.",
        "Respektuj skutečný charakter pracoviště.",
        "Ke každému návrhu napiš stručné odborné zdůvodnění.",
        "Právní předpisy uváděj pouze jako návrh k odbornému ověření, "
        "nikoli jako závazný právní výklad.",
        "Nevydávej návrhy za úplné ani definitivní.",
        "Odpověď strukturoj podle schema_odpovedi.json "
        "(nebo použij textový formát níže).",
    ]
    for rule in rules:
        lines.append(f"- {rule}")
    lines.append("")

    lines.extend(measure_formulation_style_section())
    lines.append("")

    lines.append("OTÁZKY K POSOUZENÍ")
    lines.append("-" * 40)
    questions = [
        "Jsou v analýze všechny významné zdroje?",
        "Chybí některé běžné nežádoucí události?",
        "Chybí některé skupiny ohrožených osob?",
        "Chybí některá běžná opatření?",
        "Chybí některé důležité právní požadavky?",
        "Na co se při podobných pracovištích nejčastěji zapomíná?",
    ]
    for question in questions:
        lines.append(f"- {question}")
    lines.append("")

    lines.append("FORMÁT ODPOVĚDI")
    lines.append("-" * 40)
    lines.append(
        "Formát odpovědi (použij přesně tuto strukturu u každého návrhu):\n"
        "\n"
        "Oblast: <název oblasti>\n"
        "Návrh: <navržená položka>\n"
        "Rodič: <exportní ID rodiče, nebo —>\n"
        "Zdůvodnění: <stručné odborné zdůvodnění>\n"
        "\n"
        "Odděl jednotlivé návrhy prázdným řádkem."
    )
    return "\n".join(lines).rstrip() + "\n"


def build_catalog_source_ai_peer_review_prompt(
    *,
    role: str | None = None,
    objectives: Sequence[str] | None = None,
    focus_areas: Sequence[str] | None = None,
    general_context: str = "",
) -> str:
    """Sestaví pokyn pro oponenturu katalogového zdroje rizika."""
    role_id = normalize_opponent_role(role)
    role_label = AI_PEER_REVIEW_ROLE_LABELS[role_id]
    objective_ids = normalize_catalog_objectives(objectives)
    focus_ids = normalize_focus_areas(focus_areas)
    context = " ".join((general_context or "").split()).strip()

    lines: list[str] = []
    lines.append("ROLE ODBORNÉHO OPONENTA")
    lines.append("-" * 40)
    lines.append(f"Jsi: {role_label}.")
    lines.append(
        "Proveď odborné oponentní posouzení poskytnutých podkladů katalogového "
        "zdroje rizika přesně z této odborné pozice."
    )
    lines.append("")

    lines.append("KONTEXT ZDROJE RIZIKA")
    lines.append("-" * 40)
    if context:
        lines.append(f"Obecný kontext zdroje rizika: {context}")
    else:
        lines.append(
            "Obecný kontext zdroje rizika nebyl samostatně zadán – "
            "vycházej pouze z exportovaných podkladů."
        )
    lines.append("")

    lines.append("PRÁVNÍ RÁMEC")
    lines.append("-" * 40)
    lines.append(
        "Posuzuj podle aktuálně platných právních předpisů České republiky "
        "v oblasti BOZP."
    )
    lines.append("")

    lines.append("CÍL OPONENTURY")
    lines.append("-" * 40)
    lines.append("Zaměř se zejména na:")
    for objective_id in objective_ids:
        lines.append(f"- {AI_PEER_REVIEW_OBJECTIVE_LABELS[objective_id]}")
    if focus_ids:
        lines.append("")
        lines.append("Doplňující zaměření:")
        for focus_id in focus_ids:
            lines.append(f"- {AI_PEER_REVIEW_FOCUS_AREA_LABELS[focus_id]}")
    lines.append("")

    lines.append("STRUKTURA PODKLADŮ")
    lines.append("-" * 40)
    lines.append(
        "Podklady jsou hierarchické:\n"
        "\n"
        "Zdroj rizika → Nežádoucí události → Posouzení\n"
        "→ Existující opatření → Potřebná opatření\n"
        "\n"
        "Každý objekt má stabilní exportní ID "
        "(SOURCE-…, EVENT-…, ASSESSMENT-…, EXISTING-MEASURE-…, REQUIRED-MEASURE-…).\n"
        "Při návrhu doplnění uveď rodiče pomocí tohoto ID (pole Rodič)."
    )
    lines.append("")

    lines.append("PRAVIDLA")
    lines.append("-" * 40)
    rules = [
        "Nevracej izolovaná opatření bez kompletního posouzení.",
        "Nevracej izolované ohrožené skupiny bez události a následku.",
        "Každý návrh musí být jeden ucelený balík s úplným odborným kontextem.",
        "Každé opomenutí popiš jako kompletní scénář: co se může stát → komu → "
        "jaký může být následek → jaká opatření existují nebo mají být přijata → "
        "jaká legislativa může souviset.",
        "Neměň existující položky.",
        "Neopakuj již existující položky z exportu.",
        "Nenavrhuj zjevně nereálné scénáře.",
        "Nevymýšlej technologie, zařízení ani činnosti, které nejsou z exportu "
        "ani z obecného kontextu zdroje patrné.",
        "Respektuj skutečný charakter katalogového zdroje rizika.",
        "Ke každému balíku napiš stručné odborné zdůvodnění.",
        "Právní předpisy uváděj pouze jako návrh k odbornému ověření.",
        "Nevydávej návrhy za úplné ani definitivní.",
        "Odpověď strukturoj podle schema_odpovedi.json "
        "(nebo použij textový formát níže).",
    ]
    for rule in rules:
        lines.append(f"- {rule}")
    lines.append("")

    lines.extend(measure_formulation_style_section())
    lines.append("")

    lines.append("OTÁZKY K POSOUZENÍ")
    lines.append("-" * 40)
    questions = [
        "Jsou v katalogovém zdroji popsány všechny významné nežádoucí události?",
        "Chybí některé běžné nežádoucí události?",
        "Chybí některé skupiny ohrožených osob?",
        "Chybí některá běžná opatření?",
        "Chybí některé důležité právní požadavky?",
        "Na co se u podobných zdrojů rizika nejčastěji zapomíná?",
    ]
    for question in questions:
        lines.append(f"- {question}")
    lines.append("")

    lines.append("FORMÁT ODPOVĚDI")
    lines.append("-" * 40)
    lines.append(
        "Vrať ucelené návrhové balíky (schema 2.0). Každý balík musí obsahovat "
        "událost nebo vazbu na existující EVENT-…, alespoň jedno kompletní posouzení "
        "(jedna nebo více ohrožených skupin a závažnost), volitelně opatření uvnitř posouzení "
        "a volitelně právní vazby k celému balíku.\n"
        "\n"
        "Textový fallback (použij přesně tuto strukturu u každého balíku):\n"
        "\n"
        "BALÍK: PACKAGE-001\n"
        "TYP: Nová událost\n"
        "\n"
        "UDÁLOST:\n"
        "...\n"
        "\n"
        "POSOUZENÍ:\n"
        "Ohrožená skupina: ...\n"
        "Ohrožená skupina: ...\n"
        "Závažnost: moderate\n"
        "\n"
        "EXISTUJÍCÍ OPATŘENÍ:\n"
        "- ...\n"
        "\n"
        "POTŘEBNÁ OPATŘENÍ:\n"
        "- ...\n"
        "\n"
        "PRÁVNÍ VAZBY:\n"
        "- ...\n"
        "\n"
        "ZDŮVODNĚNÍ:\n"
        "...\n"
        "\n"
        "Pro doplnění existující události použij TYP: Doplnění existující události "
        "a uveď Cílová událost: EVENT-…"
    )
    return "\n".join(lines).rstrip() + "\n"

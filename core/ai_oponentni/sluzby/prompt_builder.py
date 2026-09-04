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

# Kapitola RISK-AI-13 / RISK-CONTROL-QUESTIONS-1 – Zásady vs kontrolní otázky.
MEASURE_FORMULATION_STYLE_HEADING = "=== Styl formulace opatření a otázek ==="

# Kapitola RISK-AI-12 – pořadí posouzení stávajících položek.
MEASURE_REVIEW_ORDER_HEADING = "=== Posouzení stávajících opatření ==="


def measure_review_order_section() -> list[str]:
    """Pokyny pro revizi Zásad a kontrolních otázek."""
    return [
        MEASURE_REVIEW_ORDER_HEADING,
        "",
        "Posuzuj položky v tomto pořadí:",
        "1. Nejprve posuď stávající kontrolní otázky pro revizi rizik.",
        "2. Následně posuď Zásady bezpečné práce.",
        "3. Teprve potom zvažuj návrh nových kontrolních otázek.",
        "",
        "Nenavrhuj novou kontrolní otázku, pokud lze stejné ověření pokrýt "
        "úpravou stávající otázky.",
        "Nenavrhuj novou Zásadu bezpečné práce, pokud lze stejného cíle "
        "dosáhnout úpravou stávající zásady.",
        "",
        "Pokud jsou stávající zásady a kontrolní otázky dostatečné, "
        "nenavrhuj jejich změnu.",
    ]


def measure_formulation_style_section() -> list[str]:
    """Styl formulace Zásad vs kontrolních otázek pro revizi rizik."""
    return [
        MEASURE_FORMULATION_STYLE_HEADING,
        "",
        "Rozlišujte jazyk podle typu opatření. "
        "Stejná formulace není vhodná pro oba typy.",
        "",
        "A) Zásady bezpečné práce",
        "",
        "Zásady bezpečné práce jsou určeny zaměstnanci.",
        "Používejte přímé pokyny zaměstnanci.",
        "",
        "Preferovaný styl:",
        "- Používejte...",
        "- Dodržujte...",
        "- Udržujte...",
        "- Před zahájením práce...",
        "- Při práci...",
        "- Po skončení práce...",
        "- Nevstupujte...",
        "- Nepoužívejte...",
        "- Neprovádějte...",
        "",
        "Příklad správně:",
        "\"Při jízdě na stanovišti drážního vozidla se držte určeného madla.\"",
        "",
        "Zásady musí být srozumitelné samy o sobě a musí být možné je "
        "beze změny použít v dokumentu „Pravidla bezpečné práce“.",
        "",
        "Je vhodné nahrazovat obecné nebo neurčité formulace "
        "konkrétními pravidly bezpečného chování.",
        "",
        "Nepoužívejte pouze jmenné fráze.",
        "",
        "Nevhodné pro Zásady:",
        "- Poučení zaměstnanců.",
        "- Používání OOPP.",
        "- Kontrola zařízení.",
        "- Stabilní umístění zařízení.",
        "- Zajištění bezpečného přístupu.",
        "",
        "Preferujte aktivní věty.",
        "",
        "Místo:",
        "\"Nábytek musí být stabilně umístěn.\"",
        "",
        "Použijte:",
        "\"Umísťujte nábytek na rovný a stabilní podklad.\"",
        "",
        "Nepopisujte organizaci práce zaměstnavatele. "
        "Zásady mají popisovat bezpečné chování osoby, které jsou určeny.",
        "",
        "B) Kontrolní otázky pro revizi rizik",
        "",
        "Pole required_measures obsahuje kontrolní otázky pro revizi rizik.",
        "Slouží při konkrétní revizi k ověření, zda jsou zásady a opatření "
        "skutečně dodržovány.",
        "",
        "Každá kontrolní otázka musí:",
        "- být formulována jako otázka,",
        "- ověřovat jednu konkrétní skutečnost,",
        "- umožňovat odpověď Ano / Ne / Netýká se,",
        "- navazovat na konkrétní událost a její zásady bezpečné práce,",
        "- neobsahovat odpovědnou osobu ani termín,",
        "- neopakovat jinou otázku.",
        "",
        "Kontrolní otázka není úkol, jednorázové nápravné opatření, "
        "termínovaný požadavek ani pokyn typu „Provést revizi do…“.",
        "",
        "Příklad:",
        "Zásada: \"Kontroly, revize a údržba musí být prováděny "
        "ve stanovených termínech.\"",
        "Kontrolní otázka: \"Jsou kontroly, revize a údržba prováděny "
        "ve stanovených termínech?\"",
        "",
        "Pokud katalog neobsahuje žádné události, navrhni kontrolní otázky "
        "spolu s novými událostmi.",
        "Pokud katalog již obsahuje data, hledej chybějící nebo nevhodně "
        "formulované kontrolní otázky.",
        "",
        "C) Kontrola významu před návrhem úpravy",
        "",
        "Při návrhu úpravy nejprve určete:",
        "",
        "Je text pokynem zaměstnanci?",
        "ANO → patří mezi Zásady bezpečné práce "
        "(typ upravit_zasady_bezpecne_prace).",
        "NE, jde o ověření dodržování → jde o kontrolní otázku "
        "(typ upravit_navazujici_opatreni / nove_navazujici_opatreni).",
        "",
        "Pokud by návrh změnil tuto kategorii "
        "(např. ze zásady na otázku nebo naopak), "
        "takový návrh nesmíte navrhnout v nesprávném typu.",
        "",
        "D) Společná pravidla pro oba typy",
        "",
        "Nepište hodnotící věty.",
        "",
        "Zakázané formulace:",
        "- Riziko je zřejmé.",
        "- Není potřeba přijímat zvláštní opatření.",
        "- Opatření nejsou nutná.",
        "- Bez opatření.",
        "",
        "Nepoužívejte neurčitá slova:",
        "- vhodně",
        "- přiměřeně",
        "- dostatečně",
        "- správně",
        "- podle potřeby",
        "",
        "pokud lze napsat konkrétní znění.",
        "",
        "Pokud nelze vytvořit vhodné znění v souladu s typem položky, "
        "raději ji vůbec nenavrhujte.",
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
        "→ Zásady bezpečné práce → Kontrolní otázky pro revizi rizik\n"
        "\n"
        "Každý objekt má stabilní exportní ID (ITEM-…, EVENT-…, ASSESSMENT-…).\n"
        "Při návrhu doplnění uveď rodiče pomocí tohoto ID (pole Rodič)."
    )
    lines.append("")

    lines.append("PRAVIDLA")
    lines.append("-" * 40)
    rules = [
        "Nehodnoť závažnost rizik.",
        "Neopakuj již existující položky z exportu bez důvodu.",
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

    lines.extend(measure_review_order_section())
    lines.append("")
    lines.extend(measure_formulation_style_section())
    lines.append("")

    lines.append("OTÁZKY K POSOUZENÍ")
    lines.append("-" * 40)
    questions = [
        "Jsou v analýze všechny významné zdroje?",
        "Chybí některé běžné nežádoucí události?",
        "Chybí některé skupiny ohrožených osob?",
        "Jsou stávající kontrolní otázky pro revizi rizik dostatečné?",
        "Jsou Zásady bezpečné práce dostatečné, nebo vyžadují úpravu?",
        "Chybí skutečně nová kontrolní otázka, kterou nelze nahradit úpravou?",
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
        "Odděl jednotlivé návrhy prázdným řádkem.\n"
        "\n"
        "U návrhů k opatřením uveď volitelně typ doporučení "
        "(beze_zmen / upravit_navazujici_opatreni / "
        "upravit_zasady_bezpecne_prace / nove_navazujici_opatreni)."
    )
    return "\n".join(lines).rstrip() + "\n"


def catalog_universal_processing_rules() -> list[str]:
    """Společná pravidla pro prázdný i naplněný katalog (jeden export)."""
    return [
        "Pokud katalog neobsahuje žádné nežádoucí události, vytvoř jeho první "
        "odborný návrh.",
        "Pokud katalog již obsahuje data, proveď jejich oponenturu a navrhni "
        "chybějící nebo potřebné doplnění.",
        "Prázdný katalog je legitimní vstup a nesmí být důvodem k odmítnutí.",
        "Navrhuj nežádoucí události, ohrožené skupiny, zásady bezpečné práce, "
        "kontrolní otázky pro revizi rizik a právní vazby.",
        "Pokud katalog neobsahuje žádné nežádoucí události, navrhni spolu s nimi "
        "i první kontrolní otázky.",
        "Pokud katalog již obsahuje data, hledej chybějící nebo nevhodně "
        "formulované kontrolní otázky.",
        "Neopakuj položky, které již v katalogu existují.",
        "Nové události vracej jako proposal_package typu new_event.",
        "Doplnění existující události navaž na její exportní ID.",
        "Vrať pouze JSON podle response_schema, bez Markdownu a komentářů.",
        "Právní vazby jsou pouze návrhy k odbornému ověření.",
    ]


def build_catalog_ai_instruction(
    *,
    role: str | None = None,
    objectives: Sequence[str] | None = None,
    focus_areas: Sequence[str] | None = None,
) -> dict:
    """Strukturované instrukce pro AI_REVIEW_REQUEST.json."""
    role_id = normalize_opponent_role(role)
    objective_ids = normalize_catalog_objectives(objectives)
    focus_ids = normalize_focus_areas(focus_areas)
    goals = [AI_PEER_REVIEW_OBJECTIVE_LABELS[item_id] for item_id in objective_ids]
    if focus_ids:
        goals.extend(AI_PEER_REVIEW_FOCUS_AREA_LABELS[item_id] for item_id in focus_ids)

    rules = list(catalog_universal_processing_rules())
    rules.extend(
        [
            "Nevracej izolovaná opatření bez kompletního posouzení "
            "(u nových událostí v proposal_packages).",
            "Nevracej izolované ohrožené skupiny bez události a následku.",
            "Každý návrh nové události musí být jeden ucelený balík "
            "s úplným odborným kontextem.",
            "Při doplnění existující události použij package_type extend_event "
            "a target_event_export_id (EVENT-…).",
            "Ke každému balíku i doporučení k opatřením napiš stručné odborné "
            "zdůvodnění.",
            "Nenavrhuj zjevně nereálné scénáře.",
            "Nevymýšlej technologie, zařízení ani činnosti, které nejsou "
            "z source_data ani z obecného kontextu zdroje patrné.",
            "Posuzuj podle aktuálně platných právních předpisů České republiky "
            "v oblasti BOZP.",
            "Nevydávej návrhy za úplné ani definitivní.",
        ]
    )
    rules.append("\n".join(measure_review_order_section()).strip())
    rules.append("\n".join(measure_formulation_style_section()).strip())
    return {
        "role": role_id,
        "role_label": AI_PEER_REVIEW_ROLE_LABELS[role_id],
        "goal": goals,
        "rules": rules,
    }


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
        "→ Zásady bezpečné práce → Kontrolní otázky pro revizi rizik\n"
        "\n"
        "Každý objekt má stabilní exportní ID "
        "(SOURCE-…, EVENT-…, ASSESSMENT-…, EXISTING-MEASURE-…, REQUIRED-MEASURE-…).\n"
        "Při návrhu doplnění uveď rodiče pomocí tohoto ID."
    )
    lines.append("")

    lines.append("PRAVIDLA")
    lines.append("-" * 40)
    rules = [
        *catalog_universal_processing_rules(),
        "Nevracej izolovaná opatření bez kompletního posouzení "
        "(u nových událostí v proposal_packages).",
        "Nevracej izolované ohrožené skupiny bez události a následku.",
        "Každý návrh nové události musí být jeden ucelený balík "
        "s úplným odborným kontextem.",
        "Každé opomenutí události popiš jako kompletní scénář: "
        "co se může stát → komu → jaký může být následek → "
        "jaká opatření existují nebo mají být přijata → "
        "jaká legislativa může souviset.",
        "Nenavrhuj zjevně nereálné scénáře.",
        "Nevymýšlej technologie, zařízení ani činnosti, které nejsou z exportu "
        "ani z obecného kontextu zdroje patrné.",
        "Respektuj skutečný charakter katalogového zdroje rizika.",
        "Ke každému balíku i doporučení k opatřením napiš stručné odborné zdůvodnění.",
        "Nevydávej návrhy za úplné ani definitivní.",
        "Odpověď strukturoj podle response_schema "
        "(nebo použij textový formát níže).",
    ]
    for rule in rules:
        lines.append(f"- {rule}")
    lines.append("")

    lines.extend(measure_review_order_section())
    lines.append("")
    lines.extend(measure_formulation_style_section())
    lines.append("")

    lines.append("OTÁZKY K POSOUZENÍ")
    lines.append("-" * 40)
    questions = [
        "Jsou v katalogovém zdroji popsány všechny významné nežádoucí události?",
        "Chybí některé běžné nežádoucí události?",
        "Chybí některé skupiny ohrožených osob?",
        "Jsou stávající kontrolní otázky pro revizi rizik dostatečné?",
        "Jsou Zásady bezpečné práce dostatečné, nebo vyžadují úpravu?",
        "Chybí skutečně nová kontrolní otázka, kterou nelze nahradit úpravou?",
        "Chybí některé důležité právní požadavky?",
        "Na co se u podobných zdrojů rizika nejčastěji zapomíná?",
    ]
    for question in questions:
        lines.append(f"- {question}")
    lines.append("")

    lines.append("FORMÁT ODPOVĚDI")
    lines.append("-" * 40)
    lines.append(
        "Vrať schema 2.0 s proposal_packages (nové/doplněné události) a/nebo "
        "measure_recommendations (revize opatření).\n"
        "\n"
        "Každý prvek measure_recommendations musí obsahovat:\n"
        "- recommendation_id\n"
        "- typ: beze_zmen | upravit_navazujici_opatreni | "
        "upravit_zasady_bezpecne_prace | nove_navazujici_opatreni\n"
        "- reasoning (stručné odborné zdůvodnění)\n"
        "- proposed_text (navrhované znění; u beze_zmen může být prázdné)\n"
        "- target_export_id: REQUIRED-MEASURE-… / EXISTING-MEASURE-… "
        "při úpravě, ASSESSMENT-… při nové kontrolní otázce\n"
        "\n"
        "Ucelené návrhové balíky (proposal_packages) používej pro nové události. "
        "Každý balík musí obsahovat událost nebo vazbu na existující EVENT-…, "
        "alespoň jedno kompletní posouzení (ohrožené skupiny a závažnost), "
        "volitelně opatření uvnitř posouzení a volitelně právní vazby.\n"
        "\n"
        "Textový fallback pro balíky událostí:\n"
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
        "ZÁSADY BEZPEČNÉ PRÁCE:\n"
        "- ...\n"
        "\n"
        "NAVAZUJÍCÍ OPATŘENÍ:\n"
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

"""Okamžitá opatření z karty Oznámení MU – definice polí a exportní formát."""

OKAMZITA_OPATRENI_ITEMS: tuple[tuple[str, str], ...] = (
    ("opatreni_prvni_pomoc", "Poskytnuta první pomoc"),
    ("opatreni_zzs", "Přivolána ZZS"),
    ("opatreni_policie", "Přivolána Policie ČR"),
    ("opatreni_hzs", "Přivolán Hasičský záchranný sbor"),
    ("opatreni_zastavena_cinnost", "Zastavena nebezpečná činnost"),
    ("opatreni_zajisteno_misto", "Zajištěno místo události"),
    ("opatreni_zabraneno_manipulaci", "Zabráněno manipulaci s předměty"),
    ("opatreni_informovan_nadrizeny", "Informován nadřízený"),
    ("opatreni_informovan_bozp", "Informován BOZP"),
    ("opatreni_informovany_dalsi", "Informovány další osoby podle závažnosti"),
)


def format_checked_okamzita_opatreni(data: dict) -> str:
    """Vrátí seznam zaškrtnutých opatření pro tisk/export (každá položka na řádku)."""
    lines: list[str] = []
    for field, label in OKAMZITA_OPATRENI_ITEMS:
        if (data.get(field) or "") == "ANO":
            lines.append(label)
    return "\n".join(lines)

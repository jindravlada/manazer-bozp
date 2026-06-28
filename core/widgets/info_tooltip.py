def format_info_card(title: str, rows: list[tuple[str, str]], note: str = "") -> str:
    """
    Jednotná textová informační karta pro tooltipy.
    Použití v tabulkách napříč aplikací.
    """

    lines = []
    lines.append(title)
    lines.append("─" * 42)

    for label, value in rows:
        value = value or "—"
        lines.append(f"{label:<16} {value}")

    if note:
        lines.append("")
        lines.append("Poznámka:")
        lines.append(note)

    return "\n".join(lines)

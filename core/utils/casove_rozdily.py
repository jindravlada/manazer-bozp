"""Společná logika kontroly časové návaznosti (Šetření úrazu, Vyšetřování MU)."""

from datetime import date, datetime, time


def parse_time_seconds(text: str) -> int | None:
    text = (text or "").strip()
    if not text:
        return None
    text = text.replace(".", ":")
    parts = text.split(":")
    try:
        if len(parts) == 1:
            h = int(parts[0])
            m = 0
            s = 0
        else:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
        if h < 0 or h > 23 or m < 0 or m > 59 or s < 0 or s > 59:
            return None
        return h * 3600 + m * 60 + s
    except Exception:
        return None


def datetime_from_date_and_time(date_value: date | None, time_text: str) -> datetime | None:
    if date_value is None:
        return None
    seconds = parse_time_seconds(time_text)
    if seconds is None:
        return None
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return datetime.combine(date_value, time(h, m, s))


def casovy_rozdil_barva(minutes: int) -> str:
    if minutes < 0:
        return "#c62828"
    if minutes <= 60:
        return "#2e7d32"
    if minutes <= 180:
        return "#b8860b"
    if minutes <= 480:
        return "#ef6c00"
    return "#c62828"


def format_od_udalosti_rozdil(
    reference_dt: datetime | None,
    target_dt: datetime | None,
    *,
    pred_udalosti_text: str = "Čas je před vznikem události.",
    od_udalosti_suffix: str = "od události",
) -> tuple[str, str] | None:
    if reference_dt is None or target_dt is None:
        return None
    total_seconds = int((target_dt - reference_dt).total_seconds())
    if total_seconds < 0:
        return (pred_udalosti_text, "#c62828")
    total_minutes = total_seconds // 60
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    if h and m:
        body = f"{h} h {m} min"
    elif h:
        body = f"{h} h"
    else:
        body = f"{m} min"
    return (f"+{body} {od_udalosti_suffix}", casovy_rozdil_barva(total_minutes))

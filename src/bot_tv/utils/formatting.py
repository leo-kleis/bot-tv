from __future__ import annotations

import re
from datetime import datetime

_DURATION_REGEX = re.compile(
    r"(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?"
)


def parse_twitch_duration(duration_str: str) -> int:
    """Parsea una cadena de duración de Twitch (ej. '3h8m33s', '45m') a segundos."""
    if not duration_str:
        return 0
    match = _DURATION_REGEX.fullmatch(duration_str)
    if not match:
        return 0
    parts = match.groupdict()
    hours = int(parts["hours"]) if parts.get("hours") else 0
    minutes = int(parts["minutes"]) if parts.get("minutes") else 0
    seconds = int(parts["seconds"]) if parts.get("seconds") else 0
    return hours * 3600 + minutes * 60 + seconds


def format_date(iso_str: str | None) -> str:
    """Formatea un string ISO a un formato legible por humanos en español."""
    if not iso_str:
        return "Desconocida"
    try:
        clean_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str).astimezone()
        meses = [
            "Ene",
            "Feb",
            "Mar",
            "Abr",
            "May",
            "Jun",
            "Jul",
            "Ago",
            "Sep",
            "Oct",
            "Nov",
            "Dic",
        ]
        mes = meses[dt.month - 1]
        return f"{dt.day:02d} {mes} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return iso_str

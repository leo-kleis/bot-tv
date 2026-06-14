from __future__ import annotations

from datetime import datetime


def format_date(iso_str: str | None) -> str:
    """Formatea un string ISO a un formato legible por humanos en español."""
    if not iso_str:
        return "Desconocida"
    try:
        clean_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
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

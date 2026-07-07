"""Modelos de datos: RawOffer (lo que entrega cada adapter) y Offer (schema común).

Ver SDD §3.1. Regla: sin url válida la oferta se descarta (lo aplica el normalizer).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum


class Remote(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    UNKNOWN = "unknown"


# Para el filtro duro max_seniority: unknown no participa (nunca castiga en silencio).
SENIORITY_ORDER = {"junior": 0, "mid": 1, "senior": 2, "lead": 3}


class English(str, Enum):
    NONE = "none"
    BASIC = "basic"
    CONVERSATIONAL = "conversational"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


DESCRIPTION_MAX = 5000


def make_id(source: str, url: str) -> str:
    """id determinístico: hash de source + url."""
    return hashlib.sha1(f"{source}|{url}".encode("utf-8")).hexdigest()[:16]


@dataclass
class RawOffer:
    """Salida cruda de un adapter. El normalizer la convierte en Offer o la descarta."""

    source: str
    title: str = ""
    company: str = ""
    url: str = ""
    location: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = "USD"
    salary_period: str = "month"  # "month" | "year" | "hour"
    remote_hint: str = ""  # texto libre de la fuente sobre modalidad
    posted_at: datetime | None = None


@dataclass
class Offer:
    """Schema común. Fechas en ISO 8601 (str) para viajar sin fricción a SQLite/JSON."""

    id: str
    source: str
    title: str
    company: str
    url: str
    location: str = ""
    remote: str = Remote.UNKNOWN.value
    salary_min: int | None = None  # siempre USD/mes
    salary_max: int | None = None
    stack: list[str] = field(default_factory=list)
    seniority: str = Seniority.UNKNOWN.value
    english_required: str = English.UNKNOWN.value
    description: str = ""
    posted_at: str = ""
    fetched_at: str = ""
    date_estimated: bool = False
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"Offer sin url válida: {self.url!r}")
        if not self.title.strip():
            raise ValueError("Offer sin título")
        if not self.company.strip():
            raise ValueError("Offer sin empresa")
        self.description = self.description[:DESCRIPTION_MAX]

    def to_dict(self) -> dict:
        return asdict(self)

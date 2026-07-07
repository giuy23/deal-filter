"""Limpieza y mapeo de RawOffer al schema común Offer (SDD §3.1).

Todas las inferencias (remote, seniority, inglés, stack) son heurísticas por
keywords. Cuando no hay señal, el valor es `unknown` — el scorer lo trata
neutro, nunca castiga en silencio (SDD §9.2).
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from .models import (
    DESCRIPTION_MAX,
    English,
    Offer,
    RawOffer,
    Remote,
    Seniority,
    make_id,
)

# --- Stack: sinónimos → tag canónico (minúsculas) ---------------------------
CANONICAL_TAGS = {
    "node.js": "nodejs", "node": "nodejs", "nodejs": "nodejs",
    "javascript": "javascript", "ecmascript": "javascript",
    "typescript": "typescript",
    "react.js": "react", "reactjs": "react", "react": "react",
    "react native": "react-native",
    "vue.js": "vue", "vuejs": "vue", "vue": "vue",
    "nest.js": "nestjs", "nestjs": "nestjs",
    "next.js": "nextjs", "nextjs": "nextjs",
    "angular": "angular", "astro": "astro", "svelte": "svelte",
    "php": "php", "laravel": "laravel", "codeigniter": "codeigniter",
    "symfony": "symfony", "wordpress": "wordpress",
    "python": "python", "django": "django", "flask": "flask", "fastapi": "fastapi",
    "ruby": "ruby", "rails": "rails", "ruby on rails": "rails",
    "java": "java", "spring": "spring", "kotlin": "kotlin", "swift": "swift",
    "c#": "csharp", ".net": "dotnet", "dotnet": "dotnet",
    "golang": "go", "rust": "rust", "elixir": "elixir", "scala": "scala",
    "mysql": "mysql", "mariadb": "mysql",
    "postgres": "postgresql", "postgresql": "postgresql",
    "sql server": "sqlserver", "mongodb": "mongodb", "redis": "redis",
    "sqlite": "sqlite", "sql": "sql", "graphql": "graphql",
    "docker": "docker", "kubernetes": "kubernetes", "k8s": "kubernetes",
    "aws": "aws", "gcp": "gcp", "azure": "azure",
    "nginx": "nginx", "apache": "apache", "linux": "linux",
    "git": "git", "ci/cd": "cicd", "terraform": "terraform",
    "html": "html", "css": "css", "sass": "sass", "tailwind": "tailwind",
    "jquery": "jquery", "bootstrap": "bootstrap",
}

# Patrones precompilados con límites de palabra tolerantes a "c#", ".net", "node.js"
_TAG_PATTERNS = [
    (re.compile(r"(?<![\w./#+-])" + re.escape(k) + r"(?![\w#+])"), v)
    for k, v in CANONICAL_TAGS.items()
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# --- Modalidad -------------------------------------------------------------
_HYBRID_RE = re.compile(r"h[íi]brid|hybrid|semipresencial", re.I)
_ONSITE_RE = re.compile(r"on-?site|presencial|in[- ]office|100% oficina", re.I)
_REMOTE_RE = re.compile(
    r"remote|remoto|teletrabajo|work from home|wfh|home office|anywhere", re.I
)

# --- Seniority (el orden de chequeo importa: "semi senior" antes que "senior") ---
_LEAD_RE = re.compile(
    r"\b(lead|principal|staff (engineer|developer)|tech ?lead|l[íi]der t[ée]cnico|architect|arquitecto)\b",
    re.I,
)
_MID_RE = re.compile(r"\bsemi[- ]?senior\b|\bssr\b|\bmid[- ]?level\b|\bintermediate\b", re.I)
_SENIOR_RE = re.compile(r"\bsenior\b|\bsr\.?\b", re.I)
_JUNIOR_RE = re.compile(r"\bjunior\b|\bjr\.?\b|\btrainee\b|\bintern(ship)?\b|\bpracticante\b", re.I)

# --- Inglés ----------------------------------------------------------------
_EN_ADVANCED_RE = re.compile(
    r"fluent (in )?english|english fluency|advanced english|english[:\s]+advanced"
    r"|ingl[ée]s avanzado|native english|excellent (written and spoken )?english"
    r"|proficien(t|cy) in english|\bc1\b|\bc2\b",
    re.I,
)
_EN_CONVERSATIONAL_RE = re.compile(
    r"conversational english|intermediate english|ingl[ée]s intermedio|english[:\s]+intermediate|\bb2\b",
    re.I,
)
_EN_BASIC_RE = re.compile(r"basic english|ingl[ée]s b[áa]sico|\bb1\b|reading english", re.I)


def strip_html(text: str) -> str:
    """HTML → texto plano compacto."""
    text = _HTML_TAG_RE.sub(" ", text or "")  # primero quita tags HTML reales
    text = html.unescape(text)  # luego desescapea entities (&nbsp; → espacio, &lt; → <)
    return _WS_RE.sub(" ", text).strip()


def extract_stack(raw_tags: list[str], free_text: str) -> list[str]:
    """Tags de la fuente + escaneo del texto libre, todo canónico y sin duplicados."""
    found: list[str] = []
    for tag in raw_tags:
        canonical = CANONICAL_TAGS.get(tag.strip().lower())
        if canonical and canonical not in found:
            found.append(canonical)
    text = free_text.lower()
    for pattern, canonical in _TAG_PATTERNS:
        if canonical not in found and pattern.search(text):
            found.append(canonical)
    return found


def infer_remote(text: str) -> str:
    if _HYBRID_RE.search(text):
        return Remote.HYBRID.value
    if _ONSITE_RE.search(text):
        return Remote.ONSITE.value
    if _REMOTE_RE.search(text):
        return Remote.REMOTE.value
    return Remote.UNKNOWN.value


def infer_seniority(text: str) -> str:
    if _LEAD_RE.search(text):
        return Seniority.LEAD.value
    if _MID_RE.search(text):
        return Seniority.MID.value
    if _SENIOR_RE.search(text):
        return Seniority.SENIOR.value
    if _JUNIOR_RE.search(text):
        return Seniority.JUNIOR.value
    return Seniority.UNKNOWN.value


def infer_english(text: str) -> str:
    if _EN_ADVANCED_RE.search(text):
        return English.ADVANCED.value
    if _EN_CONVERSATIONAL_RE.search(text):
        return English.CONVERSATIONAL.value
    if _EN_BASIC_RE.search(text):
        return English.BASIC.value
    return English.UNKNOWN.value


def to_usd_month(
    value: float | None, currency: str, period: str, rates: dict[str, float]
) -> int | None:
    """SIEMPRE a USD/mes para poder comparar (SDD §3.1)."""
    if value is None or value <= 0:
        return None
    usd = value * rates.get((currency or "USD").upper(), 1.0)
    if period == "year":
        usd /= 12
    elif period == "hour":
        usd *= 160  # jornada full-time aproximada
    return int(round(usd))


def normalize(raw: RawOffer, currency_rates: dict[str, float]) -> Offer | None:
    """RawOffer → Offer, o None si no cumple lo obligatorio (title/company/url)."""
    url = (raw.url or "").strip()
    title = strip_html(raw.title)
    company = strip_html(raw.company)
    if not url.startswith(("http://", "https://")) or not title or not company:
        return None

    description = strip_html(raw.description)[:DESCRIPTION_MAX]
    search_text = " ".join([title, raw.location, raw.remote_hint, description])

    salary_min = to_usd_month(raw.salary_min, raw.salary_currency, raw.salary_period, currency_rates)
    salary_max = to_usd_month(raw.salary_max, raw.salary_currency, raw.salary_period, currency_rates)
    if salary_min and salary_max and salary_min > salary_max:
        salary_min, salary_max = salary_max, salary_min

    now = datetime.now(timezone.utc)
    date_estimated = raw.posted_at is None
    posted = raw.posted_at or now
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)

    return Offer(
        id=make_id(raw.source, url),
        source=raw.source,
        title=title,
        company=company,
        url=url,
        location=strip_html(raw.location),
        remote=infer_remote(search_text),
        salary_min=salary_min,
        salary_max=salary_max,
        stack=extract_stack(raw.tags, search_text),
        seniority=infer_seniority(title + " " + description),
        english_required=infer_english(search_text),
        description=description,
        posted_at=posted.isoformat(),
        fetched_at=now.isoformat(),
        date_estimated=date_estimated,
    )

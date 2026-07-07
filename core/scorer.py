"""Motor de pesos (SDD §4).

Dos niveles: filtros duros (descartan sin puntuar) y pesos blandos (0-100).
El breakdown se guarda SIEMPRE — transparencia total para calibrar los pesos.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .models import Offer, SENIORITY_ORDER

_LATAM_RE = re.compile(
    r"latam|latin ?america|latinoam[ée]rica|south america|gmt[-−–]5|utc[-−–]5"
    r"|espa[ñn]ol|spanish|\bper[úu]\b|\bperu\b|americas[- ]?(only|based)|chile|colombia|m[ée]xico|argentina",
    re.I,
)
# Fuentes intrínsecamente LATAM: no necesitan mencionar la región.
_LATAM_SOURCES = {"getonboard", "computrabajo"}

FRESHNESS_WINDOW_DAYS = 30


def load_profile(path: str | Path = "config/profile.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def weights_total(profile: dict) -> float:
    return sum(w["weight"] for w in profile["weights"].values())


def validate_profile(profile: dict) -> list[str]:
    """Lista de problemas (vacía = OK). El CLI avisa, no revienta (SDD §4.3)."""
    problems = []
    total = weights_total(profile)
    if abs(total - 100) > 0.01:
        problems.append(f"Los pesos suman {total}, deberían sumar 100")
    curve = profile.get("salary_curve", {})
    if curve.get("floor_usd_month", 0) >= curve.get("ceiling_usd_month", 1):
        problems.append("salary_curve: floor debe ser menor que ceiling")
    return problems


# --------------------------- Filtros duros ----------------------------------

def passes_hard_filters(offer: Offer, hard: dict) -> tuple[bool, str]:
    """(pasa, motivo_de_descarte)."""
    title_low = offer.title.lower()
    for kw in hard.get("exclude_title_keywords") or []:
        if kw.lower() in title_low:
            return False, f"título contiene {kw!r}"

    max_sen = hard.get("max_seniority")
    if max_sen and offer.seniority in SENIORITY_ORDER:
        if SENIORITY_ORDER[offer.seniority] > SENIORITY_ORDER[max_sen]:
            return False, f"seniority {offer.seniority} > {max_sen}"

    min_salary = hard.get("min_salary_usd_month")
    if min_salary and offer.salary_max is not None and offer.salary_max < min_salary:
        return False, f"salario máx {offer.salary_max} < {min_salary} USD/mes"

    if offer.english_required in (hard.get("exclude_english") or []):
        return False, f"exige inglés {offer.english_required}"

    return True, ""


# --------------------------- Factores blandos (0..1) ------------------------

def stack_match_factor(stack: list[str], my_stack: dict) -> float:
    """Σ(matches × factor de nivel) / Σ(stack de la oferta), con piso si ≥2 core."""
    if not stack:
        return 0.3  # sin datos = neutro-bajo, no castigo total
    level_factor: dict[str, float] = {}
    for tag in my_stack.get("core", []):
        level_factor[tag] = 1.0
    for tag in my_stack.get("secondary", []):
        level_factor.setdefault(tag, 0.6)
    for tag in my_stack.get("learning", []):
        level_factor.setdefault(tag, 0.3)

    total = sum(level_factor.get(tag, 0.0) for tag in stack)
    if total == 0:
        return 0.3  # ninguna coincidencia = neutro-bajo, nunca castigo a 0 (SDD §9.2)
    factor = total / len(stack)
    core_hits = sum(1 for tag in stack if level_factor.get(tag) == 1.0)
    if core_hits >= 2:
        factor = max(factor, 0.6)  # mínimo garantizado (SDD §4.1)
    return min(factor, 1.0)


def salary_factor(offer: Offer, curve: dict) -> float:
    """Curva lineal: bajo el piso=0, sobre el techo=1. Sin dato = 0.5 neutro."""
    bounds = [s for s in (offer.salary_min, offer.salary_max) if s is not None]
    if not bounds:
        return 0.5
    mid = sum(bounds) / len(bounds)
    floor = curve["floor_usd_month"]
    ceiling = curve["ceiling_usd_month"]
    return max(0.0, min(1.0, (mid - floor) / (ceiling - floor)))


def latam_factor(offer: Offer) -> float:
    if offer.source in _LATAM_SOURCES:
        return 1.0
    text = " ".join([offer.title, offer.location, offer.description])
    return 1.0 if _LATAM_RE.search(text) else 0.0


def freshness_factor(offer: Offer, now: datetime | None = None) -> float:
    """Decay lineal a 0 en 30 días."""
    now = now or datetime.now(timezone.utc)
    try:
        posted = datetime.fromisoformat(offer.posted_at)
    except ValueError:
        return 0.5
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - posted).total_seconds() / 86400)
    return max(0.0, 1.0 - age_days / FRESHNESS_WINDOW_DAYS)


def _values_factor(value: str, spec: dict, default: float = 0.5) -> float:
    return float(spec.get("values", {}).get(value, default))


def score_offer(offer: Offer, profile: dict, now: datetime | None = None) -> Offer:
    """Calcula score y breakdown IN PLACE y devuelve la oferta."""
    weights = profile["weights"]
    factors = {
        "stack_match": stack_match_factor(offer.stack, profile["my_stack"]),
        "remote": _values_factor(offer.remote, weights["remote"]),
        "salary": salary_factor(offer, profile["salary_curve"]),
        "seniority_fit": _values_factor(offer.seniority, weights["seniority_fit"]),
        "latam_friendly": latam_factor(offer),
        "english_fit": _values_factor(offer.english_required, weights["english_fit"]),
        "freshness": freshness_factor(offer, now),
    }
    breakdown = {
        name: round(weights[name]["weight"] * factor, 1)
        for name, factor in factors.items()
    }
    offer.score_breakdown = breakdown
    offer.score = round(sum(breakdown.values()), 1)
    return offer


def score_all(
    offers: list[Offer], profile: dict, now: datetime | None = None
) -> tuple[list[Offer], list[tuple[Offer, str]]]:
    """Aplica filtros duros y puntúa. Devuelve (aceptadas ordenadas, descartadas+motivo)."""
    hard = profile.get("hard_filters", {})
    kept: list[Offer] = []
    discarded: list[tuple[Offer, str]] = []
    for offer in offers:
        ok, reason = passes_hard_filters(offer, hard)
        if not ok:
            discarded.append((offer, reason))
            continue
        kept.append(score_offer(offer, profile, now))
    kept.sort(key=lambda o: o.score, reverse=True)
    return kept, discarded

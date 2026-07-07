"""Deduplicación (SDD §3.1): hash exacto + fuzzy por similitud title+company.

Regla: dos ofertas con id igual son duplicado exacto. Para fuzzy, si
title+company similitud > 0.85 y misma fuente, consideramos duplicado.
"""
from __future__ import annotations

import difflib
from collections import defaultdict

from .models import Offer


def fuzzy_similarity(s1: str, s2: str, cutoff: float = 0.6) -> float:
    """Similitud de Ratcliff/Obershelp [0..1]."""
    return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def fuzzy_key(offer: Offer) -> str:
    """Clave para comparación fuzzy: title + company + source."""
    return f"{offer.title}|{offer.company}|{offer.source}".lower()


def dedupe(offers: list[Offer], fuzzy_cutoff: float = 0.85) -> tuple[list[Offer], list[Offer]]:
    """Deduplicación exacta (por id) + fuzzy. Devuelve (únicos, duplicados_descartados)."""
    seen_ids: dict[str, Offer] = {}
    seen_fuzzy: list[Offer] = []
    duplicates: list[Offer] = []

    for offer in offers:
        # Exacto: hash de source + url
        if offer.id in seen_ids:
            duplicates.append(offer)
            continue

        # Fuzzy: comparar contra los que ya pasaron
        is_fuzzy_dup = False
        for prev in seen_fuzzy:
            sim = fuzzy_similarity(
                f"{offer.title} {offer.company}", f"{prev.title} {prev.company}", 0.6
            )
            if sim > fuzzy_cutoff and offer.source == prev.source:
                is_fuzzy_dup = True
                duplicates.append(offer)
                break

        if not is_fuzzy_dup:
            seen_ids[offer.id] = offer
            seen_fuzzy.append(offer)

    kept = sorted(seen_ids.values(), key=lambda o: o.id)  # orden determinístico
    return kept, duplicates

"""Tests de deduplicación (exacta + fuzzy)."""
import pytest

from core.models import Offer
from core.dedupe import dedupe


def test_dedupe_exact():
    """Deduplicación exacta por id."""
    o1 = Offer(
        id="exact-1",
        source="test",
        title="Job",
        company="Corp",
        url="https://example.com/1",
    )
    o1_dup = Offer(
        id="exact-1",  # mismo id
        source="test",
        title="Job Duplicated",
        company="Corp",
        url="https://example.com/1",
    )
    o2 = Offer(
        id="exact-2",
        source="test",
        title="Another",
        company="Corp",
        url="https://example.com/2",
    )

    kept, discarded = dedupe([o1, o1_dup, o2])

    assert len(kept) == 2
    assert len(discarded) == 1
    assert discarded[0].id == "exact-1"


def test_dedupe_fuzzy():
    """Deduplicación fuzzy (title+company similitud > 0.85)."""
    o1 = Offer(
        id="fuzzy-1",
        source="remoteok",
        title="Senior PHP Developer",
        company="TechCorp USA",
        url="https://example.com/1",
    )
    o1_fuzzy = Offer(
        id="fuzzy-2",
        source="remoteok",
        title="Senior PHP Developer (Remote)",  # muy similar
        company="TechCorp USA",
        url="https://example.com/2",
    )
    o2 = Offer(
        id="fuzzy-3",
        source="remoteok",
        title="Junior React Developer",  # diferente
        company="OtherCorp",
        url="https://example.com/3",
    )

    kept, discarded = dedupe([o1, o1_fuzzy, o2], fuzzy_cutoff=0.85)

    assert len(kept) == 2
    assert len(discarded) == 1
    assert any(d.id == "fuzzy-2" for d in discarded)


def test_dedupe_fuzzy_different_source():
    """Fuzzy no activa si son de diferentes fuentes."""
    o1 = Offer(
        id="src-1",
        source="remoteok",
        title="Senior PHP Developer",
        company="TechCorp",
        url="https://example.com/1",
    )
    o2 = Offer(
        id="src-2",
        source="getonboard",  # diferente fuente
        title="Senior PHP Developer",
        company="TechCorp",
        url="https://example.com/2",
    )

    kept, discarded = dedupe([o1, o2], fuzzy_cutoff=0.85)

    # Ambas pasan porque son de diferentes fuentes
    assert len(kept) == 2
    assert len(discarded) == 0


def test_dedupe_preserves_order():
    """Las ofertas únicas quedan ordenadas por id determinísticamente."""
    offers = [
        Offer(
            id="z-1",
            source="test",
            title="Senior Backend Engineer",
            company="TechCorp",
            url="https://example.com/z",
        ),
        Offer(
            id="a-1",
            source="test",
            title="Frontend Developer React",
            company="StartupAI",
            url="https://example.com/a",
        ),
    ]

    kept, _ = dedupe(offers)

    # Deben estar ordenados por id
    assert kept[0].id == "a-1"
    assert kept[1].id == "z-1"

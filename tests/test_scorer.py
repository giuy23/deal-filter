"""Tests del motor de pesos (scorer)."""
from datetime import datetime, timedelta, timezone

import pytest

from core.models import English, Offer, Remote, Seniority
from core.scorer import (
    freshness_factor,
    latam_factor,
    salary_factor,
    score_all,
    score_offer,
    stack_match_factor,
    validate_profile,
    weights_total,
)


def test_validate_profile(profile):
    """El profile.yaml debe tener pesos que sumen 100."""
    problems = validate_profile(profile)
    assert not problems, f"Profile tiene problemas: {problems}"
    assert weights_total(profile) == 100


def test_stack_match_factor(profile):
    """Stack matching con niveles de factor."""
    my_stack = profile["my_stack"]

    # Todos core: 1.0
    assert stack_match_factor(["php", "javascript", "mysql"], my_stack) == 1.0

    # Todos secondary: 0.6
    assert stack_match_factor(["laravel", "vue"], my_stack) == 0.6

    # Todos learning: 0.3
    assert stack_match_factor(["python", "react"], my_stack) == 0.3

    # Mix: (1 + 0.6 + 0.3) / 3 = 0.63
    assert abs(stack_match_factor(["php", "laravel", "python"], my_stack) - 0.63) < 0.01

    # Ninguno coincide: 0.3 (mínimo, no castigo)
    assert stack_match_factor(["rust", "go", "java"], my_stack) == 0.3

    # ≥2 core: garantiza factor ≥ 0.6 aunque haya noise
    result = stack_match_factor(["php", "javascript", "rust", "go"], my_stack)
    assert result >= 0.6


def test_salary_factor(profile):
    """Curva lineal: floor=0, ceiling=1."""
    curve = profile["salary_curve"]

    # En el piso
    o_floor = Offer(
        id="test",
        source="test",
        title="Low",
        company="Corp",
        url="https://example.com",
        salary_min=curve["floor_usd_month"],
        salary_max=curve["floor_usd_month"],
    )
    assert salary_factor(o_floor, curve) < 0.01

    # En el techo
    o_ceiling = Offer(
        id="test",
        source="test",
        title="High",
        company="Corp",
        url="https://example.com",
        salary_min=curve["ceiling_usd_month"],
        salary_max=curve["ceiling_usd_month"],
    )
    assert salary_factor(o_ceiling, curve) > 0.99

    # En el medio
    mid = (curve["floor_usd_month"] + curve["ceiling_usd_month"]) / 2
    o_mid = Offer(
        id="test",
        source="test",
        title="Mid",
        company="Corp",
        url="https://example.com",
        salary_min=int(mid),
        salary_max=int(mid),
    )
    assert 0.49 < salary_factor(o_mid, curve) < 0.51

    # Sin salario: 0.5 (neutro)
    o_unknown = Offer(
        id="test",
        source="test",
        title="Unknown",
        company="Corp",
        url="https://example.com",
    )
    assert salary_factor(o_unknown, curve) == 0.5


def test_latam_factor(profile):
    """Identifica fuentes y menciones LATAM."""
    # Getonboard es intrínsecamente LATAM
    o_latam_source = Offer(
        id="test",
        source="getonboard",
        title="Dev",
        company="Corp",
        url="https://example.com",
    )
    assert latam_factor(o_latam_source) == 1.0

    # RemoteOK con mención LATAM
    o_latam_text = Offer(
        id="test",
        source="remoteok",
        title="Dev for LATAM",
        company="Corp",
        url="https://example.com",
    )
    assert latam_factor(o_latam_text) == 1.0

    # RemoteOK sin mención LATAM
    o_no_latam = Offer(
        id="test",
        source="remoteok",
        title="Dev",
        company="Corp",
        url="https://example.com",
        location="New York",
    )
    assert latam_factor(o_no_latam) == 0.0


def test_freshness_factor(profile):
    """Decay lineal en 30 días."""
    now = datetime.now(timezone.utc)

    # Hoy: 1.0
    o_today = Offer(
        id="test",
        source="test",
        title="New",
        company="Corp",
        url="https://example.com",
        posted_at=now.isoformat(),
    )
    assert freshness_factor(o_today, now) > 0.99

    # Hace 15 días: ~0.5
    o_mid = Offer(
        id="test",
        source="test",
        title="Mid",
        company="Corp",
        url="https://example.com",
        posted_at=(now - timedelta(days=15)).isoformat(),
    )
    assert 0.48 < freshness_factor(o_mid, now) < 0.52

    # Hace 30 días: 0.0
    o_old = Offer(
        id="test",
        source="test",
        title="Old",
        company="Corp",
        url="https://example.com",
        posted_at=(now - timedelta(days=30)).isoformat(),
    )
    assert freshness_factor(o_old, now) < 0.01


def test_score_offer_synthetic(synthetic_offers, profile):
    """Verifica que el score tenga sentido para cada oferta sintética."""
    now = datetime.now(timezone.utc)
    for offer in synthetic_offers:
        score_offer(offer, profile, now)
        assert 0 <= offer.score <= 100
        assert offer.score_breakdown
        assert abs(sum(offer.score_breakdown.values()) - offer.score) < 0.1


def test_score_all_with_hard_filters(profile):
    """Filtra ofertas que incumplen hard filters antes de puntuar."""
    # Oferta que incumple max_seniority (lead)
    o_lead = Offer(
        id="test-lead",
        source="test",
        title="Tech Lead",
        company="Corp",
        url="https://example.com/1",
        seniority=Seniority.LEAD.value,
    )

    # Oferta que incumple exclude_english (advanced)
    o_en_adv = Offer(
        id="test-en",
        source="test",
        title="Dev",
        company="Corp",
        url="https://example.com/2",
        english_required=English.ADVANCED.value,
    )

    # Oferta válida
    o_ok = Offer(
        id="test-ok",
        source="test",
        title="Developer",
        company="Corp",
        url="https://example.com/3",
        seniority=Seniority.MID.value,
        english_required=English.CONVERSATIONAL.value,
    )

    kept, discarded = score_all([o_lead, o_en_adv, o_ok], profile)

    assert len(kept) == 1
    assert kept[0].id == "test-ok"
    assert len(discarded) == 2
    assert discarded[0][0].id == "test-lead"
    assert discarded[1][0].id == "test-en"

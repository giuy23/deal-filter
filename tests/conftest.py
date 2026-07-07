"""Fixtures compartidas para los tests."""
import pytest
from datetime import datetime, timedelta, timezone

from core.models import Offer, RawOffer, Remote, Seniority, English
from core.scorer import load_profile


@pytest.fixture
def profile():
    """Carga el profile.yaml de la config (debe existir)."""
    return load_profile("config/profile.yaml")


# 5 ofertas sintéticas cubriendo extremos para tests del scorer
@pytest.fixture
def synthetic_offers() -> list[Offer]:
    """Conjunto de prueba que cubre casos extremos."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # 1. Jackpot: todo coincide (remote, stack core, senior, buen salario)
    o1 = Offer(
        id="synth-1",
        source="remoteok",
        title="Senior PHP Developer (Remote)",
        company="TechCorp USA",
        url="https://example.com/1",
        location="Anywhere",
        remote=Remote.REMOTE.value,
        salary_min=3000,
        salary_max=4000,
        stack=["php", "laravel", "mysql", "javascript"],
        seniority=Seniority.SENIOR.value,
        english_required=English.NONE.value,
        description="Looking for a senior PHP dev with Laravel and Vue experience.",
        posted_at=week_ago.isoformat(),
        fetched_at=now.isoformat(),
    )

    # 2. Bueno pero onsite y sin info de sueldo
    o2 = Offer(
        id="synth-2",
        source="getonboard",
        title="PHP Developer (LATAM-friendly)",
        company="StartupPE",
        url="https://example.com/2",
        location="Lima, Peru",
        remote=Remote.ONSITE.value,
        salary_min=None,
        salary_max=None,
        stack=["php", "codeigniter"],
        seniority=Seniority.MID.value,
        english_required=English.CONVERSATIONAL.value,
        description="Buscamos desarrollador PHP con experiencia en Codeigniter para LATAM.",
        posted_at=now.isoformat(),
        fetched_at=now.isoformat(),
    )

    # 3. Sin stack matches, junior, bajo salario
    o3 = Offer(
        id="synth-3",
        source="remoteok",
        title="Junior Java Developer",
        company="OldCorp",
        url="https://example.com/3",
        location="USA",
        remote=Remote.ONSITE.value,
        salary_min=500,
        salary_max=800,
        stack=["java", "spring"],
        seniority=Seniority.JUNIOR.value,
        english_required=English.ADVANCED.value,
        description="Fresh Java dev needed for legacy system.",
        posted_at=(now - timedelta(days=35)).isoformat(),  # muy vieja
        fetched_at=now.isoformat(),
    )

    # 4. Stack secundario, híbrido, sin seniority info
    o4 = Offer(
        id="synth-4",
        source="remoteok",
        title="Web Developer",
        company="MidSizeCo",
        url="https://example.com/4",
        location="Europe",
        remote=Remote.HYBRID.value,
        salary_min=2000,
        salary_max=2500,
        stack=["vue", "postgresql"],
        seniority=Seniority.UNKNOWN.value,
        english_required=English.UNKNOWN.value,
        description="Looking for someone with Vue and PostgreSQL.",
        posted_at=week_ago.isoformat(),
        fetched_at=now.isoformat(),
    )

    # 5. Stack learning, buen salario, remote
    o5 = Offer(
        id="synth-5",
        source="remoteok",
        title="Python/React Developer (Remote)",
        company="ModernTech",
        url="https://example.com/5",
        location="Remote",
        remote=Remote.REMOTE.value,
        salary_min=2800,
        salary_max=3500,
        stack=["python", "react", "postgresql"],
        seniority=Seniority.MID.value,
        english_required=English.CONVERSATIONAL.value,
        description="Full stack with Python backend and React frontend.",
        posted_at=week_ago.isoformat(),
        fetched_at=now.isoformat(),
    )

    return [o1, o2, o3, o4, o5]


@pytest.fixture
def raw_offer_minimal() -> RawOffer:
    """RawOffer mínimo válido."""
    return RawOffer(
        source="test",
        title="Test Job",
        company="TestCorp",
        url="https://example.com/test",
    )

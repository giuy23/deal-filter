"""Tests del normalizer (extracción de heurísticas)."""
import pytest

from core.models import English, RawOffer, Remote, Seniority
from core.normalizer import (
    extract_stack,
    infer_english,
    infer_remote,
    infer_seniority,
    normalize,
    strip_html,
    to_usd_month,
)


def test_strip_html():
    """HTML → texto plano compacto."""
    assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"
    assert strip_html("&nbsp;&lt;tag&gt;") == "<tag>"
    assert strip_html("  multiple   spaces  ") == "multiple spaces"


def test_extract_stack():
    """Tags canónicos de múltiples fuentes + escaneo de texto libre."""
    # Tags de la fuente
    tags = extract_stack(["php", "javascript"], "")
    assert "php" in tags and "javascript" in tags

    # Sinónimos + canonicalización
    tags = extract_stack(["node.js", "react.js"], "")
    assert "nodejs" in tags and "react" in tags

    # Escaneo de texto libre
    tags = extract_stack([], "We use Python and React with PostgreSQL")
    assert "python" in tags and "react" in tags and "postgresql" in tags

    # Sin duplicados
    tags = extract_stack(["php"], "Somos una shop de PHP")
    assert tags.count("php") == 1


def test_infer_remote():
    """Detecta modalidad de trabajo."""
    assert infer_remote("remote position") == Remote.REMOTE.value
    assert infer_remote("work from home") == Remote.REMOTE.value
    assert infer_remote("híbrido") == Remote.HYBRID.value
    assert infer_remote("presencial") == Remote.ONSITE.value
    assert infer_remote("100% oficina") == Remote.ONSITE.value
    assert infer_remote("no info") == Remote.UNKNOWN.value


def test_infer_seniority():
    """Detecta nivel de seniority por keywords."""
    # Lead tiene prioridad
    assert infer_seniority("Tech Lead position") == Seniority.LEAD.value

    # Luego senior
    assert infer_seniority("Senior Developer") == Seniority.SENIOR.value

    # Semi-senior
    assert infer_seniority("SSR (semi-senior)") == Seniority.MID.value

    # Junior
    assert infer_seniority("Junior engineer trainee") == Seniority.JUNIOR.value

    assert infer_seniority("Unknown role") == Seniority.UNKNOWN.value


def test_infer_english():
    """Detecta nivel de inglés requerido."""
    assert infer_english("fluent english required") == English.ADVANCED.value
    assert infer_english("advanced english C2") == English.ADVANCED.value
    assert infer_english("conversational english") == English.CONVERSATIONAL.value
    assert infer_english("intermediate english B2") == English.CONVERSATIONAL.value
    assert infer_english("basic english B1") == English.BASIC.value
    assert infer_english("no English required") == English.UNKNOWN.value


def test_to_usd_month():
    """Conversión a USD/mes con tipos de cambio."""
    rates = {"USD": 1.0, "PEN": 0.27, "EUR": 1.09}

    # USD mensual directo
    assert to_usd_month(1000, "USD", "month", rates) == 1000

    # PEN → USD
    assert to_usd_month(4000, "PEN", "month", rates) == int(4000 * 0.27)

    # Anual → mensual
    assert to_usd_month(12000, "USD", "year", rates) == 1000

    # Hora → mes (160h/mes)
    assert to_usd_month(10, "USD", "hour", rates) == int(10 * 160)

    # Sin dato
    assert to_usd_month(None, "USD", "month", rates) is None
    assert to_usd_month(0, "USD", "month", rates) is None


def test_normalize_minimal(raw_offer_minimal):
    """Conversión mínima: RawOffer → Offer."""
    offer = normalize(raw_offer_minimal, {"USD": 1.0})
    assert offer is not None
    assert offer.title == "Test Job"
    assert offer.company == "TestCorp"
    assert offer.url == "https://example.com/test"
    assert offer.remote == Remote.UNKNOWN.value


def test_normalize_invalid():
    """Oferta sin título/empresa/url se descarta."""
    rates = {"USD": 1.0}

    # Sin título
    raw = RawOffer(source="test", title="", company="Corp", url="https://example.com")
    assert normalize(raw, rates) is None

    # Sin empresa
    raw = RawOffer(source="test", title="Job", company="", url="https://example.com")
    assert normalize(raw, rates) is None

    # URL inválida
    raw = RawOffer(source="test", title="Job", company="Corp", url="not-a-url")
    assert normalize(raw, rates) is None


def test_normalize_with_inference():
    """Normalizer extrae heurísticas."""
    raw = RawOffer(
        source="remoteok",
        title="Senior PHP Developer - Remote",
        company="TechCorp",
        url="https://example.com/job",
        location="Anywhere",
        remote_hint="Remote position, work from home",
        description="We seek a senior PHP dev fluent in English with Laravel, Vue, and MySQL",
        tags=["php", "laravel"],
        salary_min=2000,
        salary_currency="USD",
        salary_period="month",
    )
    offer = normalize(raw, {"USD": 1.0})
    assert offer is not None
    assert offer.remote == Remote.REMOTE.value
    assert offer.seniority == Seniority.SENIOR.value
    assert offer.english_required == English.ADVANCED.value
    assert "php" in offer.stack
    assert "laravel" in offer.stack
    assert "vue" in offer.stack

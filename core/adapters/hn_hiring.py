"""HN Who's Hiring adapter (Algolia API, parsing de texto libre)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import requests

from ..models import RawOffer
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class HnHiringAdapter(BaseAdapter):
    """Fetch desde hilos mensuales de HN 'Who is hiring?' via Algolia."""

    BASE_URL = "https://hn.algolia.com/api/v1/search"

    def __init__(self, keywords: list[str] | None = None, enabled: bool = True):
        super().__init__(enabled)
        self.keywords = keywords or []

    def fetch(self) -> list[RawOffer]:
        if not self.enabled:
            return []

        try:
            # HN: buscar el hilo mensual "Who is hiring?"
            # El hilo se postea el primer día laboral del mes
            response = self.retry_request(
                lambda timeout: requests.get(
                    self.BASE_URL,
                    params={"query": "who is hiring", "numericFilters": "points>100"},
                    timeout=timeout,
                ),
                max_retries=2,
            )
            response.raise_for_status()
            data = response.json()

            # El hilo principal es el primero
            thread_ids = []
            for hit in data.get("hits", []):
                if "Who is hiring" in hit.get("title", ""):
                    thread_ids.append(hit["objectID"])
                    break

            offers = []
            for thread_id in thread_ids:
                thread_offers = self._fetch_thread(thread_id)
                offers.extend(thread_offers)

            logger.info(f"HN Hiring: fetched {len(offers)} offers")
            return offers

        except Exception as e:
            logger.error(f"HN Hiring fetch error: {e}")
            return []

    def _fetch_thread(self, thread_id: str) -> list[RawOffer]:
        """Fetch comments del hilo y parse como ofertas."""
        try:
            response = self.retry_request(
                lambda timeout: requests.get(
                    self.BASE_URL,
                    params={"query": "", "tags": f"story_{thread_id}"},
                    timeout=timeout,
                ),
                max_retries=2,
            )
            response.raise_for_status()
            data = response.json()

            offers = []
            for hit in data.get("hits", []):
                text = hit.get("comment_text", "")
                if not text:
                    continue

                # HN: cada comentario que sea un "HN job post" (patrón común)
                # Extrae título, empresa, localización, stack, url
                if self._should_include(text):
                    offer = self._parse_comment(text, hit)
                    if offer:
                        offers.append(offer)

            return offers
        except Exception as e:
            logger.debug(f"HN thread parse error: {e}")
            return []

    def _should_include(self, text: str) -> bool:
        """Filtra por keywords."""
        if not self.keywords:
            return True
        return any(kw.lower() in text.lower() for kw in self.keywords)

    def _parse_comment(self, text: str, hit: dict) -> RawOffer | None:
        """Parse comment text como oferta (heurístico)."""
        try:
            # Patrones comunes en HN job posts:
            # "Hiring for X role" / "We're looking for X" / "Seeking X"
            # Localización: "Location: ...", "Remote: ...", "Hiring in: ..."
            # Stack: menciones de tecnologías

            lines = text.split("\n")
            title = lines[0][:100]  # Primera línea como título

            # URL: busca http(s)://
            url_match = re.search(r"https?://[^\s\)]+", text)
            url = url_match.group(0) if url_match else ""

            # Localización: busca patrones
            location = self._extract_location(text)

            # Company name: heurístico
            company = hit.get("author", "Anonymous")

            return RawOffer(
                source="hn_hiring",
                title=title,
                company=company,
                url=url,
                location=location,
                description=text[:5000],
                tags=self._extract_stack(text),
                remote_hint=self._extract_remote(text),
                posted_at=self._parse_date(hit.get("created_at")),
            )
        except Exception as e:
            logger.debug(f"HN comment parse error: {e}")
            return None

    @staticmethod
    def _extract_location(text: str) -> str:
        """Extrae localización de patrones comunes."""
        patterns = [
            r"Location:\s*([^\n]*)",
            r"based in\s*([^\n]*)",
            r"based out of\s*([^\n]*)",
            r"Located in\s*([^\n]*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_remote(text: str) -> str:
        """Detecta si es remote."""
        if re.search(r"\bremote\b|\bwork from home\b|\bwfh\b", text, re.IGNORECASE):
            return "remote"
        return ""

    @staticmethod
    def _extract_stack(text: str) -> list[str]:
        """Extrae menciones de tecnologías."""
        # Busca palabras técnicas comunes
        keywords = [
            "Python",
            "JavaScript",
            "PHP",
            "Ruby",
            "Java",
            "Go",
            "Rust",
            "Node",
            "React",
            "Vue",
            "Angular",
            "Django",
            "Rails",
            "Laravel",
        ]
        found = []
        for kw in keywords:
            if re.search(r"\b" + kw + r"\b", text, re.IGNORECASE):
                found.append(kw.lower())
        return found

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse ISO 8601 date."""
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

"""Getonboard adapter (la fuente LATAM tech por excelencia)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from ..models import RawOffer
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class GetonboardAdapter(BaseAdapter):
    """Fetch desde API pública de GetOnBoard."""

    BASE_URL = "https://api.getonboard.com/v0/job_postings"

    def __init__(self, categories: list[str] | None = None, enabled: bool = True):
        super().__init__(enabled)
        self.categories = categories or ["programming"]

    def fetch(self) -> list[RawOffer]:
        if not self.enabled:
            return []

        try:
            # GetOnBoard devuelve paginado; tomamos la primera página
            params = {"categories": ",".join(self.categories), "page": 1}
            response = self.retry_request(
                lambda timeout: requests.get(
                    self.BASE_URL, params=params, timeout=timeout
                ),
                max_retries=3,
            )
            response.raise_for_status()
            data = response.json()

            offers = []
            for item in data.get("results", []):
                offer = self._normalize_item(item)
                if offer:
                    offers.append(offer)

            logger.info(f"Getonboard: fetched {len(offers)} offers")
            return offers

        except Exception as e:
            logger.error(f"Getonboard fetch error: {e}")
            return []

    def _normalize_item(self, item: dict) -> RawOffer | None:
        """API response → RawOffer."""
        try:
            # Getonboard devuelve lista de país con "name" y currency
            country = item.get("country", {}).get("name", "")
            return RawOffer(
                source="getonboard",
                title=item.get("title", ""),
                company=item.get("company", {}).get("name", ""),
                url=item.get("url", ""),
                location=f"{item.get('city', '')}, {country}".strip(", "),
                description=item.get("description", ""),
                tags=item.get("tags", []),
                remote_hint=item.get("modality", "").lower(),
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                salary_currency=item.get("currency", "USD"),
                salary_period="month",
                posted_at=self._parse_date(item.get("created_at")),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Getonboard parse error: {e}")
            return None

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse ISO 8601 date."""
        if not date_str:
            return None
        try:
            # Getonboard usa ISO 8601
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

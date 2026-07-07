"""Adzuna adapter (API con key, cubre múltiples países)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests

from ..models import RawOffer
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class AdzunaAdapter(BaseAdapter):
    """Fetch desde API oficial de Adzuna (requiere ADZUNA_APP_ID y ADZUNA_APP_KEY en env)."""

    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(
        self,
        countries: list[str] | None = None,
        query: str = "",
        results_per_country: int = 50,
        enabled: bool = True,
    ):
        super().__init__(enabled)
        self.app_id = os.getenv("ADZUNA_APP_ID", "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")
        self.countries = countries or ["gb", "us"]
        self.query = query
        self.results_per_country = results_per_country

    def fetch(self) -> list[RawOffer]:
        if not self.enabled or not self.app_id or not self.app_key:
            logger.warning("Adzuna: missing API credentials")
            return []

        offers = []
        for country in self.countries:
            try:
                country_offers = self._fetch_country(country)
                offers.extend(country_offers)
                self.throttle(1)  # Rate limit
            except Exception as e:
                logger.error(f"Adzuna fetch error for {country}: {e}")

        logger.info(f"Adzuna: fetched {len(offers)} offers")
        return offers

    def _fetch_country(self, country: str) -> list[RawOffer]:
        """Fetch desde un país específico."""
        url = f"{self.BASE_URL}/{country}/search/1"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.results_per_country,
            "what": self.query or "developer",
        }

        response = self.retry_request(
            lambda timeout: requests.get(url, params=params, timeout=timeout),
            max_retries=2,
        )
        response.raise_for_status()
        data = response.json()

        offers = []
        for item in data.get("results", []):
            offer = self._normalize_item(item)
            if offer:
                offers.append(offer)

        return offers

    def _normalize_item(self, item: dict) -> RawOffer | None:
        """API response → RawOffer."""
        try:
            return RawOffer(
                source="adzuna",
                title=item.get("title", ""),
                company=item.get("company", {}).get("display_name", ""),
                url=item.get("redirect_url", ""),
                location=item.get("location", {}).get("display_name", ""),
                description=item.get("description", ""),
                tags=[],  # Adzuna no devuelve tags
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                salary_currency=item.get("salary_currency", "GBP"),
                salary_period="year",  # Adzuna devuelve salarios anuales
                posted_at=self._parse_date(item.get("created")),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Adzuna parse error: {e}")
            return None

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse ISO 8601 date."""
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

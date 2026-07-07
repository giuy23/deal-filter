"""Remote OK adapter (API pública JSON, sin auth requerida)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from ..models import RawOffer
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class RemoteOkAdapter(BaseAdapter):
    """Fetch desde remoteok.com/api."""

    BASE_URL = "https://remoteok.com/api"
    TIMEOUT = 15

    def __init__(self, keywords: list[str] | None = None, enabled: bool = True):
        super().__init__(enabled)
        self.keywords = keywords or []

    def fetch(self) -> list[RawOffer]:
        if not self.enabled:
            return []

        try:
            # Remote OK: la API devuelve todas las ofertas en un JSON
            # El primer item es metadata, el resto son ofertas
            response = self.retry_request(
                lambda timeout: requests.get(f"{self.BASE_URL}", timeout=timeout),
                max_retries=3,
            )
            response.raise_for_status()
            data = response.json()

            offers = []
            for item in data[1:]:  # Saltar el primer item que es metadata
                if self._should_include(item):
                    offer = self._normalize_item(item)
                    if offer:
                        offers.append(offer)

            logger.info(f"RemoteOK: fetched {len(offers)} offers")
            return offers

        except Exception as e:
            logger.error(f"RemoteOK fetch error: {e}")
            return []

    def _should_include(self, item: dict) -> bool:
        """Filtra por keywords si están configurados."""
        if not self.keywords:
            return True
        text = (item.get("title", "") + " " + item.get("description", "")).lower()
        return any(kw.lower() in text for kw in self.keywords)

    def _normalize_item(self, item: dict) -> RawOffer | None:
        """Raw API response → RawOffer."""
        try:
            # RemoteOK: position es el título, company es la empresa
            url = f"https://remoteok.com/{item.get('slug', '')}" if item.get("slug") else ""
            return RawOffer(
                source="remoteok",
                title=item.get("position", ""),
                company=item.get("company", ""),
                url=url,
                location="Remote",  # RemoteOK es siempre remoto
                description=item.get("description", ""),
                tags=item.get("tags", []),
                remote_hint="remote",
                salary_min=self._parse_salary(item.get("salary")),
                salary_max=self._parse_salary(item.get("salary")),
                salary_currency="USD",
                salary_period="month",
                posted_at=datetime.fromtimestamp(item.get("epoch", 0), tz=timezone.utc)
                if item.get("epoch")
                else None,
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"RemoteOK parse error: {e}")
            return None

    @staticmethod
    def _parse_salary(salary_str: str | int | None) -> float | None:
        """Intenta extraer número de string tipo '$3000'."""
        if not salary_str:
            return None
        if isinstance(salary_str, (int, float)):
            return float(salary_str)
        try:
            # Remove $, commas, etc
            clean = "".join(c for c in str(salary_str) if c.isdigit() or c == ".")
            return float(clean) if clean else None
        except (ValueError, TypeError):
            return None

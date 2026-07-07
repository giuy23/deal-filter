"""Computrabajo (Perú) adapter — scraping HTML (frágil, respetar robots.txt)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from ..models import RawOffer
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class ComputrabajoAdapter(BaseAdapter):
    """Fetch desde pe.computrabajo.com (scraping HTML con throttle)."""

    BASE_URL = "https://pe.computrabajo.com"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        query: str = "desarrollador-web",
        max_pages: int = 2,
        throttle_secs: float = 2.0,
        enabled: bool = True,
    ):
        super().__init__(enabled)
        self.query = query
        self.max_pages = max_pages
        self.throttle_secs = throttle_secs

    def fetch(self) -> list[RawOffer]:
        if not self.enabled:
            return []

        offers = []
        try:
            for page in range(1, self.max_pages + 1):
                page_offers = self._fetch_page(page)
                offers.extend(page_offers)
                if page < self.max_pages:
                    self.throttle(self.throttle_secs)  # Respetar robots.txt

            logger.info(f"Computrabajo: fetched {len(offers)} offers")
            return offers

        except Exception as e:
            logger.error(f"Computrabajo fetch error: {e}")
            return []

    def _fetch_page(self, page: int) -> list[RawOffer]:
        """Scrappea una página de resultados."""
        url = f"{self.BASE_URL}/b/{self.query}/p/{page}"
        headers = {"User-Agent": self.USER_AGENT}

        response = self.retry_request(
            lambda timeout: requests.get(url, headers=headers, timeout=timeout),
            max_retries=2,
        )
        response.raise_for_status()
        response.encoding = "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")
        offers = []

        # Selectores CSS: varían según la estructura actual de Computrabajo
        # Esto es lo más frágil; si Computrabajo cambia su HTML, esto revienta.
        job_items = soup.find_all("div", class_="aviso")
        if not job_items:
            # Intentar otro selector
            job_items = soup.find_all("a", class_="info_aviso")

        for item in job_items:
            offer = self._parse_item(item)
            if offer:
                offers.append(offer)

        return offers

    def _parse_item(self, item) -> RawOffer | None:
        """Parse un item HTML como RawOffer."""
        try:
            # Buscar atributos en el HTML
            link = item.find("a")
            if not link:
                return None

            url = link.get("href", "")
            if not url.startswith("http"):
                url = self.BASE_URL + url

            title = link.get_text(strip=True)

            # Company name: buscar elemento específico
            company_elem = item.find("p", class_="empresa")
            company = company_elem.get_text(strip=True) if company_elem else ""

            # Location: buscar elemento específico
            location_elem = item.find("span", class_="ubigeo")
            location = location_elem.get_text(strip=True) if location_elem else ""

            # Descripción: los primeros 500 chars del contenido
            description = item.get_text(strip=True)[:500]

            return RawOffer(
                source="computrabajo",
                title=title,
                company=company,
                url=url,
                location=location,
                description=description,
                tags=[],  # Computrabajo no devuelve tags estructurados
                posted_at=datetime.now(timezone.utc),  # No tenemos fecha exacta
            )
        except Exception as e:
            logger.debug(f"Computrabajo parse error: {e}")
            return None

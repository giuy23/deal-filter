"""Base adapter: contrato común para todas las fuentes (SDD §5)."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from ..models import RawOffer


class BaseAdapter(ABC):
    """Contrato: fetch() -> list[RawOffer], con reintentos y rate-limit propios."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @abstractmethod
    def fetch(self) -> list[RawOffer]:
        """Devuelve lista de RawOffer. Si falla, loguea y devuelve []."""
        pass

    @staticmethod
    def retry_request(
        func, max_retries: int = 3, backoff_base: float = 2.0, timeout: int = 10
    ):
        """Reintentos exponenciales para requests."""
        for attempt in range(max_retries):
            try:
                return func(timeout)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait = backoff_base ** attempt
                time.sleep(wait)

    @staticmethod
    def throttle(seconds: float) -> None:
        """Respeto de rate-limits."""
        time.sleep(seconds)

"""Persistencia: SQLite (histórico NUNCA se borra, solo se marca stale) + export JSON.

SDD §3.2: un histórico es un activo (gráficos de tendencias, análisis de demanda).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Offer


SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    location TEXT,
    remote TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    stack TEXT,                -- JSON list
    seniority TEXT,
    english_required TEXT,
    description TEXT,
    posted_at TEXT,
    fetched_at TEXT,
    date_estimated BOOLEAN,
    score REAL,
    score_breakdown TEXT,       -- JSON dict
    notified BOOLEAN DEFAULT 0, -- para digest
    stale BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    count_fetched INTEGER,
    count_accepted INTEGER,
    count_error INTEGER,
    error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_offers_fetched ON offers(fetched_at);
CREATE INDEX IF NOT EXISTS idx_offers_score ON offers(score DESC);
"""


class Store:
    def __init__(self, db_path: str | Path = "data/offers.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        for stmt in SCHEMA.split(";"):
            if stmt.strip():
                self.conn.execute(stmt)
        self.conn.commit()

    def insert_offers(self, offers: list[Offer], mark_existing_stale: bool = False) -> int:
        """Inserta nuevas ofertas. Si mark_existing_stale=True, marca las viejas como stale."""
        if mark_existing_stale:
            self.conn.execute("UPDATE offers SET stale = 1 WHERE stale = 0")

        inserted = 0
        for offer in offers:
            try:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO offers
                    (id, source, title, company, url, location, remote, salary_min, salary_max,
                     stack, seniority, english_required, description, posted_at, fetched_at,
                     date_estimated, score, score_breakdown, stale)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        offer.id,
                        offer.source,
                        offer.title,
                        offer.company,
                        offer.url,
                        offer.location,
                        offer.remote,
                        offer.salary_min,
                        offer.salary_max,
                        json.dumps(offer.stack),
                        offer.seniority,
                        offer.english_required,
                        offer.description,
                        offer.posted_at,
                        offer.fetched_at,
                        offer.date_estimated,
                        offer.score,
                        json.dumps(offer.score_breakdown),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        self.conn.commit()
        return inserted

    def log_run(
        self, source: str, count_fetched: int, count_accepted: int = 0, error_msg: str = ""
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO runs (timestamp, source, count_fetched, count_accepted, error_msg)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                source,
                count_fetched,
                count_accepted,
                error_msg,
            ),
        )
        self.conn.commit()

    def get_all_offers(self, exclude_stale: bool = False) -> list[Offer]:
        """Lee todas las ofertas de la BD como objetos Offer."""
        where = "WHERE stale = 0" if exclude_stale else ""
        cursor = self.conn.execute(
            f"SELECT * FROM offers {where} ORDER BY fetched_at DESC, score DESC"
        )
        rows = cursor.fetchall()

        cols = [col[0] for col in cursor.description]
        offers = []
        for row in rows:
            data = dict(zip(cols, row))
            # Reconvertir JSON
            data["stack"] = json.loads(data["stack"])
            data["score_breakdown"] = json.loads(data["score_breakdown"])
            # Excluir columnas que no son del Offer
            for key in ("notified", "stale"):
                data.pop(key, None)
            offers.append(Offer(**data))
        return offers

    def export_json(self, output_path: str | Path = "dashboard/public/data/offers.json") -> None:
        """Exporta todas las ofertas (no stale) a JSON para el dashboard."""
        offers = self.get_all_offers(exclude_stale=True)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump([o.to_dict() for o in offers], f, indent=2, ensure_ascii=False)

    def get_unnotified(self, min_score: float = 60) -> list[Offer]:
        """Ofertas nuevas con score ≥ threshold (para digest)."""
        cursor = self.conn.execute(
            "SELECT * FROM offers WHERE stale = 0 AND notified = 0 AND score >= ?"
            " ORDER BY score DESC LIMIT 100",
            (min_score,),
        )
        rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
        offers = []
        for row in rows:
            data = dict(zip(cols, row))
            data["stack"] = json.loads(data["stack"])
            data["score_breakdown"] = json.loads(data["score_breakdown"])
            # Excluir columnas que no son del Offer
            for key in ("notified", "stale"):
                data.pop(key, None)
            offers.append(Offer(**data))
        return offers

    def mark_notified(self, offer_ids: list[str]) -> None:
        """Marca ofertas como ya notificadas (para no re-enviar en el digest)."""
        for oid in offer_ids:
            self.conn.execute("UPDATE offers SET notified = 1 WHERE id = ?", (oid,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

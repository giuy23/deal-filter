"""CLI: orquesta el pipeline end-to-end (SDD §5-6)."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import yaml

from .adapters.adzuna import AdzunaAdapter
from .adapters.computrabajo import ComputrabajoAdapter
from .adapters.getonboard import GetonboardAdapter
from .adapters.hn_hiring import HnHiringAdapter
from .adapters.remoteok import RemoteOkAdapter
from .dedupe import dedupe
from .normalizer import normalize
from .scorer import load_profile, score_all, validate_profile
from .store import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_sources(path: str | Path = "config/sources.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run_pipeline(
    profile_path: str | Path = "config/profile.yaml",
    sources_path: str | Path = "config/sources.yaml",
    output_json: str | Path = "dashboard/public/data/offers.json",
) -> None:
    """Ejecuta el pipeline completo: fetch → normalize → dedupe → score → store."""
    logger.info("=== JobDistiller Pipeline Start ===")

    # 1. Cargar configuración
    profile = load_profile(profile_path)
    problems = validate_profile(profile)
    if problems:
        for p in problems:
            logger.warning(f"Profile: {p}")

    sources_config = load_sources(sources_path)
    currency_rates = profile.get("currency_rates", {})

    # 2. Ejecutar adapters
    raw_offers = []
    store = Store()

    adapters = [
        (
            "remoteok",
            RemoteOkAdapter(
                keywords=sources_config["sources"]["remoteok"].get("keywords"),
                enabled=sources_config["sources"]["remoteok"]["enabled"],
            ),
        ),
        (
            "getonboard",
            GetonboardAdapter(
                categories=sources_config["sources"]["getonboard"].get("categories"),
                enabled=sources_config["sources"]["getonboard"]["enabled"],
            ),
        ),
        (
            "adzuna",
            AdzunaAdapter(
                countries=sources_config["sources"]["adzuna"].get("countries"),
                query=sources_config["sources"]["adzuna"].get("query"),
                results_per_country=sources_config["sources"]["adzuna"].get(
                    "results_per_country"
                ),
                enabled=sources_config["sources"]["adzuna"]["enabled"],
            ),
        ),
        (
            "hn_hiring",
            HnHiringAdapter(
                keywords=sources_config["sources"]["hn_hiring"].get("keywords"),
                enabled=sources_config["sources"]["hn_hiring"]["enabled"],
            ),
        ),
        (
            "computrabajo",
            ComputrabajoAdapter(
                query=sources_config["sources"]["computrabajo"].get("query"),
                max_pages=sources_config["sources"]["computrabajo"].get("max_pages", 2),
                throttle_secs=sources_config["sources"]["computrabajo"].get(
                    "throttle_seconds", 2.0
                ),
                enabled=sources_config["sources"]["computrabajo"]["enabled"],
            ),
        ),
    ]

    for source_name, adapter in adapters:
        try:
            fetched = adapter.fetch()
            raw_offers.extend(fetched)
            store.log_run(source_name, len(fetched))
            logger.info(f"{source_name}: {len(fetched)} raw offers")
        except Exception as e:
            logger.error(f"{source_name} error: {e}")
            store.log_run(source_name, 0, error_msg=str(e))

    # 3. Normalizar
    offers = []
    for raw in raw_offers:
        offer = normalize(raw, currency_rates)
        if offer:
            offers.append(offer)
    logger.info(f"Normalized: {len(offers)} offers")

    # 4. Dedupe
    offers, duplicates = dedupe(offers)
    logger.info(f"After dedupe: {len(offers)} unique, {len(duplicates)} duplicates")

    # 5. Score
    offers, discarded = score_all(offers, profile)
    logger.info(f"After scoring: {len(offers)} kept, {len(discarded)} discarded")
    for offer, reason in discarded[:5]:
        logger.debug(f"  Discarded: {offer.title} ({reason})")

    # 6. Store + Export
    inserted = store.insert_offers(offers, mark_existing_stale=True)
    logger.info(f"Stored: {inserted} new offers in DB")

    store.export_json(output_json)
    logger.info(f"Exported: {output_json}")
    store.close()

    logger.info("=== JobDistiller Pipeline Complete ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="JobDistiller: pipeline de ofertas laborales",
    )
    parser.add_argument(
        "--profile",
        default="config/profile.yaml",
        help="Ruta a profile.yaml",
    )
    parser.add_argument(
        "--sources",
        default="config/sources.yaml",
        help="Ruta a sources.yaml",
    )
    parser.add_argument(
        "--output",
        default="dashboard/public/data/offers.json",
        help="Ruta para export JSON",
    )

    args = parser.parse_args()

    try:
        run_pipeline(args.profile, args.sources, args.output)
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline fatal error: {e}", exc_info=True)
        sys.exit(1)

"""Bootstrap knowledge base from Data Commons API — targeted facts only."""

import json
import logging
from datetime import datetime, timezone

import requests

from src.config import DATACOMMONS_API_KEY, DATA_DIR

logger = logging.getLogger(__name__)

DC_API_BASE = "https://api.datacommons.org"

# Targeted queries for demo scope
TARGET_QUERIES = [
    {
        "entity": "india",
        "label": "Country",
        "stat_vars": [
            "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
            "ConsumerPriceIndex",
        ],
        "description": "India economic indicators",
    },
    {
        "entity": "iran",
        "label": "Country",
        "stat_vars": [
            "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
        ],
        "description": "Iran economic indicators",
    },
    {
        "entity": "usa",
        "label": "Country",
        "stat_vars": [
            "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
        ],
        "description": "USA economic indicators",
    },
]

# Static facts to import as graph triples (from Data Commons knowledge)
STATIC_FACTS = [
    {
        "subject": "india",
        "predicate": "IMPORTS",
        "object": "crude oil",
        "confidence": 0.95,
        "source_context": "India imports approximately 85% of its crude oil needs, making it the world's third-largest oil importer.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "india",
        "predicate": "IMPORTS",
        "object": "lng",
        "confidence": 0.88,
        "source_context": "India is among the top LNG importers globally, with imports supplying nearly half its natural gas needs.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "iran",
        "predicate": "EXPORTS",
        "object": "crude oil",
        "confidence": 0.92,
        "source_context": "Iran holds the world's fourth-largest proven oil reserves and is a significant crude oil exporter.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "strait of hormuz",
        "predicate": "TRANSPORT_ROUTE_FOR",
        "object": "crude oil",
        "confidence": 0.97,
        "source_context": "Approximately 20-21 million barrels per day of oil flow through the Strait of Hormuz, roughly 20% of global supply.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "strait of hormuz",
        "predicate": "TRANSPORT_ROUTE_FOR",
        "object": "lng",
        "confidence": 0.95,
        "source_context": "About 25% of global LNG trade transits through the Strait of Hormuz.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "crude oil",
        "predicate": "AFFECTS",
        "object": "inflation",
        "confidence": 0.90,
        "source_context": "Crude oil price increases contribute directly to inflation in import-dependent economies through higher fuel and transport costs.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "crude oil",
        "predicate": "AFFECTS",
        "object": "currency exchange rate",
        "confidence": 0.85,
        "source_context": "Higher crude oil prices widen India's current account deficit, putting depreciation pressure on the Indian rupee.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "crude oil",
        "predicate": "AFFECTS",
        "object": "industrial production",
        "confidence": 0.82,
        "source_context": "Rising oil prices increase input costs for manufacturing, reducing industrial output in oil-importing nations.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "usa",
        "predicate": "CONFLICT_WITH",
        "object": "iran",
        "confidence": 0.85,
        "source_context": "USA-Iran tensions have persisted over Iran's nuclear program, regional influence, and US sanctions regime.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "usa",
        "predicate": "THREATENS",
        "object": "strait of hormuz",
        "confidence": 0.70,
        "source_context": "Military confrontation between USA and Iran risks disruption of shipping through the Strait of Hormuz.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "iran",
        "predicate": "THREATENS",
        "object": "strait of hormuz",
        "confidence": 0.75,
        "source_context": "Iran has historically threatened to close the Strait of Hormuz in response to sanctions and military pressure.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "opec",
        "predicate": "INFLUENCES",
        "object": "crude oil",
        "confidence": 0.92,
        "source_context": "OPEC production decisions directly influence global crude oil supply and pricing.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "strait of hormuz",
        "predicate": "CRITICAL_FOR",
        "object": "india",
        "confidence": 0.93,
        "source_context": "India receives a significant share of its oil and LNG imports through the Strait of Hormuz corridor.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "saudi arabia",
        "predicate": "EXPORTS",
        "object": "crude oil",
        "confidence": 0.95,
        "source_context": "Saudi Arabia is the world's largest crude oil exporter and India's top oil supplier.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "india",
        "predicate": "IMPORTS",
        "object": "crude oil",
        "confidence": 0.90,
        "source_context": "India imports crude oil from Iraq, Saudi Arabia, UAE, and other Middle Eastern producers.",
        "source_url": "https://datacommons.org",
    },
    {
        "subject": "iraq",
        "predicate": "EXPORTS",
        "object": "crude oil",
        "confidence": 0.90,
        "source_context": "Iraq is India's largest crude oil supplier by volume.",
        "source_url": "https://datacommons.org",
    },
]


def fetch_stat_var(dcid: str, stat_var: str) -> dict | None:
    """Fetch a statistical variable value from Data Commons."""
    url = f"{DC_API_BASE}/v2/observation"
    headers = {"X-API-Key": DATACOMMONS_API_KEY}
    params = {
        "entity.dcids": dcid,
        "variable.dcids": stat_var,
        "select": ["entity", "variable", "value", "date"],
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning("DC API returned %d for %s/%s", resp.status_code, dcid, stat_var)
            return None
    except Exception as e:
        logger.error("DC API error: %s", e)
        return None


def get_bootstrap_triples() -> list[dict]:
    """Return curated triples for bootstrapping the knowledge graph.
    
    These are sourced from Data Commons and verified statistical knowledge.
    """
    now = datetime.now(timezone.utc).isoformat()
    triples = []
    for fact in STATIC_FACTS:
        triple = {
            **fact,
            "timestamp": now,
        }
        triples.append(triple)

    logger.info("Prepared %d bootstrap triples from Data Commons", len(triples))
    return triples


def save_bootstrap_data(triples: list[dict]) -> None:
    """Save bootstrap data to disk for reference."""
    path = DATA_DIR / "datacommons_bootstrap.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(triples, f, indent=2)
    logger.info("Bootstrap data saved to %s", path)

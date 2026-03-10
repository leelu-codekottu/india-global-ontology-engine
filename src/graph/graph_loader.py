"""Graph loader: inserts triples into Memgraph using MERGE semantics."""

import json
import logging
from datetime import datetime, timezone

from gqlalchemy import Memgraph

from src.config import ALLOWED_NODE_LABELS, ALLOWED_RELATIONSHIP_TYPES, LOGS_DIR
from src.graph.memgraph_init import get_memgraph

logger = logging.getLogger(__name__)


def _infer_label(name: str) -> str:
    """Infer the most likely ontology label for an entity name."""
    name_lower = name.lower().strip()
    
    countries = {
        "india", "iran", "usa", "united states", "china", "russia", "saudi arabia",
        "iraq", "pakistan", "israel", "japan", "germany", "uk", "united kingdom",
        "france", "qatar", "uae", "united arab emirates", "oman", "kuwait",
        "turkey", "south korea", "brazil", "indonesia", "nigeria", "venezuela",
    }
    resources = {
        "crude oil", "oil", "petroleum", "lng", "natural gas", "coal", "uranium",
        "solar energy", "wind energy", "diesel", "gasoline", "fertilizer", "steel",
        "copper", "lithium", "rare earth", "wheat", "rice",
    }
    indicators = {
        "inflation", "cpi", "gdp", "interest rate", "currency exchange rate",
        "industrial production", "oil import volume", "trade deficit",
        "fiscal deficit", "unemployment", "wpi", "iip", "current account deficit",
        "forex reserves",
    }
    locations = {
        "strait of hormuz", "persian gulf", "suez canal", "red sea",
        "indian ocean", "south china sea", "arabian sea", "mumbai", "delhi",
        "tehran", "washington", "chabahar port",
    }
    organizations = {
        "opec", "imf", "world bank", "rbi", "fed", "federal reserve",
        "un", "united nations", "nato", "iaea", "wto", "brics", "g20",
    }

    if name_lower in countries:
        return "Country"
    if name_lower in resources:
        return "Resource"
    if name_lower in indicators:
        return "Indicator"
    if name_lower in locations:
        return "Location"
    if name_lower in organizations:
        return "Organization"

    # Heuristics
    for kw in ["index", "rate", "deficit", "surplus", "production", "volume", "price"]:
        if kw in name_lower:
            return "Indicator"
    for kw in ["port", "strait", "gulf", "canal", "sea", "ocean", "bay"]:
        if kw in name_lower:
            return "Location"

    return "Event"  # fallback


def _map_predicate(predicate: str) -> str:
    """Map an LLM-extracted predicate to an allowed relationship type."""
    pred_lower = predicate.lower().strip().replace(" ", "_")
    
    mapping = {
        "imports": "IMPORTS",
        "import": "IMPORTS",
        "exports": "EXPORTS",
        "export": "EXPORTS",
        "transport_route_for": "TRANSPORT_ROUTE_FOR",
        "transports": "TRANSPORT_ROUTE_FOR",
        "conflict_with": "CONFLICT_WITH",
        "conflicts_with": "CONFLICT_WITH",
        "threatens": "THREATENS",
        "threaten": "THREATENS",
        "disrupts": "DISRUPTS",
        "disrupt": "DISRUPTS",
        "affects": "AFFECTS",
        "affect": "AFFECTS",
        "causes": "CAUSES",
        "cause": "CAUSES",
        "influences": "INFLUENCES",
        "influence": "INFLUENCES",
        "critical_for": "CRITICAL_FOR",
        "impacts": "IMPACTS",
        "impact": "IMPACTS",
    }

    if pred_lower in mapping:
        return mapping[pred_lower]

    # Partial matching
    for key, val in mapping.items():
        if key in pred_lower:
            return val

    return "AFFECTS"  # safe fallback


def insert_triple(
    db: Memgraph,
    subject: str,
    predicate: str,
    obj: str,
    confidence: float,
    source_url: str,
    source_context: str,
    timestamp: str | None = None,
    subject_label: str | None = None,
    object_label: str | None = None,
) -> bool:
    """Insert a single SPO triple into Memgraph using MERGE.
    
    Returns True if insertion succeeded.
    """
    now = timestamp or datetime.now(timezone.utc).isoformat()
    subj_name = subject.lower().strip()
    obj_name = obj.lower().strip()

    # Infer labels
    s_label = subject_label if subject_label in ALLOWED_NODE_LABELS else _infer_label(subj_name)
    o_label = object_label if object_label in ALLOWED_NODE_LABELS else _infer_label(obj_name)

    rel_type = _map_predicate(predicate)
    if rel_type not in ALLOWED_RELATIONSHIP_TYPES:
        logger.warning("Unmapped predicate '%s' → using AFFECTS", predicate)
        rel_type = "AFFECTS"

    confidence = max(0.0, min(1.0, float(confidence)))
    source_entry = json.dumps([{"url": source_url, "snippet": source_context}])

    try:
        # MERGE subject
        db.execute(
            f"MERGE (n:{s_label} {{name: $name}}) "
            f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, n.aliases = '[]' "
            f"ON MATCH SET n.source_count = n.source_count + 1;",
            {"name": subj_name, "ts": now},
        )
        # MERGE object
        db.execute(
            f"MERGE (n:{o_label} {{name: $name}}) "
            f"ON CREATE SET n.timestamp = $ts, n.source_count = 1, n.aliases = '[]' "
            f"ON MATCH SET n.source_count = n.source_count + 1;",
            {"name": obj_name, "ts": now},
        )
        # MERGE relationship
        db.execute(
            f"MATCH (a:{s_label} {{name: $subj}}), (b:{o_label} {{name: $obj}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"ON CREATE SET r.confidence = $conf, r.sources = $sources, "
            f"r.first_seen = $ts, r.last_seen = $ts, r.version = 1, "
            f"r.status = 'active', r.source_count = 1 "
            f"ON MATCH SET r.last_seen = $ts, "
            f"r.source_count = r.source_count + 1, "
            f"r.confidence = (r.confidence * (r.source_count - 1) + $conf) / r.source_count;",
            {"subj": subj_name, "obj": obj_name, "conf": confidence,
             "sources": source_entry, "ts": now},
        )

        _log_insertion(subj_name, rel_type, obj_name, confidence, source_url)
        return True

    except Exception as e:
        logger.error("Failed to insert triple (%s)-[%s]->(%s): %s",
                     subj_name, rel_type, obj_name, e)
        return False


def insert_triples(db: Memgraph, triples: list[dict]) -> dict:
    """Insert a batch of triples. Returns summary counts."""
    inserted = 0
    failed = 0
    for t in triples:
        ok = insert_triple(
            db=db,
            subject=t.get("subject", ""),
            predicate=t.get("predicate", ""),
            obj=t.get("object", ""),
            confidence=t.get("confidence", 0.5),
            source_url=t.get("source_url", ""),
            source_context=t.get("source_context", ""),
            timestamp=t.get("timestamp"),
            subject_label=t.get("subject_label"),
            object_label=t.get("object_label"),
        )
        if ok:
            inserted += 1
        else:
            failed += 1
    return {"inserted": inserted, "failed": failed, "total": len(triples)}


def _log_insertion(subject, rel_type, obj, confidence, source_url):
    """Append insertion event to log file."""
    log_path = LOGS_DIR / "insertions.log"
    ts = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{ts} | ({subject})-[{rel_type}]->({obj}) | "
                f"conf={confidence:.2f} | src={source_url}\n")

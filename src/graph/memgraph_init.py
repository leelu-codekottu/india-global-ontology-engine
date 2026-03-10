"""Memgraph connection helper and schema bootstrap."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from gqlalchemy import Memgraph

from src.config import (
    MEMGRAPH_HOST,
    MEMGRAPH_PORT,
    DATA_DIR,
    ALLOWED_NODE_LABELS,
)

logger = logging.getLogger(__name__)


def get_memgraph() -> Memgraph:
    """Return a Memgraph connection instance."""
    return Memgraph(host=MEMGRAPH_HOST, port=MEMGRAPH_PORT)


def create_constraints(db: Memgraph | None = None) -> list[str]:
    """Create uniqueness constraints for ontology node labels that support it."""
    if db is None:
        db = get_memgraph()

    labels_with_unique_name = ALLOWED_NODE_LABELS  # all require unique name
    created = []
    for label in labels_with_unique_name:
        query = f"CREATE CONSTRAINT ON (n:{label}) ASSERT n.name IS UNIQUE;"
        try:
            db.execute(query)
            created.append(label)
            logger.info("Constraint created for %s", label)
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "constraint" in msg:
                logger.info("Constraint already exists for %s", label)
                created.append(label)
            else:
                logger.warning("Could not create constraint for %s: %s", label, e)
    return created


def create_indexes(db: Memgraph | None = None) -> list[str]:
    """Create label indexes for faster lookups."""
    if db is None:
        db = get_memgraph()
    
    created = []
    for label in ALLOWED_NODE_LABELS:
        try:
            db.execute(f"CREATE INDEX ON :{label};")
            created.append(label)
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "index" in msg:
                created.append(label)
            else:
                logger.warning("Could not create index for %s: %s", label, e)
    return created


def graph_snapshot(db: Memgraph | None = None) -> dict:
    """Produce a snapshot of current graph: label counts, edge counts, duplicates."""
    if db is None:
        db = get_memgraph()

    snapshot: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node_counts": {},
        "edge_counts": {},
        "total_nodes": 0,
        "total_edges": 0,
        "flagged_duplicates": [],
    }

    # Node counts per label
    for label in ALLOWED_NODE_LABELS:
        result = list(db.execute_and_fetch(f"MATCH (n:{label}) RETURN count(n) AS cnt;"))
        cnt = result[0]["cnt"] if result else 0
        snapshot["node_counts"][label] = cnt
        snapshot["total_nodes"] += cnt

    # Edge counts per type
    result = list(db.execute_and_fetch(
        "MATCH ()-[r]->() RETURN type(r) AS rtype, count(r) AS cnt;"
    ))
    for row in result:
        snapshot["edge_counts"][row["rtype"]] = row["cnt"]
        snapshot["total_edges"] += row["cnt"]

    # Duplicate detection (same name, different ids within same label)
    for label in ALLOWED_NODE_LABELS:
        dups = list(db.execute_and_fetch(
            f"MATCH (n:{label}) WITH n.name AS name, collect(n) AS nodes "
            f"WHERE size(nodes) > 1 RETURN name, size(nodes) AS cnt;"
        ))
        for d in dups:
            snapshot["flagged_duplicates"].append({
                "label": label,
                "name": d["name"],
                "count": d["cnt"],
            })

    return snapshot


def save_snapshot(snapshot: dict, path: Path | None = None) -> Path:
    """Write snapshot to JSON file."""
    if path is None:
        path = DATA_DIR / "graph_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)
    logger.info("Snapshot saved to %s", path)
    return path


def bootstrap_minimal_graph(db: Memgraph | None = None) -> None:
    """Insert seed nodes/edges for the demo scenario if graph is empty."""
    if db is None:
        db = get_memgraph()

    now = datetime.now(timezone.utc).isoformat()
    source = "bootstrap"

    seed_nodes = [
        ("Country", "india", ["bharat", "republic of india"]),
        ("Country", "iran", ["islamic republic of iran", "persia"]),
        ("Country", "usa", ["united states", "united states of america", "us", "america"]),
        ("Resource", "crude oil", ["petroleum", "oil"]),
        ("Resource", "lng", ["liquefied natural gas", "natural gas"]),
        ("Location", "strait of hormuz", ["hormuz strait"]),
        ("Indicator", "inflation", ["cpi", "consumer price index"]),
        ("Indicator", "currency exchange rate", ["inr/usd", "rupee dollar rate"]),
        ("Indicator", "industrial production", ["iip", "industrial output"]),
        ("Indicator", "oil import volume", ["crude import", "petroleum import"]),
        ("Organization", "opec", ["organization of the petroleum exporting countries"]),
        ("Location", "persian gulf", ["arabian gulf"]),
    ]

    for label, name, aliases in seed_nodes:
        alias_str = json.dumps(aliases)
        db.execute(
            f"MERGE (n:{label} {{name: $name}}) "
            f"ON CREATE SET n.aliases = $aliases, n.source = $source, "
            f"n.timestamp = $ts, n.source_count = 1 "
            f"ON MATCH SET n.source_count = n.source_count + 1;",
            {"name": name, "aliases": alias_str, "source": source, "ts": now},
        )

    # Seed relationships
    seed_rels = [
        ("india", "Country", "IMPORTS", "crude oil", "Resource", 0.95,
         "India imports ~85% of its crude oil needs"),
        ("iran", "Country", "EXPORTS", "crude oil", "Resource", 0.90,
         "Iran is a major crude oil exporter"),
        ("strait of hormuz", "Location", "TRANSPORT_ROUTE_FOR", "crude oil", "Resource", 0.95,
         "~20% of global oil passes through the Strait of Hormuz"),
        ("usa", "Country", "CONFLICT_WITH", "iran", "Country", 0.80,
         "USA-Iran tensions have escalated over nuclear program and sanctions"),
        ("crude oil", "Resource", "AFFECTS", "inflation", "Indicator", 0.85,
         "Crude oil price spikes directly affect inflation in oil-importing nations"),
        ("crude oil", "Resource", "AFFECTS", "currency exchange rate", "Indicator", 0.80,
         "Oil price increases weaken INR due to higher import bill"),
        ("strait of hormuz", "Location", "CRITICAL_FOR", "india", "Country", 0.90,
         "India receives significant oil/LNG shipments through Hormuz"),
        ("iran", "Country", "EXPORTS", "lng", "Resource", 0.75,
         "Iran has large natural gas reserves and exports LNG"),
        ("crude oil", "Resource", "AFFECTS", "industrial production", "Indicator", 0.80,
         "Higher oil costs raise input costs for manufacturing"),
        ("opec", "Organization", "INFLUENCES", "crude oil", "Resource", 0.90,
         "OPEC production decisions directly impact global oil prices"),
        ("usa", "Country", "THREATENS", "strait of hormuz", "Location", 0.65,
         "US-Iran conflict could lead to blockade of Strait of Hormuz"),
    ]

    for subj, slabel, rel, obj, olabel, conf, snippet in seed_rels:
        sources_json = json.dumps([{"url": "bootstrap", "snippet": snippet}])
        db.execute(
            f"MATCH (a:{slabel} {{name: $subj}}), (b:{olabel} {{name: $obj}}) "
            f"MERGE (a)-[r:{rel}]->(b) "
            f"ON CREATE SET r.confidence = $conf, r.sources = $sources, "
            f"r.first_seen = $ts, r.last_seen = $ts, r.version = 1, "
            f"r.status = 'active', r.source_count = 1 "
            f"ON MATCH SET r.last_seen = $ts, r.source_count = r.source_count + 1;",
            {"subj": subj, "obj": obj, "conf": conf,
             "sources": sources_json, "ts": now},
        )

    logger.info("Bootstrap graph inserted: %d nodes, %d relationships",
                len(seed_nodes), len(seed_rels))

"""Verifier: assigns trust tags to relationships based on source_count and confidence."""

import logging
from datetime import datetime, timezone

from gqlalchemy import Memgraph

from src.graph.memgraph_init import get_memgraph
from src.config import LOGS_DIR

logger = logging.getLogger(__name__)


def verify_all_relationships(db: Memgraph | None = None) -> dict:
    """Scan all relationships and assign trust tags.
    
    Rules:
    - source_count >= 2 AND confidence >= 0.7 → trust = 'trusted'
    - Otherwise → trust = 'untrusted'
    
    Returns summary counts.
    """
    if db is None:
        db = get_memgraph()

    results = list(db.execute_and_fetch(
        "MATCH (a)-[r]->(b) "
        "RETURN id(r) AS rid, type(r) AS rtype, a.name AS subj, b.name AS obj, "
        "r.source_count AS sc, r.confidence AS conf, r.status AS status;"
    ))

    trusted = 0
    untrusted = 0
    log_entries = []
    now = datetime.now(timezone.utc).isoformat()

    for row in results:
        rid = row["rid"]
        sc = row.get("sc") or 0
        conf = row.get("conf") or 0.0
        status = row.get("status", "active")

        if status == "deprecated":
            continue

        if sc >= 2 and conf >= 0.7:
            trust = "trusted"
            trusted += 1
        else:
            trust = "untrusted"
            untrusted += 1

        # Update trust tag on relationship using internal id
        db.execute(
            "MATCH ()-[r]->() WHERE id(r) = $rid SET r.trust = $trust, r.verified_at = $ts;",
            {"rid": rid, "trust": trust, "ts": now},
        )

        log_entries.append(
            f"{now} | ({row['subj']})-[{row['rtype']}]->({row['obj']}) | "
            f"sc={sc} conf={conf:.2f} → {trust}"
        )

    # Write verification log
    log_path = LOGS_DIR / "verification.log"
    with open(log_path, "a", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(entry + "\n")

    summary = {"trusted": trusted, "untrusted": untrusted, "total": trusted + untrusted}
    logger.info("Verification complete: %s", summary)
    return summary

"""FastAPI backend: API endpoints for the Ontology Engine."""

import json
import logging
import threading
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import DATACOMMONS_API_KEY
from src.graph.memgraph_init import get_memgraph, graph_snapshot
from src.graph.corrector import flag_relationship, re_verify_relationship
from src.graph.verifier import verify_all_relationships
from src.reasoner.graphrag import answer_question

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="India Global Ontology Engine",
    description="GraphRAG-powered geopolitical analysis focused on India",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


class FlagRequest(BaseModel):
    subject: str
    relationship: str
    object: str
    reason: str = ""


class GraphQueryRequest(BaseModel):
    cypher: str


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/snapshot")
async def get_snapshot():
    """Get current graph snapshot with node/edge counts."""
    try:
        db = get_memgraph()
        snap = graph_snapshot(db)
        return snap
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask")
async def ask_question(req: QuestionRequest):
    """GraphRAG reasoning endpoint: answer a geopolitical question."""
    try:
        db = get_memgraph()
        result = answer_question(req.question, db)
        return result
    except Exception as e:
        logger.error("Ask failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/flag")
async def flag_claim(req: FlagRequest):
    """Flag a relationship as disputed, then auto re-verify with LLM."""
    try:
        db = get_memgraph()
        success = flag_relationship(
            db=db,
            subject=req.subject,
            rel_type=req.relationship,
            obj=req.object,
            reason=req.reason,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Relationship not found")

        # Auto-trigger LLM re-verification
        reverify_result = re_verify_relationship(
            db=db,
            subject=req.subject,
            rel_type=req.relationship,
            obj=req.object,
            reason=req.reason,
        )
        return {
            "status": "flagged_and_reverified",
            "verdict": reverify_result.get("verdict", "UNKNOWN"),
            "explanation": reverify_result.get("explanation", ""),
            "old_confidence": reverify_result.get("old_confidence"),
            "new_confidence": reverify_result.get("new_confidence"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify")
async def trigger_verification():
    """Trigger verification of all relationships."""
    try:
        db = get_memgraph()
        summary = verify_all_relationships(db)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph")
async def get_full_graph(limit: int = 500, label: str = None, search: str = None):
    """Get nodes and edges for visualization.

    Query params:
      limit  – max nodes to return (default 500, keeps UI responsive)
      label  – filter by node label e.g. Country, Resource
      search – case-insensitive substring match on node name
    """
    try:
        db = get_memgraph()
        nodes = []
        edges = []

        # --- build WHERE clause ---
        where_parts = []
        params: dict = {"lim": limit or 500}
        if label:
            where_parts.append("$label IN labels(n)")
            params["label"] = label
        if search:
            where_parts.append("toLower(n.name) CONTAINS toLower($search)")
            params["search"] = search
        where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Fetch filtered nodes (limit for performance)
        node_q = (
            f"MATCH (n) {where_clause} "
            "RETURN labels(n) AS labels, n.name AS name, "
            "n.aliases AS aliases, n.source_count AS source_count "
            "LIMIT $lim;"
        )
        node_results = list(db.execute_and_fetch(node_q, params))
        node_ids = set()
        for row in node_results:
            node_ids.add(row["name"])
            nodes.append({
                "id": row["name"],
                "name": row["name"],
                "labels": row.get("labels", []),
                "source_count": row.get("source_count", 0),
            })

        # Fetch edges only between returned nodes
        edge_results = list(db.execute_and_fetch(
            "MATCH (a)-[r]->(b) "
            "WHERE a.name IN $names AND b.name IN $names "
            "RETURN a.name AS source, type(r) AS rel, "
            "b.name AS target, r.confidence AS confidence, r.status AS status, "
            "r.trust AS trust, r.sources AS sources;",
            {"names": list(node_ids)},
        ))
        for row in edge_results:
            # Parse sources JSON to extract URLs
            raw_sources = row.get("sources", "[]")
            source_urls = []
            try:
                parsed = json.loads(raw_sources) if isinstance(raw_sources, str) else (raw_sources or [])
                if isinstance(parsed, list):
                    source_urls = [s.get("url", "") for s in parsed if isinstance(s, dict) and s.get("url")]
            except (json.JSONDecodeError, TypeError):
                pass

            edges.append({
                "source": row["source"],
                "target": row["target"],
                "relationship": row["rel"],
                "confidence": row.get("confidence", 0),
                "status": row.get("status", "active"),
                "trust": row.get("trust", "untrusted"),
                "source_urls": source_urls,
            })

        # Get total counts for the header
        total_nodes = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c;"))[0]["c"]
        total_edges = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c;"))[0]["c"]

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/labels")
async def get_graph_labels():
    """Return available node labels with counts for the UI filter."""
    try:
        db = get_memgraph()
        rows = list(db.execute_and_fetch(
            "MATCH (n) UNWIND labels(n) AS lbl "
            "RETURN lbl, count(*) AS cnt ORDER BY cnt DESC;"
        ))
        return [{"label": r["lbl"], "count": r["cnt"]} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/threats")
async def get_threat_matrix():
    """Get top IMPACTS edges to India sorted by severity (confidence)."""
    try:
        db = get_memgraph()
        results = list(db.execute_and_fetch(
            "MATCH (a)-[r]->(b) "
            "WHERE b.name = 'india' OR a.name = 'india' "
            "RETURN a.name AS source, type(r) AS rel, b.name AS target, "
            "r.confidence AS confidence, r.status AS status, r.trust AS trust, "
            "r.sources AS sources "
            "ORDER BY r.confidence DESC;"
        ))
        
        threats = []
        for row in results:
            sources_raw = row.get("sources", "[]")
            try:
                sources = json.loads(sources_raw) if isinstance(sources_raw, str) else sources_raw or []
            except (json.JSONDecodeError, TypeError):
                sources = []
            
            threats.append({
                "source": row["source"],
                "relationship": row["rel"],
                "target": row["target"],
                "confidence": row.get("confidence", 0),
                "status": row.get("status", "active"),
                "trust": row.get("trust", "untrusted"),
                "evidence": sources[:2] if sources else [],
            })

        return {"threats": threats, "count": len(threats)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# DATA FRESHNESS — auto cross-verify from Data Commons on start + on demand
# ═══════════════════════════════════════════════════════════════════════════

DC_API = "https://api.datacommons.org/v2/observation"
_REFRESH_COUNTRIES = {
    "india": "country/IND", "china": "country/CHN", "usa": "country/USA",
    "japan": "country/JPN", "germany": "country/DEU",
    "united kingdom": "country/GBR", "russia": "country/RUS",
    "brazil": "country/BRA", "indonesia": "country/IDN",
    "saudi arabia": "country/SAU", "pakistan": "country/PAK",
}
_REFRESH_VARS = {
    "gdp_nominal": "Amount_EconomicActivity_GrossDomesticProduction_Nominal",
    "population": "Count_Person",
}


def _dc_fetch_latest(dcids: list[str], var_dcid: str) -> dict:
    """Fetch latest observations from Data Commons."""
    try:
        resp = requests.post(
            DC_API,
            headers={"X-API-Key": DATACOMMONS_API_KEY, "Content-Type": "application/json"},
            json={
                "date": "LATEST",
                "variable": {"dcids": [var_dcid]},
                "entity": {"dcids": dcids},
                "select": ["entity", "variable", "value", "date"],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("DC refresh fetch failed: %s", e)
    return {}


def _refresh_indicators():
    """Cross-verify key indicators with Data Commons latest data.
    
    Runs in background on startup and can be triggered via /api/refresh.
    Updates values only when DC has newer data than what's in the graph.
    """
    logger.info("[refresh] Cross-verifying key indicators with Data Commons...")
    db = get_memgraph()
    updated = 0

    for var_name, var_dcid in _REFRESH_VARS.items():
        dcids = list(_REFRESH_COUNTRIES.values())
        data = _dc_fetch_latest(dcids, var_dcid)
        if not data:
            continue

        for country_name, country_dcid in _REFRESH_COUNTRIES.items():
            try:
                facets = (
                    data.get("byVariable", {})
                    .get(var_dcid, {})
                    .get("byEntity", {})
                    .get(country_dcid, {})
                    .get("orderedFacets", [])
                )
                if not facets:
                    continue
                obs = facets[0].get("observations", [])
                if not obs:
                    continue
                dc_value = obs[0]["value"]
                dc_date = obs[0]["date"]
            except (KeyError, IndexError):
                continue

            if var_name == "gdp_nominal":
                node_name = f"{country_name} gdp"
                if dc_value >= 1e12:
                    display = f"${dc_value/1e12:.2f} trillion"
                elif dc_value >= 1e9:
                    display = f"${dc_value/1e9:.1f} billion"
                else:
                    display = f"${dc_value:,.0f}"
            elif var_name == "population":
                node_name = f"{country_name} population"
                if dc_value >= 1e9:
                    display = f"{dc_value/1e9:.2f} billion"
                elif dc_value >= 1e6:
                    display = f"{dc_value/1e6:.1f} million"
                else:
                    display = f"{dc_value:,.0f}"
            else:
                continue

            # Check if DC date is newer than what we have
            rows = list(db.execute_and_fetch(
                "MATCH (n {name: $name}) RETURN n.date AS dt, n.value AS val;",
                {"name": node_name},
            ))
            if rows:
                existing_date = str(rows[0].get("dt", "") or "")
                # Only update if DC has newer date
                if existing_date and str(dc_date) <= existing_date:
                    continue

            db.execute(
                "MATCH (n {name: $name}) "
                "SET n.value = $val, n.display_value = $display, n.date = $date, "
                "n.last_verified = $now",
                {
                    "name": node_name,
                    "val": float(dc_value),
                    "display": display,
                    "date": str(dc_date),
                    "now": datetime.now(timezone.utc).isoformat(),
                },
            )
            updated += 1
            logger.info("[refresh] Updated %s -> %s (date: %s)", node_name, display, dc_date)

    logger.info("[refresh] Cross-verification done. %d values updated.", updated)
    return updated


@app.on_event("startup")
async def on_startup():
    """Cross-verify key economic data from Data Commons on every server start."""
    thread = threading.Thread(target=_refresh_indicators, daemon=True)
    thread.start()


@app.post("/api/refresh")
async def trigger_data_refresh():
    """Manually trigger cross-verification of economic indicators with Data Commons."""
    try:
        updated = _refresh_indicators()
        return {"status": "ok", "updated_count": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

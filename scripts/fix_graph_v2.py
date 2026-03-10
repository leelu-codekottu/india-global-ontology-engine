"""Graph improvement script v2: merge duplicates, add missing edges, fix wrong edges."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gqlalchemy import Memgraph

db = Memgraph("127.0.0.1", 7687)

# ---------------------------------------------------------------------------
# 1. MERGE DUPLICATE ENTITIES (lowercase variants into proper-cased canonical)
# ---------------------------------------------------------------------------
# Strategy: for each pair, move all edges from lowercase node to proper-case
# node, then delete the lowercase node.

MERGE_PAIRS = [
    # (keep_canonical, merge_into_it)
    ("India", "india"),
    ("Iran", "iran"),
    ("USA", "usa"),
    ("Crude Oil", "crude oil"),
    ("Strait of Hormuz", "strait of hormuz"),
    ("Inflation", "inflation"),
    ("Saudi Arabia", "saudi arabia"),
    ("Iraq", "iraq"),
    ("LNG", "lng"),
    ("OPEC", "opec"),
    ("Indian Rupee", "indian rupee"),
]

def merge_nodes(keep: str, remove: str):
    """Move all relationships from 'remove' node to 'keep' node, then delete 'remove'."""
    # Check both exist
    keep_exists = list(db.execute_and_fetch(
        "MATCH (n {name: $name}) RETURN n.name AS name;", {"name": keep}
    ))
    remove_exists = list(db.execute_and_fetch(
        "MATCH (n {name: $name}) RETURN n.name AS name;", {"name": remove}
    ))

    if not remove_exists:
        print(f"  SKIP: '{remove}' does not exist")
        return
    if not keep_exists:
        # Just rename the remove node
        db.execute("MATCH (n {name: $old}) SET n.name = $new;", {"old": remove, "new": keep})
        print(f"  RENAMED: '{remove}' → '{keep}'")
        return

    # Move outgoing edges: (remove)-[r]->(x) → (keep)-[r]->(x)
    out_edges = list(db.execute_and_fetch(
        "MATCH (a {name: $rem})-[r]->(b) WHERE b.name <> $keep "
        "RETURN type(r) AS rtype, b.name AS tgt, r.confidence AS conf, "
        "r.status AS status, r.trust AS trust, r.source_context AS ctx, "
        "r.sources AS sources, r.source_count AS sc;",
        {"rem": remove, "keep": keep}
    ))
    for e in out_edges:
        rtype = e["rtype"]
        tgt = e["tgt"]
        # Check if edge already exists on keep node
        existing = list(db.execute_and_fetch(
            f"MATCH (a {{name: $keep}})-[r:{rtype}]->(b {{name: $tgt}}) RETURN r.confidence AS conf;",
            {"keep": keep, "tgt": tgt}
        ))
        if existing:
            # Merge: take max confidence
            old_conf = existing[0].get("conf") or 0
            new_conf = max(old_conf, e.get("conf") or 0)
            sc = max((existing[0].get("sc") or 0), (e.get("sc") or 0)) + 1
            db.execute(
                f"MATCH (a {{name: $keep}})-[r:{rtype}]->(b {{name: $tgt}}) "
                f"SET r.confidence = $conf, r.source_count = $sc;",
                {"keep": keep, "tgt": tgt, "conf": new_conf, "sc": sc}
            )
        else:
            # Create new edge
            conf = e.get("conf") or 0.5
            ctx = e.get("ctx") or ""
            sources = e.get("sources") or "[]"
            sc = e.get("sc") or 1
            status = e.get("status") or "active"
            trust = e.get("trust") or "untrusted"
            db.execute(
                f"MATCH (a {{name: $keep}}), (b {{name: $tgt}}) "
                f"CREATE (a)-[r:{rtype} {{confidence: $conf, source_context: $ctx, "
                f"sources: $sources, source_count: $sc, status: $status, trust: $trust}}]->(b);",
                {"keep": keep, "tgt": tgt, "conf": conf, "ctx": ctx,
                 "sources": sources, "sc": sc, "status": status, "trust": trust}
            )

    # Move incoming edges: (x)-[r]->(remove) → (x)-[r]->(keep)
    in_edges = list(db.execute_and_fetch(
        "MATCH (a)-[r]->(b {name: $rem}) WHERE a.name <> $keep "
        "RETURN type(r) AS rtype, a.name AS src, r.confidence AS conf, "
        "r.status AS status, r.trust AS trust, r.source_context AS ctx, "
        "r.sources AS sources, r.source_count AS sc;",
        {"rem": remove, "keep": keep}
    ))
    for e in in_edges:
        rtype = e["rtype"]
        src = e["src"]
        existing = list(db.execute_and_fetch(
            f"MATCH (a {{name: $src}})-[r:{rtype}]->(b {{name: $keep}}) RETURN r.confidence AS conf;",
            {"src": src, "keep": keep}
        ))
        if existing:
            old_conf = existing[0].get("conf") or 0
            new_conf = max(old_conf, e.get("conf") or 0)
            sc = max((existing[0].get("sc") or 0), (e.get("sc") or 0)) + 1
            db.execute(
                f"MATCH (a {{name: $src}})-[r:{rtype}]->(b {{name: $keep}}) "
                f"SET r.confidence = $conf, r.source_count = $sc;",
                {"src": src, "keep": keep, "conf": new_conf, "sc": sc}
            )
        else:
            conf = e.get("conf") or 0.5
            ctx = e.get("ctx") or ""
            sources = e.get("sources") or "[]"
            sc = e.get("sc") or 1
            status = e.get("status") or "active"
            trust = e.get("trust") or "untrusted"
            db.execute(
                f"MATCH (a {{name: $src}}), (b {{name: $keep}}) "
                f"CREATE (a)-[r:{rtype} {{confidence: $conf, source_context: $ctx, "
                f"sources: $sources, source_count: $sc, status: $status, trust: $trust}}]->(b);",
                {"src": src, "keep": keep, "conf": conf, "ctx": ctx,
                 "sources": sources, "sc": sc, "status": status, "trust": trust}
            )

    # Delete the duplicate node and all its remaining edges
    db.execute("MATCH (n {name: $rem}) DETACH DELETE n;", {"rem": remove})
    print(f"  MERGED: '{remove}' → '{keep}'")


print("=" * 60)
print("STEP 1: Merging duplicate entities")
print("=" * 60)
for keep, remove in MERGE_PAIRS:
    merge_nodes(keep, remove)

# ---------------------------------------------------------------------------
# 2. FIX SEMANTICALLY WRONG EDGES
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("STEP 2: Fixing semantically wrong edges")
print("=" * 60)

# "Strait of Hormuz TRANSPORT_ROUTE_FOR India" is wrong — Hormuz is a route
# for crude oil/LNG shipments, not for India itself.
try:
    db.execute(
        "MATCH (a {name: 'Strait of Hormuz'})-[r:TRANSPORT_ROUTE_FOR]->(b {name: 'India'}) "
        "DELETE r;"
    )
    print("  DELETED: (Strait of Hormuz)-[TRANSPORT_ROUTE_FOR]->(India)")
except Exception as e:
    print(f"  SKIP: {e}")

# "India AFFECTS Inflation" is backwards — Inflation affects India
try:
    db.execute(
        "MATCH (a {name: 'India'})-[r:AFFECTS]->(b {name: 'Inflation'}) DELETE r;"
    )
    print("  DELETED: (India)-[AFFECTS]->(Inflation) [backwards]")
except Exception as e:
    print(f"  SKIP: {e}")

# "India AFFECTS Indian Rupee" is vague — should be more specific
try:
    db.execute(
        "MATCH (a {name: 'India'})-[r:AFFECTS]->(b {name: 'Indian Rupee'}) DELETE r;"
    )
    print("  DELETED: (India)-[AFFECTS]->(Indian Rupee) [too vague]")
except Exception as e:
    print(f"  SKIP: {e}")


# ---------------------------------------------------------------------------
# 3. ADD MISSING STRATEGIC EDGES
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("STEP 3: Adding missing strategic edges")
print("=" * 60)

NEW_EDGES = [
    # India's specific oil dependency on Iran
    ("India", "IMPORTS", "Iran", 0.85,
     "India imported ~10% of its crude oil from Iran before US sanctions tightened",
     "geopolitical-knowledge"),

    # India's oil import dependency ratio
    ("India", "DEPENDENT_ON", "Crude Oil", 0.95,
     "India imports approximately 85% of its crude oil needs",
     "data-commons"),

    # Strategic petroleum reserve
    ("India", "MAINTAINS", "Strategic Petroleum Reserve", 0.90,
     "India maintains ~9.5 days of strategic petroleum reserves at Visakhapatnam, Mangalore, Padur",
     "government-data"),

    # Alternative suppliers
    ("Russia", "EXPORTS", "Crude Oil", 0.90,
     "Russia became India's top crude oil supplier since 2022, surpassing Iraq and Saudi Arabia",
     "trade-data"),

    # Rupee-oil link
    ("Crude Oil", "DEPRECIATES", "Indian Rupee", 0.85,
     "Higher oil import bills widen the current account deficit, putting depreciation pressure on INR",
     "economic-analysis"),

    # Iran sanctions impact
    ("USA", "SANCTIONS", "Iran", 0.95,
     "US imposes comprehensive sanctions on Iran's oil exports, limiting India's ability to import Iranian crude",
     "geopolitical-knowledge"),

    # Diesel impact on transport
    ("Crude Oil", "INPUT_FOR", "Industrial Production", 0.90,
     "Crude oil derivatives (diesel, naphtha) are critical inputs for manufacturing, transport, and agriculture",
     "economic-analysis"),

    # Inflation-rupee link
    ("Inflation", "DEPRECIATES", "Indian Rupee", 0.80,
     "High inflation erodes purchasing power and contributes to rupee depreciation via capital outflows",
     "economic-analysis"),

    # Oil price → fiscal deficit
    ("Oil Price", "AFFECTS", "Current Account Deficit", 0.85,
     "Every $10/barrel increase in crude oil adds ~$15 billion to India's annual import bill",
     "economic-analysis"),

    # OPEC production decisions
    ("OPEC", "CONTROLS", "Oil Price", 0.85,
     "OPEC production quotas directly influence global oil supply and pricing",
     "geopolitical-knowledge"),

    # Iran-Hormuz military capability
    ("Iran", "MILITARILY_CONTROLS", "Strait of Hormuz", 0.80,
     "Iran's navy and IRGC have capability to disrupt shipping through anti-ship missiles and mines",
     "military-analysis"),
]

for subj, pred, obj, conf, ctx, source in NEW_EDGES:
    # Check if target node exists, create if not
    for node_name in [subj, obj]:
        exists = list(db.execute_and_fetch(
            "MATCH (n {name: $name}) RETURN n.name;", {"name": node_name}
        ))
        if not exists:
            # Determine label
            countries = {"India", "Iran", "USA", "Russia", "Saudi Arabia", "Iraq", "Qatar", "China"}
            resources = {"Crude Oil", "LNG", "Natural Gas"}
            indicators = {"Inflation", "Oil Price", "Industrial Production", "Current Account Deficit",
                          "Indian Rupee", "Import Bill", "GDP", "Trade Deficit"}
            orgs = {"OPEC"}
            if node_name in countries:
                label = "Country"
            elif node_name in resources:
                label = "Resource"
            elif node_name in indicators:
                label = "Indicator"
            elif node_name in orgs:
                label = "Organization"
            else:
                label = "Event"
            db.execute(
                f"CREATE (n:{label} {{name: $name, source_count: 1}});",
                {"name": node_name}
            )
            print(f"  CREATED NODE: {node_name} [{label}]")

    # Check if edge already exists
    existing = list(db.execute_and_fetch(
        f"MATCH (a {{name: $subj}})-[r:{pred}]->(b {{name: $obj}}) RETURN r.confidence AS conf;",
        {"subj": subj, "obj": obj}
    ))
    if existing:
        # Update confidence if new is higher
        old = existing[0].get("conf") or 0
        if conf > old:
            db.execute(
                f"MATCH (a {{name: $subj}})-[r:{pred}]->(b {{name: $obj}}) "
                f"SET r.confidence = $conf, r.source_context = $ctx, r.source_count = r.source_count + 1;",
                {"subj": subj, "obj": obj, "conf": conf, "ctx": ctx}
            )
            print(f"  UPDATED: ({subj})-[{pred}]->({obj}) conf={old:.2f}→{conf:.2f}")
        else:
            print(f"  EXISTS:  ({subj})-[{pred}]->({obj}) conf={old:.2f} (kept)")
    else:
        db.execute(
            f"MATCH (a {{name: $subj}}), (b {{name: $obj}}) "
            f"CREATE (a)-[:{pred} {{confidence: $conf, source_context: $ctx, "
            f"sources: $sources, source_count: 1, status: 'active', trust: 'trusted'}}]->(b);",
            {"subj": subj, "obj": obj, "conf": conf, "ctx": ctx,
             "sources": f'[{{"source": "{source}", "snippet": "{ctx}"}}]'}
        )
        print(f"  ADDED:   ({subj})-[{pred}]->({obj}) conf={conf:.2f}")


# ---------------------------------------------------------------------------
# 4. FINAL SNAPSHOT
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("STEP 4: Final snapshot")
print("=" * 60)

nodes = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS cnt;"))
edges = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS cnt;"))
print(f"  Nodes: {nodes[0]['cnt']}")
print(f"  Edges: {edges[0]['cnt']}")

# Re-run verification
from src.graph.verifier import verify_all_relationships
summary = verify_all_relationships(db)
print(f"  Verification: {summary}")

from src.graph.memgraph_init import graph_snapshot, save_snapshot
snap = graph_snapshot(db)
save_snapshot(snap)
print(f"  Snapshot saved.")
print("\nDone!")

"""Quick audit of the current Memgraph state."""
from src.graph.memgraph_init import get_memgraph

db = get_memgraph()

# Label distribution
rows = list(db.execute_and_fetch(
    "MATCH (n) UNWIND labels(n) AS lbl RETURN lbl, count(*) AS cnt ORDER BY cnt DESC;"
))
print("=== LABEL DISTRIBUTION ===")
for r in rows:
    print(f"  {r['lbl']:25s} {r['cnt']:>6d}")

t = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c;"))[0]["c"]
e = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c;"))[0]["c"]
print(f"\nTOTAL: {t} nodes, {e} edges")

# Indicators
print("\n=== INDICATORS ===")
inds = list(db.execute_and_fetch("MATCH (n:Indicator) RETURN n.name AS name;"))
for r in inds:
    print(f"  {r['name']}")

# Relationship types
print("\n=== RELATIONSHIP TYPES ===")
rels = list(db.execute_and_fetch(
    "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC;"
))
for r in rels:
    print(f"  {r['t']:35s} {r['c']:>5d}")

# Sample some edges around 'india'
print("\n=== SAMPLE INDIA EDGES ===")
india_edges = list(db.execute_and_fetch(
    "MATCH (a)-[r]->(b) WHERE a.name = 'india' OR b.name = 'india' "
    "RETURN a.name AS src, type(r) AS rel, b.name AS tgt, r.confidence AS conf "
    "LIMIT 30;"
))
for r in india_edges:
    print(f"  ({r['src']}) -[{r['rel']}]-> ({r['tgt']})  conf={r['conf']}")

# Check GDP-related
print("\n=== GDP-RELATED ===")
gdp = list(db.execute_and_fetch(
    "MATCH (n) WHERE toLower(n.name) CONTAINS 'gdp' RETURN n.name AS name, labels(n) AS labels;"
))
for r in gdp:
    print(f"  {r['name']} {r['labels']}")
if not gdp:
    print("  (NONE FOUND)")

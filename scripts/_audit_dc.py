from src.graph.memgraph_init import get_memgraph
db = get_memgraph()

# Check causal edges into india gdp
print("=== FACTORS AFFECTING INDIA GDP ===")
rows = list(db.execute_and_fetch(
    'MATCH (a)-[r:AFFECTS]->(b {name: "india gdp"}) '
    'RETURN a.name AS factor, r.effect AS effect, r.source_context AS ctx '
    'ORDER BY a.name'
))
for r in rows:
    effect = r['effect'] or '?'
    ctx = (r['ctx'] or '')[:80]
    print(f"  {r['factor']:40s} | {effect:8s} | {ctx}")
print(f"\nTotal factors: {len(rows)}")

# Check india gdp node properties
print("\n=== INDIA GDP NODE ===")
rows2 = list(db.execute_and_fetch(
    'MATCH (n {name: "india gdp"}) '
    'RETURN n.display_value AS dv, n.date AS dt, n.description AS desc, n.value AS val'
))
for r in rows2:
    print(f"  Value: {r['dv']}  Date: {r['dt']}  Desc: {r['desc']}")

# Graph totals
print("\n=== GRAPH TOTALS ===")
res = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c"))
print(f"  Nodes: {res[0]['c']}")
res = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c"))
print(f"  Edges: {res[0]['c']}")

# Label distribution
print("\n=== LABEL DISTRIBUTION ===")
res = list(db.execute_and_fetch("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC"))
for r in res:
    print(f"  {r['l']:25s} {r['c']}")

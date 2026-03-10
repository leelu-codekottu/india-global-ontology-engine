"""Fix duplicates in the graph."""
import sys
sys.path.insert(0, ".")

from src.graph.memgraph_init import get_memgraph

db = get_memgraph()

# Check for case-sensitive duplicates in Indicator
dups = list(db.execute_and_fetch(
    "MATCH (n:Indicator) "
    "WITH toLower(n.name) AS lower_name, collect(n) AS nodes "
    "WHERE size(nodes) > 1 "
    "RETURN lower_name, [n in nodes | n.name] AS names, size(nodes) AS cnt;"
))

print("Duplicate indicators:")
for d in dups:
    print(f"  {d['lower_name']}: {d['names']} (count={d['cnt']})")
    names = d["names"]
    # Keep the lowercase version as canonical
    canonical = min(names, key=lambda x: (not x.islower(), len(x)))
    for name in names:
        if name != canonical:
            db.execute(
                'MATCH (n:Indicator {name: $name}) SET n.status = "deprecated";',
                {"name": name},
            )
            print(f"  Deprecated: {name} (kept: {canonical})")

print("\nDuplicates handled.")

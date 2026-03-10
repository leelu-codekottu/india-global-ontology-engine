"""Fix duplicate indicator nodes in Memgraph."""
import sys
sys.path.insert(0, ".")
from src.graph.memgraph_init import get_memgraph

db = get_memgraph()

# Find and fix duplicate indicators
dupes = ["oil price", "import bill", "inflation"]
for name in dupes:
    query = "MATCH (n:Indicator) WHERE toLower(n.name) = $name RETURN n.name AS nm, id(n) AS nid ORDER BY id(n)"
    rows = list(db.execute_and_fetch(query, {"name": name}))
    if len(rows) > 1:
        keep_id = rows[0]["nid"]
        for row in rows[1:]:
            dup_id = row["nid"]
            # Reassign outgoing edges from dup to keep
            db.execute(
                "MATCH (dup) WHERE id(dup) = $dup_id "
                "MATCH (dup)-[r]->(target) "
                "MATCH (keep) WHERE id(keep) = $keep_id "
                "WITH keep, target, type(r) AS rt, properties(r) AS props, r "
                "CREATE (keep)-[nr:AFFECTS]->(target) "
                "DELETE r",
                {"dup_id": dup_id, "keep_id": keep_id},
            )
            # Reassign incoming edges from dup to keep
            db.execute(
                "MATCH (dup) WHERE id(dup) = $dup_id "
                "MATCH (source)-[r]->(dup) "
                "MATCH (keep) WHERE id(keep) = $keep_id "
                "WITH keep, source, type(r) AS rt, properties(r) AS props, r "
                "CREATE (source)-[nr:AFFECTS]->(keep) "
                "DELETE r",
                {"dup_id": dup_id, "keep_id": keep_id},
            )
            # Delete the duplicate node
            db.execute(
                "MATCH (dup) WHERE id(dup) = $dup_id DETACH DELETE dup",
                {"dup_id": dup_id},
            )
            print(f"Merged duplicate: {name} (id {dup_id} -> {keep_id})")

# Verify
snap = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c"))
edges = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c"))
print(f"Total nodes after dedup: {snap[0]['c']}")
print(f"Total edges after dedup: {edges[0]['c']}")

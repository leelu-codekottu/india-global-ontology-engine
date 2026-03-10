"""Remove fake gap-filler nodes from Memgraph — Phase 3."""
from src.graph.memgraph_init import get_memgraph

db = get_memgraph()

t = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c;"))[0]["c"]
e = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c;"))[0]["c"]
print(f"Before: {t} nodes, {e} edges")

# Known legitimate events (from curated data)
KEEP_EVENTS = {
    "iran-us standoff", "south china sea dispute", "russia-ukraine war",
    "taiwan strait crisis", "kashmir conflict", "crimea annexation",
    "yemen civil war", "syrian civil war", "ethiopian tigray conflict",
    "nagorno-karabakh conflict", "israel-palestine conflict",
    "us-china trade war", "brexit", "arab spring aftermath",
    "houthi red sea attacks", "myanmar civil war",
    "g20 summit 2024 india", "cop28 dubai", "quad summit 2024",
    "brics summit 2024 kazan", "sco summit 2024",
    "india general election 2024", "chandrayaan-3", "gaganyaan",
    "aditya-l1", "ins vikrant commissioning", "tejas mk2 development",
    "bharatmala project", "sagarmala project", "make in india",
    "digital india", "pm gati shakti", "national hydrogen mission",
    "semiconductor mission india", "upi global expansion",
    "india-middle east-europe corridor (imec)",
    "chabahar port development", "instc activation",
    "india-japan bullet train", "india 5g rollout",
    "india semiconductor fab plants", "india ev transition",
    "isro reusable launch vehicle", "nisar satellite mission",
    "india renewable energy target 2030",
    "iran_us_tensions", "oil_supply_shock", "oil_price_shock",
    "iran nuclear deal", "jcpoa withdrawal",
    "opec production cut 2024", "india oil stockpile",
    "india strategic petroleum reserve expansion",
    "red sea shipping crisis", "suez canal disruption",
}

# Delete all Event nodes NOT in the keep list
rows = list(db.execute_and_fetch("MATCH (n:Event) RETURN n.name AS name;"))
deleted = 0
for r in rows:
    name = r["name"]
    if name.lower() not in {k.lower() for k in KEEP_EVENTS}:
        db.execute(
            "MATCH (n:Event {name: $name})-[r]-() DELETE r, n;",
            {"name": name},
        )
        # Handle isolated nodes
        db.execute(
            "MATCH (n:Event {name: $name}) WHERE NOT (n)--() DELETE n;",
            {"name": name},
        )
        deleted += 1

print(f"Deleted {deleted} fake Event nodes")

# Also clean any remaining orphan nodes
db.execute("MATCH (n) WHERE NOT (n)--() DELETE n;")

t2 = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c;"))[0]["c"]
e2 = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c;"))[0]["c"]
print(f"After:  {t2} nodes, {e2} edges")
print(f"Removed {t - t2} nodes, {e - e2} edges")

rows = list(db.execute_and_fetch(
    "MATCH (n) UNWIND labels(n) AS lbl RETURN lbl, count(*) AS cnt ORDER BY cnt DESC;"
))
for r in rows:
    print(f"  {r['lbl']:25s} {r['cnt']:>6d}")


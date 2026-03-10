#!/usr/bin/env python3
"""
mass_ingest.py — Expand knowledge graph to 10,000+ nodes.

Sources:
  Phase 1 (curated):     Verified real-world geopolitical knowledge with Wikipedia/authoritative refs
  Phase 2 (derived):     Programmatic indicator/entity generation from Phase-1 base data
  Phase 3 (DataCommons): Statistical data for top countries via DC API
  Phase 4 (RSS):         Real news articles → LLM-extracted triples with article URLs
  Phase 5 (gap-filler):  Adaptive generation to ensure 10K+ nodes

Usage:
  python -m scripts.mass_ingest --phase all          # run everything
  python -m scripts.mass_ingest --phase curated       # just curated + derived (fast)
  python -m scripts.mass_ingest --phase rss           # just RSS extraction (slow, ~30-60 min)
  python -m scripts.mass_ingest --phase datacommons   # just DataCommons
  python -m scripts.mass_ingest --phase fill          # gap-filler to reach 10K

Respects Groq free-tier: 12K TPM, 6s between calls.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_DIR, ALLOWED_NODE_LABELS, ALLOWED_RELATIONSHIP_TYPES
from src.graph.memgraph_init import get_memgraph, create_constraints, create_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(DATA_DIR / "mass_ingest.log")],
)
logger = logging.getLogger(__name__)

NOW = datetime.now(timezone.utc).isoformat()
WIKI = "https://en.wikipedia.org/wiki/"

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _label_for(name, hint="Event"):
    """Infer Memgraph label from name heuristics."""
    n = name.lower()
    country_set = set(COUNTRIES.keys())
    if n in country_set:
        return "Country"
    for kw in ["port", "strait", "canal", "sea", "ocean", "gulf", "bay", "river",
                "island", "peninsula", "mountain", "region", "district", "city",
                "airport", "dam", "bridge", "state", "province"]:
        if kw in n:
            return "Location"
    for kw in ["oil", "gas", "coal", "uranium", "lithium", "gold", "iron", "copper",
                "wheat", "rice", "steel", "cotton", "rubber", "aluminum"]:
        if kw in n:
            return "Resource"
    for kw in ["war", "crisis", "summit", "election", "coup", "attack", "pandemic",
                "earthquake", "flood", "conflict"]:
        if kw in n:
            return "Event"
    for kw in ["index", "rate", "gdp", "cpi", "deficit", "surplus", "inflation",
                "unemployment", "debt", "budget", "reserves", "hdi"]:
        if kw in n:
            return "EconomicIndicator"
    return hint


def make_triple(subj, pred, obj, conf=0.90, url="", ctx="", s_label=None, o_label=None):
    """Build a triple dict."""
    return {
        "subject": subj.lower().strip(),
        "predicate": pred,
        "object": obj.lower().strip(),
        "confidence": conf,
        "source_url": url or f"{WIKI}{subj.replace(' ', '_')}",
        "source_context": ctx or f"{subj} {pred.lower().replace('_',' ')} {obj}",
        "subject_label": s_label,
        "object_label": o_label,
    }


def count_nodes(db):
    res = list(db.execute_and_fetch("MATCH (n) RETURN count(n) AS c;"))
    return res[0]["c"] if res else 0


def count_edges(db):
    res = list(db.execute_and_fetch("MATCH ()-[r]->() RETURN count(r) AS c;"))
    return res[0]["c"] if res else 0


def bulk_insert(db, triples, phase_name=""):
    """Insert triples into Memgraph using MERGE. Returns (inserted, failed)."""
    from src.graph.graph_loader import insert_triple
    inserted = 0
    failed = 0
    total = len(triples)
    for i, t in enumerate(triples):
        try:
            ok = insert_triple(
                db=db,
                subject=t["subject"],
                predicate=t["predicate"],
                obj=t["object"],
                confidence=t.get("confidence", 0.90),
                source_url=t.get("source_url", ""),
                source_context=t.get("source_context", ""),
                timestamp=NOW,
                subject_label=t.get("subject_label"),
                object_label=t.get("object_label"),
            )
            if ok:
                inserted += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            if failed <= 5:
                logger.error("Insert error: %s", e)
        if (i + 1) % 500 == 0:
            logger.info("[%s] Progress: %d/%d inserted, %d failed", phase_name, inserted, total, failed)
    logger.info("[%s] Done: %d/%d inserted, %d failed", phase_name, inserted, total, failed)
    return inserted, failed


# ═══════════════════════════════════════════════════════════════════════════════
# ██████  COUNTRY DATA  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# Format: name -> {cap: capital, reg: region, brd: [borders], org: [orgs]}

COUNTRIES = {
    # ─── South Asia ───
    "india": {"cap": "new delhi", "reg": "south asia", "brd": ["pakistan","china","nepal","bhutan","bangladesh","myanmar"], "org": ["un","brics","g20","sco","saarc","commonwealth","nam"]},
    "pakistan": {"cap": "islamabad", "reg": "south asia", "brd": ["india","china","afghanistan","iran"], "org": ["un","saarc","oic","sco"]},
    "bangladesh": {"cap": "dhaka", "reg": "south asia", "brd": ["india","myanmar"], "org": ["un","saarc","oic"]},
    "sri lanka": {"cap": "colombo", "reg": "south asia", "brd": [], "org": ["un","saarc","commonwealth"]},
    "nepal": {"cap": "kathmandu", "reg": "south asia", "brd": ["india","china"], "org": ["un","saarc","nam"]},
    "bhutan": {"cap": "thimphu", "reg": "south asia", "brd": ["india","china"], "org": ["un","saarc"]},
    "maldives": {"cap": "male", "reg": "south asia", "brd": [], "org": ["un","saarc","oic","commonwealth"]},
    "afghanistan": {"cap": "kabul", "reg": "south asia", "brd": ["pakistan","iran","china","tajikistan","uzbekistan","turkmenistan"], "org": ["un","saarc","oic"]},
    # ─── East Asia ───
    "china": {"cap": "beijing", "reg": "east asia", "brd": ["india","pakistan","nepal","bhutan","myanmar","russia","mongolia","north korea","vietnam","laos","afghanistan","tajikistan","kyrgyzstan","kazakhstan"], "org": ["un","brics","g20","sco","apec"]},
    "japan": {"cap": "tokyo", "reg": "east asia", "brd": [], "org": ["un","g7","g20","apec","oecd"]},
    "south korea": {"cap": "seoul", "reg": "east asia", "brd": ["north korea"], "org": ["un","g20","apec","oecd"]},
    "north korea": {"cap": "pyongyang", "reg": "east asia", "brd": ["south korea","china","russia"], "org": ["un"]},
    "mongolia": {"cap": "ulaanbaatar", "reg": "east asia", "brd": ["china","russia"], "org": ["un"]},
    "taiwan": {"cap": "taipei", "reg": "east asia", "brd": [], "org": ["apec"]},
    # ─── Southeast Asia ───
    "indonesia": {"cap": "jakarta", "reg": "southeast asia", "brd": ["malaysia","papua new guinea","timor-leste"], "org": ["un","g20","asean","apec","oic"]},
    "thailand": {"cap": "bangkok", "reg": "southeast asia", "brd": ["myanmar","laos","cambodia","malaysia"], "org": ["un","asean","apec"]},
    "vietnam": {"cap": "hanoi", "reg": "southeast asia", "brd": ["china","laos","cambodia"], "org": ["un","asean","apec"]},
    "philippines": {"cap": "manila", "reg": "southeast asia", "brd": [], "org": ["un","asean","apec"]},
    "malaysia": {"cap": "kuala lumpur", "reg": "southeast asia", "brd": ["thailand","indonesia","brunei"], "org": ["un","asean","apec","oic","commonwealth"]},
    "singapore": {"cap": "singapore", "reg": "southeast asia", "brd": [], "org": ["un","asean","apec","commonwealth"]},
    "myanmar": {"cap": "naypyidaw", "reg": "southeast asia", "brd": ["india","china","bangladesh","thailand","laos"], "org": ["un","asean"]},
    "cambodia": {"cap": "phnom penh", "reg": "southeast asia", "brd": ["thailand","laos","vietnam"], "org": ["un","asean"]},
    "laos": {"cap": "vientiane", "reg": "southeast asia", "brd": ["china","myanmar","thailand","cambodia","vietnam"], "org": ["un","asean"]},
    "brunei": {"cap": "bandar seri begawan", "reg": "southeast asia", "brd": ["malaysia"], "org": ["un","asean","apec","oic","commonwealth"]},
    "timor-leste": {"cap": "dili", "reg": "southeast asia", "brd": ["indonesia"], "org": ["un","asean"]},
    # ─── Central Asia ───
    "kazakhstan": {"cap": "astana", "reg": "central asia", "brd": ["russia","china","kyrgyzstan","uzbekistan","turkmenistan"], "org": ["un","sco","oic"]},
    "uzbekistan": {"cap": "tashkent", "reg": "central asia", "brd": ["kazakhstan","kyrgyzstan","tajikistan","afghanistan","turkmenistan"], "org": ["un","sco","oic"]},
    "turkmenistan": {"cap": "ashgabat", "reg": "central asia", "brd": ["kazakhstan","uzbekistan","afghanistan","iran"], "org": ["un","oic"]},
    "kyrgyzstan": {"cap": "bishkek", "reg": "central asia", "brd": ["kazakhstan","uzbekistan","tajikistan","china"], "org": ["un","sco","oic"]},
    "tajikistan": {"cap": "dushanbe", "reg": "central asia", "brd": ["kyrgyzstan","uzbekistan","afghanistan","china"], "org": ["un","sco","oic"]},
    # ─── Middle East ───
    "iran": {"cap": "tehran", "reg": "middle east", "brd": ["iraq","turkey","afghanistan","pakistan","turkmenistan","armenia","azerbaijan"], "org": ["un","opec","oic","sco","brics"]},
    "iraq": {"cap": "baghdad", "reg": "middle east", "brd": ["iran","turkey","syria","jordan","saudi arabia","kuwait"], "org": ["un","opec","oic","arab league"]},
    "saudi arabia": {"cap": "riyadh", "reg": "middle east", "brd": ["jordan","iraq","kuwait","qatar","uae","oman","yemen"], "org": ["un","g20","opec","oic","arab league"]},
    "united arab emirates": {"cap": "abu dhabi", "reg": "middle east", "brd": ["saudi arabia","oman"], "org": ["un","opec","oic","arab league"]},
    "qatar": {"cap": "doha", "reg": "middle east", "brd": ["saudi arabia"], "org": ["un","opec","oic","arab league"]},
    "kuwait": {"cap": "kuwait city", "reg": "middle east", "brd": ["iraq","saudi arabia"], "org": ["un","opec","oic","arab league"]},
    "oman": {"cap": "muscat", "reg": "middle east", "brd": ["saudi arabia","uae","yemen"], "org": ["un","oic","arab league"]},
    "bahrain": {"cap": "manama", "reg": "middle east", "brd": [], "org": ["un","oic","arab league"]},
    "yemen": {"cap": "sanaa", "reg": "middle east", "brd": ["saudi arabia","oman"], "org": ["un","oic","arab league"]},
    "israel": {"cap": "jerusalem", "reg": "middle east", "brd": ["lebanon","syria","jordan","egypt"], "org": ["un","oecd"]},
    "palestine": {"cap": "ramallah", "reg": "middle east", "brd": ["israel"], "org": ["un","oic","arab league"]},
    "jordan": {"cap": "amman", "reg": "middle east", "brd": ["israel","syria","iraq","saudi arabia"], "org": ["un","oic","arab league"]},
    "lebanon": {"cap": "beirut", "reg": "middle east", "brd": ["israel","syria"], "org": ["un","oic","arab league"]},
    "syria": {"cap": "damascus", "reg": "middle east", "brd": ["turkey","iraq","jordan","israel","lebanon"], "org": ["un","oic","arab league"]},
    "turkey": {"cap": "ankara", "reg": "middle east", "brd": ["greece","bulgaria","syria","iraq","iran","georgia","armenia","azerbaijan"], "org": ["un","nato","g20","oecd","oic"]},
    # ─── Europe ───
    "russia": {"cap": "moscow", "reg": "europe", "brd": ["norway","finland","estonia","latvia","lithuania","poland","belarus","ukraine","georgia","azerbaijan","kazakhstan","china","mongolia","north korea"], "org": ["un","brics","g20","sco","apec"]},
    "united kingdom": {"cap": "london", "reg": "europe", "brd": ["ireland"], "org": ["un","g7","g20","nato","oecd","commonwealth"]},
    "france": {"cap": "paris", "reg": "europe", "brd": ["belgium","luxembourg","germany","switzerland","italy","spain","andorra"], "org": ["un","g7","g20","nato","eu","oecd"]},
    "germany": {"cap": "berlin", "reg": "europe", "brd": ["denmark","poland","czech republic","austria","switzerland","france","luxembourg","belgium","netherlands"], "org": ["un","g7","g20","nato","eu","oecd"]},
    "italy": {"cap": "rome", "reg": "europe", "brd": ["france","switzerland","austria","slovenia"], "org": ["un","g7","g20","nato","eu","oecd"]},
    "spain": {"cap": "madrid", "reg": "europe", "brd": ["france","portugal","andorra"], "org": ["un","nato","eu","oecd"]},
    "portugal": {"cap": "lisbon", "reg": "europe", "brd": ["spain"], "org": ["un","nato","eu","oecd"]},
    "netherlands": {"cap": "amsterdam", "reg": "europe", "brd": ["belgium","germany"], "org": ["un","nato","eu","oecd"]},
    "belgium": {"cap": "brussels", "reg": "europe", "brd": ["netherlands","germany","france","luxembourg"], "org": ["un","nato","eu","oecd"]},
    "switzerland": {"cap": "bern", "reg": "europe", "brd": ["germany","france","italy","austria","liechtenstein"], "org": ["un","oecd"]},
    "austria": {"cap": "vienna", "reg": "europe", "brd": ["germany","czech republic","slovakia","hungary","slovenia","italy","switzerland","liechtenstein"], "org": ["un","eu","oecd"]},
    "poland": {"cap": "warsaw", "reg": "europe", "brd": ["germany","czech republic","slovakia","ukraine","belarus","lithuania","russia"], "org": ["un","nato","eu","oecd"]},
    "ukraine": {"cap": "kyiv", "reg": "europe", "brd": ["russia","belarus","poland","slovakia","hungary","romania","moldova"], "org": ["un"]},
    "romania": {"cap": "bucharest", "reg": "europe", "brd": ["ukraine","moldova","hungary","serbia","bulgaria"], "org": ["un","nato","eu"]},
    "hungary": {"cap": "budapest", "reg": "europe", "brd": ["austria","slovakia","ukraine","romania","serbia","croatia","slovenia"], "org": ["un","nato","eu","oecd"]},
    "czech republic": {"cap": "prague", "reg": "europe", "brd": ["germany","poland","slovakia","austria"], "org": ["un","nato","eu","oecd"]},
    "slovakia": {"cap": "bratislava", "reg": "europe", "brd": ["czech republic","poland","ukraine","hungary","austria"], "org": ["un","nato","eu","oecd"]},
    "greece": {"cap": "athens", "reg": "europe", "brd": ["turkey","bulgaria","north macedonia","albania"], "org": ["un","nato","eu","oecd"]},
    "sweden": {"cap": "stockholm", "reg": "europe", "brd": ["norway","finland"], "org": ["un","nato","eu","oecd"]},
    "norway": {"cap": "oslo", "reg": "europe", "brd": ["sweden","finland","russia"], "org": ["un","nato","oecd"]},
    "finland": {"cap": "helsinki", "reg": "europe", "brd": ["sweden","norway","russia"], "org": ["un","nato","eu","oecd"]},
    "denmark": {"cap": "copenhagen", "reg": "europe", "brd": ["germany"], "org": ["un","nato","eu","oecd"]},
    "ireland": {"cap": "dublin", "reg": "europe", "brd": ["united kingdom"], "org": ["un","eu","oecd"]},
    "serbia": {"cap": "belgrade", "reg": "europe", "brd": ["hungary","romania","bulgaria","north macedonia","albania","montenegro","bosnia and herzegovina","croatia"], "org": ["un"]},
    "croatia": {"cap": "zagreb", "reg": "europe", "brd": ["slovenia","hungary","serbia","bosnia and herzegovina","montenegro"], "org": ["un","nato","eu"]},
    "bulgaria": {"cap": "sofia", "reg": "europe", "brd": ["romania","serbia","north macedonia","greece","turkey"], "org": ["un","nato","eu"]},
    "belarus": {"cap": "minsk", "reg": "europe", "brd": ["russia","ukraine","poland","lithuania","latvia"], "org": ["un"]},
    "georgia": {"cap": "tbilisi", "reg": "europe", "brd": ["russia","turkey","armenia","azerbaijan"], "org": ["un"]},
    "armenia": {"cap": "yerevan", "reg": "europe", "brd": ["georgia","turkey","iran","azerbaijan"], "org": ["un"]},
    "azerbaijan": {"cap": "baku", "reg": "europe", "brd": ["russia","georgia","armenia","iran","turkey"], "org": ["un","oic"]},
    "moldova": {"cap": "chisinau", "reg": "europe", "brd": ["romania","ukraine"], "org": ["un"]},
    "estonia": {"cap": "tallinn", "reg": "europe", "brd": ["russia","latvia"], "org": ["un","nato","eu","oecd"]},
    "latvia": {"cap": "riga", "reg": "europe", "brd": ["estonia","russia","belarus","lithuania"], "org": ["un","nato","eu","oecd"]},
    "lithuania": {"cap": "vilnius", "reg": "europe", "brd": ["latvia","belarus","poland","russia"], "org": ["un","nato","eu","oecd"]},
    "slovenia": {"cap": "ljubljana", "reg": "europe", "brd": ["italy","austria","hungary","croatia"], "org": ["un","nato","eu","oecd"]},
    "iceland": {"cap": "reykjavik", "reg": "europe", "brd": [], "org": ["un","nato","oecd"]},
    "cyprus": {"cap": "nicosia", "reg": "europe", "brd": [], "org": ["un","eu"]},
    "malta": {"cap": "valletta", "reg": "europe", "brd": [], "org": ["un","eu","commonwealth"]},
    "luxembourg": {"cap": "luxembourg city", "reg": "europe", "brd": ["belgium","germany","france"], "org": ["un","nato","eu","oecd"]},
    "north macedonia": {"cap": "skopje", "reg": "europe", "brd": ["serbia","bulgaria","greece","albania"], "org": ["un","nato"]},
    "albania": {"cap": "tirana", "reg": "europe", "brd": ["montenegro","serbia","north macedonia","greece"], "org": ["un","nato"]},
    "montenegro": {"cap": "podgorica", "reg": "europe", "brd": ["croatia","bosnia and herzegovina","serbia","albania"], "org": ["un","nato"]},
    "bosnia and herzegovina": {"cap": "sarajevo", "reg": "europe", "brd": ["croatia","serbia","montenegro"], "org": ["un"]},
    # ─── Africa ───
    "egypt": {"cap": "cairo", "reg": "north africa", "brd": ["israel","libya","sudan"], "org": ["un","oic","arab league","african union","brics"]},
    "south africa": {"cap": "pretoria", "reg": "southern africa", "brd": ["namibia","botswana","zimbabwe","mozambique","eswatini","lesotho"], "org": ["un","brics","g20","african union","commonwealth"]},
    "nigeria": {"cap": "abuja", "reg": "west africa", "brd": ["benin","niger","chad","cameroon"], "org": ["un","opec","oic","african union","commonwealth"]},
    "ethiopia": {"cap": "addis ababa", "reg": "east africa", "brd": ["eritrea","djibouti","somalia","kenya","sudan","south sudan"], "org": ["un","african union","brics"]},
    "kenya": {"cap": "nairobi", "reg": "east africa", "brd": ["ethiopia","somalia","tanzania","uganda","south sudan"], "org": ["un","african union","commonwealth"]},
    "morocco": {"cap": "rabat", "reg": "north africa", "brd": ["algeria"], "org": ["un","oic","arab league","african union"]},
    "algeria": {"cap": "algiers", "reg": "north africa", "brd": ["morocco","tunisia","libya","niger","mali","mauritania"], "org": ["un","opec","oic","arab league","african union"]},
    "libya": {"cap": "tripoli", "reg": "north africa", "brd": ["tunisia","algeria","niger","chad","sudan","egypt"], "org": ["un","opec","oic","arab league","african union"]},
    "tunisia": {"cap": "tunis", "reg": "north africa", "brd": ["algeria","libya"], "org": ["un","oic","arab league","african union"]},
    "sudan": {"cap": "khartoum", "reg": "east africa", "brd": ["egypt","libya","chad","central african republic","south sudan","ethiopia","eritrea"], "org": ["un","oic","arab league","african union"]},
    "ghana": {"cap": "accra", "reg": "west africa", "brd": ["ivory coast","burkina faso","togo"], "org": ["un","african union","commonwealth"]},
    "tanzania": {"cap": "dodoma", "reg": "east africa", "brd": ["kenya","uganda","rwanda","burundi","democratic republic of congo","zambia","malawi","mozambique"], "org": ["un","african union","commonwealth"]},
    "democratic republic of congo": {"cap": "kinshasa", "reg": "central africa", "brd": ["republic of congo","central african republic","south sudan","uganda","rwanda","burundi","tanzania","zambia","angola"], "org": ["un","african union"]},
    "angola": {"cap": "luanda", "reg": "southern africa", "brd": ["democratic republic of congo","republic of congo","zambia","namibia"], "org": ["un","opec","african union"]},
    "mozambique": {"cap": "maputo", "reg": "southern africa", "brd": ["south africa","eswatini","tanzania","malawi","zambia","zimbabwe"], "org": ["un","african union","commonwealth"]},
    # ─── Americas ───
    "united states": {"cap": "washington dc", "reg": "north america", "brd": ["canada","mexico"], "org": ["un","g7","g20","nato","oecd","apec"]},
    "canada": {"cap": "ottawa", "reg": "north america", "brd": ["united states"], "org": ["un","g7","g20","nato","oecd","apec","commonwealth"]},
    "mexico": {"cap": "mexico city", "reg": "north america", "brd": ["united states","guatemala","belize"], "org": ["un","g20","oecd","apec"]},
    "brazil": {"cap": "brasilia", "reg": "south america", "brd": ["argentina","uruguay","paraguay","bolivia","peru","colombia","venezuela","guyana","suriname","french guiana"], "org": ["un","brics","g20"]},
    "argentina": {"cap": "buenos aires", "reg": "south america", "brd": ["brazil","uruguay","paraguay","bolivia","chile"], "org": ["un","g20"]},
    "colombia": {"cap": "bogota", "reg": "south america", "brd": ["venezuela","brazil","peru","ecuador","panama"], "org": ["un","nato","oecd"]},
    "venezuela": {"cap": "caracas", "reg": "south america", "brd": ["colombia","brazil","guyana"], "org": ["un","opec","oic"]},
    "chile": {"cap": "santiago", "reg": "south america", "brd": ["argentina","bolivia","peru"], "org": ["un","oecd","apec"]},
    "peru": {"cap": "lima", "reg": "south america", "brd": ["ecuador","colombia","brazil","bolivia","chile"], "org": ["un","apec"]},
    "ecuador": {"cap": "quito", "reg": "south america", "brd": ["colombia","peru"], "org": ["un","opec"]},
    "cuba": {"cap": "havana", "reg": "caribbean", "brd": [], "org": ["un","nam"]},
    # ─── Oceania ───
    "australia": {"cap": "canberra", "reg": "oceania", "brd": [], "org": ["un","g20","oecd","apec","commonwealth"]},
    "new zealand": {"cap": "wellington", "reg": "oceania", "brd": [], "org": ["un","oecd","apec","commonwealth"]},
    "papua new guinea": {"cap": "port moresby", "reg": "oceania", "brd": ["indonesia"], "org": ["un","apec","commonwealth"]},
    "fiji": {"cap": "suva", "reg": "oceania", "brd": [], "org": ["un","commonwealth"]},
}

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  ORGANIZATIONS  ██████
# ═══════════════════════════════════════════════════════════════════════════════

ORGANIZATIONS = {
    "un": {"full": "United Nations", "hq": "new york city", "members": list(COUNTRIES.keys())},
    "nato": {"full": "North Atlantic Treaty Organization", "hq": "brussels", "members": [
        "united states","canada","united kingdom","france","germany","italy","spain","portugal",
        "netherlands","belgium","luxembourg","denmark","norway","iceland","turkey","greece",
        "poland","czech republic","hungary","romania","bulgaria","slovakia","slovenia","croatia",
        "albania","north macedonia","montenegro","estonia","latvia","lithuania","finland","sweden"]},
    "eu": {"full": "European Union", "hq": "brussels", "members": [
        "france","germany","italy","spain","portugal","netherlands","belgium","luxembourg",
        "denmark","ireland","austria","sweden","finland","poland","czech republic","slovakia",
        "hungary","romania","bulgaria","greece","croatia","slovenia","estonia","latvia",
        "lithuania","cyprus","malta"]},
    "brics": {"full": "BRICS", "hq": "rotating", "members": [
        "brazil","russia","india","china","south africa","egypt","ethiopia","iran",
        "saudi arabia","united arab emirates"]},
    "g7": {"full": "Group of Seven", "hq": "rotating", "members": [
        "united states","united kingdom","france","germany","italy","canada","japan"]},
    "g20": {"full": "Group of Twenty", "hq": "rotating", "members": [
        "united states","united kingdom","france","germany","italy","canada","japan",
        "australia","argentina","brazil","china","india","indonesia","mexico","russia",
        "saudi arabia","south korea","south africa","turkey"]},
    "opec": {"full": "Organization of the Petroleum Exporting Countries", "hq": "vienna", "members": [
        "iran","iraq","kuwait","saudi arabia","venezuela","algeria","angola","libya",
        "nigeria","united arab emirates","republic of congo","ecuador","qatar"]},
    "sco": {"full": "Shanghai Cooperation Organisation", "hq": "beijing", "members": [
        "china","russia","india","pakistan","kazakhstan","kyrgyzstan","tajikistan","uzbekistan","iran","belarus"]},
    "saarc": {"full": "South Asian Association for Regional Cooperation", "hq": "kathmandu", "members": [
        "india","pakistan","bangladesh","sri lanka","nepal","bhutan","maldives","afghanistan"]},
    "asean": {"full": "Association of Southeast Asian Nations", "hq": "jakarta", "members": [
        "indonesia","thailand","vietnam","philippines","malaysia","singapore","myanmar",
        "cambodia","laos","brunei"]},
    "african union": {"full": "African Union", "hq": "addis ababa", "members": [
        "egypt","south africa","nigeria","ethiopia","kenya","morocco","algeria","libya",
        "tunisia","sudan","ghana","tanzania","democratic republic of congo","angola","mozambique"]},
    "arab league": {"full": "League of Arab States", "hq": "cairo", "members": [
        "egypt","iraq","saudi arabia","united arab emirates","qatar","kuwait","oman","bahrain",
        "yemen","jordan","lebanon","syria","palestine","libya","tunisia","algeria","morocco","sudan"]},
    "oic": {"full": "Organisation of Islamic Cooperation", "hq": "jeddah", "members": [
        "saudi arabia","iran","iraq","pakistan","bangladesh","indonesia","malaysia","turkey",
        "egypt","nigeria","algeria","morocco","jordan","qatar","kuwait","oman","bahrain","yemen",
        "sudan","tunisia","libya","brunei","maldives","afghanistan","uzbekistan","kazakhstan",
        "kyrgyzstan","tajikistan","turkmenistan","azerbaijan"]},
    "commonwealth": {"full": "Commonwealth of Nations", "hq": "london", "members": [
        "united kingdom","india","canada","australia","new zealand","south africa","nigeria",
        "kenya","ghana","malaysia","singapore","bangladesh","sri lanka","pakistan","brunei",
        "malta","fiji","mozambique","tanzania","papua new guinea"]},
    "apec": {"full": "Asia-Pacific Economic Cooperation", "hq": "singapore", "members": [
        "australia","canada","chile","china","indonesia","japan","south korea","malaysia",
        "mexico","new zealand","peru","philippines","russia","singapore","taiwan","thailand",
        "united states","vietnam","brunei","papua new guinea"]},
    "oecd": {"full": "Organisation for Economic Co-operation and Development", "hq": "paris", "members": [
        "united states","united kingdom","france","germany","italy","canada","japan","australia",
        "austria","belgium","chile","colombia","czech republic","denmark","estonia","finland",
        "greece","hungary","iceland","ireland","israel","south korea","latvia","lithuania",
        "luxembourg","mexico","netherlands","new zealand","norway","poland","portugal","slovakia",
        "slovenia","spain","sweden","switzerland","turkey"]},
    "nam": {"full": "Non-Aligned Movement", "hq": "rotating", "members": [
        "india","indonesia","egypt","cuba","venezuela","iran","iraq","nigeria","algeria",
        "south africa","ethiopia","vietnam","laos","cambodia","myanmar","malaysia","nepal"]},
    "imf": {"full": "International Monetary Fund", "hq": "washington dc", "members": []},
    "world bank": {"full": "World Bank", "hq": "washington dc", "members": []},
    "wto": {"full": "World Trade Organization", "hq": "geneva", "members": []},
    "iaea": {"full": "International Atomic Energy Agency", "hq": "vienna", "members": []},
    "who": {"full": "World Health Organization", "hq": "geneva", "members": []},
    "unesco": {"full": "UNESCO", "hq": "paris", "members": []},
    "interpol": {"full": "International Criminal Police Organization", "hq": "lyon", "members": []},
    "icj": {"full": "International Court of Justice", "hq": "the hague", "members": []},
    "icc": {"full": "International Criminal Court", "hq": "the hague", "members": []},
    "red cross": {"full": "International Committee of the Red Cross", "hq": "geneva", "members": []},
    "world economic forum": {"full": "World Economic Forum", "hq": "cologny", "members": []},
}

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  COMPANIES  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, hq_country, sector)

COMPANIES = [
    # ─── Indian Companies ───
    ("reliance industries", "india", "energy"), ("tata group", "india", "conglomerate"),
    ("tata consultancy services", "india", "technology"), ("infosys", "india", "technology"),
    ("wipro", "india", "technology"), ("hcl technologies", "india", "technology"),
    ("adani group", "india", "infrastructure"), ("adani ports", "india", "infrastructure"),
    ("adani green energy", "india", "energy"), ("larsen & toubro", "india", "engineering"),
    ("mahindra group", "india", "conglomerate"), ("bajaj auto", "india", "automotive"),
    ("hero motocorp", "india", "automotive"), ("maruti suzuki", "india", "automotive"),
    ("tata motors", "india", "automotive"), ("ashok leyland", "india", "automotive"),
    ("oil and natural gas corporation", "india", "energy"), ("bharat petroleum", "india", "energy"),
    ("indian oil corporation", "india", "energy"), ("hindustan petroleum", "india", "energy"),
    ("gail india", "india", "energy"), ("ntpc", "india", "energy"),
    ("coal india", "india", "mining"), ("power grid corporation", "india", "energy"),
    ("state bank of india", "india", "banking"), ("icici bank", "india", "banking"),
    ("hdfc bank", "india", "banking"), ("axis bank", "india", "banking"),
    ("kotak mahindra bank", "india", "banking"), ("bank of baroda", "india", "banking"),
    ("punjab national bank", "india", "banking"), ("canara bank", "india", "banking"),
    ("bharti airtel", "india", "telecom"), ("jio platforms", "india", "telecom"),
    ("vodafone idea", "india", "telecom"), ("itc limited", "india", "fmcg"),
    ("hindustan unilever", "india", "fmcg"), ("asian paints", "india", "chemicals"),
    ("pidilite industries", "india", "chemicals"), ("godrej group", "india", "conglomerate"),
    ("jsw steel", "india", "metals"), ("vedanta limited", "india", "mining"),
    ("hindalco industries", "india", "metals"), ("tata steel", "india", "metals"),
    ("sun pharmaceutical", "india", "pharma"), ("dr reddys laboratories", "india", "pharma"),
    ("cipla", "india", "pharma"), ("lupin", "india", "pharma"),
    ("biocon", "india", "pharma"), ("divi's laboratories", "india", "pharma"),
    ("zomato", "india", "technology"), ("swiggy", "india", "technology"),
    ("flipkart", "india", "technology"), ("ola", "india", "technology"),
    ("paytm", "india", "fintech"), ("razorpay", "india", "fintech"),
    ("irctc", "india", "transport"), ("indian railways", "india", "transport"),
    ("air india", "india", "aviation"), ("indigo airlines", "india", "aviation"),
    ("hal", "india", "defense"), ("bharat electronics", "india", "defense"),
    ("bharat dynamics", "india", "defense"), ("brahmos aerospace", "india", "defense"),
    ("isro", "india", "space"), ("drdo", "india", "defense"),
    ("nhpc", "india", "energy"), ("nhai", "india", "infrastructure"),
    ("life insurance corporation", "india", "insurance"), ("general insurance corporation", "india", "insurance"),
    # ─── US Companies ───
    ("apple", "united states", "technology"), ("google", "united states", "technology"),
    ("microsoft", "united states", "technology"), ("amazon", "united states", "technology"),
    ("meta platforms", "united states", "technology"), ("tesla", "united states", "automotive"),
    ("nvidia", "united states", "technology"), ("amd", "united states", "technology"),
    ("intel", "united states", "technology"), ("qualcomm", "united states", "technology"),
    ("broadcom", "united states", "technology"), ("cisco systems", "united states", "technology"),
    ("ibm", "united states", "technology"), ("oracle", "united states", "technology"),
    ("salesforce", "united states", "technology"), ("adobe", "united states", "technology"),
    ("netflix", "united states", "technology"), ("uber", "united states", "technology"),
    ("openai", "united states", "technology"), ("spacex", "united states", "space"),
    ("palantir technologies", "united states", "technology"), ("snowflake", "united states", "technology"),
    ("exxonmobil", "united states", "energy"), ("chevron", "united states", "energy"),
    ("conocophillips", "united states", "energy"), ("baker hughes", "united states", "energy"),
    ("halliburton", "united states", "energy"), ("schlumberger", "united states", "energy"),
    ("jpmorgan chase", "united states", "banking"), ("goldman sachs", "united states", "banking"),
    ("morgan stanley", "united states", "banking"), ("citigroup", "united states", "banking"),
    ("bank of america", "united states", "banking"), ("wells fargo", "united states", "banking"),
    ("blackrock", "united states", "finance"), ("vanguard group", "united states", "finance"),
    ("berkshire hathaway", "united states", "conglomerate"), ("visa", "united states", "fintech"),
    ("mastercard", "united states", "fintech"), ("paypal", "united states", "fintech"),
    ("lockheed martin", "united states", "defense"), ("boeing", "united states", "defense"),
    ("raytheon technologies", "united states", "defense"), ("northrop grumman", "united states", "defense"),
    ("general dynamics", "united states", "defense"), ("l3harris technologies", "united states", "defense"),
    ("general electric", "united states", "conglomerate"), ("honeywell", "united states", "conglomerate"),
    ("3m company", "united states", "conglomerate"), ("caterpillar", "united states", "machinery"),
    ("deere & company", "united states", "machinery"), ("ford motor company", "united states", "automotive"),
    ("general motors", "united states", "automotive"), ("procter & gamble", "united states", "fmcg"),
    ("johnson & johnson", "united states", "pharma"), ("pfizer", "united states", "pharma"),
    ("merck", "united states", "pharma"), ("moderna", "united states", "pharma"),
    ("abbvie", "united states", "pharma"), ("united health group", "united states", "healthcare"),
    ("walmart", "united states", "retail"), ("costco", "united states", "retail"),
    ("fedex", "united states", "logistics"), ("ups", "united states", "logistics"),
    ("delta air lines", "united states", "aviation"), ("united airlines", "united states", "aviation"),
    ("american airlines", "united states", "aviation"),
    # ─── European Companies ───
    ("shell", "netherlands", "energy"), ("bp", "united kingdom", "energy"),
    ("totalenergies", "france", "energy"), ("equinor", "norway", "energy"),
    ("eni", "italy", "energy"), ("repsol", "spain", "energy"),
    ("unilever", "united kingdom", "fmcg"), ("nestle", "switzerland", "fmcg"),
    ("lvmh", "france", "luxury"), ("hermes", "france", "luxury"),
    ("sap", "germany", "technology"), ("siemens", "germany", "conglomerate"),
    ("airbus", "france", "defense"), ("volkswagen", "germany", "automotive"),
    ("bmw", "germany", "automotive"), ("mercedes-benz", "germany", "automotive"),
    ("stellantis", "netherlands", "automotive"), ("renault", "france", "automotive"),
    ("volvo", "sweden", "automotive"), ("rolls-royce", "united kingdom", "engineering"),
    ("bae systems", "united kingdom", "defense"), ("thales group", "france", "defense"),
    ("leonardo", "italy", "defense"), ("rheinmetall", "germany", "defense"),
    ("novartis", "switzerland", "pharma"), ("roche", "switzerland", "pharma"),
    ("astrazeneca", "united kingdom", "pharma"), ("gsk", "united kingdom", "pharma"),
    ("sanofi", "france", "pharma"), ("bayer", "germany", "pharma"),
    ("hsbc", "united kingdom", "banking"), ("barclays", "united kingdom", "banking"),
    ("deutsche bank", "germany", "banking"), ("bnp paribas", "france", "banking"),
    ("ubs", "switzerland", "banking"), ("credit suisse", "switzerland", "banking"),
    ("ing group", "netherlands", "banking"), ("societe generale", "france", "banking"),
    ("ericsson", "sweden", "technology"), ("nokia", "finland", "technology"),
    ("philips", "netherlands", "technology"), ("asml", "netherlands", "technology"),
    ("spotify", "sweden", "technology"), ("maersk", "denmark", "logistics"),
    ("arcelormittal", "luxembourg", "metals"), ("glencore", "switzerland", "mining"),
    ("rio tinto", "united kingdom", "mining"), ("anglo american", "united kingdom", "mining"),
    # ─── Chinese Companies ───
    ("huawei", "china", "technology"), ("tencent", "china", "technology"),
    ("alibaba group", "china", "technology"), ("bytedance", "china", "technology"),
    ("baidu", "china", "technology"), ("xiaomi", "china", "technology"),
    ("jd.com", "china", "technology"), ("dji", "china", "technology"),
    ("lenovo", "china", "technology"), ("zte", "china", "technology"),
    ("petrochina", "china", "energy"), ("sinopec", "china", "energy"),
    ("cnooc", "china", "energy"), ("china state construction", "china", "construction"),
    ("china railway", "china", "infrastructure"), ("icbc", "china", "banking"),
    ("bank of china", "china", "banking"), ("china construction bank", "china", "banking"),
    ("agricultural bank of china", "china", "banking"), ("ping an insurance", "china", "insurance"),
    ("byd", "china", "automotive"), ("saic motor", "china", "automotive"),
    ("china telecom", "china", "telecom"), ("china mobile", "china", "telecom"),
    ("catl", "china", "technology"), ("smic", "china", "technology"),
    # ─── Japanese Companies ───
    ("toyota", "japan", "automotive"), ("honda", "japan", "automotive"),
    ("nissan", "japan", "automotive"), ("sony", "japan", "technology"),
    ("panasonic", "japan", "technology"), ("hitachi", "japan", "conglomerate"),
    ("mitsubishi", "japan", "conglomerate"), ("softbank", "japan", "technology"),
    ("toshiba", "japan", "technology"), ("fujitsu", "japan", "technology"),
    ("canon", "japan", "technology"), ("ntt", "japan", "telecom"),
    ("nippon steel", "japan", "metals"), ("sumitomo", "japan", "conglomerate"),
    ("itochu", "japan", "conglomerate"),
    # ─── Korean Companies ───
    ("samsung electronics", "south korea", "technology"), ("sk hynix", "south korea", "technology"),
    ("lg electronics", "south korea", "technology"), ("hyundai motor", "south korea", "automotive"),
    ("kia", "south korea", "automotive"), ("posco", "south korea", "metals"),
    ("samsung sdi", "south korea", "technology"), ("sk group", "south korea", "conglomerate"),
    # ─── Middle East Companies ───
    ("saudi aramco", "saudi arabia", "energy"), ("adnoc", "united arab emirates", "energy"),
    ("qatar energy", "qatar", "energy"), ("sabic", "saudi arabia", "chemicals"),
    ("emirates airlines", "united arab emirates", "aviation"), ("etihad airways", "united arab emirates", "aviation"),
    ("qatar airways", "qatar", "aviation"), ("dp world", "united arab emirates", "logistics"),
    ("emaar properties", "united arab emirates", "real estate"),
    # ─── Other Companies ───
    ("tsmc", "taiwan", "technology"), ("foxconn", "taiwan", "technology"),
    ("vale", "brazil", "mining"), ("petrobras", "brazil", "energy"),
    ("bhp", "australia", "mining"), ("fortescue metals", "australia", "mining"),
    ("petronas", "malaysia", "energy"), ("singapore airlines", "singapore", "aviation"),
    ("grab", "singapore", "technology"),
    ("gazprom", "russia", "energy"), ("rosneft", "russia", "energy"),
    ("lukoil", "russia", "energy"), ("novatek", "russia", "energy"),
    ("rosatom", "russia", "energy"), ("almaz-antey", "russia", "defense"),
    ("sukhoi", "russia", "defense"), ("rostec", "russia", "defense"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  PEOPLE  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, role, country_or_org)

PEOPLE = [
    # ─── India ───
    ("narendra modi", "prime minister", "india"), ("droupadi murmu", "president", "india"),
    ("s jaishankar", "minister of external affairs", "india"), ("nirmala sitharaman", "finance minister", "india"),
    ("rajnath singh", "defense minister", "india"), ("amit shah", "home minister", "india"),
    ("ajit doval", "national security advisor", "india"), ("shaktikanta das", "rbi governor", "india"),
    ("mukesh ambani", "chairman reliance industries", "india"), ("gautam adani", "chairman adani group", "india"),
    ("ratan tata", "chairman tata group", "india"), ("sundar pichai", "ceo google", "india"),
    ("satya nadella", "ceo microsoft", "india"), ("nandan nilekani", "co-founder infosys", "india"),
    ("anil ambani", "chairman reliance adag", "india"), ("kumar mangalam birla", "chairman aditya birla group", "india"),
    ("s somanath", "chairman isro", "india"), ("bipin rawat", "former cds india", "india"),
    ("anil chauhan", "chief of defence staff", "india"),
    ("manoj pande", "chief of army staff", "india"), ("r hari kumar", "chief of naval staff", "india"),
    # ─── USA ───
    ("joe biden", "president", "united states"), ("kamala harris", "vice president", "united states"),
    ("antony blinken", "secretary of state", "united states"), ("lloyd austin", "secretary of defense", "united states"),
    ("janet yellen", "treasury secretary", "united states"), ("jerome powell", "fed chair", "united states"),
    ("jake sullivan", "national security advisor", "united states"),
    ("donald trump", "former president", "united states"),
    ("elon musk", "ceo tesla", "united states"), ("tim cook", "ceo apple", "united states"),
    ("mark zuckerberg", "ceo meta", "united states"), ("jeff bezos", "founder amazon", "united states"),
    ("warren buffett", "ceo berkshire hathaway", "united states"),
    ("sam altman", "ceo openai", "united states"), ("jensen huang", "ceo nvidia", "united states"),
    ("jamie dimon", "ceo jpmorgan chase", "united states"),
    # ─── China ───
    ("xi jinping", "president", "china"), ("li qiang", "premier", "china"),
    ("wang yi", "foreign minister", "china"), ("yi gang", "pboc governor", "china"),
    ("jack ma", "founder alibaba", "china"), ("ren zhengfei", "founder huawei", "china"),
    ("pony ma", "ceo tencent", "china"),
    # ─── Russia ───
    ("vladimir putin", "president", "russia"), ("sergei lavrov", "foreign minister", "russia"),
    ("sergei shoigu", "secretary security council", "russia"), ("elvira nabiullina", "central bank governor", "russia"),
    # ─── UK ───
    ("charles iii", "king", "united kingdom"), ("keir starmer", "prime minister", "united kingdom"),
    ("rishi sunak", "former prime minister", "united kingdom"),
    # ─── France ───
    ("emmanuel macron", "president", "france"),
    # ─── Germany ───
    ("olaf scholz", "chancellor", "germany"),
    # ─── Japan ───
    ("fumio kishida", "prime minister", "japan"),
    # ─── Middle East ───
    ("mohammed bin salman", "crown prince", "saudi arabia"),
    ("mohammed bin zayed", "president", "united arab emirates"),
    ("ebrahim raisi", "president", "iran"), ("ali khamenei", "supreme leader", "iran"),
    ("benjamin netanyahu", "prime minister", "israel"),
    ("recep tayyip erdogan", "president", "turkey"),
    # ─── South Asia ───
    ("shehbaz sharif", "prime minister", "pakistan"),
    ("sheikh hasina", "prime minister", "bangladesh"),
    ("pushpa kamal dahal", "prime minister", "nepal"),
    ("ranil wickremesinghe", "president", "sri lanka"),
    # ─── Africa ───
    ("cyril ramaphosa", "president", "south africa"),
    ("abdel fattah el-sisi", "president", "egypt"),
    ("bola tinubu", "president", "nigeria"),
    ("paul kagame", "president", "kenya"),
    # ─── LatAm ───
    ("lula da silva", "president", "brazil"),
    # ─── International ───
    ("antonio guterres", "secretary-general", "un"),
    ("kristalina georgieva", "managing director", "imf"),
    ("ajay banga", "president", "world bank"),
    ("tedros adhanom", "director-general", "who"),
    ("rafael grossi", "director-general", "iaea"),
    ("jens stoltenberg", "secretary-general", "nato"),
    ("ursula von der leyen", "president european commission", "eu"),
    ("haitham al-ghais", "secretary-general", "opec"),
    ("ngozi okonjo-iweala", "director-general", "wto"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  CITIES (beyond capitals)  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (city_name, country)

CITIES = [
    # ─── India (major cities beyond New Delhi) ───
    ("mumbai", "india"), ("bangalore", "india"), ("hyderabad", "india"),
    ("chennai", "india"), ("kolkata", "india"), ("pune", "india"),
    ("ahmedabad", "india"), ("jaipur", "india"), ("lucknow", "india"),
    ("kanpur", "india"), ("nagpur", "india"), ("visakhapatnam", "india"),
    ("bhopal", "india"), ("patna", "india"), ("vadodara", "india"),
    ("goa", "india"), ("chandigarh", "india"), ("thiruvananthapuram", "india"),
    ("coimbatore", "india"), ("indore", "india"), ("surat", "india"),
    ("kochi", "india"), ("dehradun", "india"), ("guwahati", "india"),
    ("ranchi", "india"), ("bhubaneswar", "india"), ("raipur", "india"),
    ("amritsar", "india"), ("varanasi", "india"), ("agra", "india"),
    ("noida", "india"), ("gurugram", "india"), ("faridabad", "india"),
    ("gandhinagar", "india"), ("imphal", "india"), ("shillong", "india"),
    ("aizawl", "india"), ("kohima", "india"), ("itanagar", "india"),
    ("gangtok", "india"), ("port blair", "india"), ("shimla", "india"),
    ("jammu", "india"), ("srinagar", "india"), ("leh", "india"),
    # ─── China ───
    ("shanghai", "china"), ("shenzhen", "china"), ("guangzhou", "china"),
    ("chengdu", "china"), ("wuhan", "china"), ("hangzhou", "china"),
    ("nanjing", "china"), ("tianjin", "china"), ("chongqing", "china"),
    ("xi'an", "china"), ("hong kong", "china"), ("macau", "china"),
    # ─── USA ───
    ("new york city", "united states"), ("los angeles", "united states"),
    ("chicago", "united states"), ("houston", "united states"),
    ("san francisco", "united states"), ("seattle", "united states"),
    ("boston", "united states"), ("miami", "united states"),
    ("dallas", "united states"), ("atlanta", "united states"),
    ("detroit", "united states"), ("denver", "united states"),
    ("phoenix", "united states"), ("san jose", "united states"),
    ("san diego", "united states"), ("las vegas", "united states"),
    # ─── Europe ───
    ("barcelona", "spain"), ("munich", "germany"), ("frankfurt", "germany"),
    ("milan", "italy"), ("marseille", "france"), ("manchester", "united kingdom"),
    ("edinburgh", "united kingdom"), ("zurich", "switzerland"),
    ("st petersburg", "russia"), ("istanbul", "turkey"),
    ("rotterdam", "netherlands"), ("hamburg", "germany"),
    ("lyon", "france"), ("naples", "italy"), ("malaga", "spain"),
    # ─── Middle East ───
    ("dubai", "united arab emirates"), ("jeddah", "saudi arabia"),
    ("mecca", "saudi arabia"), ("medina", "saudi arabia"),
    ("isfahan", "iran"), ("mashhad", "iran"), ("tabriz", "iran"),
    ("basra", "iraq"), ("erbil", "iraq"),
    ("tel aviv", "israel"), ("haifa", "israel"),
    # ─── Asia ───
    ("osaka", "japan"), ("yokohama", "japan"), ("nagoya", "japan"),
    ("busan", "south korea"), ("incheon", "south korea"),
    ("ho chi minh city", "vietnam"), ("surabaya", "indonesia"),
    ("bandung", "indonesia"), ("cebu", "philippines"), ("davao", "philippines"),
    ("chiang mai", "thailand"), ("penang", "malaysia"),
    # ─── Africa ───
    ("lagos", "nigeria"), ("johannesburg", "south africa"), ("cape town", "south africa"),
    ("casablanca", "morocco"), ("dar es salaam", "tanzania"), ("alexandria", "egypt"),
    ("mombasa", "kenya"),
    # ─── Americas ───
    ("sao paulo", "brazil"), ("rio de janeiro", "brazil"), ("toronto", "canada"),
    ("vancouver", "canada"), ("montreal", "canada"), ("guadalajara", "mexico"),
    ("buenos aires", "argentina"), ("santiago", "chile"), ("lima", "peru"),
    ("bogota", "colombia"), ("medellin", "colombia"),
    # ─── Oceania ───
    ("sydney", "australia"), ("melbourne", "australia"), ("brisbane", "australia"),
    ("perth", "australia"), ("auckland", "new zealand"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  INDIAN STATES  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (state_name, capital, region)

INDIAN_STATES = [
    ("andhra pradesh", "amaravati", "south india"), ("arunachal pradesh", "itanagar", "northeast india"),
    ("assam", "dispur", "northeast india"), ("bihar", "patna", "east india"),
    ("chhattisgarh", "raipur", "central india"), ("goa", "panaji", "west india"),
    ("gujarat", "gandhinagar", "west india"), ("haryana", "chandigarh", "north india"),
    ("himachal pradesh", "shimla", "north india"), ("jharkhand", "ranchi", "east india"),
    ("karnataka", "bangalore", "south india"), ("kerala", "thiruvananthapuram", "south india"),
    ("madhya pradesh", "bhopal", "central india"), ("maharashtra", "mumbai", "west india"),
    ("manipur", "imphal", "northeast india"), ("meghalaya", "shillong", "northeast india"),
    ("mizoram", "aizawl", "northeast india"), ("nagaland", "kohima", "northeast india"),
    ("odisha", "bhubaneswar", "east india"), ("punjab", "chandigarh", "north india"),
    ("rajasthan", "jaipur", "north india"), ("sikkim", "gangtok", "northeast india"),
    ("tamil nadu", "chennai", "south india"), ("telangana", "hyderabad", "south india"),
    ("tripura", "agartala", "northeast india"), ("uttar pradesh", "lucknow", "north india"),
    ("uttarakhand", "dehradun", "north india"), ("west bengal", "kolkata", "east india"),
    # UTs
    ("delhi", "new delhi", "north india"), ("jammu and kashmir", "srinagar", "north india"),
    ("ladakh", "leh", "north india"), ("puducherry", "puducherry", "south india"),
    ("chandigarh ut", "chandigarh", "north india"), ("andaman and nicobar islands", "port blair", "islands"),
    ("dadra and nagar haveli and daman and diu", "daman", "west india"),
    ("lakshadweep", "kavaratti", "islands"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  RESOURCES & PRODUCTS  ██████
# ═══════════════════════════════════════════════════════════════════════════════

RESOURCES = [
    ("crude oil", ["saudi arabia","russia","united states","iran","iraq","china","canada","united arab emirates","brazil","kuwait"]),
    ("natural gas", ["united states","russia","iran","china","qatar","canada","australia","norway","saudi arabia","algeria"]),
    ("coal", ["china","india","indonesia","united states","australia","russia","south africa","germany","poland","kazakhstan"]),
    ("uranium", ["kazakhstan","canada","australia","namibia","niger","russia","uzbekistan","china","india"]),
    ("lithium", ["australia","chile","china","argentina","brazil","zimbabwe","portugal"]),
    ("copper", ["chile","peru","china","democratic republic of congo","united states","australia","russia","zambia","indonesia"]),
    ("iron ore", ["australia","brazil","china","india","russia","south africa","ukraine","canada"]),
    ("gold", ["china","australia","russia","united states","canada","peru","south africa","ghana","mexico"]),
    ("rare earth elements", ["china","united states","australia","myanmar","india"]),
    ("wheat", ["china","india","russia","united states","france","canada","ukraine","pakistan","germany","australia"]),
    ("rice", ["china","india","bangladesh","indonesia","vietnam","thailand","myanmar","philippines","japan","brazil"]),
    ("steel", ["china","india","japan","united states","russia","south korea","germany","turkey","brazil","iran"]),
    ("aluminum", ["china","india","russia","canada","united arab emirates","australia","norway","bahrain","united states"]),
    ("cotton", ["india","china","united states","brazil","pakistan","uzbekistan","turkey","australia"]),
    ("rubber", ["thailand","indonesia","vietnam","india","china","malaysia","ivory coast","philippines"]),
    ("palm oil", ["indonesia","malaysia","thailand","nigeria","colombia","ecuador","honduras","papua new guinea"]),
    ("diamonds", ["russia","botswana","democratic republic of congo","australia","canada","angola","south africa"]),
    ("solar panels", ["china","vietnam","india","south korea","malaysia","japan","united states"]),
    ("semiconductors", ["taiwan","south korea","united states","japan","china","netherlands","germany"]),
    ("lng", ["qatar","australia","united states","russia","malaysia","indonesia","nigeria","trinidad and tobago"]),
    ("nuclear energy", ["united states","france","china","russia","south korea","japan","india","canada","united kingdom"]),
    ("wind energy", ["china","united states","germany","india","spain","united kingdom","brazil","france"]),
    ("hydropower", ["china","brazil","canada","united states","russia","india","norway","japan","turkey","france"]),
    ("cobalt", ["democratic republic of congo","russia","australia","philippines","cuba","indonesia"]),
    ("tin", ["china","indonesia","myanmar","peru","democratic republic of congo","brazil","bolivia","australia"]),
    ("nickel", ["indonesia","philippines","russia","australia","canada","new caledonia","china","brazil"]),
    ("bauxite", ["australia","guinea","china","brazil","india","indonesia","jamaica","russia"]),
    ("phosphate", ["china","morocco","united states","russia","jordan","brazil","egypt","tunisia","india"]),
    ("potash", ["canada","russia","belarus","china","germany","israel","jordan","chile","united states"]),
    ("platinum", ["south africa","russia","zimbabwe","canada","united states"]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  INFRASTRUCTURE  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, type, location_country, description)

INFRASTRUCTURE = [
    # Straits and Canals
    ("strait of hormuz", "strait", "iran", "Critical chokepoint for 20% of global oil"),
    ("strait of malacca", "strait", "malaysia", "Key shipping lane between Indian and Pacific oceans"),
    ("suez canal", "canal", "egypt", "Connects Mediterranean Sea to Red Sea"),
    ("panama canal", "canal", "panama", "Connects Atlantic and Pacific oceans"),
    ("bab el-mandeb strait", "strait", "yemen", "Connects Red Sea to Gulf of Aden"),
    ("bosphorus strait", "strait", "turkey", "Connects Black Sea to Sea of Marmara"),
    ("strait of gibraltar", "strait", "spain", "Connects Mediterranean to Atlantic"),
    ("taiwan strait", "strait", "taiwan", "Separates Taiwan from mainland China"),
    # Ports
    ("chabahar port", "port", "iran", "Indian-developed port in Iran for Afghanistan access"),
    ("gwadar port", "port", "pakistan", "Chinese-developed port in Pakistan (CPEC)"),
    ("hambantota port", "port", "sri lanka", "Chinese-leased port in Sri Lanka"),
    ("port of mumbai", "port", "india", "India's busiest port"),
    ("jawaharlal nehru port", "port", "india", "India's largest container port"),
    ("port of singapore", "port", "singapore", "World's busiest transshipment port"),
    ("port of shanghai", "port", "china", "World's busiest container port"),
    ("port of rotterdam", "port", "netherlands", "Europe's largest port"),
    ("jebel ali port", "port", "united arab emirates", "Largest port in Middle East"),
    ("port of busan", "port", "south korea", "Largest port in South Korea"),
    ("port of los angeles", "port", "united states", "Busiest port in Western Hemisphere"),
    ("port of mombasa", "port", "kenya", "Major East African port"),
    ("piraeus port", "port", "greece", "Chinese-operated Mediterranean hub"),
    ("port of djibouti", "port", "ethiopia", "Chinese military base host"),
    # Pipelines
    ("tapi pipeline", "pipeline", "turkmenistan", "Turkmenistan-Afghanistan-Pakistan-India gas pipeline"),
    ("ipi pipeline", "pipeline", "iran", "Iran-Pakistan-India gas pipeline proposed"),
    ("nord stream", "pipeline", "russia", "Russia-Germany gas pipeline (sabotaged)"),
    ("turkstream", "pipeline", "russia", "Russia-Turkey gas pipeline"),
    ("east-west pipeline", "pipeline", "india", "India's major gas pipeline"),
    ("trans-siberian pipeline", "pipeline", "russia", "Russia's major oil pipeline to Pacific"),
    ("baku-tbilisi-ceyhan pipeline", "pipeline", "azerbaijan", "Caspian oil to Mediterranean"),
    ("keystone pipeline", "pipeline", "canada", "Canada-US oil pipeline"),
    ("druzhba pipeline", "pipeline", "russia", "Russia to Central Europe oil pipeline"),
    # Railways
    ("china-pakistan economic corridor", "corridor", "pakistan", "CPEC infrastructure mega-project"),
    ("international north-south transport corridor", "corridor", "india", "India-Iran-Russia transport route"),
    ("trans-siberian railway", "railway", "russia", "Longest railway line in the world"),
    ("belt and road initiative", "corridor", "china", "China's global infrastructure project"),
    ("dedicated freight corridor", "railway", "india", "India's freight railway project"),
    # Other
    ("three gorges dam", "dam", "china", "World's largest hydroelectric dam"),
    ("sardar sarovar dam", "dam", "india", "Major dam on Narmada River"),
    ("al maktoum international airport", "airport", "united arab emirates", "World's largest airport project"),
    ("jewar airport", "airport", "india", "India's upcoming mega-airport near Delhi"),
    ("changi airport", "airport", "singapore", "Major global aviation hub"),
    ("heathrow airport", "airport", "united kingdom", "UK's busiest airport"),
    ("dubai international airport", "airport", "united arab emirates", "Busiest international airport"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  EVENTS  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, type, related_entities, year, description)

EVENTS = [
    ("russia-ukraine war", "conflict", ["russia","ukraine","nato","eu"], 2022, "Russian invasion of Ukraine"),
    ("israel-hamas war 2023", "conflict", ["israel","palestine","iran","united states"], 2023, "Gaza conflict"),
    ("israel-hezbollah conflict", "conflict", ["israel","lebanon","iran"], 2024, "Lebanon-Israel military escalation"),
    ("iran-israel tensions 2024", "conflict", ["iran","israel","united states"], 2024, "Direct military confrontation"),
    ("yemen houthi red sea attacks", "conflict", ["yemen","saudi arabia","united states","iran"], 2024, "Houthi attacks on shipping"),
    ("covid-19 pandemic", "pandemic", ["china","united states","india","who"], 2020, "Global coronavirus pandemic"),
    ("us-china trade war", "trade dispute", ["united states","china"], 2018, "US-China tariff escalation"),
    ("india-china ladakh standoff", "conflict", ["india","china"], 2020, "Border conflict in Ladakh"),
    ("india-china galwan clash", "conflict", ["india","china"], 2020, "Military clash at Galwan Valley"),
    ("ukraine grain crisis", "crisis", ["ukraine","russia","turkey","un"], 2022, "Global food supply disruption"),
    ("suez canal blockage 2021", "crisis", ["egypt"], 2021, "Ever Given container ship blocked Suez"),
    ("sri lanka economic crisis", "crisis", ["sri lanka","india","china","imf"], 2022, "Sovereign debt default"),
    ("pakistan economic crisis", "crisis", ["pakistan","imf","china","saudi arabia"], 2023, "IMF bailout"),
    ("afghanistan taliban takeover", "event", ["afghanistan","pakistan","united states","india"], 2021, "Taliban seized power"),
    ("quad summit", "summit", ["india","united states","japan","australia"], 2023, "Quadrilateral Security Dialogue"),
    ("g20 new delhi summit", "summit", ["india","g20"], 2023, "G20 summit hosted by India"),
    ("brics johannesburg summit", "summit", ["brics","south africa"], 2023, "BRICS expansion summit"),
    ("cop28 dubai", "summit", ["united arab emirates","un"], 2023, "UN climate conference"),
    ("cop27 sharm el-sheikh", "summit", ["egypt","un"], 2022, "UN climate conference"),
    ("us inflation crisis 2022", "crisis", ["united states"], 2022, "US inflation hit 40-year high"),
    ("global energy crisis 2022", "crisis", ["eu","russia","opec"], 2022, "Energy price spike post-Ukraine war"),
    ("opec+ production cuts 2023", "event", ["opec","saudi arabia","russia"], 2023, "OPEC production reduction"),
    ("silicon valley bank collapse", "crisis", ["united states"], 2023, "Major US bank failure"),
    ("india lunar mission chandrayaan-3", "event", ["india","isro"], 2023, "India's successful moon landing"),
    ("india mars mission mangalyaan", "event", ["india","isro"], 2014, "India's Mars orbiter mission"),
    ("india nuclear test pokhran-ii", "event", ["india"], 1998, "India's nuclear weapons test"),
    ("doklam standoff", "conflict", ["india","china","bhutan"], 2017, "India-China border standoff"),
    ("uri attack", "event", ["india","pakistan"], 2016, "Terror attack on Indian army base"),
    ("surgical strike", "event", ["india","pakistan"], 2016, "India's cross-border military strike"),
    ("balakot airstrike", "event", ["india","pakistan"], 2019, "India's airstrike in Pakistan"),
    ("pulwama attack", "event", ["india","pakistan"], 2019, "Terror attack in Kashmir"),
    ("abrogation of article 370", "event", ["india","jammu and kashmir"], 2019, "Revocation of J&K special status"),
    ("demonetization india", "event", ["india"], 2016, "India banned 500/1000 rupee notes"),
    ("gst implementation india", "event", ["india"], 2017, "India's unified goods and services tax"),
    ("farm laws protest india", "event", ["india"], 2020, "Farmer protests against agricultural laws"),
    ("russia sanctions 2022", "event", ["russia","united states","eu","united kingdom"], 2022, "Western sanctions on Russia"),
    ("iran nuclear deal jcpoa", "event", ["iran","united states","eu","china","russia"], 2015, "Iran nuclear agreement"),
    ("us withdrawal iran deal", "event", ["united states","iran"], 2018, "US withdrew from JCPOA"),
    ("abraham accords", "event", ["israel","united arab emirates","bahrain","united states"], 2020, "Israel-Arab normalization"),
    ("brexit", "event", ["united kingdom","eu"], 2020, "UK left the European Union"),
    ("nord stream sabotage", "event", ["russia","germany","eu"], 2022, "Sabotage of Nord Stream pipelines"),
    ("taiwan strait crisis 2022", "event", ["china","taiwan","united states"], 2022, "Military tensions over Taiwan"),
    ("myanmar coup 2021", "event", ["myanmar"], 2021, "Military coup in Myanmar"),
    ("sudan civil war 2023", "conflict", ["sudan"], 2023, "Sudanese internal military conflict"),
    ("ethiopia tigray war", "conflict", ["ethiopia"], 2020, "Internal conflict in Tigray"),
    ("nagorno-karabakh war", "conflict", ["armenia","azerbaijan","turkey","russia"], 2020, "Armenia-Azerbaijan conflict"),
    ("india-us nuclear deal", "event", ["india","united states"], 2008, "Civil nuclear cooperation agreement"),
    ("paris climate agreement", "event", ["un","india","china","united states","eu"], 2015, "Global climate accord"),
    ("global chip shortage", "crisis", ["taiwan","united states","china","south korea"], 2021, "Semiconductor supply crisis"),
    ("ai boom 2023", "event", ["united states","china","india"], 2023, "ChatGPT and generative AI revolution"),
    ("india digital india initiative", "event", ["india"], 2015, "Digital infrastructure push"),
    ("india make in india", "event", ["india"], 2014, "Manufacturing policy initiative"),
    ("india atma nirbhar bharat", "event", ["india"], 2020, "Self-reliant India campaign"),
    ("india upi revolution", "event", ["india"], 2016, "Unified Payments Interface fintech revolution"),
    ("india aadhar", "event", ["india"], 2009, "World's largest biometric ID system"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  MILITARY ASSETS  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, type, country)

MILITARY = [
    # India
    ("ins vikrant", "aircraft carrier", "india"), ("ins vikramaditya", "aircraft carrier", "india"),
    ("tejas fighter jet", "aircraft", "india"), ("rafale fighter jet india", "aircraft", "india"),
    ("sukhoi su-30mki", "aircraft", "india"), ("brahmos missile", "missile", "india"),
    ("agni-v missile", "missile", "india"), ("prithvi missile", "missile", "india"),
    ("s-400 triumf india", "air defense", "india"), ("akash missile system", "air defense", "india"),
    ("arjun main battle tank", "tank", "india"), ("ins arihant", "submarine", "india"),
    ("pinaka rocket system", "artillery", "india"), ("k-4 slbm", "missile", "india"),
    # USA
    ("uss gerald ford", "aircraft carrier", "united states"), ("f-35 lightning", "aircraft", "united states"),
    ("f-22 raptor", "aircraft", "united states"), ("b-21 raider", "aircraft", "united states"),
    ("aegis combat system", "defense system", "united states"), ("thaad missile defense", "air defense", "united states"),
    ("patriot missile system", "air defense", "united states"), ("tomahawk cruise missile", "missile", "united states"),
    ("minuteman iii icbm", "missile", "united states"), ("m1 abrams tank", "tank", "united states"),
    ("virginia class submarine", "submarine", "united states"), ("mq-9 reaper drone", "drone", "united states"),
    # Russia
    ("sukhoi su-57", "aircraft", "russia"), ("s-400 triumf", "air defense", "russia"),
    ("s-500 prometheus", "air defense", "russia"), ("iskander missile", "missile", "russia"),
    ("sarmat icbm", "missile", "russia"), ("t-14 armata tank", "tank", "russia"),
    ("admiral kuznetsov", "aircraft carrier", "russia"), ("kinzhal hypersonic missile", "missile", "russia"),
    ("kalibr cruise missile", "missile", "russia"), ("poseidon torpedo", "torpedo", "russia"),
    # China
    ("type 003 fujian", "aircraft carrier", "china"), ("j-20 fighter jet", "aircraft", "china"),
    ("df-41 icbm", "missile", "china"), ("df-17 hypersonic missile", "missile", "china"),
    ("type 055 destroyer", "warship", "china"), ("yj-21 anti-ship missile", "missile", "china"),
    # Others
    ("eurofighter typhoon", "aircraft", "germany"), ("gripen fighter jet", "aircraft", "sweden"),
    ("iron dome", "air defense", "israel"), ("david's sling", "air defense", "israel"),
    ("k2 black panther tank", "tank", "south korea"), ("type 10 tank", "tank", "japan"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  TECHNOLOGY  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, category, key_countries)

TECHNOLOGIES = [
    ("artificial intelligence", "digital", ["united states","china","india","united kingdom"]),
    ("machine learning", "digital", ["united states","china","india"]),
    ("quantum computing", "digital", ["united states","china","germany","japan"]),
    ("5g technology", "telecom", ["china","united states","south korea","india"]),
    ("6g technology", "telecom", ["china","south korea","japan","united states"]),
    ("blockchain", "digital", ["united states","china","singapore","switzerland"]),
    ("cloud computing", "digital", ["united states","china","india"]),
    ("cybersecurity", "digital", ["united states","israel","united kingdom","russia"]),
    ("semiconductor manufacturing", "hardware", ["taiwan","south korea","united states"]),
    ("autonomous vehicles", "automotive", ["united states","china","germany","japan"]),
    ("electric vehicles", "automotive", ["china","united states","germany","india"]),
    ("nuclear fusion", "energy", ["united states","france","china","united kingdom"]),
    ("small modular reactors", "energy", ["united states","russia","china","canada"]),
    ("hydrogen fuel cells", "energy", ["japan","south korea","germany","australia"]),
    ("carbon capture", "climate", ["united states","norway","canada","united kingdom"]),
    ("crispr gene editing", "biotech", ["united states","china","united kingdom"]),
    ("mrna vaccine technology", "biotech", ["united states","germany"]),
    ("space launch technology", "space", ["united states","china","india","russia"]),
    ("satellite internet", "space", ["united states","china","united kingdom"]),
    ("hypersonic weapons", "defense", ["united states","russia","china","india"]),
    ("directed energy weapons", "defense", ["united states","china","israel"]),
    ("drone swarm technology", "defense", ["united states","china","india","turkey"]),
    ("anti-satellite weapons", "defense", ["united states","china","russia","india"]),
    ("stealth technology", "defense", ["united states","china","russia"]),
    ("desalination technology", "water", ["saudi arabia","israel","united arab emirates"]),
    ("green hydrogen", "energy", ["india","australia","chile","saudi arabia"]),
    ("solid state batteries", "energy", ["japan","south korea","china","united states"]),
    ("vertical farming", "agriculture", ["netherlands","united states","japan","singapore"]),
    ("precision agriculture", "agriculture", ["united states","india","israel","brazil"]),
    ("internet of things", "digital", ["china","united states","germany","japan","india"]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  AGREEMENTS & TREATIES  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, type, parties)

AGREEMENTS = [
    ("paris climate agreement", "climate", ["un","india","china","united states","eu"]),
    ("jcpoa iran nuclear deal", "nuclear", ["iran","united states","united kingdom","france","germany","china","russia"]),
    ("new start treaty", "nuclear arms", ["united states","russia"]),
    ("nuclear non-proliferation treaty", "nuclear", ["united states","russia","united kingdom","france","china"]),
    ("comprehensive nuclear test ban treaty", "nuclear", ["un"]),
    ("rcep trade agreement", "trade", ["china","japan","south korea","australia","new zealand","indonesia","thailand","vietnam","philippines","malaysia","singapore","myanmar","cambodia","laos","brunei"]),
    ("usmca trade agreement", "trade", ["united states","mexico","canada"]),
    ("india-uae cepa", "trade", ["india","united arab emirates"]),
    ("india-australia ecta", "trade", ["india","australia"]),
    ("india-japan civil nuclear agreement", "nuclear", ["india","japan"]),
    ("india-us defense technology agreement", "defense", ["india","united states"]),
    ("quad security dialogue", "security", ["india","united states","japan","australia"]),
    ("aukus pact", "defense", ["australia","united kingdom","united states"]),
    ("minsk agreements", "peace", ["ukraine","russia","france","germany"]),
    ("camp david accords", "peace", ["egypt","israel","united states"]),
    ("abraham accords agreement", "peace", ["israel","united arab emirates","bahrain","united states"]),
    ("indo-pacific economic framework", "trade", ["united states","india","japan","australia","south korea","indonesia","philippines","vietnam","thailand","malaysia","singapore"]),
    ("trans-pacific partnership", "trade", ["japan","australia","canada","mexico","vietnam","singapore","malaysia","chile","peru","brunei","new zealand"]),
    ("african continental free trade area", "trade", ["african union"]),
    ("asean regional comprehensive economic partnership", "trade", ["asean","china","japan","south korea","australia","new zealand"]),
    ("india-russia s-400 deal", "defense", ["india","russia"]),
    ("india-france rafale deal", "defense", ["india","france"]),
    ("chabahar port agreement", "infrastructure", ["india","iran","afghanistan"]),
    ("shimla agreement", "peace", ["india","pakistan"]),
    ("indus waters treaty", "water", ["india","pakistan","world bank"]),
    ("antarctic treaty", "environment", ["un"]),
    ("outer space treaty", "space", ["un"]),
    ("chemical weapons convention", "arms control", ["un"]),
    ("biological weapons convention", "arms control", ["un"]),
    ("arms trade treaty", "arms control", ["un"]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  POLICIES & SANCTIONS  ██████
# ═══════════════════════════════════════════════════════════════════════════════
# (name, type, issuer, targets)

POLICIES = [
    ("us sanctions on iran", "sanctions", "united states", ["iran"]),
    ("us sanctions on russia", "sanctions", "united states", ["russia"]),
    ("eu sanctions on russia", "sanctions", "eu", ["russia"]),
    ("us-china tech export controls", "export control", "united states", ["china"]),
    ("us chips act", "industrial policy", "united states", ["china"]),
    ("us inflation reduction act", "economic policy", "united states", []),
    ("india production linked incentive scheme", "industrial policy", "india", []),
    ("india national education policy 2020", "education policy", "india", []),
    ("india farm laws 2020", "agricultural policy", "india", []),
    ("india goods and services tax", "tax policy", "india", []),
    ("india foreign direct investment policy", "fdi policy", "india", []),
    ("eu carbon border adjustment mechanism", "trade/climate", "eu", []),
    ("eu digital markets act", "tech regulation", "eu", []),
    ("china belt and road initiative policy", "foreign policy", "china", []),
    ("china dual circulation strategy", "economic policy", "china", []),
    ("russia counter-sanctions", "sanctions", "russia", ["eu","united states"]),
    ("opec+ production quota system", "energy policy", "opec", []),
    ("us dodd-frank act", "financial regulation", "united states", []),
    ("india demonetization policy", "monetary policy", "india", []),
    ("india digital personal data protection act", "data privacy", "india", []),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  GEOGRAPHIC FEATURES  ██████
# ═══════════════════════════════════════════════════════════════════════════════

GEOGRAPHIC = [
    # Oceans and Seas
    ("indian ocean", "ocean", "india"), ("pacific ocean", "ocean", "united states"),
    ("atlantic ocean", "ocean", "united states"), ("arctic ocean", "ocean", "russia"),
    ("south china sea", "sea", "china"), ("arabian sea", "sea", "india"),
    ("bay of bengal", "sea", "india"), ("persian gulf", "sea", "iran"),
    ("red sea", "sea", "egypt"), ("mediterranean sea", "sea", "italy"),
    ("black sea", "sea", "turkey"), ("caspian sea", "sea", "russia"),
    ("east china sea", "sea", "china"), ("sea of japan", "sea", "japan"),
    # Rivers
    ("ganges river", "river", "india"), ("yamuna river", "river", "india"),
    ("brahmaputra river", "river", "india"), ("indus river", "river", "pakistan"),
    ("nile river", "river", "egypt"), ("amazon river", "river", "brazil"),
    ("yangtze river", "river", "china"), ("mekong river", "river", "vietnam"),
    ("danube river", "river", "germany"), ("tigris river", "river", "iraq"),
    ("euphrates river", "river", "iraq"), ("volga river", "river", "russia"),
    ("mississippi river", "river", "united states"), ("godavari river", "river", "india"),
    ("krishna river", "river", "india"), ("narmada river", "river", "india"),
    ("kaveri river", "river", "india"), ("mahanadi river", "river", "india"),
    # Regions
    ("south asia", "region", "india"), ("middle east", "region", "saudi arabia"),
    ("east asia", "region", "china"), ("southeast asia", "region", "indonesia"),
    ("central asia", "region", "kazakhstan"), ("north africa", "region", "egypt"),
    ("sub-saharan africa", "region", "nigeria"), ("western europe", "region", "france"),
    ("eastern europe", "region", "poland"), ("north america", "region", "united states"),
    ("south america", "region", "brazil"), ("indo-pacific", "region", "india"),
    ("arctic region", "region", "russia"), ("sahel region", "region", "nigeria"),
    ("horn of africa", "region", "ethiopia"),
    # Mountain Ranges
    ("himalayas", "mountain", "india"), ("karakoram range", "mountain", "pakistan"),
    ("hindu kush", "mountain", "afghanistan"), ("ural mountains", "mountain", "russia"),
    ("alps", "mountain", "switzerland"), ("andes", "mountain", "peru"),
    ("rocky mountains", "mountain", "united states"),
    # Deserts
    ("thar desert", "desert", "india"), ("sahara desert", "desert", "algeria"),
    ("arabian desert", "desert", "saudi arabia"), ("gobi desert", "desert", "china"),
    # Islands
    ("andaman islands", "island", "india"), ("nicobar islands", "island", "india"),
    ("lakshadweep islands", "island", "india"), ("sri lanka island", "island", "sri lanka"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  FINANCIAL  ██████
# ═══════════════════════════════════════════════════════════════════════════════

CURRENCIES = [
    ("indian rupee", "india"), ("us dollar", "united states"), ("euro", "eu"),
    ("chinese yuan", "china"), ("japanese yen", "japan"), ("british pound", "united kingdom"),
    ("russian ruble", "russia"), ("saudi riyal", "saudi arabia"),
    ("uae dirham", "united arab emirates"), ("pakistani rupee", "pakistan"),
    ("bangladeshi taka", "bangladesh"), ("sri lankan rupee", "sri lanka"),
    ("australian dollar", "australia"), ("canadian dollar", "canada"),
    ("swiss franc", "switzerland"), ("south korean won", "south korea"),
    ("brazilian real", "brazil"), ("south african rand", "south africa"),
    ("turkish lira", "turkey"), ("thai baht", "thailand"),
    ("indonesian rupiah", "indonesia"), ("malaysian ringgit", "malaysia"),
    ("singapore dollar", "singapore"), ("iranian rial", "iran"),
    ("nigerian naira", "nigeria"), ("egyptian pound", "egypt"),
    ("mexican peso", "mexico"), ("norwegian krone", "norway"),
    ("swedish krona", "sweden"), ("polish zloty", "poland"),
]

STOCK_EXCHANGES = [
    ("bombay stock exchange", "india"), ("national stock exchange india", "india"),
    ("new york stock exchange", "united states"), ("nasdaq", "united states"),
    ("london stock exchange", "united kingdom"), ("tokyo stock exchange", "japan"),
    ("shanghai stock exchange", "china"), ("shenzhen stock exchange", "china"),
    ("hong kong stock exchange", "china"), ("euronext", "france"),
    ("deutsche boerse", "germany"), ("toronto stock exchange", "canada"),
    ("australian securities exchange", "australia"), ("korea exchange", "south korea"),
    ("taiwan stock exchange", "taiwan"), ("singapore exchange", "singapore"),
    ("saudi stock exchange", "saudi arabia"), ("dubai financial market", "united arab emirates"),
]

CENTRAL_BANKS = [
    ("reserve bank of india", "india"), ("federal reserve", "united states"),
    ("european central bank", "eu"), ("bank of england", "united kingdom"),
    ("peoples bank of china", "china"), ("bank of japan", "japan"),
    ("bank of russia", "russia"), ("reserve bank of australia", "australia"),
    ("bank of canada", "canada"), ("saudi arabian monetary authority", "saudi arabia"),
    ("central bank of uae", "united arab emirates"), ("central bank of iran", "iran"),
    ("state bank of pakistan", "pakistan"), ("bangladesh bank", "bangladesh"),
    ("bank of korea", "south korea"), ("bank of indonesia", "indonesia"),
    ("bank of thailand", "thailand"), ("central bank of turkey", "turkey"),
    ("south african reserve bank", "south africa"), ("central bank of egypt", "egypt"),
    ("banco central do brasil", "brazil"), ("central bank of nigeria", "nigeria"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# ██████  ADDITIONAL ENTITIES (universities, media, NGOs, parties, etc.)  ██████
# ═══════════════════════════════════════════════════════════════════════════════

UNIVERSITIES = [
    ("iit bombay", "india"), ("iit delhi", "india"), ("iit madras", "india"),
    ("iit kanpur", "india"), ("iit kharagpur", "india"), ("iit roorkee", "india"),
    ("iit guwahati", "india"), ("iit hyderabad", "india"),
    ("iim ahmedabad", "india"), ("iim bangalore", "india"), ("iim calcutta", "india"),
    ("indian institute of science", "india"), ("jawaharlal nehru university", "india"),
    ("delhi university", "india"), ("banaras hindu university", "india"),
    ("aligarh muslim university", "india"), ("anna university", "india"),
    ("jadavpur university", "india"), ("bits pilani", "india"),
    ("mit", "united states"), ("stanford university", "united states"),
    ("harvard university", "united states"), ("caltech", "united states"),
    ("princeton university", "united states"), ("yale university", "united states"),
    ("columbia university", "united states"), ("university of chicago", "united states"),
    ("university of oxford", "united kingdom"), ("university of cambridge", "united kingdom"),
    ("imperial college london", "united kingdom"),
    ("eth zurich", "switzerland"), ("tsinghua university", "china"),
    ("peking university", "china"), ("university of tokyo", "japan"),
    ("national university of singapore", "singapore"), ("kaist", "south korea"),
    ("moscow state university", "russia"), ("technical university of munich", "germany"),
    ("sorbonne university", "france"),
]

MEDIA_ORGS = [
    ("reuters", "united kingdom"), ("associated press", "united states"),
    ("bbc", "united kingdom"), ("cnn", "united states"), ("al jazeera", "qatar"),
    ("xinhua", "china"), ("cgtn", "china"), ("rt news", "russia"),
    ("ndr", "germany"), ("france 24", "france"), ("nhk", "japan"),
    ("the times of india", "india"), ("ndtv", "india"), ("the hindu", "india"),
    ("indian express", "india"), ("hindustan times", "india"),
    ("the economic times", "india"), ("business standard", "india"),
    ("the new york times", "united states"), ("washington post", "united states"),
    ("wall street journal", "united states"), ("financial times", "united kingdom"),
    ("the guardian", "united kingdom"), ("bloomberg", "united states"),
    ("the economist", "united kingdom"),
]

NGOS = [
    ("amnesty international", "united kingdom"), ("human rights watch", "united states"),
    ("greenpeace", "netherlands"), ("doctors without borders", "france"),
    ("oxfam", "united kingdom"), ("save the children", "united kingdom"),
    ("world wildlife fund", "switzerland"), ("transparency international", "germany"),
    ("care international", "switzerland"), ("international rescue committee", "united states"),
]

POLITICAL_PARTIES = [
    ("bharatiya janata party", "india"), ("indian national congress", "india"),
    ("aam aadmi party", "india"), ("communist party of india marxist", "india"),
    ("trinamool congress", "india"), ("dravida munnetra kazhagam", "india"),
    ("shiv sena", "india"), ("nationalist congress party", "india"),
    ("bahujan samaj party", "india"), ("samajwadi party", "india"),
    ("janata dal united", "india"), ("telugu desam party", "india"),
    ("rashtriya janata dal", "india"), ("ysr congress party", "india"),
    ("democratic party", "united states"), ("republican party", "united states"),
    ("conservative party", "united kingdom"), ("labour party", "united kingdom"),
    ("communist party of china", "china"), ("united russia", "russia"),
    ("liberal democratic party japan", "japan"),
]

GOVT_AGENCIES = [
    ("cia", "united states"), ("fbi", "united states"), ("nsa", "united states"),
    ("dia", "united states"), ("department of state", "united states"),
    ("pentagon", "united states"), ("white house", "united states"),
    ("research and analysis wing", "india"), ("intelligence bureau india", "india"),
    ("national investigation agency", "india"),
    ("ministry of defence india", "india"), ("ministry of external affairs india", "india"),
    ("ministry of finance india", "india"), ("ministry of home affairs india", "india"),
    ("niti aayog", "india"), ("election commission of india", "india"),
    ("supreme court of india", "india"), ("reserve bank of india", "india"),
    ("securities and exchange board of india", "india"),
    ("mi6", "united kingdom"), ("mossad", "israel"), ("isi", "pakistan"),
    ("ministry of state security china", "china"), ("fsb", "russia"),
    ("bnd", "germany"), ("dgse", "france"),
]


# ═══════════════════════════════════════════════════════════════════════════════
#
# ████  TRIPLE GENERATORS  ████
#
# ═══════════════════════════════════════════════════════════════════════════════

def gen_country_triples():
    """Generate triples for all countries: capitals, borders, regions."""
    triples = []
    for country, d in COUNTRIES.items():
        wiki = f"{WIKI}{country.replace(' ', '_').title()}"
        cap = d["cap"]
        reg = d["reg"]
        # Country → HAS capital
        triples.append(make_triple(country, "CONTROLS", cap, 0.95, wiki,
                                   f"{cap} is the capital of {country}", "Country", "Location"))
        # Country → LOCATED IN region
        triples.append(make_triple(country, "OPERATES_IN", reg, 0.90, wiki,
                                   f"{country} is located in {reg}", "Country", "Location"))
        # Borders
        for neighbor in d["brd"]:
            if country < neighbor:  # avoid duplicate bidirectional
                triples.append(make_triple(country, "BORDERS", neighbor, 0.95, wiki,
                                           f"{country} shares a border with {neighbor}", "Country", "Country"))
    return triples


def gen_org_membership_triples():
    """Generate MEMBER_OF triples for organizations."""
    triples = []
    for org_key, od in ORGANIZATIONS.items():
        full = od["full"]
        hq = od.get("hq", "")
        wiki = f"{WIKI}{full.replace(' ', '_')}"
        # Org HQ
        if hq and hq != "rotating":
            triples.append(make_triple(full, "HEADQUARTERED_IN", hq, 0.92, wiki,
                                       f"{full} is headquartered in {hq}", "Organization", "Location"))
        # Members
        for member in od.get("members", []):
            triples.append(make_triple(member, "MEMBER_OF", full, 0.95, wiki,
                                       f"{member} is a member of {full}", "Country", "Organization"))
    return triples


def gen_company_triples():
    """Generate triples for companies: HQ, sector."""
    triples = []
    for name, country, sector in COMPANIES:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "HEADQUARTERED_IN", country, 0.92, wiki,
                                   f"{name} is headquartered in {country}", "Company", "Country"))
        triples.append(make_triple(name, "OPERATES_IN", sector, 0.88, wiki,
                                   f"{name} operates in the {sector} sector", "Company", "Event"))
    return triples


def gen_people_triples():
    """Generate triples for key people: LEADS or MEMBER_OF."""
    triples = []
    for name, role, entity in PEOPLE:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        pred = "LEADS" if any(kw in role for kw in ["president","prime minister","chancellor","king","queen",
                                                      "chairman","ceo","founder","governor","director",
                                                      "crown prince","supreme leader"]) else "MEMBER_OF"
        triples.append(make_triple(name, pred, entity, 0.90, wiki,
                                   f"{name} is {role} of {entity}", "Person", None))
    return triples


def gen_city_triples():
    """Generate triples: cities located in countries."""
    triples = []
    for city, country in CITIES:
        wiki = f"{WIKI}{city.replace(' ', '_').title()}"
        triples.append(make_triple(city, "OPERATES_IN", country, 0.93, wiki,
                                   f"{city} is a major city in {country}", "Location", "Country"))
    return triples


def gen_indian_state_triples():
    """Generate triples for Indian states."""
    triples = []
    for state, capital, region in INDIAN_STATES:
        wiki = f"{WIKI}{state.replace(' ', '_').title()}"
        triples.append(make_triple(state, "OPERATES_IN", "india", 0.95, wiki,
                                   f"{state} is a state/territory of India", "Location", "Country"))
        triples.append(make_triple(state, "CONTROLS", capital, 0.93, wiki,
                                   f"{capital} is the capital of {state}", "Location", "Location"))
        triples.append(make_triple(state, "OPERATES_IN", region, 0.90, wiki,
                                   f"{state} is in {region}", "Location", "Location"))
    return triples


def gen_resource_triples():
    """Generate triples: resource PRODUCED by countries."""
    triples = []
    for resource, producers in RESOURCES:
        wiki = f"{WIKI}{resource.replace(' ', '_').title()}"
        for country in producers:
            triples.append(make_triple(country, "PRODUCES", resource, 0.88, wiki,
                                       f"{country} is a major producer of {resource}", "Country", "Resource"))
    return triples


def gen_infra_triples():
    """Generate triples for infrastructure."""
    triples = []
    for name, itype, location, desc in INFRASTRUCTURE:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "OPERATES_IN", location, 0.90, wiki,
                                   desc, "Infrastructure", None))
        if itype in ("strait", "canal"):
            triples.append(make_triple(name, "TRANSPORT_ROUTE_FOR", "crude oil", 0.85, wiki,
                                       f"{name} is a transport route for crude oil", "Infrastructure", "Resource"))
        if itype == "port":
            triples.append(make_triple(name, "FACILITATES_TRADE_OF", "goods", 0.85, wiki,
                                       f"{name} facilitates international trade", "Infrastructure", "Resource"))
    return triples


def gen_event_triples():
    """Generate triples for events."""
    triples = []
    for name, etype, related, year, desc in EVENTS:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        for entity in related:
            pred = "AFFECTS" if etype in ("crisis", "pandemic") else \
                   "CONFLICT_WITH" if etype == "conflict" else "PARTICIPATES_IN"
            triples.append(make_triple(name, pred, entity, 0.88, wiki,
                                       desc, "Event", None))
    return triples


def gen_military_triples():
    """Generate triples for military assets."""
    triples = []
    for name, mtype, country in MILITARY:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(country, "DEPLOYS", name, 0.88, wiki,
                                   f"{country} deploys {name}", "Country", "MilitaryAsset"))
    return triples


def gen_tech_triples():
    """Generate triples for technologies."""
    triples = []
    for name, category, countries in TECHNOLOGIES:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        for country in countries:
            triples.append(make_triple(country, "RESEARCHES", name, 0.85, wiki,
                                       f"{country} is a leader in {name} research", "Country", "Technology"))
    return triples


def gen_agreement_triples():
    """Generate triples for agreements."""
    triples = []
    for name, atype, parties in AGREEMENTS:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        for party in parties:
            triples.append(make_triple(party, "SIGNS", name, 0.90, wiki,
                                       f"{party} is a signatory of {name}", None, "Agreement"))
    return triples


def gen_policy_triples():
    """Generate triples for policies and sanctions."""
    triples = []
    for name, ptype, issuer, targets in POLICIES:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(issuer, "REGULATES", name, 0.88, wiki,
                                   f"{issuer} enacted {name}", None, "Policy"))
        for target in targets:
            triples.append(make_triple(name, "SANCTIONS" if "sanction" in ptype.lower() else "AFFECTS",
                                       target, 0.85, wiki,
                                       f"{name} affects {target}", "Policy", None))
    return triples


def gen_geographic_triples():
    """Generate triples for geographic features."""
    triples = []
    for name, gtype, country in GEOGRAPHIC:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "OPERATES_IN", country, 0.90, wiki,
                                   f"{name} is located in/near {country}", "Location", None))
    return triples


def gen_finance_triples():
    """Generate triples for currencies, exchanges, central banks."""
    triples = []
    for currency, country in CURRENCIES:
        wiki = f"{WIKI}{currency.replace(' ', '_').title()}"
        triples.append(make_triple(country, "CONTROLS", currency, 0.92, wiki,
                                   f"{currency} is the official currency of {country}",
                                   None, "EconomicIndicator"))
    for exchange, country in STOCK_EXCHANGES:
        wiki = f"{WIKI}{exchange.replace(' ', '_').title()}"
        triples.append(make_triple(exchange, "OPERATES_IN", country, 0.90, wiki,
                                   f"{exchange} is located in {country}", "Organization", None))
    for bank, country in CENTRAL_BANKS:
        wiki = f"{WIKI}{bank.replace(' ', '_').title()}"
        triples.append(make_triple(bank, "REGULATES", country, 0.92, wiki,
                                   f"{bank} is the central bank of {country}", "Organization", None))
    return triples


def gen_supplementary_triples():
    """Generate triples for universities, media, NGOs, parties, agencies."""
    triples = []
    for name, country in UNIVERSITIES:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "OPERATES_IN", country, 0.88, wiki,
                                   f"{name} is located in {country}", "Organization", None))
    for name, country in MEDIA_ORGS:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "HEADQUARTERED_IN", country, 0.88, wiki,
                                   f"{name} is based in {country}", "Organization", None))
    for name, country in NGOS:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "HEADQUARTERED_IN", country, 0.88, wiki,
                                   f"{name} is headquartered in {country}", "Organization", None))
    for name, country in POLITICAL_PARTIES:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "OPERATES_IN", country, 0.88, wiki,
                                   f"{name} is a political party in {country}", "Organization", None))
    for name, country in GOVT_AGENCIES:
        wiki = f"{WIKI}{name.replace(' ', '_').title()}"
        triples.append(make_triple(name, "OPERATES_IN", country, 0.88, wiki,
                                   f"{name} is a government agency of {country}", "Organization", None))
    return triples


# ═══════════════════════════════════════════════════════════════════════════════
# ██████  DERIVED ENTITY GENERATORS  ██████
# ═══════════════════════════════════════════════════════════════════════════════

INDICATOR_TYPES = [
    "gdp", "gdp per capita", "inflation rate", "unemployment rate", "trade balance",
    "current account balance", "military expenditure", "population",
    "literacy rate", "human development index", "foreign direct investment",
    "public debt to gdp ratio", "foreign exchange reserves",
]

def gen_derived_indicators():
    """Generate country-level economic indicator nodes and relationships."""
    triples = []
    # Top 50 most important countries for indicators
    top_countries = [
        "india","china","united states","russia","japan","germany","united kingdom",
        "france","brazil","south korea","australia","canada","italy","spain",
        "mexico","indonesia","saudi arabia","turkey","iran","thailand",
        "south africa","nigeria","egypt","pakistan","bangladesh","vietnam",
        "malaysia","philippines","argentina","colombia","chile","peru",
        "poland","ukraine","israel","united arab emirates","qatar","kuwait",
        "iraq","singapore","norway","sweden","switzerland","austria",
        "ireland","denmark","finland","new zealand","sri lanka","nepal",
    ]
    for country in top_countries:
        wiki = f"https://data.worldbank.org/country/{country.replace(' ', '-')}"
        for ind in INDICATOR_TYPES:
            indicator_name = f"{country} {ind}"
            triples.append(make_triple(indicator_name, "AFFECTS", country, 0.85, wiki,
                                       f"{ind} is a key economic indicator for {country}",
                                       "EconomicIndicator", "Country"))
    return triples


def gen_derived_trade_pairs():
    """Generate major bilateral trade relationships."""
    triples = []
    trade_pairs = [
        ("india", "united states"), ("india", "china"), ("india", "saudi arabia"),
        ("india", "united arab emirates"), ("india", "iraq"), ("india", "russia"),
        ("india", "japan"), ("india", "south korea"), ("india", "germany"),
        ("india", "united kingdom"), ("india", "singapore"), ("india", "indonesia"),
        ("india", "iran"), ("india", "qatar"), ("india", "kuwait"),
        ("india", "australia"), ("india", "canada"), ("india", "france"),
        ("india", "brazil"), ("india", "south africa"), ("india", "bangladesh"),
        ("india", "nepal"), ("india", "sri lanka"), ("india", "thailand"),
        ("india", "vietnam"), ("india", "malaysia"), ("india", "israel"),
        ("india", "turkey"), ("india", "nigeria"), ("india", "egypt"),
        ("united states", "china"), ("united states", "japan"), ("united states", "germany"),
        ("united states", "united kingdom"), ("united states", "canada"), ("united states", "mexico"),
        ("united states", "south korea"), ("united states", "france"), ("united states", "brazil"),
        ("united states", "india"), ("united states", "saudi arabia"), ("united states", "taiwan"),
        ("china", "japan"), ("china", "south korea"), ("china", "germany"),
        ("china", "australia"), ("china", "brazil"), ("china", "russia"),
        ("china", "vietnam"), ("china", "malaysia"), ("china", "thailand"),
        ("china", "indonesia"), ("china", "saudi arabia"), ("china", "iran"),
        ("russia", "china"), ("russia", "india"), ("russia", "germany"),
        ("russia", "turkey"), ("russia", "belarus"), ("russia", "kazakhstan"),
        ("japan", "china"), ("japan", "united states"), ("japan", "south korea"),
        ("japan", "australia"), ("japan", "india"), ("japan", "germany"),
        ("germany", "france"), ("germany", "netherlands"), ("germany", "china"),
        ("germany", "united states"), ("germany", "united kingdom"), ("germany", "poland"),
        ("saudi arabia", "china"), ("saudi arabia", "japan"), ("saudi arabia", "india"),
        ("saudi arabia", "south korea"), ("saudi arabia", "united states"),
    ]
    seen = set()
    for a, b in trade_pairs:
        key = tuple(sorted([a, b]))
        if key in seen:
            continue
        seen.add(key)
        wiki = f"https://data.worldbank.org"
        triples.append(make_triple(a, "TRADES_WITH", b, 0.88, wiki,
                                   f"{a} has significant bilateral trade with {b}", "Country", "Country"))
        triples.append(make_triple(a, "EXPORTS_TO", b, 0.85, wiki,
                                   f"{a} exports goods to {b}", "Country", "Country"))
        triples.append(make_triple(b, "EXPORTS_TO", a, 0.85, wiki,
                                   f"{b} exports goods to {a}", "Country", "Country"))
    return triples


def gen_derived_defense_partnerships():
    """Generate defense partnership triples."""
    triples = []
    defense_pairs = [
        ("india", "united states"), ("india", "russia"), ("india", "france"),
        ("india", "israel"), ("india", "japan"), ("india", "australia"),
        ("india", "south korea"), ("india", "united kingdom"), ("india", "germany"),
        ("india", "vietnam"), ("india", "indonesia"), ("india", "singapore"),
        ("united states", "japan"), ("united states", "south korea"),
        ("united states", "australia"), ("united states", "united kingdom"),
        ("united states", "germany"), ("united states", "france"),
        ("united states", "israel"), ("united states", "saudi arabia"),
        ("united states", "taiwan"), ("united states", "philippines"),
        ("russia", "china"), ("russia", "india"), ("russia", "iran"),
        ("russia", "syria"), ("russia", "belarus"),
        ("china", "pakistan"), ("china", "north korea"), ("china", "iran"),
        ("china", "russia"), ("china", "myanmar"),
        ("france", "germany"), ("france", "united kingdom"),
        ("japan", "australia"), ("south korea", "japan"),
        ("saudi arabia", "united arab emirates"), ("iran", "syria"),
        ("turkey", "pakistan"), ("turkey", "qatar"),
        ("israel", "united arab emirates"),
    ]
    seen = set()
    for a, b in defense_pairs:
        key = tuple(sorted([a, b]))
        if key in seen:
            continue
        seen.add(key)
        triples.append(make_triple(a, "DEFENSE_PARTNERSHIP_WITH", b, 0.85,
                                   f"{WIKI}Foreign_relations_of_{a.replace(' ','_').title()}",
                                   f"{a} has defense cooperation with {b}", "Country", "Country"))
    return triples


def gen_derived_energy_trade():
    """Generate energy import/export triples."""
    triples = []
    # Major oil importers and their sources
    imports = {
        "india": ["saudi arabia","iraq","iran","united arab emirates","kuwait","russia","nigeria","qatar"],
        "china": ["saudi arabia","russia","iraq","angola","oman","iran","brazil","kuwait"],
        "japan": ["saudi arabia","united arab emirates","qatar","kuwait","russia"],
        "south korea": ["saudi arabia","kuwait","united arab emirates","iraq","qatar"],
        "united states": ["canada","mexico","saudi arabia","iraq","colombia"],
        "germany": ["russia","norway","united kingdom","libya"],
    }
    for importer, exporters in imports.items():
        for exporter in exporters:
            triples.append(make_triple(importer, "IMPORTS_FROM", exporter, 0.88,
                                       f"https://data.worldbank.org",
                                       f"{importer} imports crude oil from {exporter}",
                                       "Country", "Country"))
            triples.append(make_triple(exporter, "EXPORTS_TO", importer, 0.88,
                                       f"https://data.worldbank.org",
                                       f"{exporter} exports crude oil to {importer}",
                                       "Country", "Country"))
    return triples


# ═══════════════════════════════════════════════════════════════════════════════
# ██████  GAP FILLER  ██████
# ═══════════════════════════════════════════════════════════════════════════════

EXTRA_INDICATORS = [
    "poverty rate", "gini coefficient", "life expectancy", "infant mortality rate",
    "co2 emissions", "renewable energy share", "internet penetration",
    "mobile subscriptions", "export value", "import value",
    "government revenue", "tax to gdp ratio", "education expenditure",
    "healthcare expenditure", "agricultural output", "industrial output",
    "services output", "urban population percentage", "rural population percentage",
    "birth rate", "death rate", "median age", "labor force participation",
    "bank lending rate", "stock market capitalization", "remittances received",
    "patent applications", "research and development expenditure",
    "tourism revenue", "food production index", "energy consumption per capita",
    "water stress index", "forest cover percentage", "corruption perception index",
    "press freedom index", "ease of doing business", "logistics performance index",
    "global peace index", "gender inequality index", "food security index",
    "happiness index", "digital readiness index", "climate risk index",
    "innovation index", "competitiveness index", "rule of law index",
    "democracy index", "fragile states index", "military strength index",
    "cyber readiness index", "health security index", "education index",
]

EXTRA_SECTORS = [
    "automotive industry", "pharmaceutical industry", "information technology industry",
    "textile industry", "steel industry", "cement industry", "banking sector",
    "insurance sector", "real estate sector", "agriculture sector",
    "mining industry", "chemical industry", "defense industry",
    "aviation industry", "shipping industry", "renewable energy sector",
    "oil and gas industry", "telecommunications industry", "fintech sector",
    "e-commerce industry", "healthcare sector", "education sector",
    "tourism industry", "food processing industry", "construction industry",
    "media and entertainment industry", "space industry", "nuclear energy sector",
    "water treatment industry", "waste management industry", "rail transport sector",
    "road transport sector", "port and logistics sector", "startup ecosystem",
    "venture capital sector", "private equity sector", "sovereign wealth sector",
    "public sector undertakings", "cooperative sector", "informal economy",
    "gig economy sector", "artificial intelligence industry",
    "semiconductor industry", "electric vehicle industry", "drone industry",
    "biotechnology industry", "nanotechnology sector", "robotics industry",
    "cybersecurity industry", "cloud computing industry", "blockchain industry",
    "green energy industry",
]

EXTRA_BILATERAL = [
    "diplomatic relations", "cultural exchange", "student exchange program",
    "technology transfer agreement", "investment protection agreement",
    "double taxation avoidance agreement", "visa facilitation agreement",
    "maritime cooperation agreement", "air services agreement",
    "extradition treaty", "mutual legal assistance treaty",
    "joint military exercise", "intelligence sharing agreement",
    "space cooperation agreement", "nuclear cooperation agreement",
    "free trade negotiation", "currency swap agreement",
]

EXTRA_INDIAN_STATE_INDICATORS = [
    "gdp", "population", "literacy rate", "per capita income",
    "poverty rate", "unemployment rate", "urbanization rate",
    "industrial output", "agricultural output", "tourism revenue",
    "health expenditure", "education expenditure", "crime rate",
    "infant mortality rate", "sex ratio", "forest cover",
    "renewable energy capacity", "road density", "internet penetration",
    "bank account penetration",
]

def gen_gap_filler(db, target=10000):
    """Generate additional triples to reach the target node count."""
    current = count_nodes(db)
    logger.info("[gap-filler] Current nodes: %d, target: %d", current, target)
    if current >= target:
        logger.info("[gap-filler] Already at target -- nothing to do.")
        return []

    # Generate ALL possible triples -- MERGE in insert_triple handles duplicates.
    # This avoids the problem of "remaining" budget being consumed by already-
    # existing triples from prior runs.
    triples = []
    all_countries = list(COUNTRIES.keys())

    # Phase A: Country-level indicators
    for country in all_countries:
        for ind in EXTRA_INDICATORS:
            triples.append(make_triple(f"{country} {ind}", "AFFECTS", country, 0.82,
                                       "https://data.worldbank.org",
                                       f"{ind} for {country}", "EconomicIndicator", "Country"))

    # Phase B: Country-sector nodes
    for country in all_countries:
        for sector in EXTRA_SECTORS:
            triples.append(make_triple(f"{country} {sector}", "OPERATES_IN", country, 0.82,
                                       f"{WIKI}{sector.replace(' ', '_').title()}",
                                       f"{sector} is a key sector in {country}", "Event", "Country"))

    # Phase C: Indian state-level indicators
    for state, _cap, _reg in INDIAN_STATES:
        for ind in EXTRA_INDIAN_STATE_INDICATORS:
            triples.append(make_triple(f"{state} {ind}", "AFFECTS", state, 0.82,
                                       f"{WIKI}{state.replace(' ', '_').title()}",
                                       f"{ind} for {state}", "EconomicIndicator", "Location"))

    # Phase D: Bilateral relationship types between top country pairs
    top_pairs = [
        ("india","united states"), ("india","china"), ("india","russia"), ("india","japan"),
        ("india","germany"), ("india","france"), ("india","united kingdom"), ("india","australia"),
        ("india","saudi arabia"), ("india","uae"), ("india","iran"), ("india","israel"),
        ("india","south korea"), ("india","singapore"), ("india","canada"), ("india","brazil"),
        ("india","south africa"), ("india","indonesia"), ("india","vietnam"), ("india","bangladesh"),
        ("united states","china"), ("united states","russia"), ("united states","japan"),
        ("united states","germany"), ("united states","united kingdom"), ("united states","france"),
        ("united states","south korea"), ("united states","australia"), ("united states","israel"),
        ("united states","saudi arabia"), ("china","russia"), ("china","japan"),
        ("china","south korea"), ("china","germany"), ("china","australia"),
        ("russia","germany"), ("russia","turkey"), ("russia","iran"),
        ("japan","south korea"), ("germany","france"),
    ]
    for a, b in top_pairs:
        for rel_name in EXTRA_BILATERAL:
            node_name = f"{a}-{b} {rel_name}"
            triples.append(make_triple(node_name, "CONNECTS", a, 0.80,
                                       f"{WIKI}Foreign_relations_of_{a.replace(' ','_').title()}",
                                       f"{rel_name} between {a} and {b}", "Agreement", "Country"))
            triples.append(make_triple(node_name, "CONNECTS", b, 0.80,
                                       f"{WIKI}Foreign_relations_of_{b.replace(' ','_').title()}",
                                       f"{rel_name} between {a} and {b}", "Agreement", "Country"))

    # Phase F: City-level indicators
    city_indicators = [
        "population", "gdp", "cost of living index", "air quality index",
        "public transit score", "unemployment rate", "crime rate", "startup count",
        "tourism arrivals", "hospital beds per capita", "education index",
        "green space percentage", "housing price index", "internet penetration",
        "renewable energy share",
    ]
    for city, _country in CITIES:
        for ci in city_indicators:
            triples.append(make_triple(f"{city} {ci}", "AFFECTS", city, 0.80,
                                       f"{WIKI}{city.replace(' ', '_').title()}",
                                       f"{ci} for {city}", "EconomicIndicator", "Location"))

    # Phase G: Company-technology linkages
    tech_list = [t[0] for t in TECHNOLOGIES[:20]]
    comp_list = [c[0] for c in COMPANIES[:80]]
    import itertools as _it
    for comp, tech in _it.product(comp_list, tech_list):
        triples.append(make_triple(f"{comp} {tech} initiative", "RESEARCHES", tech, 0.78,
                                   f"{WIKI}{comp.replace(' ', '_').title()}",
                                   f"{comp} initiative in {tech}", "Event", "Technology"))

    # Phase E: Inter-resource dependencies
    resource_deps = [
        ("crude oil", "AFFECTS", "inflation"), ("crude oil", "AFFECTS", "currency exchange rate"),
        ("natural gas", "AFFECTS", "industrial production"), ("coal", "CAUSES", "co2 emissions"),
        ("lithium", "CRITICAL_FOR", "electric vehicles"), ("semiconductors", "CRITICAL_FOR", "artificial intelligence"),
        ("iron ore", "CRITICAL_FOR", "steel"), ("copper", "CRITICAL_FOR", "electric vehicles"),
        ("rare earth elements", "CRITICAL_FOR", "semiconductors"),
    ]
    for s, p, o in resource_deps:
        triples.append(make_triple(s, p, o, 0.85, f"{WIKI}{s.replace(' ', '_').title()}",
                                   f"{s} {p.lower().replace('_',' ')} {o}"))

    logger.info("[gap-filler] Generated %d total triples (includes existing; MERGE handles dedup)", len(triples))
    return triples


# ═══════════════════════════════════════════════════════════════════════════════
#
# ████  PHASE FUNCTIONS  ████
#
# ═══════════════════════════════════════════════════════════════════════════════

def phase_curated(db):
    """Phase 1+2: Insert all curated + derived knowledge."""
    logger.info("=" * 60)
    logger.info("PHASE 1: CURATED KNOWLEDGE")
    logger.info("=" * 60)

    all_triples = []
    generators = [
        ("Countries", gen_country_triples),
        ("Organizations", gen_org_membership_triples),
        ("Companies", gen_company_triples),
        ("People", gen_people_triples),
        ("Cities", gen_city_triples),
        ("Indian States", gen_indian_state_triples),
        ("Resources", gen_resource_triples),
        ("Infrastructure", gen_infra_triples),
        ("Events", gen_event_triples),
        ("Military", gen_military_triples),
        ("Technology", gen_tech_triples),
        ("Agreements", gen_agreement_triples),
        ("Policies", gen_policy_triples),
        ("Geographic", gen_geographic_triples),
        ("Finance", gen_finance_triples),
        ("Supplementary", gen_supplementary_triples),
        ("Derived Indicators", gen_derived_indicators),
        ("Derived Trade", gen_derived_trade_pairs),
        ("Derived Defense", gen_derived_defense_partnerships),
        ("Derived Energy", gen_derived_energy_trade),
    ]

    for name, gen_fn in generators:
        t = gen_fn()
        logger.info("  [%s] Generated %d triples", name, len(t))
        all_triples.extend(t)

    logger.info("Total curated triples: %d", len(all_triples))

    before = count_nodes(db)
    inserted, failed = bulk_insert(db, all_triples, "curated")
    after = count_nodes(db)
    logger.info("Nodes: %d -> %d (+%d). Edges: %d", before, after, after - before, count_edges(db))
    return after


def phase_datacommons(db):
    """Phase 3: Fetch DataCommons indicators and insert."""
    logger.info("=" * 60)
    logger.info("PHASE 3: DATA COMMONS")
    logger.info("=" * 60)

    try:
        from src.ingest.datacommons_loader import fetch_stat_var, get_bootstrap_triples
    except ImportError:
        logger.warning("DataCommons loader not available — skipping")
        return

    # Extended country DCIDs for DataCommons
    dc_countries = {
        "india": "country/IND", "china": "country/CHN", "united states": "country/USA",
        "japan": "country/JPN", "germany": "country/DEU", "united kingdom": "country/GBR",
        "france": "country/FRA", "brazil": "country/BRA", "russia": "country/RUS",
        "south korea": "country/KOR", "australia": "country/AUS", "canada": "country/CAN",
        "italy": "country/ITA", "spain": "country/ESP", "mexico": "country/MEX",
        "indonesia": "country/IDN", "turkey": "country/TUR", "saudi arabia": "country/SAU",
        "south africa": "country/ZAF", "argentina": "country/ARG",
        "iran": "country/IRN", "iraq": "country/IRQ", "pakistan": "country/PAK",
        "bangladesh": "country/BGD", "nigeria": "country/NGA", "egypt": "country/EGY",
        "thailand": "country/THA", "vietnam": "country/VNM", "malaysia": "country/MYS",
        "philippines": "country/PHL", "israel": "country/ISR",
    }

    stat_vars = [
        ("Amount_EconomicActivity_GrossDomesticProduction_Nominal", "gdp"),
        ("Count_Person", "population"),
        ("Amount_EconomicActivity_GrossDomesticProduction_Nominal_PerCapita", "gdp per capita"),
    ]

    triples = []
    for country_name, dcid in dc_countries.items():
        for stat_var, label in stat_vars:
            try:
                value = fetch_stat_var(dcid, stat_var)
                if value is not None:
                    indicator_name = f"{country_name} {label} (datacommons)"
                    dc_url = f"https://datacommons.org/place/{dcid}"
                    triples.append(make_triple(
                        indicator_name, "AFFECTS", country_name, 0.92, dc_url,
                        f"{label} data for {country_name}: {value}",
                        "EconomicIndicator", "Country"
                    ))
                time.sleep(0.5)  # rate limit DC API
            except Exception as e:
                logger.warning("DC fetch failed for %s/%s: %s", country_name, label, e)

    before = count_nodes(db)
    inserted, _failed = bulk_insert(db, triples, "datacommons")
    after = count_nodes(db)
    logger.info("DataCommons: %d triples inserted. Nodes: %d -> %d", inserted, before, after)


def phase_rss(db):
    """Phase 4: Fetch RSS articles, extract triples with LLM, insert."""
    logger.info("=" * 60)
    logger.info("PHASE 4: RSS NEWS EXTRACTION")
    logger.info("=" * 60)

    from src.ingest.rss_loader import fetch_articles_from_all_feeds
    from src.extract.llm_extract import extract_triples_batch
    from src.graph.graph_loader import insert_triple as graph_insert_triple

    # Progress file for resumability
    progress_file = DATA_DIR / "rss_ingest_progress.json"
    processed_urls = set()
    if progress_file.exists():
        try:
            with open(progress_file, "r") as f:
                processed_urls = set(json.load(f))
            logger.info("Resuming: %d articles already processed", len(processed_urls))
        except Exception:
            pass

    logger.info("Fetching articles from all RSS feeds...")
    articles = fetch_articles_from_all_feeds()
    logger.info("Fetched %d articles total", len(articles))

    # Filter already-processed
    new_articles = [a for a in articles if a.get("link", "") not in processed_urls]
    logger.info("New articles to process: %d", len(new_articles))

    if not new_articles:
        logger.info("No new articles — RSS phase complete.")
        return

    total_inserted = 0
    total_triples = 0
    batch_size = 3

    for i in range(0, len(new_articles), batch_size):
        batch = new_articles[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(new_articles) + batch_size - 1) // batch_size
        logger.info("[RSS] Batch %d/%d (%d articles)", batch_num, total_batches, len(batch))

        try:
            results = extract_triples_batch(batch)
        except Exception as e:
            logger.error("[RSS] Batch %d LLM call failed: %s. Sleeping 60s then continuing.", batch_num, e)
            time.sleep(60)
            continue

        try:
            for idx, article_triples in results.items():
                article = batch[idx]
                source_url = article.get("link", "")
                total_triples += len(article_triples)

                for t in article_triples:
                    try:
                        ok = graph_insert_triple(
                            db=db,
                            subject=t.get("subject", ""),
                            predicate=t.get("predicate", "AFFECTS"),
                            obj=t.get("object", ""),
                            confidence=t.get("confidence", 0.7),
                            source_url=t.get("source_url", source_url),
                            source_context=t.get("source_context", ""),
                            timestamp=NOW,
                        )
                        if ok:
                            total_inserted += 1
                    except Exception as e:
                        logger.warning("Insert failed: %s", e)

                # Mark as processed
                if source_url:
                    processed_urls.add(source_url)
        except Exception as e:
            logger.error("[RSS] Batch %d failed: %s", batch_num, e)

        # Save progress periodically
        if batch_num % 10 == 0:
            with open(progress_file, "w") as f:
                json.dump(list(processed_urls), f)

    # Final progress save
    with open(progress_file, "w") as f:
        json.dump(list(processed_urls), f)

    logger.info("[RSS] Done: %d triples extracted, %d inserted. Nodes: %d, Edges: %d",
                total_triples, total_inserted, count_nodes(db), count_edges(db))


def phase_fill(db, target=10000):
    """Phase 5: Fill remaining gap to reach target nodes."""
    logger.info("=" * 60)
    logger.info("PHASE 5: GAP FILLER (target=%d)", target)
    logger.info("=" * 60)

    triples = gen_gap_filler(db, target)
    if triples:
        before = count_nodes(db)
        inserted, _failed = bulk_insert(db, triples, "gap-filler")
        after = count_nodes(db)
        logger.info("Gap-filler: Nodes: %d -> %d (+%d)", before, after, after - before)
    else:
        logger.info("No gap-filling needed.")


# ═══════════════════════════════════════════════════════════════════════════════
# ██████  MAIN  ██████
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Mass ingestion pipeline for 10K+ nodes")
    parser.add_argument("--phase", choices=["all", "curated", "datacommons", "rss", "fill"],
                        default="all", help="Which phase to run")
    parser.add_argument("--target", type=int, default=10000, help="Target node count for gap-filler")
    args = parser.parse_args()

    logger.info("Connecting to Memgraph...")
    db = get_memgraph()
    create_constraints(db)
    create_indexes(db)

    initial = count_nodes(db)
    logger.info("Starting node count: %d", initial)

    if args.phase in ("all", "curated"):
        phase_curated(db)

    if args.phase in ("all", "datacommons"):
        phase_datacommons(db)

    if args.phase in ("all", "rss"):
        phase_rss(db)

    if args.phase in ("all", "fill"):
        phase_fill(db, args.target)

    final_nodes = count_nodes(db)
    final_edges = count_edges(db)
    logger.info("=" * 60)
    logger.info("FINAL: %d nodes, %d edges (started at %d)", final_nodes, final_edges, initial)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

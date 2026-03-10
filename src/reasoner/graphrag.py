"""GraphRAG: vector + graph retrieval with LLM synthesis for question answering.

All LLM calls go through the rate-limited _call_llm helper in
src.extract.llm_extract so the 4 s gap / 429-retry logic is shared.
"""

import json
import logging
import re
from datetime import datetime, timezone

import numpy as np

from src.config import DATA_DIR
from src.extract.llm_extract import _call_llm      # shared rate-limited caller
from src.graph.memgraph_init import get_memgraph

logger = logging.getLogger(__name__)


DECOMPOSITION_PROMPT = """You are a geopolitical and economic analysis assistant focused on India and global affairs.
Given the user's question, decompose it into 2-5 specific sub-queries that can be answered by searching a knowledge graph.
The knowledge graph contains: Countries, Organizations, Companies, People, Resources, Events, Indicators, Technologies, Policies, Agreements, Infrastructure, Military assets, and Locations — with relationships like IMPORTS, EXPORTS, BORDERS, MEMBER_OF, TRADES_WITH, AFFECTS, SANCTIONS, DEFENSE_PARTNERSHIP_WITH, etc.

Question: {question}

Return a JSON array of sub-query strings. Example:
["What countries does India trade with?", "What is India's GDP trend?", "Which organizations is India a member of?"]
"""

SYNTHESIS_PROMPT = """You are a world-class geopolitical and economic analyst with deep expertise in India and global affairs.
Answer the user's question using the knowledge graph evidence below AND your analytical expertise.

QUESTION: {question}

KNOWLEDGE GRAPH EVIDENCE:
{subgraph_text}

REASONING INSTRUCTIONS:
1. Study the graph TOPOLOGY: which nodes affect which, and whether the effect is positive, negative, or mixed.
2. Use node values (GDP figures, population, indicators) as quantitative anchors for your analysis.
3. Follow causal chains: e.g., oil prices -> inflation -> interest rates -> GDP growth.
4. For projection/forecasting questions, identify ALL factors affecting the target, assess their trajectory, and synthesize a reasoned forecast.
5. Cite specific relationships from the graph as evidence.
6. When graph evidence is partial, combine it with your general knowledge to give the best possible answer.
7. NEVER refuse to answer. Always provide your best analytical assessment.
8. For "What will GDP be by 2040?" type questions: identify growth drivers (services, manufacturing, FDI, demographics) vs headwinds (inflation, oil dependency, fiscal deficit), estimate growth rates, and project.

OUTPUT FORMAT (strict JSON):
{{
  "answer": "Your detailed analytical answer as a paragraph",
  "causal_chain": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ..."
  ],
  "evidence": [
    {{
      "subject": "entity1",
      "relationship": "REL_TYPE",
      "object": "entity2",
      "confidence": 0.85,
      "source_url": "url if available"
    }}
  ],
  "overall_confidence": 0.75,
  "uncertainties": ["List of gaps or low-confidence areas"],
  "key_impacts": [
    {{
      "domain": "energy/inflation/currency/trade/defense/technology",
      "severity": "high/medium/low",
      "description": "Brief impact description"
    }}
  ]
}}
"""


def decompose_question(question: str) -> list[str]:
    """Use LLM to decompose a complex question into sub-queries."""
    try:
        raw = _call_llm(
            DECOMPOSITION_PROMPT.format(question=question),
            label="decompose-question",
            max_tokens=512,
        )
        cleaned = raw
        # Strip markdown fences
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        # Try to find a JSON array anywhere in the response
        arr_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if arr_match:
            cleaned = arr_match.group(0)
        sub_queries = json.loads(cleaned)
        if isinstance(sub_queries, list):
            return sub_queries
        return [question]
    except Exception as e:
        logger.error("Decomposition failed: %s", e)
        return [question]


def find_entry_nodes(db, query: str, limit: int = 15) -> list[dict]:
    """Find relevant entry nodes via keyword matching on the graph."""
    keywords = _extract_keywords(query)
    nodes = []
    seen = set()

    for kw in keywords:
        results = list(db.execute_and_fetch(
            "MATCH (n) WHERE toLower(n.name) CONTAINS $kw "
            "RETURN labels(n) AS labels, n.name AS name, n.aliases AS aliases "
            "LIMIT $limit;",
            {"kw": kw.lower(), "limit": limit},
        ))
        for row in results:
            name = row.get("name", "")
            if name not in seen:
                seen.add(name)
                nodes.append({
                    "name": name,
                    "labels": row.get("labels", []),
                    "aliases": row.get("aliases", "[]"),
                })

    return nodes[:limit]


MAX_CONTEXT_NODES = 60
MAX_CONTEXT_EDGES = 100


def traverse_subgraph(db, entry_names: list[str], depth: int = 2) -> dict:
    """Traverse the graph from entry nodes up to given depth.
    
    Returns a subgraph dict with nodes and edges.
    Includes node properties (value, description, display_value) for richer context.
    Caps results to MAX_CONTEXT_NODES / MAX_CONTEXT_EDGES to stay within
    LLM token limits.
    """
    nodes = {}
    edges = []
    seen_edges = set()

    for name in entry_names:
        results = list(db.execute_and_fetch(
            f"MATCH path = (start {{name: $name}})-[*1..{depth}]-(end) "
            "UNWIND relationships(path) AS r "
            "WITH startNode(r) AS a, r, endNode(r) AS b "
            "RETURN a.name AS src, labels(a) AS src_labels, "
            "a.description AS src_desc, a.value AS src_value, "
            "a.display_value AS src_display, a.date AS src_date, "
            "type(r) AS rel_type, r.confidence AS confidence, "
            "r.sources AS sources, r.status AS status, r.trust AS trust, "
            "r.effect AS effect, r.source_context AS source_context, "
            "b.name AS tgt, labels(b) AS tgt_labels, "
            "b.description AS tgt_desc, b.value AS tgt_value, "
            "b.display_value AS tgt_display, b.date AS tgt_date;",
            {"name": name},
        ))

        for row in results:
            src = row.get("src", "")
            tgt = row.get("tgt", "")
            rel = row.get("rel_type", "")
            
            if src not in nodes and len(nodes) < MAX_CONTEXT_NODES:
                nodes[src] = {
                    "name": src,
                    "labels": row.get("src_labels", []),
                    "description": row.get("src_desc", ""),
                    "value": row.get("src_value"),
                    "display_value": row.get("src_display", ""),
                    "date": row.get("src_date", ""),
                }
            if tgt not in nodes and len(nodes) < MAX_CONTEXT_NODES:
                nodes[tgt] = {
                    "name": tgt,
                    "labels": row.get("tgt_labels", []),
                    "description": row.get("tgt_desc", ""),
                    "value": row.get("tgt_value"),
                    "display_value": row.get("tgt_display", ""),
                    "date": row.get("tgt_date", ""),
                }

            edge_key = f"{src}-{rel}-{tgt}"
            if edge_key not in seen_edges and len(edges) < MAX_CONTEXT_EDGES:
                seen_edges.add(edge_key)
                edges.append({
                    "source": src,
                    "target": tgt,
                    "relationship": rel,
                    "confidence": row.get("confidence", 0),
                    "status": row.get("status", "active"),
                    "trust": row.get("trust", "untrusted"),
                    "sources": row.get("sources", "[]"),
                    "effect": row.get("effect", ""),
                    "source_context": row.get("source_context", ""),
                })

        # Stop early if we hit the caps
        if len(nodes) >= MAX_CONTEXT_NODES or len(edges) >= MAX_CONTEXT_EDGES:
            break

    return {"nodes": list(nodes.values()), "edges": edges}


MAX_CONTEXT_CHARS = 6000   # ~1500 tokens, room for node descriptions + edge contexts


def format_subgraph_for_llm(subgraph: dict) -> str:
    """Format subgraph as readable text for LLM context.
    
    Includes node properties (descriptions, values) and edge effects for
    richer evidence and causal reasoning.
    Truncates to MAX_CONTEXT_CHARS to stay within Groq token limits.
    Prioritizes high-confidence edges.
    """
    # Sort edges by confidence descending so the most reliable appear first
    sorted_edges = sorted(
        subgraph.get("edges", []),
        key=lambda e: float(e.get("confidence") or 0),
        reverse=True,
    )

    lines = []
    lines.append("NODES:")
    for n in subgraph.get("nodes", []):
        labels = ", ".join(n.get("labels", []))
        parts = [f"  - {n['name']} [{labels}]"]
        desc = n.get("description") or ""
        if desc:
            parts.append(f" -- {desc}")
        display = n.get("display_value") or ""
        date = n.get("date") or ""
        if display:
            parts.append(f" (value: {display}")
            if date:
                parts.append(f", as of {date}")
            parts.append(")")
        lines.append("".join(parts))

    lines.append("\nRELATIONSHIPS:")
    for e in sorted_edges:
        conf = e.get("confidence") or 0
        src = e.get("source") or "?"
        tgt = e.get("target") or "?"
        rel = e.get("relationship") or "RELATED_TO"
        effect = e.get("effect") or ""
        
        line = (
            f"  - ({src}) -[{rel}]-> ({tgt}) "
            f"[confidence={float(conf):.2f}]"
        )
        if effect:
            line += f" [effect: {effect}]"
        
        # Add source_context directly from edge property
        ctx = e.get("source_context") or ""
        if ctx:
            line += f" -- {ctx[:150]}"
        else:
            # Fall back to sources JSON
            raw_sources = e.get("sources", "[]")
            try:
                parsed = json.loads(raw_sources) if isinstance(raw_sources, str) else (raw_sources or [])
                if isinstance(parsed, list):
                    for s in parsed:
                        snippet = s.get("snippet", "") if isinstance(s, dict) else ""
                        if snippet:
                            line += f" -- {snippet[:120]}"
                            break
            except (json.JSONDecodeError, TypeError):
                pass
        lines.append(line)

    text = "\n".join(lines)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS] + "\n  ... (truncated for token limit)"
    return text


def synthesize_answer(question: str, subgraph: dict) -> dict:
    """Use LLM to synthesize an answer from the subgraph evidence."""
    subgraph_text = format_subgraph_for_llm(subgraph)
    logger.info("Subgraph context: %d chars for LLM", len(subgraph_text))

    prompt = SYNTHESIS_PROMPT.format(
        question=question,
        subgraph_text=subgraph_text,
    )
    logger.info("Synthesis prompt: %d chars (~%d tokens)", len(prompt), len(prompt) // 4)

    try:
        raw = _call_llm(prompt, label="synthesize-answer", max_tokens=2048)
        cleaned = raw
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        # Find JSON object in response
        obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if obj_match:
            cleaned = obj_match.group(0)
        result = json.loads(cleaned)
        result["subgraph"] = subgraph
        result["question"] = question
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception as e:
        logger.error("Synthesis failed: %s", e)
        return {
            "answer": f"Synthesis failed: {e}",
            "question": question,
            "subgraph": subgraph,
            "overall_confidence": 0.0,
            "error": str(e),
        }


def answer_question(question: str, db=None) -> dict:
    """Full GraphRAG pipeline: decompose → find nodes → traverse → synthesize."""
    if db is None:
        db = get_memgraph()

    logger.info("Processing question: %s", question)

    # 1. Decompose
    sub_queries = decompose_question(question)
    logger.info("Sub-queries: %s", sub_queries)

    # 2. Find entry nodes from all sub-queries
    all_entry_names = []
    for sq in sub_queries:
        nodes = find_entry_nodes(db, sq, limit=5)
        all_entry_names.extend([n["name"] for n in nodes])

    # Deduplicate and cap entry nodes to avoid exploding context
    entry_names = list(dict.fromkeys(all_entry_names))[:15]
    logger.info("Entry nodes (%d): %s", len(entry_names), entry_names)

    # 3. Traverse subgraph (depth=2 to stay within token limits)
    subgraph = traverse_subgraph(db, entry_names, depth=2)
    logger.info("Subgraph: %d nodes, %d edges", len(subgraph["nodes"]), len(subgraph["edges"]))

    # 4. Synthesize
    result = synthesize_answer(question, subgraph)

    return result


def save_demo_result(result: dict, path=None) -> str:
    """Save demo result to JSON."""
    path = path or (DATA_DIR / "demo_result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info("Demo result saved to %s", path)
    return str(path)


def _extract_keywords(text: str) -> list[str]:
    """Extract potential entity keywords from query text.
    
    Uses a comprehensive domain vocabulary plus individual words.
    """
    # Multi-word domain terms (check these first)
    domain_phrases = [
        "united states", "united kingdom", "saudi arabia", "south korea",
        "north korea", "south africa", "new zealand", "sri lanka",
        "south china sea", "strait of hormuz", "persian gulf",
        "crude oil", "natural gas", "rare earth", "nuclear energy",
        "climate change", "trade war", "trade deficit", "current account",
        "foreign policy", "defense partnership", "bilateral relations",
        "supply chain", "stock market", "interest rate", "exchange rate",
        "currency exchange rate", "industrial production",
        "make in india", "digital india", "bullet train",
        "belt and road", "quad summit", "g20 summit",
        "electric vehicles", "artificial intelligence", "semiconductor",
        "renewable energy", "space technology",
    ]
    # Single-word entity terms
    domain_words = {
        "india", "china", "usa", "iran", "russia", "pakistan", "japan",
        "germany", "france", "brazil", "israel", "turkey", "australia",
        "canada", "indonesia", "bangladesh", "nepal", "ukraine", "taiwan",
        "iraq", "uae", "qatar", "egypt", "nigeria", "mexico", "vietnam",
        "oil", "lng", "gas", "coal", "lithium", "copper", "iron",
        "steel", "wheat", "rice", "cotton", "gold", "diamond",
        "inflation", "gdp", "economy", "trade", "tariff", "sanctions",
        "currency", "rupee", "dollar", "yuan", "yen", "euro",
        "opec", "nato", "brics", "asean", "saarc", "quad", "sco",
        "un", "imf", "who", "wto",
        "military", "defense", "navy", "army", "nuclear", "missile",
        "war", "conflict", "tension", "crisis", "attack",
        "import", "export", "investment", "manufacturing",
        "technology", "startup", "fintech", "5g", "ai",
        "modi", "biden", "trump", "xi", "putin",
        "isro", "drdo", "nasa", "spacex",
        "mumbai", "delhi", "bangalore", "chennai", "kolkata",
        "beijing", "shanghai", "tokyo", "moscow", "washington",
        "london", "paris", "berlin", "dubai", "riyadh",
        "energy", "power", "solar", "wind", "hydrogen",
        "population", "unemployment", "poverty", "growth",
        "budget", "fiscal", "monetary", "reserve",
    }
    
    text_lower = text.lower()
    found = []
    
    # Check multi-word phrases first
    for phrase in domain_phrases:
        if phrase in text_lower:
            found.append(phrase)
    
    # Check single words
    for term in domain_words:
        if term in text_lower and term not in found:
            found.append(term)

    # Also split into individual significant words from the query
    stop_words = {
        "how", "will", "would", "the", "a", "an", "of", "and", "or",
        "is", "are", "was", "were", "be", "to", "in", "on", "at",
        "for", "with", "what", "does", "do", "affect", "impact",
        "could", "should", "can", "may", "might", "has", "have",
        "been", "being", "this", "that", "these", "those", "from",
        "by", "about", "between", "which", "who", "where", "when",
        "why", "its", "it", "if", "not", "but", "all", "more",
        "than", "over", "under", "any", "some", "much", "many",
    }
    words = text_lower.split()
    for w in words:
        w = w.strip("?.,!;:'\"")
        if len(w) > 2 and w not in stop_words and w not in found:
            found.append(w)

    return found

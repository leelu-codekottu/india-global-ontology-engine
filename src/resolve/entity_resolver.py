"""Entity resolver: string-based deduplication and alias clustering.

Uses normalized string matching (case-insensitive, stripped) plus
Levenshtein-like heuristics for entity resolution. No external embedding
API required.
"""

import json
import logging
from collections import defaultdict

import numpy as np

from src.config import SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)


def _normalize(name: str) -> str:
    """Lowercase, strip, collapse whitespace, remove underscores."""
    return " ".join(name.lower().strip().replace("_", " ").split())


def _string_similarity(a: str, b: str) -> float:
    """Simple token-overlap Jaccard similarity between two normalised names."""
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 1.0 if a == b else 0.0
    return len(ta & tb) / len(ta | tb)


class EntityResolver:
    """Resolves entity names to canonical forms using embedding similarity."""

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold or SIMILARITY_THRESHOLD
        self.canonical_map: dict[str, str] = {}  # alias → canonical
        self.alias_clusters: dict[str, list[str]] = defaultdict(list)  # canonical → [aliases]

    def resolve(self, name: str) -> str:
        """Resolve an entity name to its canonical form.

        Uses exact normalised match first, then token-overlap Jaccard similarity.
        """
        norm = _normalize(name)

        # Direct cache hit
        if norm in self.canonical_map:
            return self.canonical_map[norm]

        # Exact match in known canonicals
        if norm in self.alias_clusters:
            return norm

        # Token-overlap similarity check
        best_match = None
        best_sim = 0.0

        for canonical in self.alias_clusters:
            canon_norm = _normalize(canonical)
            # exact normalised match
            if canon_norm == norm:
                self.canonical_map[norm] = canonical
                return canonical
            sim = _string_similarity(norm, canon_norm)
            if sim > best_sim:
                best_sim = sim
                best_match = canonical

        if best_match and best_sim >= self.threshold:
            self.canonical_map[norm] = best_match
            self.alias_clusters[best_match].append(norm)
            logger.info("Resolved '%s' -> '%s' (sim=%.3f)", norm, best_match, best_sim)
            return best_match
        else:
            self.canonical_map[norm] = norm
            self.alias_clusters[norm] = []
            logger.info("New canonical entity: '%s'", norm)
            return norm

    def resolve_triples(self, triples: list[dict]) -> list[dict]:
        """Resolve subject and object names in a list of triples."""
        resolved = []
        for t in triples:
            t_copy = dict(t)
            t_copy["subject"] = self.resolve(t["subject"])
            t_copy["object"] = self.resolve(t["object"])
            resolved.append(t_copy)
        return resolved

    def seed_from_graph(self, db) -> None:
        """Seed the resolver with existing nodes from Memgraph."""
        from src.config import ALLOWED_NODE_LABELS

        for label in ALLOWED_NODE_LABELS:
            try:
                rows = list(db.execute_and_fetch(
                    f"MATCH (n:{label}) RETURN n.name AS name, n.aliases AS aliases;"
                ))
                for row in rows:
                    name = row.get("name", "")
                    if not name:
                        continue
                    self.canonical_map[name] = name
                    aliases_raw = row.get("aliases", "[]")
                    try:
                        aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw or []
                    except (json.JSONDecodeError, TypeError):
                        aliases = []
                    self.alias_clusters[name] = aliases
                    for alias in aliases:
                        self.canonical_map[alias.lower().strip()] = name
            except Exception as e:
                logger.warning("Failed to seed from label %s: %s", label, e)

        logger.info("Seeded resolver with %d canonical entities", len(self.alias_clusters))

    def get_stats(self) -> dict:
        """Return resolver statistics."""
        return {
            "canonical_entities": len(self.alias_clusters),
            "total_aliases": sum(len(v) for v in self.alias_clusters.values()),
        }

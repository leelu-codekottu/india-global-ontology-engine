"""LLM-based triple extraction with deterministic settings.

Supports Groq (primary, free tier) and Gemini (fallback).

Implements:
  - Sequential processing (no parallel LLM calls)
  - 4-second minimum delay between API calls
  - 429 retry with 10s backoff, max 3 retries
  - Batch extraction (up to 3 articles per request)
  - Content-hash caching to skip duplicate articles
  - Full request/retry logging
"""

import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    LLM_PROVIDER,
    EXTRACTION_MODEL,
    ALLOWED_NODE_LABELS,
    ALLOWED_RELATIONSHIP_TYPES,
    FAILED_DIR,
    SAVE_FAILED_EXTRACTIONS,
    DATA_DIR,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded clients (avoids import errors if SDK not installed)
# ---------------------------------------------------------------------------
_groq_client = None
_gemini_configured = False


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client

# ---------------------------------------------------------------------------
# Rate-limiter: enforces min 4 s gap between any two Gemini calls globally
# ---------------------------------------------------------------------------
_rate_lock = threading.Lock()
_last_call_time: float = 0.0
_MIN_CALL_GAP = 10.0         # seconds between calls (Groq free tier: 30 RPM + 6K TPM)
_RETRY_WAIT = 30.0           # base seconds to wait on 429 (exponential backoff)
_MAX_RETRIES = 5             # per-request retry cap

# ---------------------------------------------------------------------------
# Result cache (persisted as JSON beside the data dir)
# ---------------------------------------------------------------------------
_CACHE_PATH = DATA_DIR / "extraction_cache.json"
_cache: dict[str, list[dict]] = {}


def _load_cache() -> None:
    global _cache
    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            logger.info("Loaded extraction cache: %d entries", len(_cache))
        except Exception:
            _cache = {}


def _save_cache() -> None:
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except Exception:
        pass


def _content_hash(text: str) -> str:
    """SHA-256 of article text (first 6000 chars, stripped)."""
    return hashlib.sha256(text.strip()[:6000].encode("utf-8")).hexdigest()


# Pre-load cache at import time
_load_cache()


# ---------------------------------------------------------------------------
# Low-level LLM wrapper with rate-limit + retry (Groq primary, Gemini fallback)
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, label: str = "extraction", max_tokens: int = 2048) -> str:
    """Send a single prompt to the configured LLM provider, respecting rate limits.

    * Waits until at least _MIN_CALL_GAP seconds since the last call.
    * On 429, waits _RETRY_WAIT seconds and retries up to _MAX_RETRIES times.
    * Returns the raw response text.
    * Raises on unrecoverable errors.
    """
    global _last_call_time

    provider = LLM_PROVIDER.lower()

    for attempt in range(1, _MAX_RETRIES + 1):
        # --- enforce minimum gap ---
        with _rate_lock:
            elapsed = time.time() - _last_call_time
            if elapsed < _MIN_CALL_GAP:
                gap = _MIN_CALL_GAP - elapsed
                logger.debug("[rate-limit] waiting %.1fs before next call", gap)
                time.sleep(gap)
            _last_call_time = time.time()

        logger.info("[%s] %s — attempt %d/%d", provider, label, attempt, _MAX_RETRIES)
        try:
            if provider == "groq":
                client = _get_groq_client()
                response = client.chat.completions.create(
                    model=EXTRACTION_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=max_tokens,
                )
                text = response.choices[0].message.content.strip()
            else:
                # Gemini fallback
                import google.generativeai as genai
                global _gemini_configured
                if not _gemini_configured:
                    genai.configure(api_key=GEMINI_API_KEY)
                    _gemini_configured = True
                model = genai.GenerativeModel(EXTRACTION_MODEL)
                resp = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,
                        max_output_tokens=4096,
                    ),
                )
                text = resp.text.strip()

            logger.info("[%s] %s — success", provider, label)
            return text

        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str:
                wait = _RETRY_WAIT * (1.5 ** (attempt - 1))  # exponential backoff
                logger.warning(
                    "[%s] 429 rate-limited on %s (attempt %d/%d). "
                    "Waiting %.0fs before retry…",
                    provider, label, attempt, _MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            # non-retryable
            raise

    raise RuntimeError(f"LLM call '{label}' failed after {_MAX_RETRIES} retries (429)")


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SINGLE_EXTRACTION_PROMPT = """You are a knowledge-graph extraction engine for a comprehensive global ontology with an India focus.

TASK: Extract structured triples (Subject-Predicate-Object) from the news article below.
Cover ALL domains present in the article:
- Economics: GDP, trade, FDI, inflation, interest rates, stock markets, fiscal policy, debt, budget
- Energy: oil, gas, LNG, renewables, solar, wind, nuclear, coal, hydrogen
- Defense & Security: military, weapons, alliances, conflicts, terrorism, cybersecurity
- Technology: AI, semiconductors, 5G, space, startups, digital economy, EVs, biotech
- Diplomacy: summits, treaties, sanctions, bilateral relations, multilateral forums
- Climate & Environment: emissions, disasters, sustainability, green finance
- Governance: elections, policy reforms, regulations, judiciary
- Infrastructure: transport, logistics, ports, railways, smart cities
- Social: healthcare, education, demographics, migration, poverty, employment

STRICT RULES:
1. Extract ALL factual claims stated or directly implied — do not limit to any single topic.
2. Subject and Object: canonical lowercase names (e.g., "india", "crude oil", "world bank", "gdp").
3. Predicate must be one of: {allowed_rels}
4. Confidence: your assessment of how clearly the text supports this (0.0-1.0).
5. source_context: a 1-2 sentence quote or close paraphrase from the article. No context = skip triple.
6. Do NOT hallucinate. Only extract what the article says.
7. Extract at least economic indicators and country relationships when present.
8. For quantitative facts (GDP=$3.7T, inflation=6.2%), include the value in source_context.

NODE LABELS: {allowed_labels}

ARTICLE:
Title: {title}
Source: {source}
Published: {published}
Text: {text}

OUTPUT (strict JSON array, no markdown fences):
[
  {{
    "subject": "lowercase name",
    "predicate": "RELATIONSHIP_TYPE",
    "object": "lowercase name",
    "confidence": 0.85,
    "timestamp": "{timestamp}",
    "source_url": "{source_url}",
    "source_context": "supporting snippet from the article"
  }}
]

If no relevant triples can be extracted, return: []
"""

_BATCH_EXTRACTION_PROMPT = """You are a knowledge-graph extraction engine for a comprehensive global ontology with an India focus.

TASK: Extract structured triples (Subject-Predicate-Object) from EACH article below.
Cover ALL domains: economics, energy, defense, technology, diplomacy, climate, governance, infrastructure, social.

STRICT RULES:
1. Extract ALL factual claims stated or directly implied — no topic restrictions.
2. Subject and Object: canonical lowercase names.
3. Predicate must be one of: {allowed_rels}
4. Confidence: your assessment (0.0-1.0).
5. source_context: 1-2 sentence snippet from the SPECIFIC article. No cross-article references.
6. Do NOT hallucinate.
7. For quantitative facts, include the value in source_context.

NODE LABELS: {allowed_labels}

--- ARTICLES ---
{articles_block}
--- END ARTICLES ---

OUTPUT (strict JSON object, no markdown fences):
{{
  "article_0": [
    {{
      "subject": "name",
      "predicate": "RELATIONSHIP_TYPE",
      "object": "name",
      "confidence": 0.85,
      "timestamp": "{timestamp}",
      "source_url": "",
      "source_context": "snippet"
    }}
  ],
  "article_1": [ ... ]
}}

If no triples for an article, map it to [].
"""


# ---------------------------------------------------------------------------
# Public API — single-article extraction (with cache)
# ---------------------------------------------------------------------------

def extract_triples(
    title: str,
    text: str,
    source_url: str = "",
    source_name: str = "",
    published: str = "",
) -> list[dict]:
    """Extract SPO triples from one article text using the configured LLM.

    Checks content-hash cache first; if hit, returns cached triples.
    """
    if not text or len(text.strip()) < 50:
        logger.warning("Text too short for extraction: %s", title)
        return []

    # --- cache check ---
    h = _content_hash(text)
    if h in _cache:
        logger.info("[cache-hit] Reusing %d cached triples for '%s'", len(_cache[h]), title)
        return _cache[h]

    now = datetime.now(timezone.utc).isoformat()

    # Inject correction hints from past flagged/rejected triples
    try:
        from src.graph.corrector import get_correction_hints
        correction_block = get_correction_hints()
    except Exception:
        correction_block = ""

    prompt = _SINGLE_EXTRACTION_PROMPT.format(
        allowed_rels=", ".join(ALLOWED_RELATIONSHIP_TYPES),
        allowed_labels=", ".join(ALLOWED_NODE_LABELS),
        title=title,
        source=source_name,
        published=published,
        text=text[:6000],
        timestamp=now,
        source_url=source_url,
    ) + correction_block

    try:
        raw_text = _call_llm(prompt, label=f"extract:{title[:40]}")
        triples = _parse_and_validate(raw_text, source_url, title)
        logger.info("Extracted %d triples from '%s'", len(triples), title)
        # cache
        _cache[h] = triples
        _save_cache()
        return triples
    except Exception as e:
        logger.error("LLM extraction failed for '%s': %s", title, e)
        if SAVE_FAILED_EXTRACTIONS:
            _save_failed(title, source_url, str(e))
        return []


# ---------------------------------------------------------------------------
# Public API — batch extraction (≤ 3 articles per call)
# ---------------------------------------------------------------------------

def extract_triples_batch(articles: list[dict]) -> dict[int, list[dict]]:
    """Extract triples from up to 3 articles in a single LLM call.

    Returns {index_in_input: [triples]}.
    Articles already cached are skipped from the LLM call.
    """
    results: dict[int, list[dict]] = {}
    uncached: list[tuple[int, dict, str]] = []   # (orig_index, article, hash)

    for idx, article in enumerate(articles):
        text = article.get("text") or article.get("summary", "")
        if not text or len(text.strip()) < 50:
            results[idx] = []
            continue
        h = _content_hash(text)
        if h in _cache:
            logger.info("[cache-hit] batch idx %d — reusing %d triples", idx, len(_cache[h]))
            results[idx] = _cache[h]
        else:
            uncached.append((idx, article, h))

    if not uncached:
        return results

    # Build batch prompt for uncached articles
    now = datetime.now(timezone.utc).isoformat()
    blocks = []
    idx_map: dict[str, tuple[int, str]] = {}   # "article_N" -> (orig_idx, hash)
    for batch_i, (orig_idx, article, h) in enumerate(uncached):
        title = article.get("title", f"Article {orig_idx}")
        text = (article.get("text") or article.get("summary", ""))[:4000]
        source_url = article.get("link", article.get("url", ""))
        source_name = article.get("source_name", "")
        published = article.get("published", "")
        blocks.append(
            f"[article_{batch_i}]\n"
            f"Title: {title}\nSource: {source_name}\nPublished: {published}\n"
            f"URL: {source_url}\nText: {text}\n"
        )
        idx_map[f"article_{batch_i}"] = (orig_idx, h)

    # Inject correction hints from past flagged/rejected triples
    try:
        from src.graph.corrector import get_correction_hints
        correction_block = get_correction_hints()
    except Exception:
        correction_block = ""

    prompt = _BATCH_EXTRACTION_PROMPT.format(
        allowed_rels=", ".join(ALLOWED_RELATIONSHIP_TYPES),
        allowed_labels=", ".join(ALLOWED_NODE_LABELS),
        articles_block="\n".join(blocks),
        timestamp=now,
    ) + correction_block

    try:
        raw = _call_llm(prompt, label=f"batch-extract:{len(uncached)} articles")
        parsed = _parse_batch_response(raw)
        for key, (orig_idx, h) in idx_map.items():
            triples = parsed.get(key, [])
            src_url = uncached[[i for i, (oi, _, _) in enumerate(uncached) if oi == orig_idx][0]][1].get("link", "")
            title = uncached[[i for i, (oi, _, _) in enumerate(uncached) if oi == orig_idx][0]][1].get("title", "")
            validated = _parse_and_validate(json.dumps(triples), src_url, title) if isinstance(triples, list) else []
            results[orig_idx] = validated
            _cache[h] = validated
        _save_cache()
    except Exception as e:
        logger.error("Batch extraction failed: %s", e)
        for _, (orig_idx, _) in idx_map.items():
            results.setdefault(orig_idx, [])

    return results


def _parse_batch_response(raw_text: str) -> dict:
    """Parse the batch JSON response {article_0: [...], ...}."""
    cleaned = raw_text
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as e:
        logger.error("Batch JSON parse error: %s\nRaw: %s", e, raw_text[:500])
    return {}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _parse_and_validate(raw_text: str, source_url: str, title: str) -> list[dict]:
    """Parse LLM JSON output and validate each triple."""
    cleaned = raw_text
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s\nRaw: %s", e, raw_text[:500])
        if SAVE_FAILED_EXTRACTIONS:
            _save_failed(title, source_url, f"JSON parse error: {e}")
        return []

    if not isinstance(data, list):
        logger.error("Expected JSON array, got %s", type(data))
        return []

    valid = []
    for i, triple in enumerate(data):
        if not _validate_triple(triple, i):
            continue
        triple["subject"] = triple["subject"].lower().strip()
        triple["object"] = triple["object"].lower().strip()
        triple["predicate"] = triple["predicate"].upper().strip()
        triple["confidence"] = max(0.0, min(1.0, float(triple.get("confidence", 0.5))))

        if not triple.get("source_context", "").strip():
            logger.warning("Triple %d discarded: no source_context", i)
            if SAVE_FAILED_EXTRACTIONS:
                _save_failed(title, source_url, f"No source_context for triple {i}")
            continue

        valid.append(triple)

    return valid


def _validate_triple(triple: dict, index: int) -> bool:
    required = ["subject", "predicate", "object"]
    for field in required:
        if field not in triple or not triple[field]:
            logger.warning("Triple %d missing '%s' — skipped", index, field)
            return False
    return True


def _save_failed(title: str, source_url: str, error: str):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^\w\s-]", "", title)[:50].strip().replace(" ", "_")
    path = FAILED_DIR / f"{ts}_{safe_title}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "title": title,
                "source_url": source_url,
                "error": error,
                "timestamp": ts,
            }, f, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def extract_from_article(article: dict) -> list[dict]:
    """Extract triples from a single article dict (with caching + rate limit)."""
    text = article.get("text") or article.get("summary", "")
    return extract_triples(
        title=article.get("title", ""),
        text=text,
        source_url=article.get("link", article.get("url", "")),
        source_name=article.get("source_name", ""),
        published=article.get("published", ""),
    )

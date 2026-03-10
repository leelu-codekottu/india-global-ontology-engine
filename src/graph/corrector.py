"""Corrector: handles feedback loop — dispute, re-verify, deprecate, log corrections.

Self-correction flow:
1. User flags an edge via the UI  → flag_relationship() halves confidence
2. System auto-triggers LLM re-verification → re_verify_relationship()
   - LLM checks the source_context against the triple claim
   - Verdict: CONFIRMED → restore confidence, mark trusted
   - Verdict: WEAKENED  → keep reduced confidence, mark untrusted
   - Verdict: REJECTED  → deprecate the edge
3. All corrections are logged to corrections.log for audit
4. Accumulated corrections are injected into future extraction prompts
   via get_correction_hints() so the extraction LLM avoids repeat mistakes.
"""

import json
import logging
import re
from datetime import datetime, timezone

from gqlalchemy import Memgraph

from src.graph.memgraph_init import get_memgraph
from src.config import CORRECTIONS_LOG, LOGS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Re-verification prompt — the LLM acts as a fact-checker
# ---------------------------------------------------------------------------
_REVERIFY_PROMPT = """You are a fact-checking engine for a geopolitical knowledge graph.

A user has disputed the following knowledge-graph edge:
  Subject:   {subject}
  Predicate: {predicate}
  Object:    {object}

The original extraction context (evidence snippet from the source article):
  "{source_context}"

User's dispute reason: "{reason}"

TASK: Evaluate whether the triple is factually supported by the source context.

RULES:
1. CONFIRMED — The source context clearly supports this triple.
2. WEAKENED  — The source context partially supports it, but the triple overstates or is ambiguous.
3. REJECTED  — The source context does NOT support this triple, or the triple is clearly wrong.

Return ONLY a JSON object (no markdown fences):
{{
  "verdict": "CONFIRMED" | "WEAKENED" | "REJECTED",
  "explanation": "1-2 sentence justification",
  "suggested_confidence": 0.0 to 1.0
}}
"""


def flag_relationship(
    db: Memgraph,
    subject: str,
    rel_type: str,
    obj: str,
    reason: str = "",
) -> bool:
    """Flag a relationship as disputed. Reduces confidence by 50%."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = list(db.execute_and_fetch(
            f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
            f"RETURN id(r) AS rid, r.confidence AS conf, r.version AS ver;",
            {"subj": subject.lower().strip(), "obj": obj.lower().strip()},
        ))

        if not result:
            logger.warning("Relationship not found: (%s)-[%s]->(%s)", subject, rel_type, obj)
            return False

        row = result[0]
        new_conf = max(0.0, (row.get("conf") or 0.5) * 0.5)
        new_ver = (row.get("ver") or 1) + 1

        db.execute(
            f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
            f"SET r.status = 'disputed', r.confidence = $conf, "
            f"r.version = $ver, r.disputed_at = $ts, r.dispute_reason = $reason;",
            {"subj": subject.lower().strip(), "obj": obj.lower().strip(),
             "conf": new_conf, "ver": new_ver, "ts": now, "reason": reason},
        )

        _log_correction(subject, rel_type, obj, "flagged", reason, now)
        logger.info("Flagged (%s)-[%s]->(%s) as disputed, confidence → %.2f",
                     subject, rel_type, obj, new_conf)
        return True

    except Exception as e:
        logger.error("Error flagging relationship: %s", e)
        return False


def deprecate_relationship(
    db: Memgraph,
    subject: str,
    rel_type: str,
    obj: str,
) -> bool:
    """Mark a relationship as deprecated (soft delete)."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute(
            f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
            f"SET r.status = 'deprecated', r.deprecated_at = $ts;",
            {"subj": subject.lower().strip(), "obj": obj.lower().strip(), "ts": now},
        )
        _log_correction(subject, rel_type, obj, "deprecated", "", now)
        return True
    except Exception as e:
        logger.error("Error deprecating relationship: %s", e)
        return False


def _log_correction(subject, rel_type, obj, action, reason, timestamp):
    """Append correction to corrections.log for future training."""
    entry = {
        "timestamp": timestamp,
        "subject": subject,
        "predicate": rel_type,
        "object": obj,
        "action": action,
        "reason": reason,
    }
    with open(CORRECTIONS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# LLM-based self-verification
# ---------------------------------------------------------------------------

def re_verify_relationship(
    db: Memgraph,
    subject: str,
    rel_type: str,
    obj: str,
    reason: str = "",
) -> dict:
    """Ask the LLM to fact-check a disputed edge against its source context.

    Returns {"verdict": ..., "explanation": ..., "new_confidence": ...}.
    Also updates the edge in-place based on the verdict.
    """
    from src.extract.llm_extract import _call_llm

    now = datetime.now(timezone.utc).isoformat()
    subj_lower = subject.lower().strip()
    obj_lower = obj.lower().strip()

    # Fetch the edge and its source_context
    rows = list(db.execute_and_fetch(
        f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
        f"RETURN r.source_context AS ctx, r.confidence AS conf, "
        f"r.sources AS sources, r.version AS ver;",
        {"subj": subj_lower, "obj": obj_lower},
    ))

    if not rows:
        return {"verdict": "NOT_FOUND", "explanation": "Edge not found in graph"}

    row = rows[0]
    source_context = row.get("ctx") or ""

    # If no source_context on the edge, try extracting snippets from sources JSON
    if not source_context:
        try:
            srcs = json.loads(row.get("sources") or "[]")
            if isinstance(srcs, list):
                snippets = [s.get("snippet", "") for s in srcs if isinstance(s, dict)]
                source_context = " ".join(snippets).strip()
        except (json.JSONDecodeError, TypeError):
            pass

    if not source_context:
        source_context = "(no source context available)"

    prompt = _REVERIFY_PROMPT.format(
        subject=subject,
        predicate=rel_type,
        object=obj,
        source_context=source_context[:2000],
        reason=reason or "User flagged without specific reason",
    )

    try:
        raw = _call_llm(prompt, label=f"re-verify:{subject}-{rel_type}-{obj}")
        cleaned = raw
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if obj_match:
            cleaned = obj_match.group(0)
        result = json.loads(cleaned)
    except Exception as e:
        logger.error("Re-verification LLM call failed: %s", e)
        return {"verdict": "ERROR", "explanation": str(e)}

    verdict = result.get("verdict", "WEAKENED").upper()
    suggested_conf = float(result.get("suggested_confidence", 0.5))
    explanation = result.get("explanation", "")
    old_conf = row.get("conf") or 0.5
    new_ver = (row.get("ver") or 1) + 1

    # Apply verdict to the graph
    if verdict == "CONFIRMED":
        new_conf = max(old_conf, suggested_conf, 0.7)
        db.execute(
            f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
            f"SET r.status = 'active', r.confidence = $conf, r.trust = 'trusted', "
            f"r.version = $ver, r.reverified_at = $ts, r.reverify_verdict = 'CONFIRMED';",
            {"subj": subj_lower, "obj": obj_lower,
             "conf": new_conf, "ver": new_ver, "ts": now},
        )
        _log_correction(subject, rel_type, obj, "confirmed", explanation, now)
        logger.info("Re-verified CONFIRMED: (%s)-[%s]->(%s) conf=%.2f",
                     subject, rel_type, obj, new_conf)

    elif verdict == "REJECTED":
        db.execute(
            f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
            f"SET r.status = 'deprecated', r.confidence = 0.0, r.trust = 'rejected', "
            f"r.version = $ver, r.reverified_at = $ts, r.reverify_verdict = 'REJECTED';",
            {"subj": subj_lower, "obj": obj_lower,
             "ver": new_ver, "ts": now},
        )
        _log_correction(subject, rel_type, obj, "rejected", explanation, now)
        logger.info("Re-verified REJECTED: (%s)-[%s]->(%s) → deprecated",
                     subject, rel_type, obj)

    else:  # WEAKENED
        new_conf = min(suggested_conf, old_conf * 0.7)
        db.execute(
            f"MATCH (a {{name: $subj}})-[r:{rel_type}]->(b {{name: $obj}}) "
            f"SET r.status = 'active', r.confidence = $conf, r.trust = 'untrusted', "
            f"r.version = $ver, r.reverified_at = $ts, r.reverify_verdict = 'WEAKENED';",
            {"subj": subj_lower, "obj": obj_lower,
             "conf": new_conf, "ver": new_ver, "ts": now},
        )
        _log_correction(subject, rel_type, obj, "weakened", explanation, now)
        logger.info("Re-verified WEAKENED: (%s)-[%s]->(%s) conf=%.2f",
                     subject, rel_type, obj, new_conf)

    return {
        "verdict": verdict,
        "explanation": explanation,
        "old_confidence": old_conf,
        "new_confidence": new_conf if verdict != "REJECTED" else 0.0,
        "subject": subject,
        "predicate": rel_type,
        "object": obj,
    }


# ---------------------------------------------------------------------------
# Correction hints — injected into future extraction prompts
# ---------------------------------------------------------------------------

def get_correction_hints(max_hints: int = 20) -> str:
    """Read corrections.log and produce a hint block for the extraction prompt.

    This teaches the LLM what past extractions were wrong so it avoids
    repeating the same mistakes.
    """
    try:
        with open(CORRECTIONS_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return ""

    # Only use rejected/weakened entries as hints
    hints = []
    for line in reversed(lines):
        try:
            entry = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        action = entry.get("action", "")
        if action in ("rejected", "weakened", "flagged"):
            s = entry.get("subject", "")
            p = entry.get("predicate", "")
            o = entry.get("object", "")
            reason = entry.get("reason", "")
            hints.append(f"- AVOID: ({s})-[{p}]->({o}) — {reason}")
        if len(hints) >= max_hints:
            break

    if not hints:
        return ""

    return (
        "\n\nPAST CORRECTION HINTS (triples previously flagged as incorrect — "
        "do NOT re-extract these unless the article explicitly supports them):\n"
        + "\n".join(hints)
    )

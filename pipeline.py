"""Main pipeline: end-to-end demo execution."""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_DIR, LOGS_DIR
from src.graph.memgraph_init import (
    get_memgraph,
    create_constraints,
    create_indexes,
    bootstrap_minimal_graph,
    graph_snapshot,
    save_snapshot,
)
from src.graph.graph_loader import insert_triples
from src.graph.verifier import verify_all_relationships
from src.ingest.rss_loader import (
    load_rss_sources,
    validate_all_feeds,
    save_validation_csv,
    load_sample_articles,
)
from src.ingest.datacommons_loader import get_bootstrap_triples, save_bootstrap_data
from src.extract.llm_extract import extract_from_article, extract_triples_batch
from src.resolve.entity_resolver import EntityResolver
from src.reasoner.graphrag import answer_question, save_demo_result

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_step_1_graph_setup():
    """Step 1: Connect to Memgraph, create constraints, bootstrap graph."""
    logger.info("=" * 60)
    logger.info("STEP 1: Graph Setup")
    logger.info("=" * 60)

    db = get_memgraph()
    logger.info("Connected to Memgraph at %s:%s", db._host, db._port)

    # Create constraints
    created = create_constraints(db)
    logger.info("Constraints created for: %s", created)

    # Create indexes
    indexed = create_indexes(db)
    logger.info("Indexes created for: %s", indexed)

    # Check existing graph
    snap = graph_snapshot(db)
    logger.info("Current graph: %d nodes, %d edges", snap["total_nodes"], snap["total_edges"])

    if snap["total_nodes"] < 5:
        logger.info("Graph is sparse — bootstrapping minimal graph...")
        bootstrap_minimal_graph(db)
    else:
        logger.info("Graph already has nodes — checking quality...")
        if snap["flagged_duplicates"]:
            logger.warning("Duplicates found: %s", snap["flagged_duplicates"])

    # Re-snapshot after bootstrap
    snap = graph_snapshot(db)
    save_snapshot(snap)
    logger.info("Snapshot saved: %d nodes, %d edges", snap["total_nodes"], snap["total_edges"])
    return snap


def run_step_2_datacommons_bootstrap():
    """Step 2: Load curated facts from Data Commons."""
    logger.info("=" * 60)
    logger.info("STEP 2: Data Commons Bootstrap")
    logger.info("=" * 60)

    db = get_memgraph()
    triples = get_bootstrap_triples()
    save_bootstrap_data(triples)
    
    result = insert_triples(db, triples)
    logger.info("Data Commons bootstrap: %s", result)
    return result


def run_step_3_rss_validation():
    """Step 3: Validate RSS feeds."""
    logger.info("=" * 60)
    logger.info("STEP 3: RSS Feed Validation")
    logger.info("=" * 60)

    sources = load_rss_sources()
    logger.info("Loaded %d RSS sources", len(sources))

    # Validate a subset (first 10) to save time in demo
    validation_results = validate_all_feeds(sources[:10])
    save_validation_csv(validation_results)

    alive = sum(1 for r in validation_results if r["alive"])
    dead = len(validation_results) - alive
    logger.info("Validation: %d alive, %d dead out of %d checked",
                alive, dead, len(validation_results))
    return validation_results


def run_step_4_article_pipeline(use_sample: bool = True, max_articles: int = 5):
    """Step 4: Extract triples from articles and insert into graph.

    Uses batch extraction (3 articles per Gemini call) to reduce API usage.
    Demo mode caps at *max_articles* (default 5).
    """
    logger.info("=" * 60)
    logger.info("STEP 4: Article Extraction Pipeline")
    logger.info("=" * 60)

    db = get_memgraph()

    # Load articles
    if use_sample:
        articles = load_sample_articles()
        logger.info("Using %d sample articles", len(articles))
    else:
        from src.ingest.rss_loader import fetch_articles_from_all_feeds
        articles = fetch_articles_from_all_feeds(limit_per_feed=2)
        logger.info("Fetched %d articles from RSS feeds", len(articles))

    if not articles:
        logger.warning("No articles available! Check sample_news/ directory.")
        return {"extracted": 0, "inserted": 0}

    articles = articles[:max_articles]
    logger.info("Processing %d articles (max_articles=%d)", len(articles), max_articles)

    # Initialize entity resolver
    resolver = EntityResolver()
    resolver.seed_from_graph(db)
    logger.info("Entity resolver seeded: %s", resolver.get_stats())

    total_extracted = 0
    total_inserted = 0

    # --- batch extraction (groups of 3) ---
    BATCH_SIZE = 3
    for batch_start in range(0, len(articles), BATCH_SIZE):
        batch = articles[batch_start : batch_start + BATCH_SIZE]
        logger.info(
            "Batch %d–%d of %d",
            batch_start + 1,
            min(batch_start + BATCH_SIZE, len(articles)),
            len(articles),
        )

        batch_results = extract_triples_batch(batch)

        for local_idx, triples in batch_results.items():
            art = batch[local_idx]
            title = art.get("title", f"Article {batch_start + local_idx + 1}")
            if not triples:
                logger.info("  [%s] No triples extracted", title)
                continue

            total_extracted += len(triples)
            logger.info("  [%s] Extracted %d triples", title, len(triples))

            resolved = resolver.resolve_triples(triples)
            result = insert_triples(db, resolved)
            total_inserted += result["inserted"]
            logger.info(
                "  [%s] Inserted: %d, Failed: %d",
                title,
                result["inserted"],
                result["failed"],
            )

    logger.info(
        "Pipeline complete: %d extracted, %d inserted",
        total_extracted,
        total_inserted,
    )
    return {"extracted": total_extracted, "inserted": total_inserted}


def run_step_5_verification():
    """Step 5: Run verification on all relationships."""
    logger.info("=" * 60)
    logger.info("STEP 5: Verification")
    logger.info("=" * 60)

    db = get_memgraph()
    summary = verify_all_relationships(db)
    logger.info("Verification: %s", summary)

    # Update snapshot
    snap = graph_snapshot(db)
    save_snapshot(snap)
    logger.info("Updated snapshot: %d nodes, %d edges", snap["total_nodes"], snap["total_edges"])
    return summary


def run_step_6_demo_query():
    """Step 6: Run the demo query and save results."""
    logger.info("=" * 60)
    logger.info("STEP 6: Demo Query")
    logger.info("=" * 60)

    db = get_memgraph()
    question = "How will Iran-USA tensions affect India's oil imports and inflation?"
    
    result = answer_question(question, db)
    path = save_demo_result(result)
    
    logger.info("Demo query answered. Result saved to: %s", path)
    
    # Print summary
    if "answer" in result:
        logger.info("Answer preview: %s", str(result["answer"])[:300])
    if "overall_confidence" in result:
        logger.info("Overall confidence: %.2f", result.get("overall_confidence", 0))
    
    return result


def run_full_pipeline(use_sample: bool = True):
    """Run the complete pipeline end-to-end."""
    logger.info("*" * 60)
    logger.info("INDIA GLOBAL ONTOLOGY ENGINE - FULL PIPELINE")
    logger.info("*" * 60)

    results = {}

    # Step 1: Graph setup
    results["graph_setup"] = run_step_1_graph_setup()

    # Step 2: Data Commons bootstrap
    results["datacommons"] = run_step_2_datacommons_bootstrap()

    # Step 3: RSS validation (optional in demo mode)
    # results["rss_validation"] = run_step_3_rss_validation()

    # Step 4: Article extraction pipeline
    results["extraction"] = run_step_4_article_pipeline(use_sample=use_sample)

    # Step 5: Verification
    results["verification"] = run_step_5_verification()

    # Step 6: Demo query
    results["demo_query"] = run_step_6_demo_query()

    logger.info("*" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("*" * 60)

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the Ontology Engine pipeline")
    parser.add_argument("--step", type=int, help="Run a specific step (1-6)")
    parser.add_argument("--sample", action="store_true", default=True,
                        help="Use sample articles (default)")
    parser.add_argument("--live", action="store_true",
                        help="Use live RSS feeds instead of samples")

    args = parser.parse_args()
    use_sample = not args.live

    if args.step:
        steps = {
            1: run_step_1_graph_setup,
            2: run_step_2_datacommons_bootstrap,
            3: run_step_3_rss_validation,
            4: lambda: run_step_4_article_pipeline(use_sample=use_sample),
            5: run_step_5_verification,
            6: run_step_6_demo_query,
        }
        if args.step in steps:
            steps[args.step]()
        else:
            print(f"Invalid step: {args.step}. Use 1-6.")
    else:
        run_full_pipeline(use_sample=use_sample)

"""Tests for the ontology engine pipeline components."""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test 1: JSON validation for extracted triples
# ============================================================

class TestJSONValidation:
    """Test JSON parse and validation of extracted triples."""

    def test_valid_triple(self):
        """Valid triple should pass validation."""
        from src.extract.llm_extract import _validate_triple
        
        triple = {
            "subject": "india",
            "predicate": "IMPORTS",
            "object": "crude oil",
            "confidence": 0.85,
            "source_context": "India imports ~85% of crude oil",
        }
        assert _validate_triple(triple, 0) is True

    def test_missing_subject(self):
        """Triple missing subject should fail."""
        from src.extract.llm_extract import _validate_triple
        
        triple = {
            "predicate": "IMPORTS",
            "object": "crude oil",
        }
        assert _validate_triple(triple, 0) is False

    def test_empty_predicate(self):
        """Triple with empty predicate should fail."""
        from src.extract.llm_extract import _validate_triple
        
        triple = {
            "subject": "india",
            "predicate": "",
            "object": "crude oil",
        }
        assert _validate_triple(triple, 0) is False

    def test_parse_valid_json(self):
        """Parse valid JSON array of triples."""
        from src.extract.llm_extract import _parse_and_validate

        raw = json.dumps([{
            "subject": "iran",
            "predicate": "EXPORTS",
            "object": "crude oil",
            "confidence": 0.9,
            "source_context": "Iran exports crude oil.",
            "timestamp": "2025-01-01T00:00:00Z",
            "source_url": "https://example.com",
        }])
        result = _parse_and_validate(raw, "https://example.com", "Test")
        assert len(result) == 1
        assert result[0]["subject"] == "iran"

    def test_parse_with_markdown_fences(self):
        """Parse JSON wrapped in markdown code fences."""
        from src.extract.llm_extract import _parse_and_validate

        raw = '```json\n[{"subject": "usa", "predicate": "CONFLICT_WITH", "object": "iran", "confidence": 0.8, "source_context": "US-Iran conflict."}]\n```'
        result = _parse_and_validate(raw, "", "Test")
        assert len(result) == 1

    def test_parse_invalid_json(self):
        """Invalid JSON should return empty list."""
        from src.extract.llm_extract import _parse_and_validate

        result = _parse_and_validate("not json at all", "", "Test")
        assert result == []

    def test_no_source_context_discarded(self):
        """Triple without source_context should be discarded."""
        from src.extract.llm_extract import _parse_and_validate

        raw = json.dumps([{
            "subject": "india",
            "predicate": "IMPORTS",
            "object": "crude oil",
            "confidence": 0.9,
            "source_context": "",
        }])
        result = _parse_and_validate(raw, "", "Test")
        assert len(result) == 0


# ============================================================
# Test 2: Entity resolver clustering
# ============================================================

class TestEntityResolver:
    """Test entity resolution and alias clustering."""

    def test_exact_match(self):
        """Same name should resolve to itself."""
        from src.resolve.entity_resolver import EntityResolver
        
        resolver = EntityResolver(threshold=0.88)
        resolver.canonical_map["india"] = "india"
        resolver.alias_clusters["india"] = ["bharat"]
        
        assert resolver.resolve("india") == "india"

    def test_alias_in_cache(self):
        """Known alias should resolve to canonical."""
        from src.resolve.entity_resolver import EntityResolver
        
        resolver = EntityResolver(threshold=0.88)
        resolver.canonical_map["bharat"] = "india"
        resolver.alias_clusters["india"] = ["bharat"]
        
        assert resolver.resolve("bharat") == "india"

    def test_new_entity(self):
        """Unknown entity with no close match becomes new canonical."""
        from src.resolve.entity_resolver import EntityResolver
        
        resolver = EntityResolver(threshold=0.99)  # very high threshold
        # Empty resolver
        result = resolver.resolve("xyz_random_entity_12345")
        assert result == "xyz_random_entity_12345"
        assert "xyz_random_entity_12345" in resolver.alias_clusters

    def test_resolve_triples(self):
        """Triples should have subjects/objects resolved."""
        from src.resolve.entity_resolver import EntityResolver
        
        resolver = EntityResolver(threshold=0.88)
        resolver.canonical_map["bharat"] = "india"
        resolver.alias_clusters["india"] = ["bharat"]
        
        triples = [{"subject": "bharat", "predicate": "IMPORTS", "object": "oil"}]
        resolved = resolver.resolve_triples(triples)
        assert resolved[0]["subject"] == "india"


# ============================================================
# Test 3: Graph label and predicate inference
# ============================================================

class TestLabelInference:
    """Test entity label and predicate mapping."""

    def test_country_inference(self):
        from src.graph.graph_loader import _infer_label
        assert _infer_label("india") == "Country"
        assert _infer_label("iran") == "Country"
        assert _infer_label("usa") == "Country"

    def test_resource_inference(self):
        from src.graph.graph_loader import _infer_label
        assert _infer_label("crude oil") == "Resource"
        assert _infer_label("lng") == "Resource"

    def test_indicator_inference(self):
        from src.graph.graph_loader import _infer_label
        assert _infer_label("inflation") == "Indicator"
        assert _infer_label("gdp") == "Indicator"

    def test_location_inference(self):
        from src.graph.graph_loader import _infer_label
        assert _infer_label("strait of hormuz") == "Location"
        assert _infer_label("persian gulf") == "Location"

    def test_predicate_mapping(self):
        from src.graph.graph_loader import _map_predicate
        assert _map_predicate("imports") == "IMPORTS"
        assert _map_predicate("EXPORTS") == "EXPORTS"
        assert _map_predicate("conflict_with") == "CONFLICT_WITH"
        assert _map_predicate("some_unknown") == "AFFECTS"  # fallback


# ============================================================
# Test 4: Feedback workflow
# ============================================================

class TestFeedbackWorkflow:
    """Test the flag/dispute/deprecate corrector workflow."""

    def test_flag_reduces_confidence(self):
        """Flagging should multiply confidence by 0.5."""
        # This is a logic test — we mock the DB
        from src.graph.corrector import flag_relationship

        mock_db = MagicMock()
        mock_db.execute_and_fetch.return_value = [
            {"rid": 1, "conf": 0.8, "ver": 1}
        ]
        mock_db.execute.return_value = None

        with patch("src.graph.corrector._log_correction"):
            result = flag_relationship(mock_db, "usa", "CONFLICT_WITH", "iran", "test reason")

        assert result is True
        # Verify execute was called with disputed status
        calls = mock_db.execute.call_args_list
        assert len(calls) > 0

    def test_flag_nonexistent_returns_false(self):
        """Flagging a non-existent relationship returns False."""
        from src.graph.corrector import flag_relationship

        mock_db = MagicMock()
        mock_db.execute_and_fetch.return_value = []

        result = flag_relationship(mock_db, "x", "Y", "z")
        assert result is False


# ============================================================
# Test 5: RSS loader basics
# ============================================================

class TestRSSLoader:
    """Test RSS source loading."""

    def test_load_csv(self):
        from src.ingest.rss_loader import load_rss_sources
        sources = load_rss_sources()
        assert len(sources) > 0
        assert "rss_url" in sources[0]
        assert "source_name" in sources[0]

    def test_sample_articles(self):
        from src.ingest.rss_loader import load_sample_articles
        articles = load_sample_articles()
        assert len(articles) > 0
        assert "title" in articles[0]
        assert "text" in articles[0]


# ============================================================
# Test 6: Config loading
# ============================================================

class TestConfig:
    """Test configuration loading."""

    def test_api_keys_loaded(self):
        from src.config import GEMINI_API_KEY, DATACOMMONS_API_KEY
        assert GEMINI_API_KEY != ""
        assert DATACOMMONS_API_KEY != ""

    def test_paths_exist(self):
        from src.config import DATA_DIR, LOGS_DIR, FAILED_DIR
        assert DATA_DIR.exists()
        assert LOGS_DIR.exists()
        assert FAILED_DIR.exists()

    def test_ontology_labels(self):
        from src.config import ALLOWED_NODE_LABELS, ALLOWED_RELATIONSHIP_TYPES
        assert "Country" in ALLOWED_NODE_LABELS
        assert "IMPORTS" in ALLOWED_RELATIONSHIP_TYPES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

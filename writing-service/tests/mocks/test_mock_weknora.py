"""Tests for the mock WeKnora implementation."""

import pytest

from app.schemas.retrieval import Query
from tests.mocks.mock_weknora import MockWeKnora, get_mock_weknora, reset_mock_weknora


class TestMockWeKnora:
    """Tests for MockWeKnora."""

    def setup_method(self):
        """Reset mock before each test."""
        reset_mock_weknora()

    def test_search_by_query_id(self):
        """Test direct query_id lookup."""
        mock = get_mock_weknora()
        query = Query(
            query_id="q_001",
            question="Any question",
            section_assignments=["sec_01"],
        )
        results = mock.search(query)
        assert results.query_id == "q_001"
        assert len(results.results) > 0

    def test_search_by_keywords_corporate(self):
        """Test keyword-based search for corporate terms."""
        mock = get_mock_weknora()
        query = Query(
            query_id="q_test",
            question="What is the corporate structure and ownership?",
            section_assignments=["sec_01"],
        )
        results = mock.search(query)
        assert len(results.results) > 0
        # Should find corporate registry and ownership documents
        doc_types = {r.doc_type for r in results.results}
        assert "corporate_registry" in doc_types or "ownership_filing" in doc_types

    def test_search_by_keywords_regulatory(self):
        """Test keyword-based search for regulatory terms."""
        mock = get_mock_weknora()
        query = Query(
            query_id="q_test",
            question="What is the FINMA license status?",
            section_assignments=["sec_02"],
        )
        results = mock.search(query)
        assert len(results.results) > 0

    def test_search_by_keywords_risk(self):
        """Test keyword-based search for risk terms."""
        mock = get_mock_weknora()
        query = Query(
            query_id="q_test",
            question="What is the risk assessment?",
            section_assignments=["sec_03"],
        )
        results = mock.search(query)
        assert len(results.results) > 0

    def test_search_no_results(self):
        """Test search with no matching keywords."""
        mock = get_mock_weknora()
        query = Query(
            query_id="q_test",
            question="Something completely unrelated xyz123",
            section_assignments=["sec_01"],
        )
        results = mock.search(query)
        assert len(results.results) == 0

    def test_execute_multiple_queries(self):
        """Test executing multiple queries at once."""
        mock = get_mock_weknora()
        queries = [
            Query(
                query_id="q_001",
                question="Corporate structure",
                section_assignments=["sec_01"],
            ),
            Query(
                query_id="q_002",
                question="Regulatory compliance",
                section_assignments=["sec_02"],
            ),
        ]
        results = mock.execute_queries(queries)
        assert len(results) == 2
        assert all(r.query_id in ["q_001", "q_002"] for r in results)

    def test_deduplication_in_keyword_search(self):
        """Test that keyword search doesn't return duplicate documents."""
        mock = get_mock_weknora()
        # Use multiple overlapping keywords
        query = Query(
            query_id="q_test",
            question="corporate structure and ownership and registration",
            section_assignments=["sec_01"],
        )
        results = mock.search(query)
        doc_ids = [r.doc_id for r in results.results]
        assert len(doc_ids) == len(set(doc_ids)), "Duplicate doc_ids found"

    def test_singleton_behavior(self):
        """Test that get_mock_weknora returns singleton."""
        mock1 = get_mock_weknora()
        mock2 = get_mock_weknora()
        assert mock1 is mock2

        reset_mock_weknora()
        mock3 = get_mock_weknora()
        assert mock1 is not mock3

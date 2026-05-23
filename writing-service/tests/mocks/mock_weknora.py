"""Mock WeKnora knowledge base for testing."""

import json
from pathlib import Path
from typing import Any

from app.schemas.retrieval import Query, QueryResults, QueryResultItem


class MockWeKnora:
    """
    Mock implementation of WeKnora knowledge base.

    Uses keyword matching to return relevant results from fixtures.
    """

    def __init__(self, fixtures_path: Path | None = None):
        """Initialize with optional custom fixtures path."""
        if fixtures_path is None:
            fixtures_path = Path(__file__).parent.parent / "fixtures"
        self.fixtures_path = fixtures_path
        self._query_results = self._load_query_results()
        self._keyword_index = self._build_keyword_index()

    def _load_query_results(self) -> dict[str, list[dict[str, Any]]]:
        """Load query results from fixture file."""
        results_file = self.fixtures_path / "sample_query_results.json"
        if not results_file.exists():
            return {}

        with open(results_file) as f:
            data = json.load(f)

        # Index by query_id
        return {qr["query_id"]: qr["results"] for qr in data.get("query_results", [])}

    def _build_keyword_index(self) -> dict[str, list[dict[str, Any]]]:
        """Build keyword index for fuzzy matching."""
        index: dict[str, list[dict[str, Any]]] = {}

        # Keywords mapped to query IDs
        keyword_mapping = {
            "corporate": "q_001",
            "structure": "q_001",
            "ownership": "q_001",
            "registration": "q_001",
            "ubo": "q_001",
            "beneficial": "q_001",
            "board": "q_001",
            "directors": "q_001",
            "regulatory": "q_002",
            "compliance": "q_002",
            "finma": "q_002",
            "license": "q_002",
            "sanctions": "q_002",
            "ofac": "q_002",
            "risk": "q_003",
            "assessment": "q_003",
            "monitoring": "q_003",
            "business": "q_004",
            "activities": "q_004",
            "operations": "q_004",
            "revenue": "q_004",
            "services": "q_004",
            "pending": "q_005",
            "investigation": "q_005",
        }

        for keyword, query_id in keyword_mapping.items():
            if query_id in self._query_results:
                index[keyword] = self._query_results[query_id]

        return index

    def search(self, query: Query) -> QueryResults:
        """
        Execute a search query against the mock knowledge base.

        Uses keyword overlap to find relevant results.
        """
        # First try direct query_id match
        if query.query_id in self._query_results:
            results = self._query_results[query.query_id]
            return QueryResults(
                query_id=query.query_id,
                results=[QueryResultItem(**r) for r in results],
                total_found=len(results),
                truncated=False,
            )

        # Fall back to keyword matching
        question_lower = query.question.lower()
        matched_results: list[dict[str, Any]] = []
        seen_doc_ids: set[str] = set()

        for keyword, results in self._keyword_index.items():
            if keyword in question_lower:
                for result in results:
                    if result["doc_id"] not in seen_doc_ids:
                        matched_results.append(result)
                        seen_doc_ids.add(result["doc_id"])

        return QueryResults(
            query_id=query.query_id,
            results=[QueryResultItem(**r) for r in matched_results],
            total_found=len(matched_results),
            truncated=False,
        )

    def execute_queries(self, queries: list[Query]) -> list[QueryResults]:
        """Execute multiple queries."""
        return [self.search(q) for q in queries]


# Module-level singleton for convenience
_mock_weknora: MockWeKnora | None = None


def get_mock_weknora() -> MockWeKnora:
    """Get or create the mock WeKnora singleton."""
    global _mock_weknora
    if _mock_weknora is None:
        _mock_weknora = MockWeKnora()
    return _mock_weknora


def reset_mock_weknora() -> None:
    """Reset the singleton (for testing)."""
    global _mock_weknora
    _mock_weknora = None

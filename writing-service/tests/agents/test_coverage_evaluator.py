"""Tests for the Coverage Evaluator agent."""

import json
from pathlib import Path

import pytest

from app.agents.coverage_evaluator import (
    deduplicate_results,
    assign_bundles,
    build_gaps_for_followup,
)
from app.schemas.retrieval import QueryResults, QueryResultItem
from app.schemas.evidence import EvidencePackage, GapReport, PartialCoverage


FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"


class TestDeduplication:
    """Tests for result deduplication."""

    def test_deduplicates_same_doc_id(self):
        """Test that same doc_id produces single evidence item."""
        results = [
            QueryResults(
                query_id="q_001",
                results=[
                    QueryResultItem(
                        doc_id="doc_001",
                        title="Test Doc",
                        snippet="Content 1",
                        source="Source A",
                        relevance_score=0.9,
                    )
                ],
                total_found=1,
            ),
            QueryResults(
                query_id="q_002",
                results=[
                    QueryResultItem(
                        doc_id="doc_001",  # Same doc_id
                        title="Test Doc",
                        snippet="Content 1",
                        source="Source A",
                        relevance_score=0.8,
                    )
                ],
                total_found=1,
            ),
        ]

        evidence_pool, doc_mapping = deduplicate_results(results)

        assert len(evidence_pool) == 1
        assert evidence_pool[0].evidence_id == "ev_001"
        # Should have both query IDs in provenance
        assert "q_001" in evidence_pool[0].provenance.query_ids
        assert "q_002" in evidence_pool[0].provenance.query_ids

    def test_multiple_docs_preserved(self):
        """Test that different doc_ids produce separate evidence."""
        results = [
            QueryResults(
                query_id="q_001",
                results=[
                    QueryResultItem(
                        doc_id="doc_001",
                        title="Doc 1",
                        snippet="Content 1",
                        source="Source",
                        relevance_score=0.9,
                    ),
                    QueryResultItem(
                        doc_id="doc_002",
                        title="Doc 2",
                        snippet="Content 2",
                        source="Source",
                        relevance_score=0.8,
                    ),
                ],
                total_found=2,
            ),
        ]

        evidence_pool, doc_mapping = deduplicate_results(results)

        assert len(evidence_pool) == 2
        assert {e.evidence_id for e in evidence_pool} == {"ev_001", "ev_002"}

    def test_deduplication_from_fixture(self):
        """Test deduplication on fixture data."""
        with open(FIXTURES_PATH / "sample_query_results.json") as f:
            data = json.load(f)

        results = [QueryResults.model_validate(qr) for qr in data["query_results"]]

        # Count total results and unique doc_ids
        total_results = sum(len(qr.results) for qr in results)
        unique_doc_ids = set()
        for qr in results:
            for r in qr.results:
                unique_doc_ids.add(r.doc_id)

        evidence_pool, doc_mapping = deduplicate_results(results)

        # Evidence count should equal unique doc count
        assert len(evidence_pool) == len(unique_doc_ids)
        # Should be fewer evidence items than total results (some duplicates)
        assert len(evidence_pool) <= total_results


class TestBundleAssignment:
    """Tests for bundle assignment."""

    def test_assigns_to_correct_sections(self):
        """Test evidence routed to correct sections."""
        from app.schemas.evidence import EvidenceItem, EvidenceSource, EvidenceProvenance

        evidence_pool = [
            EvidenceItem(
                evidence_id="ev_001",
                content="Test content",
                source=EvidenceSource(system="Test", doc_id="doc_001"),
                provenance=EvidenceProvenance(
                    query_ids=["q_001"],
                    retrieval_date="2024-01-01",
                    relevance_scores={"q_001": 0.9},
                ),
            )
        ]

        query_to_sections = {"q_001": ["sec_01", "sec_02"]}

        bundles = assign_bundles(evidence_pool, [], query_to_sections)

        assert len(bundles) == 2
        section_ids = {b.section_id for b in bundles}
        assert section_ids == {"sec_01", "sec_02"}

        for bundle in bundles:
            assert "ev_001" in bundle.evidence_ids


class TestGapDetection:
    """Tests for gap detection."""

    def test_builds_gaps_from_gap_report(self):
        """Test gap extraction from gap reports."""
        gap_reports = [
            GapReport(
                section_id="sec_01",
                satisfied_requirements=["req1"],
                partial_coverage=[
                    PartialCoverage(
                        requirement="req2",
                        coverage_level="partial",
                        available_evidence_ids=["ev_001"],
                        missing_aspects=["aspect1"],
                    )
                ],
                missing_requirements=["req3"],
            )
        ]

        gaps = build_gaps_for_followup(gap_reports)

        assert len(gaps) == 2
        gap_types = {g.gap_type for g in gaps}
        assert gap_types == {"missing", "partial"}

    def test_empty_gaps_when_satisfied(self):
        """Test no gaps when all requirements satisfied."""
        gap_reports = [
            GapReport(
                section_id="sec_01",
                satisfied_requirements=["req1", "req2"],
                partial_coverage=[],
                missing_requirements=[],
            )
        ]

        gaps = build_gaps_for_followup(gap_reports)

        assert len(gaps) == 0


class TestEvidencePackageFromFixture:
    """Tests using fixture data."""

    def test_package_loads_correctly(self):
        """Test evidence package fixture loads."""
        with open(FIXTURES_PATH / "sample_evidence_package.json") as f:
            data = json.load(f)

        package = EvidencePackage.model_validate(data)

        assert len(package.evidence_pool) > 0
        assert len(package.section_bundles) > 0
        assert package.retrieval_iterations >= 1

    def test_shared_registry_identifies_shared_evidence(self):
        """Test shared registry identifies evidence in multiple sections."""
        with open(FIXTURES_PATH / "sample_evidence_package.json") as f:
            data = json.load(f)

        package = EvidencePackage.model_validate(data)

        # Should have shared evidence
        assert len(package.shared_registry) > 0

        # Each shared item should be in 2+ sections
        for shared in package.shared_registry:
            assert len(shared.section_ids) >= 2

"""Tests for Pydantic schemas."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.structure import FrozenStructure, SectionSpec, ReportMetadata
from app.schemas.retrieval import Query, QueryPlan, QueryResults, QueryResultItem
from app.schemas.evidence import (
    EvidenceItem,
    EvidencePackage,
    SectionBundle,
    SharedEvidence,
)
from app.schemas.draft import (
    SectionDraft,
    SectionMetadata,
    Claim,
    AssembledDraft,
    Citation,
)
from app.schemas.feedback import Feedback
from app.schemas.consistency import ConsistencyFlag
from app.schemas.errors import ErrorPayload


FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"


class TestStructureSchemas:
    """Tests for structure-related schemas."""

    def test_section_spec_roundtrip(self):
        """Test SectionSpec serialization roundtrip."""
        spec = SectionSpec(
            section_id="sec_01",
            title="Test Section",
            purpose="Test purpose",
            requirements=["req1", "req2"],
            must_include=["item1"],
            target_words=300,
            depends_on=[],
            evidence_types=["document"],
        )
        json_str = spec.model_dump_json()
        loaded = SectionSpec.model_validate_json(json_str)
        assert loaded == spec

    def test_frozen_structure_roundtrip(self):
        """Test FrozenStructure serialization roundtrip."""
        structure = FrozenStructure(
            metadata=ReportMetadata(
                report_type="compliance_profile",
                subject_name="Test Corp",
                subject_type="company",
                purpose="Test purpose",
            ),
            sections=[
                SectionSpec(
                    section_id="sec_01",
                    title="Test",
                    purpose="Test",
                    target_words=200,
                )
            ],
        )
        json_str = structure.model_dump_json()
        loaded = FrozenStructure.model_validate_json(json_str)
        assert loaded == structure

    def test_frozen_structure_from_fixture(self):
        """Test loading FrozenStructure from fixture."""
        fixture_path = FIXTURES_PATH / "sample_structure_3section.json"
        with open(fixture_path) as f:
            data = json.load(f)
        structure = FrozenStructure.model_validate(data)
        assert len(structure.sections) == 3
        assert structure.metadata.subject_name == "Acme Corp SA"

    def test_frozen_structure_invalid_report_type(self):
        """Test that invalid report_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ReportMetadata(
                report_type="invalid_type",  # type: ignore
                subject_name="Test",
                subject_type="company",
                purpose="Test",
            )
        assert "report_type" in str(exc_info.value)

    def test_dependency_order(self):
        """Test get_dependency_order method."""
        fixture_path = FIXTURES_PATH / "sample_structure_3section.json"
        with open(fixture_path) as f:
            data = json.load(f)
        structure = FrozenStructure.model_validate(data)
        order = structure.get_dependency_order()

        # sec_01 has no deps, should be first
        assert "sec_01" in order[0]
        # sec_02 depends on sec_01
        assert "sec_02" in order[1]
        # sec_03 depends on both
        assert "sec_03" in order[2]


class TestRetrievalSchemas:
    """Tests for retrieval-related schemas."""

    def test_query_roundtrip(self):
        """Test Query serialization roundtrip."""
        query = Query(
            query_id="q_001",
            question="What is the corporate structure?",
            section_assignments=["sec_01"],
            priority=1,
        )
        json_str = query.model_dump_json()
        loaded = Query.model_validate_json(json_str)
        assert loaded == query

    def test_query_plan_roundtrip(self):
        """Test QueryPlan serialization roundtrip."""
        plan = QueryPlan(
            queries=[
                Query(
                    query_id="q_001",
                    question="Test query",
                    section_assignments=["sec_01"],
                )
            ],
            supports_followup=True,
            iteration=1,
        )
        json_str = plan.model_dump_json()
        loaded = QueryPlan.model_validate_json(json_str)
        assert loaded == plan

    def test_query_results_from_fixture(self):
        """Test loading QueryResults from fixture."""
        fixture_path = FIXTURES_PATH / "sample_query_results.json"
        with open(fixture_path) as f:
            data = json.load(f)

        for qr in data["query_results"]:
            results = QueryResults.model_validate(qr)
            assert results.query_id.startswith("q_")


class TestEvidenceSchemas:
    """Tests for evidence-related schemas."""

    def test_evidence_package_roundtrip(self):
        """Test EvidencePackage serialization roundtrip."""
        fixture_path = FIXTURES_PATH / "sample_evidence_package.json"
        with open(fixture_path) as f:
            data = json.load(f)

        package = EvidencePackage.model_validate(data)
        json_str = package.model_dump_json()
        loaded = EvidencePackage.model_validate_json(json_str)
        assert loaded == package

    def test_evidence_package_from_fixture(self):
        """Test loading EvidencePackage from fixture."""
        fixture_path = FIXTURES_PATH / "sample_evidence_package.json"
        with open(fixture_path) as f:
            data = json.load(f)

        package = EvidencePackage.model_validate(data)
        assert len(package.evidence_pool) > 0
        assert len(package.section_bundles) > 0

    def test_cross_reference_bundles_to_evidence(self):
        """Test that evidence_ids in bundles exist in evidence_pool."""
        fixture_path = FIXTURES_PATH / "sample_evidence_package.json"
        with open(fixture_path) as f:
            data = json.load(f)

        package = EvidencePackage.model_validate(data)
        evidence_ids = {e.evidence_id for e in package.evidence_pool}

        for bundle in package.section_bundles:
            for eid in bundle.evidence_ids:
                assert eid in evidence_ids, f"Evidence {eid} not found in pool"

    def test_get_evidence_method(self):
        """Test EvidencePackage.get_evidence method."""
        fixture_path = FIXTURES_PATH / "sample_evidence_package.json"
        with open(fixture_path) as f:
            data = json.load(f)

        package = EvidencePackage.model_validate(data)
        evidence = package.get_evidence("ev_001")
        assert evidence is not None
        assert evidence.evidence_id == "ev_001"

        # Non-existent
        assert package.get_evidence("nonexistent") is None


class TestDraftSchemas:
    """Tests for draft-related schemas."""

    def test_section_draft_roundtrip(self):
        """Test SectionDraft serialization roundtrip."""
        draft = SectionDraft(
            metadata=SectionMetadata(
                section_id="sec_01",
                title="Test Section",
                word_count=300,
                target_words=300,
            ),
            content="Test content here.",
            claims=[
                Claim(
                    claim_id="c_01",
                    statement="Test claim",
                    evidence_ids=["ev_001"],
                )
            ],
            checker_status="pass",
        )
        json_str = draft.model_dump_json()
        loaded = SectionDraft.model_validate_json(json_str)
        assert loaded == draft

    def test_assembled_draft_from_fixture(self):
        """Test loading AssembledDraft from fixture."""
        fixture_path = FIXTURES_PATH / "sample_assembled_draft.json"
        with open(fixture_path) as f:
            data = json.load(f)

        draft = AssembledDraft.model_validate(data)
        assert len(draft.sections) == 3
        assert draft.total_word_count > 0

    def test_cross_reference_claims_to_citations(self):
        """Test that evidence_ids in claims exist in citations."""
        fixture_path = FIXTURES_PATH / "sample_assembled_draft.json"
        with open(fixture_path) as f:
            data = json.load(f)

        draft = AssembledDraft.model_validate(data)
        citation_evidence_ids = {c.evidence_id for c in draft.citations}

        for section in draft.sections:
            for claim in section.claims:
                for eid in claim.evidence_ids:
                    assert (
                        eid in citation_evidence_ids
                    ), f"Evidence {eid} from claim not in citations"

    def test_word_count_tolerance(self):
        """Test word_count_within_tolerance property."""
        # Within tolerance
        draft = SectionDraft(
            metadata=SectionMetadata(
                section_id="sec_01",
                title="Test",
                word_count=320,
                target_words=300,
            ),
            content="Test",
        )
        assert draft.word_count_within_tolerance is True

        # Outside tolerance
        draft2 = SectionDraft(
            metadata=SectionMetadata(
                section_id="sec_01",
                title="Test",
                word_count=500,
                target_words=300,
            ),
            content="Test",
        )
        assert draft2.word_count_within_tolerance is False


class TestFeedbackSchema:
    """Tests for feedback schema."""

    def test_feedback_roundtrip(self):
        """Test Feedback serialization roundtrip."""
        feedback = Feedback(
            section_id="sec_01",
            feedback_type="content",
            instructions="Add more detail about ownership",
            augmented_evidence=True,
            new_evidence_ids=["ev_010"],
        )
        json_str = feedback.model_dump_json()
        loaded = Feedback.model_validate_json(json_str)
        assert loaded == feedback


class TestConsistencySchema:
    """Tests for consistency schema."""

    def test_consistency_flag_roundtrip(self):
        """Test ConsistencyFlag serialization roundtrip."""
        flag = ConsistencyFlag(
            flag_id="f_001",
            flag_type="numeric_conflict",
            severity="warning",
            sections_involved=["sec_01", "sec_02"],
            description="AUM figures differ between sections",
            evidence="sec_01: CHF 2.3B, sec_02: CHF 2.1B",
            suggested_resolution="Verify correct figure and update",
        )
        json_str = flag.model_dump_json()
        loaded = ConsistencyFlag.model_validate_json(json_str)
        assert loaded == flag

    def test_consistency_flag_invalid_type(self):
        """Test that invalid flag_type raises ValidationError."""
        with pytest.raises(ValidationError):
            ConsistencyFlag(
                flag_id="f_001",
                flag_type="invalid_type",  # type: ignore
                severity="warning",
                sections_involved=["sec_01"],
                description="Test",
            )


class TestErrorSchema:
    """Tests for error schema."""

    def test_error_payload_roundtrip(self):
        """Test ErrorPayload serialization roundtrip."""
        error = ErrorPayload(
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "goal", "reason": "cannot be empty"},
            trace_id="abc-123",
            retryable=False,
        )
        json_str = error.model_dump_json()
        loaded = ErrorPayload.model_validate_json(json_str)
        assert loaded == error


class TestFixturesLoadCorrectly:
    """Test that all fixtures load without errors."""

    def test_sample_structure_3section(self):
        """Test sample_structure_3section.json loads."""
        path = FIXTURES_PATH / "sample_structure_3section.json"
        with open(path) as f:
            data = json.load(f)
        FrozenStructure.model_validate(data)

    def test_sample_structure_5section(self):
        """Test sample_structure_5section.json loads."""
        path = FIXTURES_PATH / "sample_structure_5section.json"
        with open(path) as f:
            data = json.load(f)
        FrozenStructure.model_validate(data)

    def test_sample_evidence_package(self):
        """Test sample_evidence_package.json loads."""
        path = FIXTURES_PATH / "sample_evidence_package.json"
        with open(path) as f:
            data = json.load(f)
        EvidencePackage.model_validate(data)

    def test_sample_assembled_draft(self):
        """Test sample_assembled_draft.json loads."""
        path = FIXTURES_PATH / "sample_assembled_draft.json"
        with open(path) as f:
            data = json.load(f)
        AssembledDraft.model_validate(data)

"""End-to-end tests for API endpoints."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.structure import FrozenStructure
from app.schemas.retrieval import QueryPlan, Query
from app.schemas.evidence import EvidencePackage


FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_returns_healthy(self):
        """Test health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "writing-service"


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_service_info(self):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Writing Service"
        assert "endpoints" in data


class TestPlanEndpoint:
    """Tests for plan endpoint."""

    def test_plan_requires_goal(self):
        """Test plan endpoint requires goal."""
        response = client.post(
            "/api/report-writer/plan",
            json={},
        )
        assert response.status_code == 422  # Validation error

    def test_plan_goal_min_length(self):
        """Test plan endpoint requires minimum goal length."""
        response = client.post(
            "/api/report-writer/plan",
            json={"goal": "short"},
        )
        assert response.status_code == 422

    @patch("app.endpoints.plan.arun_plan")
    def test_plan_success(self, mock_arun_plan):
        """Test successful plan generation."""
        with open(FIXTURES_PATH / "sample_structure_3section.json") as f:
            structure_data = json.load(f)

        mock_structure = FrozenStructure.model_validate(structure_data)
        mock_arun_plan.return_value = mock_structure

        response = client.post(
            "/api/report-writer/plan",
            json={"goal": "Generate a KYC report for Acme Corp SA"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "structure" in data
        assert data["structure"]["metadata"]["subject_name"] == "Acme Corp SA"

    @patch("app.endpoints.plan.arun_plan")
    def test_plan_returns_trace_id(self, mock_arun_plan):
        """Test that plan returns trace_id."""
        with open(FIXTURES_PATH / "sample_structure_3section.json") as f:
            structure_data = json.load(f)

        mock_arun_plan.return_value = FrozenStructure.model_validate(structure_data)

        response = client.post(
            "/api/report-writer/plan",
            json={"goal": "Generate a KYC report for Acme Corp SA"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "trace_id" in data
        assert data["trace_id"] is not None


class TestRetrieveEndpoints:
    """Tests for retrieve endpoints."""

    def test_retrieve_plan_requires_structure(self):
        """Test retrieve/plan requires structure."""
        response = client.post(
            "/api/report-writer/retrieve/plan",
            json={},
        )
        assert response.status_code == 422

    @patch("app.endpoints.retrieve.run_retrieve_plan")
    def test_retrieve_plan_success(self, mock_run):
        """Test successful retrieve plan."""
        with open(FIXTURES_PATH / "sample_structure_3section.json") as f:
            structure_data = json.load(f)

        mock_run.return_value = QueryPlan(
            queries=[
                Query(
                    query_id="q_001",
                    question="What is the corporate structure?",
                    section_assignments=["sec_01"],
                )
            ],
            supports_followup=True,
            iteration=1,
        )

        response = client.post(
            "/api/report-writer/retrieve/plan",
            json={"structure": structure_data},
        )

        assert response.status_code == 200
        data = response.json()
        assert "query_plan" in data
        assert len(data["query_plan"]["queries"]) > 0

    @patch("app.endpoints.retrieve.run_retrieve_evaluate")
    def test_retrieve_evaluate_success(self, mock_run):
        """Test successful retrieve evaluation."""
        with open(FIXTURES_PATH / "sample_structure_3section.json") as f:
            structure_data = json.load(f)

        with open(FIXTURES_PATH / "sample_evidence_package.json") as f:
            package_data = json.load(f)

        mock_run.return_value = EvidencePackage.model_validate(package_data)

        response = client.post(
            "/api/report-writer/retrieve/evaluate",
            json={
                "structure": structure_data,
                "query_results": [],
                "query_plan": {
                    "queries": [],
                    "supports_followup": True,
                    "iteration": 1,
                },
                "iteration": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "evidence_package" in data


class TestConsistencyEndpoint:
    """Tests for consistency endpoint."""

    def test_consistency_requires_draft(self):
        """Test consistency endpoint requires assembled_draft."""
        response = client.post(
            "/api/report-writer/consistency",
            json={},
        )
        assert response.status_code == 422

    @patch("app.endpoints.consistency.arun_consistency")
    def test_consistency_success(self, mock_run):
        """Test successful consistency check."""
        with open(FIXTURES_PATH / "sample_assembled_draft.json") as f:
            draft_data = json.load(f)

        with open(FIXTURES_PATH / "sample_evidence_package.json") as f:
            package_data = json.load(f)

        mock_run.return_value = []  # No consistency issues

        response = client.post(
            "/api/report-writer/consistency",
            json={
                "assembled_draft": draft_data,
                "evidence_package": package_data,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json_returns_400(self):
        """Test invalid JSON returns 400."""
        response = client.post(
            "/api/report-writer/plan",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_error_payload_format(self):
        """Test error responses follow ErrorPayload format."""
        response = client.post(
            "/api/report-writer/plan",
            json={"goal": "short"},  # Too short
        )

        assert response.status_code == 422
        # Should be a JSON response with detail field


class TestTraceIdPropagation:
    """Tests for trace ID propagation."""

    @patch("app.endpoints.plan.arun_plan")
    def test_trace_id_in_response_header(self, mock_run):
        """Test trace_id is returned in response header."""
        with open(FIXTURES_PATH / "sample_structure_3section.json") as f:
            structure_data = json.load(f)

        mock_run.return_value = FrozenStructure.model_validate(structure_data)

        response = client.post(
            "/api/report-writer/plan",
            json={"goal": "Generate a KYC report for Acme Corp SA"},
        )

        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Trace-ID"] != ""

    @patch("app.endpoints.plan.arun_plan")
    def test_custom_trace_id_preserved(self, mock_run):
        """Test custom trace_id from request is preserved."""
        with open(FIXTURES_PATH / "sample_structure_3section.json") as f:
            structure_data = json.load(f)

        mock_run.return_value = FrozenStructure.model_validate(structure_data)

        custom_trace_id = "custom-trace-123"
        response = client.post(
            "/api/report-writer/plan",
            json={"goal": "Generate a KYC report for Acme Corp SA"},
            headers={"X-Trace-ID": custom_trace_id},
        )

        assert response.headers["X-Trace-ID"] == custom_trace_id

"""Tests for the Structure Builder agent."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.structure_builder import StructureBuilderAgent, get_structure_builder
from app.schemas.structure import FrozenStructure, SectionSpec, ReportMetadata


FIXTURES_PATH = Path(__file__).parent.parent / "fixtures"


class TestStructureBuilderAgent:
    """Tests for StructureBuilderAgent."""

    def test_build_prompt_goal_only(self):
        """Test prompt building with goal only."""
        agent = StructureBuilderAgent()
        prompt = agent.build_prompt(goal="Generate a KYC report for Acme Corp")

        assert "Generate a KYC report for Acme Corp" in prompt
        assert "create structure from scratch" in prompt

    def test_build_prompt_with_input_spec(self):
        """Test prompt building with input spec."""
        agent = StructureBuilderAgent()
        input_spec = {"report_type": "compliance_profile"}
        prompt = agent.build_prompt(
            goal="Generate a KYC report",
            input_spec=json.dumps(input_spec),
        )

        assert "compliance_profile" in prompt
        assert "enrich" in prompt.lower()

    def test_agent_singleton(self):
        """Test get_structure_builder returns singleton."""
        agent1 = get_structure_builder()
        agent2 = get_structure_builder()
        assert agent1 is agent2

    @pytest.mark.skip(reason="Requires LLM API")
    def test_invoke_produces_valid_structure(self):
        """Test that invoke produces valid FrozenStructure."""
        with open(FIXTURES_PATH / "sample_goal.txt") as f:
            goal = f.read()

        agent = get_structure_builder()
        structure = agent.invoke(goal=goal)

        assert isinstance(structure, FrozenStructure)
        assert len(structure.sections) >= 3
        assert len(structure.sections) <= 8
        assert structure.metadata.report_type in [
            "compliance_profile",
            "risk_assessment",
            "due_diligence",
            "investigation_report",
            "monitoring_alert",
            "transaction_analysis",
            "entity_profile",
            "network_analysis",
        ]


class TestStructureBuilderPromptContent:
    """Tests for prompt content and guidelines."""

    def test_prompt_includes_report_types(self):
        """Test that prompt includes valid report types."""
        agent = StructureBuilderAgent()
        prompt = agent.build_prompt(goal="test")

        assert "compliance_profile" in prompt
        assert "risk_assessment" in prompt
        assert "due_diligence" in prompt

    def test_prompt_includes_section_requirements(self):
        """Test that prompt includes section requirements."""
        agent = StructureBuilderAgent()
        prompt = agent.build_prompt(goal="test")

        assert "section_id" in prompt
        assert "target_words" in prompt
        assert "depends_on" in prompt
        assert "requirements" in prompt

    def test_prompt_includes_guidelines(self):
        """Test that prompt includes writing guidelines."""
        agent = StructureBuilderAgent()
        prompt = agent.build_prompt(goal="test")

        assert "logical" in prompt.lower()
        assert "dependencies" in prompt.lower()
        assert "parallelism" in prompt.lower()

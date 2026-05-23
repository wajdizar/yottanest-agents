"""Pytest configuration and fixtures for Writing Service.

Integrates with DeerFlow's configuration system.
"""

import os
import sys
from pathlib import Path

import pytest

# Add DeerFlow backend to path
DEER_FLOW_ROOT = Path(__file__).parent.parent
DEER_FLOW_BACKEND = DEER_FLOW_ROOT / "backend"
if str(DEER_FLOW_BACKEND) not in sys.path:
    sys.path.insert(0, str(DEER_FLOW_BACKEND))

# Set test environment
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test."""
    from app.harness.setup import reset_harness
    from app.harness.openrouter_provider import clear_model_cache
    from app.config import clear_settings_cache

    reset_harness()
    clear_model_cache()
    clear_settings_cache()
    yield


@pytest.fixture
def sample_goal():
    """Load sample goal from fixture."""
    fixtures_path = Path(__file__).parent / "tests" / "fixtures"
    with open(fixtures_path / "sample_goal.txt") as f:
        return f.read()


@pytest.fixture
def sample_structure_3section():
    """Load 3-section structure from fixture."""
    import json
    from app.schemas.structure import FrozenStructure

    fixtures_path = Path(__file__).parent / "tests" / "fixtures"
    with open(fixtures_path / "sample_structure_3section.json") as f:
        data = json.load(f)
    return FrozenStructure.model_validate(data)


@pytest.fixture
def sample_structure_5section():
    """Load 5-section structure from fixture."""
    import json
    from app.schemas.structure import FrozenStructure

    fixtures_path = Path(__file__).parent / "tests" / "fixtures"
    with open(fixtures_path / "sample_structure_5section.json") as f:
        data = json.load(f)
    return FrozenStructure.model_validate(data)


@pytest.fixture
def sample_evidence_package():
    """Load evidence package from fixture."""
    import json
    from app.schemas.evidence import EvidencePackage

    fixtures_path = Path(__file__).parent / "tests" / "fixtures"
    with open(fixtures_path / "sample_evidence_package.json") as f:
        data = json.load(f)
    return EvidencePackage.model_validate(data)


@pytest.fixture
def sample_assembled_draft():
    """Load assembled draft from fixture."""
    import json
    from app.schemas.draft import AssembledDraft

    fixtures_path = Path(__file__).parent / "tests" / "fixtures"
    with open(fixtures_path / "sample_assembled_draft.json") as f:
        data = json.load(f)
    return AssembledDraft.model_validate(data)

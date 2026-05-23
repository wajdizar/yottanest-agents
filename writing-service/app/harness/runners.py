"""Runners for each capability (endpoint logic)."""

import asyncio
import time
from typing import AsyncIterator, Any

from app.agents.structure_builder import get_structure_builder
from app.agents.retrieval_planner import get_retrieval_planner
from app.agents.coverage_evaluator import (
    get_coverage_evaluator,
    deduplicate_results,
    assign_bundles,
    build_gaps_for_followup,
)
from app.agents.section_writer import get_section_writer
from app.agents.section_editor import get_section_editor
from app.agents.section_checker import get_section_checker
from app.agents.assembler import get_assembler
from app.agents.consistency_checker import get_consistency_checker
from app.agents.base import AgentError
from app.config import get_settings
from app.logging import get_logger
from app.schemas.structure import FrozenStructure
from app.schemas.retrieval import QueryPlan, PreviousIteration, QueryResults
from app.schemas.evidence import EvidencePackage, EvidenceItem, SharedEvidence
from app.schemas.draft import SectionDraft, AssembledDraft
from app.schemas.feedback import Feedback
from app.schemas.consistency import ConsistencyFlag
from app.schemas.errors import ErrorCodes


logger = get_logger("runners")


# =============================================================================
# Plan Capability
# =============================================================================


def run_plan(
    goal: str,
    input_spec: dict | None = None,
) -> FrozenStructure:
    """
    Generate a report structure from a goal.

    Args:
        goal: Description of what the report should accomplish
        input_spec: Optional partial structure to enrich

    Returns:
        Complete frozen structure
    """
    logger.info("run_plan_start", goal_length=len(goal), has_input_spec=input_spec is not None)

    agent = get_structure_builder()
    structure = agent.invoke(goal=goal, input_spec=input_spec)

    logger.info(
        "run_plan_complete",
        section_count=len(structure.sections),
        report_type=structure.metadata.report_type,
    )

    return structure


async def arun_plan(
    goal: str,
    input_spec: dict | None = None,
) -> FrozenStructure:
    """Async version of run_plan."""
    logger.info("arun_plan_start", goal_length=len(goal))

    agent = get_structure_builder()
    structure = await agent.ainvoke(goal=goal, input_spec=input_spec)

    logger.info("arun_plan_complete", section_count=len(structure.sections))

    return structure


# =============================================================================
# Retrieve Capability
# =============================================================================


def run_retrieve_plan(
    structure: FrozenStructure,
    previous_iteration: PreviousIteration | None = None,
) -> QueryPlan:
    """
    Generate retrieval queries for a structure.

    Args:
        structure: Report structure
        previous_iteration: Optional info from previous iteration

    Returns:
        Query plan
    """
    logger.info(
        "run_retrieve_plan_start",
        section_count=len(structure.sections),
        iteration=previous_iteration.iteration + 1 if previous_iteration else 1,
    )

    agent = get_retrieval_planner()
    plan = agent.invoke(structure=structure, previous_iteration=previous_iteration)

    logger.info(
        "run_retrieve_plan_complete",
        query_count=len(plan.queries),
        iteration=plan.iteration,
    )

    return plan


def run_retrieve_evaluate(
    structure: FrozenStructure,
    query_results: list[QueryResults],
    query_plan: QueryPlan,
    iteration: int = 1,
) -> EvidencePackage:
    """
    Evaluate query results and build evidence package.

    Args:
        structure: Report structure
        query_results: Results from executing queries
        query_plan: The query plan that was executed
        iteration: Current iteration number

    Returns:
        Evidence package
    """
    settings = get_settings()
    logger.info(
        "run_retrieve_evaluate_start",
        result_count=len(query_results),
        iteration=iteration,
    )

    # Build query to sections mapping
    query_to_sections = {
        q.query_id: q.section_assignments for q in query_plan.queries
    }

    evaluator = get_coverage_evaluator()
    package = evaluator.evaluate(
        structure=structure,
        query_results=query_results,
        query_to_sections=query_to_sections,
        iteration=iteration,
        max_iterations=settings.retrieval_max_iterations,
    )

    logger.info(
        "run_retrieve_evaluate_complete",
        evidence_count=len(package.evidence_pool),
        needs_followup=package.needs_followup,
    )

    return package


# =============================================================================
# Write Capability
# =============================================================================


class WriteEvent:
    """Base class for write events."""

    event_type: str


class SectionStartedEvent(WriteEvent):
    """Emitted when a section begins processing."""

    event_type = "section_started"

    def __init__(self, section_id: str, title: str):
        self.section_id = section_id
        self.title = title


class SectionStepCompleteEvent(WriteEvent):
    """Emitted when a step completes for a section."""

    event_type = "section_step_complete"

    def __init__(self, section_id: str, step: str, status: str):
        self.section_id = section_id
        self.step = step  # "writer" | "editor" | "checker"
        self.status = status


class SectionCompleteEvent(WriteEvent):
    """Emitted when a section is complete."""

    event_type = "section_complete"

    def __init__(self, section_id: str, draft: SectionDraft):
        self.section_id = section_id
        self.draft = draft


class SectionRetryEvent(WriteEvent):
    """Emitted when a section is being retried."""

    event_type = "section_retry"

    def __init__(self, section_id: str, retry_count: int, reason: str):
        self.section_id = section_id
        self.retry_count = retry_count
        self.reason = reason


class AssemblingEvent(WriteEvent):
    """Emitted when assembly begins."""

    event_type = "assembling"


class WriteCompleteEvent(WriteEvent):
    """Emitted when write is complete."""

    event_type = "complete"

    def __init__(self, draft: AssembledDraft):
        self.draft = draft


class WriteErrorEvent(WriteEvent):
    """Emitted on error."""

    event_type = "error"

    def __init__(self, error_code: str, message: str, section_id: str | None = None):
        self.error_code = error_code
        self.message = message
        self.section_id = section_id


async def _write_section(
    section_id: str,
    structure: FrozenStructure,
    evidence_package: EvidencePackage,
    events: asyncio.Queue,
) -> SectionDraft:
    """Write a single section with retry logic."""
    settings = get_settings()
    section = structure.get_section(section_id)
    if not section:
        raise AgentError(
            f"Section {section_id} not found",
            error_code=ErrorCodes.SECTION_NOT_FOUND,
        )

    # Get evidence for this section
    evidence = evidence_package.get_evidence_for_section(section_id)

    # Get shared evidence
    shared_evidence = [
        se for se in evidence_package.shared_registry
        if section_id in se.section_ids
    ]

    writer = get_section_writer()
    editor = get_section_editor()
    checker = get_section_checker()

    retry_count = 0
    max_retries = settings.section_checker_max_retries

    while True:
        try:
            # Emit section started
            await events.put(SectionStartedEvent(section_id, section.title))

            # Write
            draft = await writer.ainvoke(
                section=section,
                evidence=evidence,
                metadata=structure.metadata,
                shared_evidence=shared_evidence,
                global_instructions=structure.global_instructions,
            )
            await events.put(SectionStepCompleteEvent(section_id, "writer", "success"))

            # Edit
            draft = await editor.ainvoke(draft=draft)
            await events.put(SectionStepCompleteEvent(section_id, "editor", "success"))

            # Check
            draft = await checker.ainvoke(
                draft=draft,
                section=section,
                evidence=evidence,
            )
            await events.put(SectionStepCompleteEvent(section_id, "checker", draft.checker_status))

            # Update retry count in metadata
            draft.metadata.retry_count = retry_count

            # Check if retry needed
            if draft.checker_status == "fail" and retry_count < max_retries:
                retry_count += 1
                await events.put(
                    SectionRetryEvent(
                        section_id,
                        retry_count,
                        "; ".join(draft.checker_notes),
                    )
                )
                continue

            await events.put(SectionCompleteEvent(section_id, draft))
            return draft

        except asyncio.TimeoutError:
            # Section timeout
            draft = SectionDraft(
                metadata=SectionMetadata(
                    section_id=section_id,
                    title=section.title,
                    word_count=0,
                    target_words=section.target_words,
                    retry_count=retry_count,
                ),
                content="[Section timed out]",
                claims=[],
                checker_status="timeout",
                checker_notes=["Section processing timed out"],
            )
            await events.put(SectionCompleteEvent(section_id, draft))
            return draft

        except Exception as e:
            logger.error("section_write_error", section_id=section_id, error=str(e))
            raise


async def run_write(
    structure: FrozenStructure,
    evidence_package: EvidencePackage,
) -> AsyncIterator[WriteEvent]:
    """
    Write all sections and assemble into final draft.

    Yields events as sections are processed.
    """
    settings = get_settings()
    events: asyncio.Queue = asyncio.Queue()

    logger.info(
        "run_write_start",
        section_count=len(structure.sections),
    )

    # Get dependency order for parallel processing
    dependency_order = structure.get_dependency_order()
    completed_drafts: dict[str, SectionDraft] = {}

    try:
        # Process sections in dependency order
        for batch in dependency_order:
            # Create tasks for this batch (can run in parallel)
            tasks = []
            for section_id in batch:
                task = asyncio.create_task(
                    asyncio.wait_for(
                        _write_section(
                            section_id,
                            structure,
                            evidence_package,
                            events,
                        ),
                        timeout=settings.section_timeout_seconds,
                    )
                )
                tasks.append((section_id, task))

            # Wait for batch to complete, yielding events as they come
            pending_tasks = {t for _, t in tasks}
            task_to_section = {t: s for s, t in tasks}

            while pending_tasks:
                # Check for events
                while not events.empty():
                    yield events.get_nowait()

                # Wait a bit for tasks
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    timeout=0.1,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    section_id = task_to_section[task]
                    try:
                        draft = task.result()
                        completed_drafts[section_id] = draft
                    except asyncio.TimeoutError:
                        # Handle timeout
                        section = structure.get_section(section_id)
                        from app.schemas.draft import SectionMetadata
                        draft = SectionDraft(
                            metadata=SectionMetadata(
                                section_id=section_id,
                                title=section.title if section else "Unknown",
                                word_count=0,
                                target_words=section.target_words if section else 0,
                            ),
                            content="[Section timed out]",
                            claims=[],
                            checker_status="timeout",
                        )
                        completed_drafts[section_id] = draft
                        yield SectionCompleteEvent(section_id, draft)
                    except Exception as e:
                        yield WriteErrorEvent(
                            ErrorCodes.WRITING_FAILED,
                            str(e),
                            section_id,
                        )
                        raise

            # Yield any remaining events from this batch
            while not events.empty():
                yield events.get_nowait()

        # All sections complete - assemble
        yield AssemblingEvent()

        # Order sections by structure
        ordered_drafts = []
        for section in structure.sections:
            if section.section_id in completed_drafts:
                ordered_drafts.append(completed_drafts[section.section_id])

        # Assemble
        assembler = get_assembler()
        assembled = await assembler.ainvoke(
            sections=ordered_drafts,
            structure=structure,
            evidence_pool=evidence_package.evidence_pool,
        )

        logger.info(
            "run_write_complete",
            total_word_count=assembled.total_word_count,
            has_failures=assembled.has_failures,
        )

        yield WriteCompleteEvent(assembled)

    except Exception as e:
        logger.error("run_write_error", error=str(e))
        yield WriteErrorEvent(ErrorCodes.WRITING_FAILED, str(e))
        raise


# =============================================================================
# Revise Capability
# =============================================================================


async def run_revise(
    section_id: str,
    original_draft: SectionDraft,
    structure: FrozenStructure,
    evidence_package: EvidencePackage,
    feedback: Feedback,
) -> SectionDraft:
    """
    Revise a section based on feedback.

    Args:
        section_id: Section to revise
        original_draft: Original section draft
        structure: Report structure
        evidence_package: Evidence package
        feedback: Revision feedback

    Returns:
        Revised section draft
    """
    settings = get_settings()
    logger.info("run_revise_start", section_id=section_id, feedback_type=feedback.feedback_type)

    section = structure.get_section(section_id)
    if not section:
        raise AgentError(
            f"Section {section_id} not found",
            error_code=ErrorCodes.SECTION_NOT_FOUND,
        )

    # Get evidence
    evidence = evidence_package.get_evidence_for_section(section_id)

    # Add new evidence if augmented
    if feedback.augmented_evidence:
        for eid in feedback.new_evidence_ids:
            item = evidence_package.get_evidence(eid)
            if item and item not in evidence:
                evidence.append(item)

    # Get shared evidence
    shared_evidence = [
        se for se in evidence_package.shared_registry
        if section_id in se.section_ids
    ]

    writer = get_section_writer()
    editor = get_section_editor()
    checker = get_section_checker()

    retry_count = 0
    max_retries = settings.section_checker_max_retries

    while True:
        # Write (revise mode)
        draft = await writer.ainvoke(
            section=section,
            evidence=evidence,
            metadata=structure.metadata,
            shared_evidence=shared_evidence,
            global_instructions=structure.global_instructions,
            original_draft=original_draft,
            feedback=feedback,
        )

        # Edit
        draft = await editor.ainvoke(draft=draft)

        # Check
        draft = await checker.ainvoke(
            draft=draft,
            section=section,
            evidence=evidence,
        )

        draft.metadata.retry_count = retry_count

        if draft.checker_status == "fail" and retry_count < max_retries:
            retry_count += 1
            continue

        logger.info(
            "run_revise_complete",
            section_id=section_id,
            checker_status=draft.checker_status,
            changelog_count=len(draft.changelog),
        )

        return draft


# =============================================================================
# Consistency Capability
# =============================================================================


def run_consistency(
    draft: AssembledDraft,
    evidence_package: EvidencePackage,
) -> list[ConsistencyFlag]:
    """
    Check consistency of assembled draft.

    Args:
        draft: Assembled draft to check
        evidence_package: Evidence package

    Returns:
        List of consistency flags
    """
    logger.info("run_consistency_start", section_count=len(draft.sections))

    checker = get_consistency_checker()
    result = checker.invoke(draft=draft, evidence_package=evidence_package)

    logger.info(
        "run_consistency_complete",
        flag_count=len(result.flags),
        summary=result.summary,
    )

    return result.flags


async def arun_consistency(
    draft: AssembledDraft,
    evidence_package: EvidencePackage,
) -> list[ConsistencyFlag]:
    """Async version of run_consistency."""
    logger.info("arun_consistency_start", section_count=len(draft.sections))

    checker = get_consistency_checker()
    result = await checker.ainvoke(draft=draft, evidence_package=evidence_package)

    logger.info("arun_consistency_complete", flag_count=len(result.flags))

    return result.flags

"""MANARA Agent Factory (G05).

Public API:
* :class:`GeneralistVsSpecialistResolver` — decides if specialist is needed
* :class:`AgentRecipeRegistry` — CRUD + rehydration (the phone book)
* :class:`EphemeralAgentRuntime` — instantiate, execute, terminate
* :class:`ToolPermissionResolver` — intersection of capability × role × investigation
* :class:`MockProvider` / :class:`ZAIProvider` — LLM backends
* :func:`create_clinical_prosthetics_reviewer_recipe` — canonical G05 test recipe
* :func:`create_general_analyst_recipe` — the default generalist
"""

from manara.agents.factory import (
    AgentRecipeRegistry,
    EphemeralAgentRuntime,
    EvaluationResult,
    ExecutionResult,
    GeneralistVsSpecialistResolver,
    ResolutionResult,
    ToolPermissionResolver,
    ToolPermissions,
    create_clinical_prosthetics_reviewer_recipe,
    create_general_analyst_recipe,
)
from manara.agents.providers import (
    LLMProvider,
    LLMResponse,
    MockProvider,
    ZAIProvider,
    get_provider,
    reset_provider,
)

__all__ = [
    "AgentRecipeRegistry",
    "EphemeralAgentRuntime",
    "EvaluationResult",
    "ExecutionResult",
    "GeneralistVsSpecialistResolver",
    "LLMProvider",
    "LLMResponse",
    "MockProvider",
    "ResolutionResult",
    "ToolPermissionResolver",
    "ToolPermissions",
    "ZAIProvider",
    "create_clinical_prosthetics_reviewer_recipe",
    "create_general_analyst_recipe",
    "get_provider",
    "reset_provider",
]

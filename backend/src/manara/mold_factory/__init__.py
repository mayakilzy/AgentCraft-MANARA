"""MANARA Mold Factory (G04 + G04-R1).

Public API:
* :class:`MoldArchitect` — composes temporary molds with three-tier coverage
* :class:`CoverageLevel` — enum: NONE | CATALOG | OPERATIONAL | VERIFIED
* :class:`UnknownDomainDetector` — detects whether a domain has an existing mold
* :class:`InvestigationWorkflowService` — enforces the G00 state machine
"""

from manara.mold_factory.architect import (
    CoverageLevel,
    GapRecord,
    MoldArchitect,
    MoldCompositionResult,
    NeedCoverage,
)
from manara.mold_factory.detector import DetectionResult, UnknownDomainDetector
from manara.mold_factory.workflow import (
    InvestigationWorkflowService,
    TransitionResult,
    WorkflowTransitionError,
)

__all__ = [
    "CoverageLevel",
    "DetectionResult",
    "GapRecord",
    "InvestigationWorkflowService",
    "MoldArchitect",
    "MoldCompositionResult",
    "NeedCoverage",
    "TransitionResult",
    "UnknownDomainDetector",
    "WorkflowTransitionError",
]

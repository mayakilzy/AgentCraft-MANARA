"""MANARA Mold Factory (G04).

Public API:
* :class:`MoldArchitect` — composes temporary molds from existing capabilities
* :class:`UnknownDomainDetector` — detects whether a domain has an existing mold
* :class:`InvestigationWorkflowService` — enforces the G00 state machine
"""

from manara.mold_factory.architect import (
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

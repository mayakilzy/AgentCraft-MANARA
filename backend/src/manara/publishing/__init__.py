"""MANARA Publishing Engine (G07).

Public API:
* :class:`DossierBuilder` — builds research dossiers from evidence
* :class:`PresenterEditionBuilder` — builds 3-5 minute presenter scripts
* :class:`StoryboardBuilder` — builds visual storyboards with evidence/fiction classification
* :class:`QualityGate` — 6 rejection rules before publication
* :class:`PublicationRegistry` — persistence + download
"""

from manara.publishing.engine import (
    ClaimType,
    DossierBuilder,
    DossierOutput,
    DossierSection,
    PresenterEditionBuilder,
    PresenterOutput,
    PublicationRegistry,
    QualityGate,
    QualityGateResult,
    SceneType,
    StoryboardBuilder,
    StoryboardOutput,
)

__all__ = [
    "ClaimType",
    "DossierBuilder",
    "DossierOutput",
    "DossierSection",
    "PresenterEditionBuilder",
    "PresenterOutput",
    "PublicationRegistry",
    "QualityGate",
    "QualityGateResult",
    "SceneType",
    "StoryboardBuilder",
    "StoryboardOutput",
]

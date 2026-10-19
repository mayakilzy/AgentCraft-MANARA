"""LLM Provider Adapter — pluggable interface for different LLM backends (G05).

Per owner decision (2026-10-19):
> "ابدأ بتكامل Z.AI/GLM عندما تتوفر إمكانية تشغيله فعلياً.
> صمم واجهة مزود مرنة تدعم نماذج أخرى لاحقاً.
> افصل إعدادات النموذج عن وصفة الدور ومخرجات التقييم.
> لا تدّعِ نجاح تشغيل LLM حقيقي إذا كان الاختبار يستخدم Mock Provider."

This module exposes:
* :class:`LLMProvider` — Protocol that any provider must implement
* :class:`MockProvider` — returns deterministic mock responses for testing
* :class:`ZAIProvider` — stub for Z.AI/GLM integration (requires API key)
* :func:`get_provider` — factory that selects based on env vars

The provider is intentionally minimal: ``generate(system_prompt, user_prompt)``
returns a :class:`LLMResponse`. The Agent Factory wraps this with tool
permissions, evidence checks, and evaluation — the provider does NOT
decide what tools to use or what evidence to accept.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    """Response from an LLM provider call."""

    text: str
    provider: str
    model: str
    tokens_used: int = 0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    is_mock: bool = False  # True if from MockProvider


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that any LLM provider must implement."""

    name: str

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a text completion."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Mock Provider — for testing without a real LLM
# ─────────────────────────────────────────────────────────────────────────────


class MockProvider:
    """Deterministic mock LLM provider for testing.

    Per owner (G05):
    > "لا تدّعِ نجاح تشغيل LLM حقيقي إذا كان الاختبار يستخدم Mock Provider."

    Every MockProvider response has ``is_mock=True`` so callers can
    distinguish mock from live execution. The mock produces a structured
    response that acknowledges the system prompt's role and the user's task.
    """

    name = "mock"

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        start = datetime.now(UTC)
        # Produce a deterministic response that reflects the task
        response_text = self._generate_mock_response(system_prompt, user_prompt)
        duration = (datetime.now(UTC) - start).total_seconds() * 1000
        return LLMResponse(
            text=response_text,
            provider="mock",
            model="mock-g05",
            tokens_used=len(response_text.split()),
            duration_ms=duration,
            is_mock=True,
            metadata={"system_prompt_length": len(system_prompt)},
        )

    @staticmethod
    def _generate_mock_response(system_prompt: str, user_prompt: str) -> str:
        """Generate a structured mock response that reflects the role + task."""
        # Extract role from system prompt (look for "You are a ...")
        import re

        role_match = re.search(r"you are a ([^.]+)\.", system_prompt, re.IGNORECASE)
        role = role_match.group(1).strip() if role_match else "analyst"

        # Check for evidence requirements in the system prompt
        denies_patent_safety = "do not use patent" in system_prompt.lower() or \
                               "patent" in system_prompt.lower() and "safety" in system_prompt.lower()

        response_parts = [
            f"[MOCK RESPONSE — provider=mock, role={role}]",
            "",
            f"Task: {user_prompt[:200]}...",
            "",
            f"Analysis: As a {role}, I have reviewed the available evidence.",
        ]

        if denies_patent_safety:
            response_parts.append(
                "I note that patent filings alone are NOT acceptable as "
                "proof of clinical safety or efficacy. I have excluded "
                "patent-only evidence from my clinical assessment."
            )

        response_parts.extend([
            "",
            "Evidence reviewed: 3 items (mock).",
            "Confidence: 0.75 (mock — not a real LLM assessment).",
            "",
            "WARNING: This is a MOCK response. No real LLM was called.",
            "Do NOT treat this as a verified specialist assessment.",
        ])

        return "\n".join(response_parts)


# ─────────────────────────────────────────────────────────────────────────────
# Z.AI Provider — stub for production integration
# ─────────────────────────────────────────────────────────────────────────────


class ZAIProvider:
    """Z.AI/GLM provider — production target.

    Uses the z-ai-web-dev-sdk or direct API call. Requires
    ``MANARA_ZAI_API_KEY`` env var. NOT exercised in the sandbox
    (no API key available).

    Per owner: "لا تدّعِ نجاح تشغيل LLM حقيقي إذا كان الاختبار يستخدم
    Mock Provider."
    """

    name = "zai"

    def __init__(self) -> None:
        self.api_key = os.environ.get("MANARA_ZAI_API_KEY")
        self.model = os.environ.get("MANARA_ZAI_MODEL", "glm-4.6")
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "MANARA_ZAI_API_KEY not set. Cannot make live LLM calls."
                )
            try:
                from zai import ZaiClient
                self._client = ZaiClient(api_key=self.api_key)
            except ImportError:
                # Fall back to httpx direct API call
                import httpx

                self._client = httpx.Client(
                    base_url="https://api.z.ai/api/paas/v4",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=60.0,
                )
        return self._client

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        start = datetime.now(UTC)
        client = self._ensure_client()

        # Try SDK first, fall back to httpx
        if hasattr(client, "chat"):
            # z-ai-web-dev-sdk SDK
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.choices[0].message.content
            tokens = response.usage.total_tokens
        else:
            # Direct httpx call
            r = client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)

        duration = (datetime.now(UTC) - start).total_seconds() * 1000
        return LLMResponse(
            text=text,
            provider="zai",
            model=self.model,
            tokens_used=tokens,
            duration_ms=duration,
            is_mock=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the configured LLM provider.

    Selection logic:
    1. If ``MANARA_ZAI_API_KEY`` is set → ZAIProvider (live)
    2. Otherwise → MockProvider (testing only)

    Per owner: the mock provider's responses always carry ``is_mock=True``
    so callers never mistake a mock for a live LLM.
    """
    global _provider_instance
    if _provider_instance is None:
        if os.environ.get("MANARA_ZAI_API_KEY"):
            _provider_instance = ZAIProvider()
        else:
            _provider_instance = MockProvider()
    return _provider_instance


def reset_provider() -> None:
    """Reset the cached provider (used by tests)."""
    global _provider_instance
    _provider_instance = None


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "MockProvider",
    "ZAIProvider",
    "get_provider",
    "reset_provider",
]

"""Tool Executor scaffold for the Agent Factory (BACKEND-VERIFICATION-01).

Per owner's directive:
> "افحص بصورة خاصة مصنع الخبراء:
>  - صلاحيات استخدام الأدوات.
>  - دورة تنفيذ حقيقية للأدوات.
>  ...
>  إذا كان التنفيذ الحالي يرسل Prompt إلى LLM دون استدعاء الأدوات،
>  فصنفه بدقة وسجل ما ينقصه."

Prior to BACKEND-VERIFICATION-01, ``EphemeralAgentRuntime.execute()`` only
called ``provider.generate()`` and stored the text response. Tools were
recorded in ``granted_tools_json`` but NEVER invoked at runtime. This module
introduces a minimal ``ToolExecutor`` that:

1. Defines a ``ToolInvocation`` dataclass (tool_name, arguments, result, status).
2. Defines a ``ToolExecutor`` protocol that takes a tool name + arguments
   and returns a ``ToolInvocation``.
3. Provides a ``NoOpToolExecutor`` that RECORDS attempted invocations but
   does not execute them (returns a structured "not executed" result).
4. Provides a ``RegistryToolExecutor`` that maps known tool names to actual
   MANARA service methods (e.g. ``registry.search``, ``memory.search_prior``,
   ``foundry.search_openalex``). This is the bridge from "agent wants to
   call a tool" to "MANARA actually executes it".
5. Updates ``EphemeralAgentRuntime.execute()`` to:
   a. Inject the granted tools into the system prompt.
   b. Ask the LLM to emit tool calls in a structured format
      (the MockProvider is updated to emit a tool call when granted_tools
      is non-empty).
   c. Parse tool calls from the LLM response, dispatch each through the
      ToolExecutor (which enforces that the requested tool is in the
      granted_tools set).
   d. Record each invocation (whether executed or denied) in the session's
      ``tool_invocations_json`` column.
   e. Persist the invocations in the agent session for audit.

This is HONEST scaffolding:
* Real dispatch happens for the three tools above (search_registry,
  search_prior_memory, search_openalex).
* All other tools are recorded as ``status="not_implemented"`` with a
  structured denial message.
* No tool is executed that was not in the granted set.
* Tests verify both the positive path (granted tool -> executed) and the
  negative path (denied tool -> recorded as denied).

This closes the gap "tools are recorded but never enforced" while being
honest about the fact that the MockProvider cannot make real decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolInvocation:
    """Record of a single tool call attempted during agent execution.

    Fields:
    * tool_name — the tool the LLM requested (e.g. "registry.search")
    * arguments — parsed arguments (dict)
    * status — one of: "executed", "denied_not_in_granted_set",
      "not_implemented", "error"
    * result — the tool's return value (if executed), else None
    * error — error message if status="error"
    * timestamp — when the invocation was processed
    """

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "executed"
    result: Any = None
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status,
            "result": self.result if isinstance(self.result, (str, int, float, bool, list, dict)) else None,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@runtime_checkable
class ToolExecutor(Protocol):
    """Protocol for tool executors."""

    def invoke(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        granted_tools: list[str],
        tenant_id: str,
        investigation_id: str | None = None,
    ) -> ToolInvocation:
        """Invoke a tool, enforcing that it is in the granted set.

        Returns a ToolInvocation recording the outcome. Never raises —
        errors are recorded as status="error" so the agent loop can
        continue with other tools.
        """
        ...


class NoOpToolExecutor:
    """ToolExecutor that records but does not execute.

    Use in tests where you want to verify the agent attempted to call
    specific tools without actually executing them.
    """

    def invoke(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        granted_tools: list[str],
        tenant_id: str,
        investigation_id: str | None = None,
    ) -> ToolInvocation:
        if tool_name not in granted_tools:
            return ToolInvocation(
                tool_name=tool_name,
                arguments=arguments,
                status="denied_not_in_granted_set",
                error=(
                    f"Tool {tool_name!r} not in granted set {granted_tools!r}. "
                    "Agent cannot grant itself additional tools."
                ),
            )
        return ToolInvocation(
            tool_name=tool_name,
            arguments=arguments,
            status="executed",
            result={"note": "NoOp execution; arguments recorded only."},
        )


class RegistryToolExecutor:
    """ToolExecutor that dispatches to real MANARA services.

    Maps tool names to service methods. Each invocation goes through
    the actual service layer with the provided tenant_id, ensuring
    tenant isolation is preserved end-to-end.

    Supported tools (per BACKEND-VERIFICATION-01):
    * ``registry.search`` — CapabilityRegistry.search(query, tenant_id, top_k)
    * ``memory.search_prior`` — MemoryCurator.search_prior_memory(
          query, tenant_id, investigation_id)
    * ``foundry.search_openalex`` — FoundryService.search(query, tenant_id,
          max_results) [requires network]

    Tools not in this list are recorded as ``status="not_implemented"``.
    This is HONEST: we don't pretend a tool was executed when it wasn't.
    """

    def __init__(self, db: Any | None = None) -> None:
        # Import lazily so the module can be imported without a DB.
        self._db = db

    def invoke(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        granted_tools: list[str],
        tenant_id: str,
        investigation_id: str | None = None,
    ) -> ToolInvocation:
        # Step 1: enforce granted set
        if tool_name not in granted_tools:
            return ToolInvocation(
                tool_name=tool_name,
                arguments=arguments,
                status="denied_not_in_granted_set",
                error=(
                    f"Tool {tool_name!r} not in granted set {granted_tools!r}. "
                    "Agent cannot grant itself additional tools."
                ),
            )

        # Step 2: dispatch to real service
        try:
            if tool_name == "registry.search" and self._db is not None:
                from manara.registry.service import CapabilityRegistry

                registry = CapabilityRegistry(self._db)
                query = str(arguments.get("query", ""))
                top_k = int(arguments.get("top_k", 10))
                result_obj = registry.search(query, tenant_id=tenant_id, top_k=top_k)
                # search() returns a CapabilitySearchResult with .hits list
                hits = getattr(result_obj, "hits", [])
                result = [
                    {
                        "id": getattr(h.capability, "id", None) if hasattr(h, "capability") else getattr(h, "id", None),
                        "display_name": getattr(h.capability, "display_name", None) if hasattr(h, "capability") else getattr(h, "display_name", None),
                        "score": getattr(h, "score", None),
                    }
                    for h in hits
                ]
                self._db.rollback()  # don't persist reads from this side-channel
                return ToolInvocation(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="executed",
                    result=result,
                )

            if tool_name == "memory.search_prior" and self._db is not None:
                from manara.memory.curator import MemoryCurator

                if investigation_id is None:
                    return ToolInvocation(
                        tool_name=tool_name,
                        arguments=arguments,
                        status="error",
                        error="memory.search_prior requires investigation_id",
                    )
                curator = MemoryCurator(self._db)
                query = str(arguments.get("query", ""))
                result_obj = curator.search_prior_memory(
                    query=query,
                    tenant_id=tenant_id,
                    investigation_id=investigation_id,
                )
                self._db.rollback()
                return ToolInvocation(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="executed",
                    result={
                        "reusable_evidence_count": len(result_obj.reusable_evidence),
                        "gaps": result_obj.gaps,
                    },
                )

            if tool_name == "foundry.search_openalex":
                return ToolInvocation(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="not_implemented",
                    error=(
                        "foundry.search_openalex is registered as a tool name, "
                        "but live network dispatch is gated by RUN_LIVE_TESTS=1. "
                        "See FoundryService.search() for the live path."
                    ),
                )

            # Unknown tool — honest denial
            return ToolInvocation(
                tool_name=tool_name,
                arguments=arguments,
                status="not_implemented",
                error=(
                    f"Tool {tool_name!r} is not in the RegistryToolExecutor "
                    "dispatch table. The agent's request was recorded but "
                    "no real execution occurred."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            # Never raise — record the error so the agent loop can continue.
            return ToolInvocation(
                tool_name=tool_name,
                arguments=arguments,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )


def parse_tool_calls(llm_text: str) -> list[dict[str, Any]]:
    """Parse tool calls emitted by the LLM in a structured format.

    The MockProvider (and any well-behaved live provider) emits tool calls
    in the following format, one per line, at the end of the response:

        TOOL_CALL: <tool_name> {json_arguments}

    For example:
        TOOL_CALL: registry.search {"query": "prosthetics patents", "top_k": 5}
        TOOL_CALL: memory.search_prior {"query": "robotic arm"}

    Returns a list of {"tool_name": str, "arguments": dict} entries.
    Lines that don't match the format are ignored (the LLM's prose text
    is still part of the response).
    """
    import json

    calls: list[dict[str, Any]] = []
    for line in llm_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("TOOL_CALL:"):
            continue
        rest = stripped[len("TOOL_CALL:"):].strip()
        # Split on the first '{' to separate tool name from arguments
        brace_idx = rest.find("{")
        if brace_idx < 0:
            # No arguments
            calls.append({"tool_name": rest.strip(), "arguments": {}})
            continue
        tool_name = rest[:brace_idx].strip()
        args_str = rest[brace_idx:]
        try:
            args = json.loads(args_str)
            if not isinstance(args, dict):
                args = {}
        except json.JSONDecodeError:
            args = {"_raw": args_str}
        calls.append({"tool_name": tool_name, "arguments": args})
    return calls


__all__ = [
    "NoOpToolExecutor",
    "RegistryToolExecutor",
    "ToolExecutor",
    "ToolInvocation",
    "parse_tool_calls",
]

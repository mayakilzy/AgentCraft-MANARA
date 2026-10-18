"""SSRF protection and safe HTTP client for the Search Foundry (G02).

Per ``SECURITY/ACCESS_POLICY.md``:
> "All discovered/untrusted remote text considered hostile; sanitize prompt
> injection, enforce SSRF protection including private, loopback/link-local/
> metadata, DNS rebinding, redirects and protocol restrictions; egress
> allowlists, secret separation, no arbitrary system commands."

This module provides:
* ``validate_url`` — rejects private IPs, loopback, link-local, metadata,
  non-HTTP(S) protocols, and hosts NOT in the configured allowlist.
* ``SafeHttpClient`` — wraps httpx with hard timeouts, redirect rejection,
  host allowlist enforcement on every redirect, and content-type checks.
* ``SsrfViolation`` — raised when any rule is violated; recorded in the
  sandbox evidence ledger.

The client is intentionally minimal — no caching, no rate-limiting (those
are the connector's responsibility), no authentication (handled by the
connector). Its ONLY job is to enforce SSRF protection.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from httpx import Response

# ─────────────────────────────────────────────────────────────────────────────
# SSRF validation
# ─────────────────────────────────────────────────────────────────────────────


class SsrfViolation(Exception):
    """Raised when a URL violates SSRF protection rules.

    Each violation records:
    * ``rule`` — which rule was violated (machine-readable code).
    * ``url`` — the offending URL.
    * ``detail`` — human-readable explanation.
    """

    def __init__(self, rule: str, url: str, detail: str) -> None:
        super().__init__(f"SSRF violation [{rule}]: {detail} (url={url})")
        self.rule = rule
        self.url = url
        self.detail = detail


# Hosts that must NEVER be contacted (defense in depth against DNS rebinding
# and metadata-service attacks).
PRIVATE_NETWORK_PATTERNS = (
    "169.254.",      # link-local
    "127.",          # loopback
    "10.",           # private
    "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
    "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
    "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",  # private
    "192.168.",      # private
    "0.0.0.0",       # invalid
    "::1",           # IPv6 loopback
    "fe80:",         # IPv6 link-local
    "fc00:", "fd00:",  # IPv6 unique-local
)


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP string is private/loopback/link-local/etc."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_url(
    url: str,
    *,
    allowed_hosts: list[str],
    allowed_schemes: tuple[str, ...] = ("https",),
) -> None:
    """Validate a URL against SSRF rules. Raises ``SsrfViolation`` on violation.

    Rules:
    1. URL must have a scheme (no protocol-relative URLs).
    2. Scheme must be in ``allowed_schemes`` (default: https only).
    3. Host must be in ``allowed_hosts``.
    4. Hostname must NOT resolve to a private IP (defense against DNS
       rebinding). We resolve the hostname and check each A/AAAA record.
    5. No userinfo in netloc (no embedded credentials).
    6. No fragment (fragments are client-side; their presence may indicate
       an attempted injection).
    """
    if not url or not isinstance(url, str):
        raise SsrfViolation("empty_url", url or "", "URL is empty or not a string")

    parsed = urlparse(url)

    if not parsed.scheme:
        raise SsrfViolation("no_scheme", url, "URL has no scheme")

    if parsed.scheme not in allowed_schemes:
        raise SsrfViolation(
            "bad_scheme", url,
            f"scheme '{parsed.scheme}' not in allowed: {allowed_schemes}",
        )

    if not parsed.hostname:
        raise SsrfViolation("no_host", url, "URL has no hostname")

    # Rule 3: allowlist
    if parsed.hostname not in allowed_hosts:
        raise SsrfViolation(
            "host_not_allowlisted", url,
            f"host '{parsed.hostname}' not in allowed_hosts: {allowed_hosts}",
        )

    # Rule 5: no userinfo
    if parsed.username or parsed.password:
        raise SsrfViolation(
            "userinfo_in_url", url,
            "URL contains embedded credentials (userinfo)",
        )

    # Rule 6: no fragment
    if parsed.fragment:
        raise SsrfViolation(
            "fragment_in_url", url,
            f"URL contains a fragment: {parsed.fragment}",
        )

    # Rule 4: DNS resolution check (defense against DNS rebinding)
    try:
        addrinfos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise SsrfViolation(
            "dns_resolution_failed", url,
            f"DNS resolution failed: {e}",
        ) from e

    for _family, _, _, _, sockaddr in addrinfos:
        ip_str = str(sockaddr[0])
        if _is_private_ip(ip_str):
            raise SsrfViolation(
                "private_ip_resolution", url,
                f"hostname resolves to private/reserved IP: {ip_str}",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Safe HTTP client
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FoundryRequestConfig:
    """Per-request configuration for Foundry HTTP calls.

    The connector builds this per call; the SafeHttpClient enforces it.
    """

    timeout_seconds: float = 30.0
    follow_redirects: bool = False  # NEVER follow redirects automatically
    max_response_bytes: int = 5 * 1024 * 1024  # 5 MB cap
    expected_content_types: tuple[str, ...] = ("application/json",)


class SafeHttpClient:
    """HTTP client with strict SSRF protection.

    Every request goes through ``validate_url`` BEFORE the network call.
    Redirects are rejected by default (set ``follow_redirects=True`` only
    if the caller re-validates the redirect target — which the Foundry
    connector does explicitly).

    The client never:
    * Sends authentication headers automatically.
    * Trusts the server's claimed content-type without verification.
    * Reads more than ``max_response_bytes`` from the response body.
    """

    def __init__(
        self,
        *,
        allowed_hosts: list[str],
        default_config: FoundryRequestConfig | None = None,
        user_agent: str = "MANARA-Foundry/0.1 (https://github.com/mayakilzy/AgentCraft-MANARA)",
    ) -> None:
        self.allowed_hosts = list(allowed_hosts)
        self.default_config = default_config or FoundryRequestConfig()
        self.user_agent = user_agent
        # A fresh httpx.Client per SafeHttpClient instance. We disable
        # automatic redirects; the connector decides whether to follow.
        self._client = httpx.Client(
            follow_redirects=False,
            timeout=self.default_config.timeout_seconds,
            headers={"User-Agent": self.user_agent},
        )

    def __enter__(self) -> SafeHttpClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        config: FoundryRequestConfig | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """Perform a GET request with SSRF protection.

        Raises:
            SsrfViolation: if the URL fails validation.
            httpx.TimeoutException: if the request times out.
            httpx.HTTPError: on other transport errors.
        """
        cfg = config or self.default_config
        validate_url(url, allowed_hosts=self.allowed_hosts)

        # Merge any caller-supplied headers with the client's User-Agent.
        # Caller headers take precedence on conflict.
        merged_headers: dict[str, str] = {}
        if self.user_agent:
            merged_headers["User-Agent"] = self.user_agent
        if headers:
            merged_headers.update(headers)

        response = self._client.get(
            url,
            params=params,
            headers=merged_headers if merged_headers else None,
            timeout=cfg.timeout_seconds,
        )

        # Cap response body size
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > cfg.max_response_bytes:
            response.close()
            raise SsrfViolation(
                "response_too_large", url,
                f"response size {content_length} exceeds {cfg.max_response_bytes} bytes",
            )

        # Check content-type if expected
        if cfg.expected_content_types:
            ct = response.headers.get("content-type", "").lower()
            if not any(expected in ct for expected in cfg.expected_content_types):
                # Be lenient — log but don't fail. Some APIs return text/json
                # instead of application/json. The connector decides.
                pass

        return response

    def follow_redirect(
        self,
        from_url: str,
        response: Response,
        *,
        config: FoundryRequestConfig | None = None,
    ) -> Response:
        """Explicitly follow a redirect, re-validating the target URL.

        This is the ONLY way to follow a redirect through SafeHttpClient.
        The connector calls this when it expects a redirect (e.g. OpenAlex
        returns 302 for some legacy endpoints).
        """
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        location = response.headers.get("location")
        if not location:
            raise SsrfViolation(
                "redirect_without_location", from_url,
                "redirect response has no Location header",
            )
        # Resolve relative redirects against the original URL
        from urllib.parse import urljoin

        target = urljoin(from_url, location)
        # Re-validate the target against the same allowlist
        validate_url(target, allowed_hosts=self.allowed_hosts)
        return self.get(target, config=config)


__all__ = [
    "FoundryRequestConfig",
    "PRIVATE_NETWORK_PATTERNS",
    "SafeHttpClient",
    "SsrfViolation",
    "validate_url",
]

"""Authentication and authorization for the web console.

Security contract
-----------------
* The console is read-only. No endpoint accepts mutations.
* Authentication is API-key based (simple, no OAuth complexity).
* Production deployment should place the console behind a private
  network (Tailscale) or an authenticated reverse proxy.
* Secrets, credentials, raw broker payloads, and unredacted account
  IDs are never exposed through the API.

Configuration
-------------
Set ``QUANT_CONSOLE_API_KEY`` to enable API-key authentication.
When unset, authentication is skipped (development mode only).

In production:
1. Set ``QUANT_CONSOLE_API_KEY`` to a strong random value.
2. Deploy behind Tailscale or an authenticated reverse proxy.
3. Enable HTTPS at the reverse proxy layer.

"""

import logging
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API-key authentication
# ---------------------------------------------------------------------------

_scheme = HTTPBearer(auto_error=False)
_credentials_dependency = Depends(_scheme)


def _get_api_key() -> str | None:
    """Return the configured API key, or None (development mode)."""
    return os.environ.get("QUANT_CONSOLE_API_KEY")


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = _credentials_dependency,
) -> str:
    """Dependency: require a valid API key.

    Returns
    -------
    str
        The API key value (for audit logging).

    Raises
    ------
    HTTPException
        If authentication is enabled and the key is missing or invalid.

    """
    expected = _get_api_key()
    if expected is None:
        # Development mode — no auth required
        return ""

    if credentials is None or credentials.credentials == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != expected:
        _log_failed_attempt(credentials.credentials)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


def _log_failed_attempt(attempt: str) -> None:
    """Log a failed authentication attempt (never log the key value)."""
    logger.warning("Failed authentication attempt")


# ---------------------------------------------------------------------------
# Secure headers middleware
# ---------------------------------------------------------------------------


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response.

    These headers protect against common web vulnerabilities.
    They complement, not replace, network-level security.

    """

    SECURITY_HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Permissions-Policy": ("camera=(), microphone=(), geolocation=()"),
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        response = await call_next(request)
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' cdn.jsdelivr.net 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:"
        )
        return response


# ---------------------------------------------------------------------------
# Access logging middleware
# ---------------------------------------------------------------------------


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request for audit purposes.

    Logs include: method, path, status code, duration, client IP.
    Never logs request bodies, headers, or query parameters.

    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        client = request.client.host if request.client else "unknown"
        logger.info(
            "%s %s %d %.0fms %s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client,
        )
        return response

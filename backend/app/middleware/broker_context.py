"""Subdomain-based broker context middleware."""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# Reserved slugs that map to platform context (not a broker)
PLATFORM_SLUGS = {"platform", "admin", "api", "localhost", "127"}


class BrokerContextMiddleware(BaseHTTPMiddleware):
    """
    Extract broker slug from Host header subdomain.
    Sets request.state.broker_slug and request.state.is_platform_request.

    Examples:
      broker1.yourdomain.com -> broker_slug="broker1", is_platform=False
      platform.yourdomain.com -> broker_slug=None, is_platform=True
      localhost:5173 -> broker_slug=None, is_platform=True (dev mode)
    """

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        # Strip port
        hostname = host.split(":")[0]

        # Extract subdomain (first part before first dot)
        parts = hostname.split(".")
        if len(parts) >= 3:
            # e.g. broker1.yourdomain.com
            slug = parts[0].lower()
        elif len(parts) == 2 and parts[1] not in ("localhost",):
            # e.g. broker1.example or with TLD
            slug = parts[0].lower()
        else:
            # localhost, 127.0.0.1, single-label hostname
            slug = None

        # Check if this is a platform request
        is_platform = slug is None or slug in PLATFORM_SLUGS

        request.state.broker_slug = None if is_platform else slug
        request.state.is_platform_request = is_platform

        response = await call_next(request)
        return response

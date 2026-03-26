"""Internal API versioning utilities.

Provides helpers to register /internal/v1/ aliases for existing
/internal/ routes, and a catch-all handler that returns 410 Gone
for unsupported versions (/internal/v{N}/ where N > 1).
"""
import logging
import re
from typing import List

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Current supported versions
SUPPORTED_VERSIONS: List[int] = [1]

# Regex to detect /internal/v{N}/ where N is a positive integer
_VERSION_PATTERN = re.compile(r"^/internal/v(\d+)/")


def register_v1_internal_aliases(app: FastAPI) -> None:
    """Register /internal/v1/ aliases for all existing /internal/ routes.

    Iterates over all registered routes with paths starting with
    /internal/ (excluding already-versioned ones) and creates
    duplicated routes under /internal/v1/.
    """
    routes_to_add = []

    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue

        # Only process /internal/ routes that are NOT already versioned
        if not path.startswith("/internal/"):
            continue
        if _VERSION_PATTERN.match(path):
            continue

        # Build v1 alias path: /internal/foo -> /internal/v1/foo
        suffix = path[len("/internal"):]  # e.g., /search/hybrid
        v1_path = f"/internal/v1{suffix}"

        # Clone the route with the new path
        route_copy = _clone_route(route, v1_path)
        if route_copy is not None:
            routes_to_add.append(route_copy)

    for r in routes_to_add:
        app.routes.append(r)

    logger.info(
        "Registered %d internal API v1 aliases", len(routes_to_add)
    )


def _clone_route(route, new_path: str):
    """Clone a FastAPI route with a new path."""
    from fastapi.routing import APIRoute

    if not isinstance(route, APIRoute):
        return None

    return APIRoute(
        path=new_path,
        endpoint=route.endpoint,
        methods=route.methods,
        name=f"{route.name}_v1" if route.name else None,
        response_model=route.response_model,
        dependencies=route.dependencies,
        tags=route.tags,
        responses=route.responses,
        response_class=route.response_class,
        response_model_include=route.response_model_include,
        response_model_exclude=route.response_model_exclude,
    )


def add_version_gone_handler(app: FastAPI) -> None:
    """Add middleware that returns 410 Gone for unsupported internal API versions.

    Any request matching /internal/v{N}/... where N is not in
    SUPPORTED_VERSIONS will receive a 410 Gone response with
    available version information.
    """

    @app.middleware("http")
    async def version_gone_middleware(
        request: Request, call_next
    ) -> Response:
        path = request.url.path
        match = _VERSION_PATTERN.match(path)
        if match:
            version = int(match.group(1))
            if version not in SUPPORTED_VERSIONS:
                return JSONResponse(
                    status_code=410,
                    content={
                        "detail": f"API version v{version} is not supported.",
                        "available_versions": [
                            f"v{v}" for v in SUPPORTED_VERSIONS
                        ],
                        "message": (
                            "Use /internal/v1/... or unversioned /internal/..."
                        ),
                    },
                )
        return await call_next(request)

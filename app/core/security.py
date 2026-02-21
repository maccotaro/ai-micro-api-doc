"""JWT authentication and authorization for Document Processing Gateway."""
import logging
from typing import Optional, Dict, Any, List, Tuple
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from jose.exceptions import JWKError

from app.core.config import settings

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_jwks() -> Dict[str, Any]:
    """Fetch JWKS from auth service (cached)."""
    try:
        response = httpx.get(settings.JWKS_URL, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )


def get_public_key(kid: str) -> Optional[Any]:
    """Get public key from JWKS by key ID."""
    jwks_data = get_jwks()
    for key_data in jwks_data.get("keys", []):
        if key_data.get("kid") == kid:
            try:
                return jwk.construct(key_data)
            except JWKError as e:
                logger.error(f"Failed to construct JWK: {e}")
                return None
    return None


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT token."""
    try:
        # Get unverified header to find key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing key ID",
            )

        # Get public key
        public_key = get_public_key(kid)
        if not public_key:
            # Clear cache and retry
            get_jwks.cache_clear()
            public_key = get_public_key(kid)

        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown signing key",
            )

        # Decode token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """Get current user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    return {
        "user_id": payload.get("sub"),
        "roles": payload.get("roles", []),
        "permissions": payload.get("permissions", []),
        "tenant_id": payload.get("tenant_id"),
        "department": payload.get("department"),
        "clearance_level": payload.get("clearance_level"),
    }


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require admin role."""
    roles = current_user.get("roles", [])
    if "admin" not in roles and "super_admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def get_access_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Get raw access token from request."""
    if credentials:
        return credentials.credentials
    return None


def require_permission(resource: str, action: str):
    """Resource x action permission check using JWT permissions array."""
    def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        required = f"{resource}:{action}"
        user_permissions = current_user.get("permissions", [])

        resource_wildcard = f"{resource}:*"
        global_wildcard = "*:*"

        if (
            required in user_permissions
            or resource_wildcard in user_permissions
            or global_wildcard in user_permissions
        ):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {required}",
        )
    return permission_checker


def require_any_permission(permissions: List[Tuple[str, str]]):
    """Allow access if user has ANY of the listed (resource, action) permissions."""
    def checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_perms = set(current_user.get("permissions", []))
        required = {f"{r}:{a}" for r, a in permissions}
        if user_perms & required or "*:*" in user_perms:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    return checker

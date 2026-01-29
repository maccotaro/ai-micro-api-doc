"""Unit tests for app/core/security.py"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


class TestGetJwks:
    """Tests for get_jwks function."""

    @patch("app.core.security.httpx.get")
    @patch("app.core.security.get_jwks.cache_clear")
    def test_get_jwks_success(self, mock_cache_clear, mock_httpx_get, mock_jwks_response):
        """Should fetch JWKS from auth service."""
        from app.core.security import get_jwks

        # Clear the cache before test
        get_jwks.cache_clear()

        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks_response
        mock_response.raise_for_status = MagicMock()
        mock_httpx_get.return_value = mock_response

        result = get_jwks()

        assert result == mock_jwks_response
        mock_httpx_get.assert_called_once()

    @patch("app.core.security.httpx.get")
    def test_get_jwks_failure(self, mock_httpx_get):
        """Should raise HTTPException when JWKS fetch fails."""
        from app.core.security import get_jwks

        # Clear the cache before test
        get_jwks.cache_clear()

        mock_httpx_get.side_effect = Exception("Connection failed")

        with pytest.raises(HTTPException) as exc_info:
            get_jwks()

        assert exc_info.value.status_code == 503
        assert "Authentication service unavailable" in exc_info.value.detail


class TestGetPublicKey:
    """Tests for get_public_key function."""

    @patch("app.core.security.get_jwks")
    @patch("app.core.security.jwk.construct")
    def test_get_public_key_found(self, mock_construct, mock_get_jwks, mock_jwks_response):
        """Should return public key when kid matches."""
        from app.core.security import get_public_key

        mock_get_jwks.return_value = mock_jwks_response
        mock_key = MagicMock()
        mock_construct.return_value = mock_key

        result = get_public_key("test-key-id")

        assert result == mock_key

    @patch("app.core.security.get_jwks")
    def test_get_public_key_not_found(self, mock_get_jwks, mock_jwks_response):
        """Should return None when kid not found."""
        from app.core.security import get_public_key

        mock_get_jwks.return_value = mock_jwks_response

        result = get_public_key("unknown-key-id")

        assert result is None


class TestDecodeToken:
    """Tests for decode_token function."""

    @patch("app.core.security.jwt.get_unverified_header")
    def test_decode_token_missing_kid(self, mock_get_header):
        """Should raise HTTPException when kid is missing."""
        from app.core.security import decode_token

        mock_get_header.return_value = {}

        with pytest.raises(HTTPException) as exc_info:
            decode_token("test-token")

        assert exc_info.value.status_code == 401
        assert "Token missing key ID" in exc_info.value.detail

    @patch("app.core.security.jwt.get_unverified_header")
    @patch("app.core.security.get_public_key")
    @patch("app.core.security.get_jwks")
    def test_decode_token_unknown_key(self, mock_get_jwks, mock_get_public_key, mock_get_header):
        """Should raise HTTPException when signing key is unknown."""
        from app.core.security import decode_token

        mock_get_header.return_value = {"kid": "unknown-key"}
        mock_get_public_key.return_value = None
        mock_get_jwks.cache_clear = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            decode_token("test-token")

        assert exc_info.value.status_code == 401
        assert "Unknown signing key" in exc_info.value.detail


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self):
        """Should raise HTTPException when no credentials provided."""
        from app.core.security import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)

        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("app.core.security.decode_token")
    async def test_get_current_user_success(self, mock_decode_token, sample_jwt_payload):
        """Should return user info from valid token."""
        from app.core.security import get_current_user

        mock_decode_token.return_value = sample_jwt_payload
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

        result = await get_current_user(credentials)

        assert result["user_id"] == "test-user-123"
        assert result["roles"] == ["admin", "user"]
        assert result["tenant_id"] == "test-tenant-id"


class TestRequireAdmin:
    """Tests for require_admin function."""

    @pytest.mark.asyncio
    async def test_require_admin_with_admin_role(self):
        """Should pass when user has admin role."""
        from app.core.security import require_admin

        current_user = {"user_id": "test", "roles": ["admin"]}

        result = await require_admin(current_user)

        assert result == current_user

    @pytest.mark.asyncio
    async def test_require_admin_with_super_admin_role(self):
        """Should pass when user has super_admin role."""
        from app.core.security import require_admin

        current_user = {"user_id": "test", "roles": ["super_admin"]}

        result = await require_admin(current_user)

        assert result == current_user

    @pytest.mark.asyncio
    async def test_require_admin_without_admin_role(self):
        """Should raise HTTPException when user lacks admin role."""
        from app.core.security import require_admin

        current_user = {"user_id": "test", "roles": ["user"]}

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(current_user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail


class TestGetAccessToken:
    """Tests for get_access_token function."""

    def test_get_access_token_with_credentials(self):
        """Should return token when credentials provided."""
        from app.core.security import get_access_token

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")

        result = get_access_token(credentials)

        assert result == "test-token"

    def test_get_access_token_without_credentials(self):
        """Should return None when no credentials provided."""
        from app.core.security import get_access_token

        result = get_access_token(None)

        assert result is None

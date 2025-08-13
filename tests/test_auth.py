"""
Test suite for OIDC authentication functionality.

This module contains comprehensive tests for the authentication system
including token validation, OBO flow, and middleware integration.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import json
import httpx

from fastapi import Request
from fastapi.testclient import TestClient

from mcp_gateway.auth.models import (
    AuthConfig, 
    TokenClaims, 
    UserContext, 
    MCPServiceAuth,
    AuthStrategy
)
from mcp_gateway.auth.token_validator import TokenValidator
from mcp_gateway.auth.obo_service import OBOTokenService
from mcp_gateway.auth.middleware import AuthenticationMiddleware
from mcp_gateway.auth.exceptions import (
    TokenValidationError,
    TokenExchangeError,
    KeycloakConnectionError
)


@pytest.fixture
def auth_config():
    """Create test authentication configuration."""
    return AuthConfig(
        keycloak_server_url="https://keycloak.test.com",
        realm="test-realm",
        client_id="test-client",
        client_secret="test-secret",
        audience="test-audience",
        issuer="https://keycloak.test.com/realms/test-realm",
        jwks_cache_ttl=3600,
        enable_token_introspection=False,
        enable_obo=True,
        obo_cache_ttl=1800,
        clock_skew_tolerance=300,
        required_scopes=["mcp:read"]
    )


@pytest.fixture
def sample_token_claims():
    """Create sample token claims for testing."""
    exp_time = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    iat_time = int(datetime.utcnow().timestamp())
    
    return TokenClaims(
        sub="user-123",
        iss="https://keycloak.test.com/realms/test-realm",
        aud="test-audience",
        exp=exp_time,
        iat=iat_time,
        preferred_username="testuser",
        email="test@example.com",
        name="Test User",
        scope="openid profile mcp:read mcp:call",
        resource_access={
            "test-client": {
                "roles": ["user", "mcp-access"]
            }
        },
        realm_access={
            "roles": ["user"]
        }
    )


@pytest.fixture
def sample_jwt_token():
    """Create a sample JWT token string for testing."""
    # This is a dummy JWT token for testing - in real tests you might use a JWT library
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsImlzcyI6Imh0dHBzOi8va2V5Y2xvYWsudGVzdC5jb20vcmVhbG1zL3Rlc3QtcmVhbG0iLCJhdWQiOiJ0ZXN0LWF1ZGllbmNlIiwiZXhwIjoxNjcwMDAwMDAwLCJpYXQiOjE2Njk5OTY0MDAsInByZWZlcnJlZF91c2VybmFtZSI6InRlc3R1c2VyIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwibmFtZSI6IlRlc3QgVXNlciIsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgbWNwOnJlYWQgbWNwOmNhbGwifQ.dummy-signature"


class TestAuthConfig:
    """Test authentication configuration model."""
    
    def test_auth_config_creation(self, auth_config):
        """Test creating auth configuration."""
        assert auth_config.realm == "test-realm"
        assert auth_config.client_id == "test-client"
        assert auth_config.enable_obo is True
        
    def test_jwks_uri_property(self, auth_config):
        """Test JWKS URI generation."""
        expected = "https://keycloak.test.com/realms/test-realm/protocol/openid-connect/certs"
        assert auth_config.jwks_uri == expected
        
    def test_token_endpoint_property(self, auth_config):
        """Test token endpoint generation."""
        expected = "https://keycloak.test.com/realms/test-realm/protocol/openid-connect/token"
        assert auth_config.token_endpoint == expected
        
    def test_issuer_url_property(self, auth_config):
        """Test issuer URL generation."""
        expected = "https://keycloak.test.com/realms/test-realm"
        assert auth_config.issuer_url == expected


class TestTokenClaims:
    """Test token claims model."""
    
    def test_token_claims_creation(self, sample_token_claims):
        """Test creating token claims."""
        assert sample_token_claims.sub == "user-123"
        assert sample_token_claims.preferred_username == "testuser"
        assert sample_token_claims.email == "test@example.com"
        
    def test_scopes_property(self, sample_token_claims):
        """Test scopes extraction."""
        expected_scopes = ["openid", "profile", "mcp:read", "mcp:call"]
        assert sample_token_claims.scopes == expected_scopes
        
    def test_has_scope(self, sample_token_claims):
        """Test scope checking."""
        assert sample_token_claims.has_scope("mcp:read") is True
        assert sample_token_claims.has_scope("mcp:admin") is False
        
    def test_has_any_scope(self, sample_token_claims):
        """Test multiple scope checking."""
        assert sample_token_claims.has_any_scope(["mcp:read", "mcp:write"]) is True
        assert sample_token_claims.has_any_scope(["mcp:admin", "mcp:write"]) is False
        
    def test_get_client_roles(self, sample_token_claims):
        """Test client role extraction."""
        roles = sample_token_claims.get_client_roles("test-client")
        assert "user" in roles
        assert "mcp-access" in roles
        
    def test_get_realm_roles(self, sample_token_claims):
        """Test realm role extraction."""
        roles = sample_token_claims.get_realm_roles()
        assert "user" in roles
        
    def test_is_expired(self, sample_token_claims):
        """Test token expiration checking."""
        assert sample_token_claims.is_expired is False
        
        # Test with expired token
        sample_token_claims.exp = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
        assert sample_token_claims.is_expired is True


class TestUserContext:
    """Test user context model."""
    
    def test_user_context_from_claims(self, sample_token_claims):
        """Test creating user context from token claims."""
        user_context = UserContext.from_token_claims(sample_token_claims)
        
        assert user_context.user_id == "user-123"
        assert user_context.username == "testuser"
        assert user_context.email == "test@example.com"
        assert "mcp:read" in user_context.scopes
        assert "user" in user_context.roles
        
    def test_has_scope(self, sample_token_claims):
        """Test scope checking in user context."""
        user_context = UserContext.from_token_claims(sample_token_claims)
        
        assert user_context.has_scope("mcp:read") is True
        assert user_context.has_scope("mcp:admin") is False
        
    def test_has_role(self, sample_token_claims):
        """Test role checking in user context."""
        user_context = UserContext.from_token_claims(sample_token_claims)
        
        assert user_context.has_role("user") is True
        assert user_context.has_role("admin") is False


class TestTokenValidator:
    """Test token validation functionality."""
    
    @pytest.mark.asyncio
    async def test_token_validator_initialization(self, auth_config):
        """Test token validator initialization."""
        validator = TokenValidator(auth_config)
        
        assert validator.config == auth_config
        assert validator._jwks_cache is None
        
        await validator.close()
        
    @pytest.mark.asyncio
    @patch('mcp_gateway.auth.token_validator.httpx.AsyncClient')
    async def test_get_jwks_success(self, mock_client, auth_config):
        """Test successful JWKS retrieval."""
        # Mock JWKS response
        mock_jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-key-id",
                    "n": "test-modulus",
                    "e": "AQAB"
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        
        mock_http_client = AsyncMock()
        mock_http_client.get.return_value = mock_response
        mock_client.return_value = mock_http_client
        
        validator = TokenValidator(auth_config)
        validator.http_client = mock_http_client
        
        with patch('mcp_gateway.auth.token_validator.JsonWebKey') as mock_jwk:
            mock_jwk.import_key_set.return_value = mock_jwks
            
            result = await validator._get_jwks()
            
            assert result == mock_jwks
            mock_http_client.get.assert_called_once_with(auth_config.jwks_uri)
            
        await validator.close()
        
    @pytest.mark.asyncio
    @patch('mcp_gateway.auth.token_validator.httpx.AsyncClient')
    async def test_get_jwks_failure(self, mock_client, auth_config):
        """Test JWKS retrieval failure."""
        mock_http_client = AsyncMock()
        mock_http_client.get.side_effect = httpx.HTTPError("Connection failed")
        mock_client.return_value = mock_http_client
        
        validator = TokenValidator(auth_config)
        validator.http_client = mock_http_client
        
        with pytest.raises(KeycloakConnectionError):
            await validator._get_jwks()
            
        await validator.close()
        
    @pytest.mark.asyncio
    async def test_validate_claims_success(self, auth_config, sample_token_claims):
        """Test successful claim validation."""
        validator = TokenValidator(auth_config)
        
        claims_dict = sample_token_claims.model_dump()
        
        # This should not raise any exceptions
        await validator._validate_claims(claims_dict)
        
        await validator.close()
        
    @pytest.mark.asyncio
    async def test_validate_claims_expired_token(self, auth_config):
        """Test claim validation with expired token."""
        validator = TokenValidator(auth_config)
        
        expired_claims = {
            "exp": int((datetime.utcnow() - timedelta(hours=1)).timestamp()),
            "iss": auth_config.issuer,
            "aud": auth_config.audience
        }
        
        with pytest.raises(TokenValidationError, match="Token has expired"):
            await validator._validate_claims(expired_claims)
            
        await validator.close()
        
    @pytest.mark.asyncio
    async def test_validate_claims_invalid_issuer(self, auth_config):
        """Test claim validation with invalid issuer."""
        validator = TokenValidator(auth_config)
        
        exp_time = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        invalid_claims = {
            "exp": exp_time,
            "iss": "https://wrong-issuer.com",
            "aud": auth_config.audience
        }
        
        with pytest.raises(TokenValidationError, match="Invalid issuer"):
            await validator._validate_claims(invalid_claims)
            
        await validator.close()


class TestOBOService:
    """Test On-Behalf-Of token service."""
    
    @pytest.mark.asyncio
    async def test_obo_service_initialization(self, auth_config):
        """Test OBO service initialization."""
        obo_service = OBOTokenService(auth_config)
        
        assert obo_service.config == auth_config
        assert len(obo_service._token_cache) == 0
        
        await obo_service.close()
        
    @pytest.mark.asyncio
    @patch('mcp_gateway.auth.obo_service.httpx.AsyncClient')
    async def test_exchange_token_success(self, mock_client, auth_config, sample_token_claims, sample_jwt_token):
        """Test successful token exchange."""
        # Mock token exchange response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-service-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        mock_client.return_value = mock_http_client
        
        obo_service = OBOTokenService(auth_config)
        obo_service.http_client = mock_http_client
        
        service_config = MCPServiceAuth(
            service_id="test-service",
            target_audience="test-service-audience",
            required_scopes=["mcp:call"],
            auth_strategy=AuthStrategy.OBO_REQUIRED
        )
        
        result = await obo_service._exchange_token(
            sample_jwt_token,
            sample_token_claims,
            service_config
        )
        
        assert result == "new-service-token"
        mock_http_client.post.assert_called_once()
        
        await obo_service.close()
        
    @pytest.mark.asyncio
    @patch('mcp_gateway.auth.obo_service.httpx.AsyncClient')
    async def test_exchange_token_failure(self, mock_client, auth_config, sample_token_claims, sample_jwt_token):
        """Test token exchange failure."""
        # Mock token exchange error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Token exchange failed"
        }
        
        mock_http_client = AsyncMock()
        mock_http_client.post.return_value = mock_response
        mock_client.return_value = mock_http_client
        
        obo_service = OBOTokenService(auth_config)
        obo_service.http_client = mock_http_client
        
        service_config = MCPServiceAuth(
            service_id="test-service",
            auth_strategy=AuthStrategy.PASSTHROUGH
        )
        
        with pytest.raises(TokenExchangeError):
            await obo_service._exchange_token(
                sample_jwt_token,
                sample_token_claims,
                service_config
            )
            
        await obo_service.close()
        
    @pytest.mark.asyncio
    async def test_get_service_token_with_passthrough(self, auth_config, sample_token_claims, sample_jwt_token):
        """Test service token retrieval with passthrough enabled."""
        obo_service = OBOTokenService(auth_config)
        
        service_config = MCPServiceAuth(
            service_id="test-service",
            auth_strategy=AuthStrategy.PASSTHROUGH
        )
        
        result = await obo_service.get_service_token(
            sample_jwt_token,
            sample_token_claims,
            service_config
        )
        
        assert result == sample_jwt_token
        
        await obo_service.close()
        
    @pytest.mark.asyncio
    async def test_cache_functionality(self, auth_config):
        """Test token caching functionality."""
        obo_service = OBOTokenService(auth_config)
        
        cache_key = "test-key"
        test_token = "test-token"
        
        # Test caching
        await obo_service._cache_token(cache_key, test_token)
        
        # Test retrieval
        cached_token = await obo_service._get_cached_token(cache_key)
        assert cached_token == test_token
        
        await obo_service.close()


class TestAuthenticationMiddleware:
    """Test authentication middleware."""
    
    def test_middleware_initialization(self, auth_config):
        """Test middleware initialization."""
        app = Mock()
        middleware = AuthenticationMiddleware(app, auth_config)
        
        assert middleware.auth_config == auth_config
        assert "/" in middleware.public_endpoints
        assert "/health" in middleware.public_endpoints
        
    def test_extract_bearer_token_success(self, auth_config):
        """Test successful bearer token extraction."""
        app = Mock()
        middleware = AuthenticationMiddleware(app, auth_config)
        
        # Mock request with Authorization header
        request = Mock()
        request.headers.get.return_value = "Bearer test-token-here"
        
        token = middleware._extract_bearer_token(request)
        assert token == "test-token-here"
        
    def test_extract_bearer_token_missing(self, auth_config):
        """Test bearer token extraction with missing header."""
        app = Mock()
        middleware = AuthenticationMiddleware(app, auth_config)
        
        # Mock request without Authorization header
        request = Mock()
        request.headers.get.return_value = None
        
        token = middleware._extract_bearer_token(request)
        assert token is None
        
    def test_extract_bearer_token_invalid_format(self, auth_config):
        """Test bearer token extraction with invalid format."""
        app = Mock()
        middleware = AuthenticationMiddleware(app, auth_config)
        
        # Mock request with invalid Authorization header
        request = Mock()
        request.headers.get.return_value = "Invalid format"
        
        token = middleware._extract_bearer_token(request)
        assert token is None
        
    def test_is_public_endpoint(self, auth_config):
        """Test public endpoint checking."""
        app = Mock()
        middleware = AuthenticationMiddleware(app, auth_config)
        
        assert middleware._is_public_endpoint("/") is True
        assert middleware._is_public_endpoint("/health") is True
        assert middleware._is_public_endpoint("/api/v1/health") is True
        assert middleware._is_public_endpoint("/docs") is True
        assert middleware._is_public_endpoint("/api/v1/services") is False


class TestMCPServiceAuth:
    """Test MCP service authentication configuration."""
    
    def test_service_auth_creation(self):
        """Test creating service auth configuration."""
        service_auth = MCPServiceAuth(
            service_id="test-service",
            target_audience="test-audience",
            required_scopes=["mcp:read", "mcp:call"],
            auth_strategy=AuthStrategy.OBO_REQUIRED,
            custom_headers={"X-Custom": "value"}
        )
        
        assert service_auth.service_id == "test-service"
        assert service_auth.target_audience == "test-audience"
        assert "mcp:read" in service_auth.required_scopes
        assert service_auth.auth_strategy == AuthStrategy.OBO_REQUIRED
        assert service_auth.custom_headers["X-Custom"] == "value"


# Integration Tests
class TestAuthenticationIntegration:
    """Integration tests for the authentication system."""
    
    @pytest.mark.asyncio
    async def test_full_authentication_flow(self, auth_config, sample_token_claims, sample_jwt_token):
        """Test complete authentication flow."""
        # This would be a more comprehensive integration test
        # that tests the entire flow from token to authenticated request
        pass
        
    @pytest.mark.asyncio 
    async def test_error_handling_chain(self, auth_config):
        """Test error handling throughout the authentication chain."""
        # Test various error scenarios and ensure proper error propagation
        pass

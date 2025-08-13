"""
Authentication middleware for FastAPI.

This module provides FastAPI middleware for OIDC authentication,
handling token extraction, validation, and user context creation.
"""

import logging
from typing import Callable, Optional
import traceback

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .token_validator import TokenValidator
from .models import AuthConfig, UserContext
from .exceptions import (
    AuthenticationError,
    TokenValidationError,
    KeycloakConnectionError
)

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for OIDC authentication.
    
    This middleware:
    1. Extracts Bearer tokens from Authorization headers
    2. Validates tokens using the TokenValidator
    3. Creates user context for authenticated requests
    4. Returns 401 for authentication failures
    5. Skips authentication for health and documentation endpoints
    """
    
    def __init__(self, app, auth_config: AuthConfig):
        """
        Initialize the authentication middleware.
        
        Args:
            app: FastAPI application instance
            auth_config: Authentication configuration
        """
        super().__init__(app)
        self.auth_config = auth_config
        self.token_validator = TokenValidator(auth_config)
        
        # Endpoints that don't require authentication
        self.public_endpoints = {
            "/",
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
        
        logger.info(
            "Authentication middleware initialized",
            extra={
                "realm": auth_config.realm,
                "public_endpoints": len(self.public_endpoints)
            }
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process incoming requests and handle authentication.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in the chain
            
        Returns:
            Response: HTTP response
        """
        # Skip authentication for public endpoints
        if self._is_public_endpoint(request.url.path):
            logger.debug(f"Skipping authentication for public endpoint: {request.url.path}")
            return await call_next(request)
        
        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        try:
            # Extract and validate token
            user_context = await self._authenticate_request(request)
            
            if user_context:
                # Add user context to request state
                request.state.user = user_context
                request.state.authenticated = True
                
                logger.debug(
                    "Request authenticated successfully",
                    extra={
                        "user_id": user_context.user_id,
                        "username": user_context.username,
                        "path": request.url.path,
                        "method": request.method
                    }
                )
            else:
                # This shouldn't happen if authentication is working correctly
                logger.error("Authentication succeeded but no user context created")
                return self._create_error_response(
                    "Authentication failed",
                    status.HTTP_401_UNAUTHORIZED
                )
            
            # Continue to next middleware/handler
            response = await call_next(request)
            
            # Add authentication headers to response
            response.headers["X-Authenticated"] = "true"
            response.headers["X-User-ID"] = user_context.user_id
            
            return response
            
        except TokenValidationError as e:
            logger.warning(
                "Token validation failed",
                extra={
                    "error": str(e),
                    "path": request.url.path,
                    "method": request.method,
                    "remote_addr": request.client.host if request.client else None
                }
            )
            return self._create_error_response(
                "Invalid or expired token",
                status.HTTP_401_UNAUTHORIZED,
                error_code="token_invalid"
            )
            
        except KeycloakConnectionError as e:
            logger.error(
                "Keycloak connection error during authentication",
                extra={
                    "error": str(e),
                    "path": request.url.path,
                    "method": request.method
                }
            )
            return self._create_error_response(
                "Authentication service temporarily unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="auth_service_unavailable"
            )
            
        except AuthenticationError as e:
            logger.warning(
                "Authentication error",
                extra={
                    "error": str(e),
                    "error_code": e.error_code,
                    "path": request.url.path,
                    "method": request.method
                }
            )
            return self._create_error_response(
                str(e),
                status.HTTP_401_UNAUTHORIZED,
                error_code=e.error_code
            )
            
        except Exception as e:
            logger.error(
                "Unexpected error during authentication",
                extra={
                    "error": str(e),
                    "path": request.url.path,
                    "method": request.method,
                    "traceback": traceback.format_exc()
                },
                exc_info=True
            )
            return self._create_error_response(
                "Internal authentication error",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="auth_internal_error"
            )
    
    async def _authenticate_request(self, request: Request) -> Optional[UserContext]:
        """
        Authenticate a request and return user context.
        
        Args:
            request: HTTP request to authenticate
            
        Returns:
            Optional[UserContext]: User context if authentication succeeds
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Extract Bearer token from Authorization header
        token = self._extract_bearer_token(request)
        if not token:
            raise AuthenticationError("Missing or invalid Authorization header")
        
        # Validate the token
        token_claims = await self.token_validator.validate_token(token)
        
        # Create user context from validated claims
        user_context = UserContext.from_token_claims(token_claims)
        
        # Store original token in user context for potential OBO use
        request.state.access_token = token
        request.state.token_claims = token_claims
        
        return user_context
    
    def _extract_bearer_token(self, request: Request) -> Optional[str]:
        """
        Extract Bearer token from Authorization header.
        
        Args:
            request: HTTP request
            
        Returns:
            Optional[str]: Bearer token if present and valid format
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        
        # Check for Bearer token format
        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        token = parts[1].strip()
        return token if token else None
    
    def _is_public_endpoint(self, path: str) -> bool:
        """
        Check if an endpoint is public (doesn't require authentication).
        
        Args:
            path: Request path
            
        Returns:
            bool: True if endpoint is public
        """
        # Exact match for public endpoints
        if path in self.public_endpoints:
            return True
        
        # Check for documentation endpoints (in case of different mounting)
        doc_patterns = ["/docs", "/redoc", "/openapi.json"]
        for pattern in doc_patterns:
            if path.endswith(pattern):
                return True
        
        return False
    
    def _create_error_response(
        self,
        message: str,
        status_code: int,
        error_code: Optional[str] = None
    ) -> JSONResponse:
        """
        Create standardized error response.
        
        Args:
            message: Error message
            status_code: HTTP status code
            error_code: Optional error code for client handling
            
        Returns:
            JSONResponse: Error response
        """
        content = {
            "detail": message,
            "type": "authentication_error"
        }
        
        if error_code:
            content["error_code"] = error_code
        
        headers = {
            "WWW-Authenticate": f'Bearer realm="{self.auth_config.realm}"'
        }
        
        return JSONResponse(
            content=content,
            status_code=status_code,
            headers=headers
        )
    
    async def close(self) -> None:
        """Clean up resources."""
        await self.token_validator.close()
        logger.debug("Authentication middleware closed")


def get_current_user(request: Request) -> Optional[UserContext]:
    """
    Dependency function to get current authenticated user.
    
    This function can be used as a FastAPI dependency to access
    the current user context in route handlers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Optional[UserContext]: Current user context if authenticated
    """
    return getattr(request.state, 'user', None)


def require_authentication(request: Request) -> UserContext:
    """
    Dependency function that requires authentication.
    
    This function raises an HTTPException if the request is not authenticated.
    Use this for endpoints that absolutely require authentication.
    
    Args:
        request: FastAPI request object
        
    Returns:
        UserContext: Current user context
        
    Raises:
        HTTPException: If request is not authenticated
    """
    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def get_access_token(request: Request) -> Optional[str]:
    """
    Get the original access token from the request.
    
    This function can be used to access the original user token
    for OBO token exchange or other purposes.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Optional[str]: Original access token if available
    """
    return getattr(request.state, 'access_token', None)

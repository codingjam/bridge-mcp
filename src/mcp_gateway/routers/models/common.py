"""
Common API Models

Shared Pydantic models used across multiple API endpoints.
These models provide consistent response formats and common data structures.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    error_code: Optional[str] = Field(default=None, description="Error code for programmatic handling")


class SuccessResponse(BaseModel):
    """Standard success response format."""
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")


class HealthResponse(BaseModel):
    """Health check response format."""
    status: str = Field(..., description="Service health status")
    timestamp: str = Field(..., description="Health check timestamp")
    version: Optional[str] = Field(default=None, description="Service version")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional health details")


class StatusResponse(BaseModel):
    """General status response format."""
    status: str = Field(..., description="Operation status")
    message: Optional[str] = Field(default=None, description="Status message")
    timestamp: Optional[str] = Field(default=None, description="Status timestamp")


class PaginatedResponse(BaseModel):
    """Paginated response format for list endpoints."""
    items: List[Dict[str, Any]] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")


# Export all models
__all__ = [
    "ErrorResponse",
    "SuccessResponse",
    "HealthResponse", 
    "StatusResponse",
    "PaginatedResponse",
]

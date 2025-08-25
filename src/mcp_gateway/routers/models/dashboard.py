"""
Dashboard API Models

Pydantic models for dashboard management endpoints.
These models handle service configuration and management operations.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class ServiceCreateRequest(BaseModel):
    """Request model for creating a new service"""
    name: str = Field(..., min_length=1, description="Human-readable service name")
    description: Optional[str] = Field(default="", description="Service description")
    transport: str = Field(..., pattern="^(http|stdio)$", description="Transport protocol (http or stdio)")
    enabled: bool = Field(default=True, description="Whether service is enabled")
    
    # HTTP-specific fields
    endpoint: Optional[str] = Field(default=None, description="HTTP endpoint URL")
    timeout: Optional[float] = Field(default=30.0, ge=0.1, le=300.0, description="Request timeout in seconds")
    health_check_path: Optional[str] = Field(default="/health", description="Health check endpoint path")
    
    # STDIO-specific fields  
    command: Optional[List[str]] = Field(default=None, description="Command to execute for stdio transport")
    working_directory: Optional[str] = Field(default=None, description="Working directory for stdio command")
    
    # Authentication
    auth: Optional[Dict] = Field(default=None, description="Authentication configuration")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Service tags for categorization")


class ServiceCreateResponse(BaseModel):
    """Response model for service creation"""
    id: str = Field(..., description="Generated service ID")
    status: str = Field(..., description="Creation status")
    message: str = Field(..., description="Status message")


class ServiceDeleteResponse(BaseModel):
    """Response model for service deletion"""
    id: str = Field(..., description="Deleted service ID")
    status: str = Field(..., description="Deletion status")
    message: str = Field(..., description="Status message")


class ServiceInfo(BaseModel):
    """Service information model"""
    service_id: str = Field(..., description="Service identifier")
    name: str = Field(..., description="Service name")
    description: str = Field(..., description="Service description")
    connection_type: str = Field(..., description="Connection type (http/stdio)")
    status: str = Field(..., description="Service status")


class ServiceListResponse(BaseModel):
    """Response model for listing services"""
    services: List[ServiceInfo] = Field(..., description="List of registered services")


class ServiceTestRequest(BaseModel):
    """Request model for testing a service connection"""
    transport: str = Field(..., pattern="^(http|stdio)$", description="Transport protocol")
    endpoint: Optional[str] = Field(default=None, description="HTTP endpoint URL")
    command: Optional[List[str]] = Field(default=None, description="Command to execute for stdio transport")
    timeout: Optional[float] = Field(default=5.0, ge=0.1, le=60.0, description="Test timeout in seconds")


class ServiceTestResponse(BaseModel):
    """Response model for service connection test"""
    success: bool = Field(..., description="Whether the test was successful")
    message: str = Field(..., description="Test result message")
    response_time: Optional[float] = Field(default=None, description="Response time in seconds")
    details: Optional[Dict] = Field(default=None, description="Additional test details")


# Export all models
__all__ = [
    "ServiceCreateRequest",
    "ServiceCreateResponse",
    "ServiceDeleteResponse", 
    "ServiceTestRequest",
    "ServiceTestResponse",
]

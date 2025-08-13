"""
MCP Gateway Service Registry
Manages available MCP servers and their configurations with validation and type safety
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

logger = logging.getLogger(__name__)


class MCPService(BaseModel):
    """Configuration for an MCP server with comprehensive validation"""
    
    name: str = Field(..., min_length=1, description="Human-readable service name")
    description: str = Field(default="", description="Service description")
    endpoint: Union[HttpUrl, str] = Field(..., description="Service endpoint URL or command")
    transport: str = Field(default="http", pattern="^(http|stdio)$", description="Transport protocol")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")
    timeout: Optional[float] = Field(default=None, ge=0.1, le=300.0, description="Request timeout in seconds")
    enabled: bool = Field(default=True, description="Whether service is enabled")
    
    # HTTP-specific fields
    base_path: Optional[str] = Field(default=None, description="Base path to prepend to requests")
    
    # Stdio-specific fields
    command: Optional[List[str]] = Field(default=None, description="Command to execute for stdio transport")
    working_directory: Optional[str] = Field(default=None, description="Working directory for stdio command")
    environment: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")
    
    # Service metadata
    version: Optional[str] = Field(default=None, description="Service version")
    tags: List[str] = Field(default_factory=list, description="Service tags for categorization")
    
    @model_validator(mode='after')
    def validate_transport_config(self):
        """Validate configuration based on transport type"""
        transport = self.transport
        
        # Validate endpoint for HTTP transport
        if transport == 'http':
            endpoint = str(self.endpoint)
            if not (endpoint.startswith('http://') or endpoint.startswith('https://')):
                raise ValueError("HTTP endpoint must start with http:// or https://")
        
        # Validate command for stdio transport
        if transport == 'stdio' and not self.command:
            raise ValueError("Stdio transport requires a command to execute")
        elif transport == 'http' and self.command:
            logger.warning("Command specified for HTTP transport - will be ignored")
        
        return self
    
    class Config:
        """Pydantic configuration"""
        extra = "forbid"  # Reject unknown fields
        validate_assignment = True  # Validate on assignment


class GlobalConfig(BaseModel):
    """Global service configuration with production defaults"""
    
    # Timeout settings (in seconds)
    default_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    connect_timeout: float = Field(default=10.0, ge=1.0, le=60.0)
    read_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    write_timeout: float = Field(default=10.0, ge=1.0, le=60.0)
    pool_timeout: float = Field(default=5.0, ge=1.0, le=30.0)
    health_check_timeout: float = Field(default=5.0, ge=1.0, le=30.0)
    
    # Connection pool settings
    max_connections: int = Field(default=100, ge=1, le=1000)
    max_keepalive_connections: int = Field(default=20, ge=1, le=100)
    
    # Health check settings
    health_check_interval: int = Field(default=60, ge=10, le=3600, description="Seconds between health checks")
    enable_health_checks: bool = Field(default=True, description="Enable automatic health checking")
    
    # Service discovery settings
    enable_service_discovery: bool = Field(default=False, description="Enable dynamic service discovery")
    
    # Logging settings
    enable_request_logging: bool = Field(default=True, description="Log all requests")
    log_request_body: bool = Field(default=False, description="Include request body in logs (security risk)")
    log_response_body: bool = Field(default=False, description="Include response body in logs (security risk)")
    
    class Config:
        """Pydantic configuration"""
        extra = "forbid"
        validate_assignment = True


class ServiceRegistry:
    """Registry for managing MCP services with validation and lifecycle management"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/services.yaml")
        self.services: Dict[str, MCPService] = {}
        self.global_config = GlobalConfig()
        self._health_status: Dict[str, bool] = {}
        
    async def load_services(self) -> None:
        """
        Load services from configuration file with comprehensive error handling
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is malformed
            ValueError: If service configuration is invalid
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"Service config file not found: {self.config_path}")
                logger.info("Creating default configuration file...")
                await self._create_default_config()
                return
            
            logger.info(f"Loading services from {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                logger.warning("Empty configuration file")
                return
            
            # Load and validate global configuration
            if 'global' in config_data:
                try:
                    self.global_config = GlobalConfig(**config_data['global'])
                    logger.info("Loaded global configuration")
                except Exception as e:
                    logger.error(f"Invalid global configuration: {e}")
                    logger.info("Using default global configuration")
                    self.global_config = GlobalConfig()
            
            # Load and validate services
            if 'services' in config_data:
                loaded_count = 0
                for service_id, service_config in config_data['services'].items():
                    try:
                        service = MCPService(**service_config)
                        self.services[service_id] = service
                        self._health_status[service_id] = True  # Assume healthy initially
                        loaded_count += 1
                        
                        logger.info(
                            f"Loaded service: {service_id}",
                            extra={
                                "service_id": service_id,
                                "name": service.name,
                                "transport": service.transport,
                                "enabled": service.enabled
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to load service {service_id}: {e}")
                        continue
                
                logger.info(f"Successfully loaded {loaded_count} MCP services")
            else:
                logger.warning("No services section found in configuration")
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {self.config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load service registry: {e}")
            raise
    
    async def get_service(self, service_id: str) -> Optional[MCPService]:
        """Get service by ID with validation"""
        if not service_id:
            return None
        return self.services.get(service_id)
    
    async def get_all_services(self) -> Dict[str, MCPService]:
        """Get all registered services (copy to prevent external modification)"""
        return self.services.copy()
    
    async def get_enabled_services(self) -> Dict[str, MCPService]:
        """Get only enabled services"""
        return {
            service_id: service 
            for service_id, service in self.services.items() 
            if service.enabled
        }
    
    async def get_services_by_transport(self, transport: str) -> Dict[str, MCPService]:
        """Get services that support specific transport"""
        return {
            service_id: service 
            for service_id, service in self.services.items() 
            if service.transport == transport and service.enabled
        }
    
    async def get_services_by_tag(self, tag: str) -> Dict[str, MCPService]:
        """Get services that have a specific tag"""
        return {
            service_id: service 
            for service_id, service in self.services.items() 
            if tag in service.tags and service.enabled
        }
    
    async def add_service(self, service_id: str, service: MCPService) -> None:
        """
        Add or update a service (for dynamic registration)
        
        Args:
            service_id: Unique service identifier
            service: Service configuration
        """
        if not service_id:
            raise ValueError("Service ID cannot be empty")
        
        self.services[service_id] = service
        self._health_status[service_id] = True
        
        logger.info(
            f"Added/updated service: {service_id}",
            extra={
                "service_id": service_id,
                "name": service.name,
                "transport": service.transport
            }
        )
    
    async def remove_service(self, service_id: str) -> bool:
        """
        Remove a service
        
        Args:
            service_id: Service to remove
            
        Returns:
            True if service was removed, False if not found
        """
        if service_id in self.services:
            del self.services[service_id]
            self._health_status.pop(service_id, None)
            logger.info(f"Removed service: {service_id}")
            return True
        return False
    
    async def update_health_status(self, service_id: str, is_healthy: bool) -> None:
        """Update health status for a service"""
        if service_id in self.services:
            self._health_status[service_id] = is_healthy
    
    async def get_health_status(self, service_id: str) -> Optional[bool]:
        """Get health status for a service"""
        return self._health_status.get(service_id)
    
    async def get_all_health_status(self) -> Dict[str, bool]:
        """Get health status for all services"""
        return self._health_status.copy()
    
    def get_global_config(self) -> GlobalConfig:
        """Get global configuration"""
        return self.global_config
    
    async def _create_default_config(self) -> None:
        """Create a default configuration file"""
        default_config = {
            'global': {
                'default_timeout': 30.0,
                'health_check_interval': 60,
                'enable_health_checks': True,
                'max_connections': 100
            },
            'services': {
                'example-mcp-server': {
                    'name': 'Example MCP Server',
                    'description': 'Example HTTP MCP server for testing',
                    'endpoint': 'http://localhost:3000',
                    'transport': 'http',
                    'enabled': True,
                    'tags': ['example', 'test']
                }
            }
        }
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        
        logger.info(f"Created default configuration at {self.config_path}")

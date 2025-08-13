"""
MCP Gateway Service Registry
Manages available MCP servers and their configurations with validation and type safety
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

# Import authentication models
from ..auth.models import MCPServiceAuth, AuthStrategy

logger = logging.getLogger(__name__)


class MCPService(BaseModel):
    """Configuration for an MCP server with comprehensive validation"""
    
    name: str = Field(..., min_length=1, description="Human-readable service name")
    description: str = Field(default="", description="Service description")
    endpoint: Union[HttpUrl, str] = Field(..., description="Service endpoint URL or command")
    transport: str = Field(default="http", pattern="^(http|stdio)$", description="Transport protocol")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")
    timeout: Optional[float] = Field(default=30.0, ge=0.1, le=300.0, description="Request timeout in seconds")
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
    
    # Authentication configuration (raw YAML data)
    auth: Optional[Dict] = Field(default=None, description="Authentication configuration")
    
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
    """Global service configuration with simple defaults"""
    
    # Basic timeout settings
    default_timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Default request timeout")
    health_check_timeout: float = Field(default=5.0, ge=1.0, le=30.0, description="Health check timeout")
    health_check_interval: int = Field(default=60, ge=10, le=3600, description="Health check interval in seconds")
    
    # Service discovery
    enable_service_discovery: bool = Field(default=False, description="Enable dynamic service discovery")
    enable_health_checks: bool = Field(default=True, description="Enable periodic health checks")
    
    class Config:
        """Pydantic configuration"""
        extra = "forbid"
        validate_assignment = True


class ServiceRegistry:
    """Registry for managing MCP services with validation and lifecycle management"""
    
    def __init__(self, config_path: Optional[Path] = None, auth_config=None):
        self.config_path = config_path or Path("config/services.yaml")
        self.auth_config = auth_config  # Global auth configuration
        self.services: Dict[str, MCPService] = {}
        self.global_config = GlobalConfig()
        self._health_status: Dict[str, bool] = {}
        self._service_auth_configs: Dict[str, MCPServiceAuth] = {}
        
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
                        
                        # Load authentication configuration for this service
                        await self._load_service_auth_config(service_id, service)
                        
                        loaded_count += 1
                        
                        logger.info(
                            f"Loaded service: {service_id}",
                            extra={
                                "service_id": service_id,
                                "name": service.name,
                                "transport": service.transport,
                                "enabled": service.enabled,
                                "has_auth": service_id in self._service_auth_configs
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to load service {service_id}: {e}")
                        continue
                
                logger.info(f"Successfully loaded {loaded_count} MCP services")
                logger.info(f"Loaded authentication configs for {len(self._service_auth_configs)} services")
            else:
                logger.warning("No services section found in configuration")
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {self.config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load service registry: {e}")
            raise
    
    async def _load_service_auth_config(self, service_id: str, service: MCPService) -> None:
        """
        Load authentication configuration for a specific service.
        
        Args:
            service_id: The service identifier
            service: The service configuration object
        """
        if not service.auth:
            # No auth configuration - use default (no auth)
            self._service_auth_configs[service_id] = MCPServiceAuth(
                service_id=service_id,
                auth_strategy=AuthStrategy.NO_AUTH
            )
            return
        
        try:
            auth_config = service.auth
            
            # Extract auth strategy (with fallback to no_auth)
            strategy_str = auth_config.get("strategy", "no_auth")
            try:
                auth_strategy = AuthStrategy(strategy_str)
            except ValueError:
                logger.warning(f"Invalid auth strategy '{strategy_str}' for service {service_id}, using no_auth")
                auth_strategy = AuthStrategy.NO_AUTH
            
            # Create MCPServiceAuth object
            service_auth = MCPServiceAuth(
                service_id=service_id,
                auth_strategy=auth_strategy,
                target_audience=auth_config.get("target_audience"),
                required_scopes=auth_config.get("required_scopes", []),
                custom_headers=auth_config.get("custom_headers", {}),
                obo_client_id=auth_config.get("obo_client_id"),
                obo_client_secret=auth_config.get("obo_client_secret")
            )
            
            self._service_auth_configs[service_id] = service_auth
            
            logger.info(
                f"Loaded auth config for service {service_id}",
                extra={
                    "service_id": service_id,
                    "auth_strategy": auth_strategy.value,
                    "target_audience": service_auth.target_audience,
                    "has_custom_headers": bool(service_auth.custom_headers),
                    "required_scopes_count": len(service_auth.required_scopes)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to load auth config for service {service_id}: {e}")
            # Fallback to no auth
            self._service_auth_configs[service_id] = MCPServiceAuth(
                service_id=service_id,
                auth_strategy=AuthStrategy.NO_AUTH
            )
    
    async def get_service(self, service_id: str) -> Optional[MCPService]:
        """Get service by ID with validation"""
        if not service_id:
            return None
        return self.services.get(service_id)
    
    async def get_service_auth(self, service_id: str) -> Optional[MCPServiceAuth]:
        """
        Get authentication configuration for a specific service.
        
        Args:
            service_id: The service identifier
            
        Returns:
            MCPServiceAuth object if found, None otherwise
        """
        return self._service_auth_configs.get(service_id)
    
    async def get_all_service_auth_configs(self) -> Dict[str, MCPServiceAuth]:
        """Get all service authentication configurations (copy to prevent modification)"""
        return self._service_auth_configs.copy()
    
    async def get_services_with_auth_strategy(self, strategy: AuthStrategy) -> Dict[str, MCPService]:
        """
        Get services that use a specific authentication strategy.
        
        Args:
            strategy: The authentication strategy to filter by
            
        Returns:
            Dictionary of service_id -> MCPService for services using the strategy
        """
        matching_services = {}
        for service_id, auth_config in self._service_auth_configs.items():
            if auth_config.auth_strategy == strategy and service_id in self.services:
                service = self.services[service_id]
                if service.enabled:
                    matching_services[service_id] = service
        return matching_services
    
    async def update_service_auth(self, service_id: str, auth_config: MCPServiceAuth) -> bool:
        """
        Update authentication configuration for a service (for dynamic updates).
        
        Args:
            service_id: The service identifier
            auth_config: New authentication configuration
            
        Returns:
            True if updated successfully, False if service not found
        """
        if service_id in self.services:
            self._service_auth_configs[service_id] = auth_config
            logger.info(
                f"Updated auth config for service {service_id}",
                extra={
                    "service_id": service_id,
                    "auth_strategy": auth_config.auth_strategy.value
                }
            )
            return True
        return False
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
        """Create a default configuration file with authentication examples"""
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
                    'tags': ['example', 'test'],
                    'auth': {
                        'strategy': 'no_auth'
                    }
                },
                'secure-analytics-server': {
                    'name': 'Secure Analytics Server',
                    'description': 'Analytics server requiring OBO authentication',
                    'endpoint': 'https://analytics.company.com',
                    'transport': 'http',
                    'enabled': False,  # Disabled by default
                    'tags': ['analytics', 'secure'],
                    'auth': {
                        'strategy': 'obo_required',
                        'target_audience': 'analytics-api',
                        'required_scopes': ['analytics:read', 'analytics:write'],
                        'custom_headers': {
                            'X-Service-Name': 'mcp-gateway',
                            'X-Version': '1.0.0'
                        }
                    }
                },
                'legacy-passthrough-server': {
                    'name': 'Legacy Passthrough Server',
                    'description': 'Legacy server that accepts user tokens directly',
                    'endpoint': 'https://legacy.company.com',
                    'transport': 'http',
                    'enabled': False,  # Disabled by default
                    'tags': ['legacy'],
                    'auth': {
                        'strategy': 'passthrough',
                        'custom_headers': {
                            'X-Gateway': 'mcp-gateway'
                        }
                    }
                }
            }
        }
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        
        logger.info(f"Created default configuration with auth examples at {self.config_path}")

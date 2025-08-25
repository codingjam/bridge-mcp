"""
Service Registry MCP Adapter

Adapts the existing ServiceRegistry configuration system to work with
the MCP Client, bridging services.yaml configuration with MCP SDK.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..core.service_registry import ServiceRegistry, MCPService
from .transport_factory import MCPTransportFactory
from .session_manager import MCPSessionConfig
from .exceptions import MCPClientError, MCPConnectionError


logger = logging.getLogger(__name__)


class ServiceRegistryMCPAdapter:
    """
    Adapter that bridges ServiceRegistry with MCP Client functionality.
    
    This class converts services.yaml configurations into MCP client
    transport configurations and session configs.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        """
        Initialize adapter with existing ServiceRegistry.
        
        Args:
            service_registry: Existing ServiceRegistry instance
        """
        self.service_registry = service_registry
    
    def get_transport_config(self, service_id: str) -> Dict[str, Any]:
        """
        Convert ServiceRegistry service config to MCP transport config.
        
        Args:
            service_id: Service identifier from services.yaml
            
        Returns:
            Transport configuration dictionary for MCPTransportFactory
            
        Raises:
            MCPClientError: If service not found or invalid configuration
        """
        service = self.service_registry.services.get(service_id)
        if not service:
            raise MCPClientError(
                f"Service '{service_id}' not found in registry",
                details={"service_id": service_id}
            )
        
        if not service.enabled:
            raise MCPClientError(
                f"Service '{service_id}' is disabled",
                details={"service_id": service_id, "enabled": service.enabled}
            )
        
        if service.transport == "http":
            return self._convert_http_service(service)
        elif service.transport == "stdio":
            return self._convert_stdio_service(service)
        else:
            raise MCPClientError(
                f"Unsupported transport type: {service.transport}",
                details={"service_id": service_id, "transport": service.transport}
            )
    
    def _convert_http_service(self, service: MCPService) -> Dict[str, Any]:
        """Convert HTTP service to transport config."""
        config = {
            "type": "http",
            "url": str(service.endpoint),
            "timeout": service.timeout
        }
        
        # Add custom headers if available
        auth_config = self.service_registry._service_auth_configs.get(
            service.name,  # Using service name as key - may need adjustment
            None
        )
        
        if auth_config and auth_config.custom_headers:
            config["headers"] = auth_config.custom_headers
        
        return config
    
    def _convert_stdio_service(self, service: MCPService) -> Dict[str, Any]:
        """Convert stdio service to transport config."""
        if not service.command:
            raise MCPClientError(
                f"Stdio service '{service.name}' missing command configuration",
                details={"service_name": service.name}
            )
        
        config = {
            "type": "stdio",
            "command": service.command[0],
            "args": service.command[1:] if len(service.command) > 1 else None
        }
        
        # Add working directory if available
        if hasattr(service, 'working_directory') and service.working_directory:
            config["cwd"] = service.working_directory
        
        # Add environment variables if available  
        if hasattr(service, 'environment') and service.environment:
            config["env"] = service.environment
        
        return config
    
    def get_session_config(
        self, 
        service_id: str, 
        session_id: Optional[str] = None
    ) -> MCPSessionConfig:
        """
        Create MCP session config from ServiceRegistry service.
        
        Args:
            service_id: Service identifier from services.yaml
            session_id: Optional custom session ID
            
        Returns:
            MCPSessionConfig for the service
            
        Raises:
            MCPClientError: If service not found or invalid
        """
        service = self.service_registry.services.get(service_id)
        if not service:
            raise MCPClientError(
                f"Service '{service_id}' not found in registry",
                details={"service_id": service_id}
            )
        
        transport_config = self.get_transport_config(service_id)
        
        # Use service timeout or global default
        timeout = service.timeout or self.service_registry.global_config.default_timeout
        
        return MCPSessionConfig(
            session_id=session_id or f"{service_id}_{service.name}",
            server_name=service.name,
            transport_config=transport_config,
            max_retries=3,  # Could be made configurable
            retry_delay=1.0,
            session_timeout=timeout * 10,  # Session timeout longer than request timeout
            heartbeat_interval=self.service_registry.global_config.health_check_interval,
            auto_reconnect=True
        )
    
    def list_enabled_services(self) -> List[str]:
        """
        List all enabled MCP services from the registry.
        
        Returns:
            List of enabled service IDs
        """
        return [
            service_id 
            for service_id, service in self.service_registry.services.items()
            if service.enabled
        ]
    
    def get_service_info(self, service_id: str) -> Dict[str, Any]:
        """
        Get comprehensive service information.
        
        Args:
            service_id: Service identifier
            
        Returns:
            Service information dictionary
            
        Raises:
            MCPClientError: If service not found
        """
        service = self.service_registry.services.get(service_id)
        if not service:
            raise MCPClientError(
                f"Service '{service_id}' not found in registry",
                details={"service_id": service_id}
            )
        
        # Get auth config if available
        auth_config = self.service_registry._service_auth_configs.get(service_id)
        
        return {
            "service_id": service_id,
            "name": service.name,
            "description": service.description,
            "endpoint": str(service.endpoint),
            "transport": service.transport,
            "enabled": service.enabled,
            "timeout": service.timeout,
            "health_check_path": service.health_check_path,
            "has_auth": auth_config is not None,
            "auth_strategy": auth_config.auth_strategy.value if auth_config else None,
            "required_scopes": auth_config.required_scopes if auth_config else [],
            "custom_headers": auth_config.custom_headers if auth_config else {}
        }
    
    def validate_service_for_mcp(self, service_id: str) -> bool:
        """
        Validate that a service is properly configured for MCP.
        
        Args:
            service_id: Service identifier
            
        Returns:
            True if service is valid for MCP, False otherwise
        """
        try:
            service = self.service_registry.services.get(service_id)
            if not service:
                logger.error(f"Service {service_id} not found")
                return False
            
            if not service.enabled:
                logger.warning(f"Service {service_id} is disabled")
                return False
            
            # Validate transport-specific requirements
            if service.transport == "stdio":
                if not service.command:
                    logger.error(f"Stdio service {service_id} missing command")
                    return False
            elif service.transport == "http":
                if not service.endpoint:
                    logger.error(f"HTTP service {service_id} missing endpoint")
                    return False
            else:
                logger.error(f"Unsupported transport: {service.transport}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validation error for service {service_id}: {e}")
            return False
    
    def get_health_status(self, service_id: str) -> bool:
        """
        Get health status from ServiceRegistry.
        
        Args:
            service_id: Service identifier
            
        Returns:
            True if service is healthy, False otherwise
        """
        return self.service_registry._health_status.get(service_id, False)
    
    def list_services_by_transport(self, transport_type: str) -> List[str]:
        """
        List services by transport type.
        
        Args:
            transport_type: Transport type ("http" or "stdio")
            
        Returns:
            List of service IDs with the specified transport
        """
        return [
            service_id
            for service_id, service in self.service_registry.services.items()
            if service.transport == transport_type and service.enabled
        ]
    
    def get_global_config(self) -> Dict[str, Any]:
        """
        Get global configuration from ServiceRegistry.
        
        Returns:
            Global configuration dictionary
        """
        return {
            "default_timeout": self.service_registry.global_config.default_timeout,
            "health_check_timeout": self.service_registry.global_config.health_check_timeout,
            "health_check_interval": self.service_registry.global_config.health_check_interval,
            "enable_service_discovery": self.service_registry.global_config.enable_service_discovery,
            "enable_health_checks": self.service_registry.global_config.enable_health_checks
        }
    
    async def reload_services(self) -> None:
        """
        Reload services from services.yaml file.
        
        This allows dynamic configuration updates without restart.
        """
        try:
            await self.service_registry.load_services()
            logger.info("Successfully reloaded services from configuration")
        except Exception as e:
            logger.error(f"Failed to reload services: {e}")
            raise MCPClientError(
                f"Failed to reload services: {str(e)}",
                details={"error": str(e)}
            )


# Convenience functions for common operations
def create_mcp_adapter(config_path: Optional[Path] = None) -> ServiceRegistryMCPAdapter:
    """
    Create an MCP adapter with a new ServiceRegistry instance.
    
    Args:
        config_path: Optional path to services.yaml file
        
    Returns:
        ServiceRegistryMCPAdapter instance
    """
    service_registry = ServiceRegistry(config_path=config_path)
    return ServiceRegistryMCPAdapter(service_registry)


async def get_mcp_transport_configs(
    adapter: ServiceRegistryMCPAdapter,
    service_ids: Optional[List[str]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Get transport configurations for multiple services.
    
    Args:
        adapter: ServiceRegistryMCPAdapter instance
        service_ids: Optional list of service IDs (if None, gets all enabled)
        
    Returns:
        Dictionary mapping service_id -> transport_config
    """
    if service_ids is None:
        service_ids = adapter.list_enabled_services()
    
    configs = {}
    for service_id in service_ids:
        try:
            if adapter.validate_service_for_mcp(service_id):
                configs[service_id] = adapter.get_transport_config(service_id)
        except Exception as e:
            logger.warning(f"Failed to get config for service {service_id}: {e}")
    
    return configs

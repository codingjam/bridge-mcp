# OIDC Authentication with Keycloak - Setup Guide

> **Production-ready setup guide for OIDC authentication with Keycloak**

## Status

**✅ Production Ready**: This setup guide reflects the implemented and tested authentication system. All configurations described here are operational and production-ready as of Phase 1 completion.

**🔐 Security Features**: Includes JWT validation, token caching, On-Behalf-Of flow, and comprehensive security monitoring.

This document provides step-by-step instructions for configuring OIDC authentication with Keycloak for the MCP Gateway.

## Overview

The MCP Gateway supports OIDC (OpenID Connect) authentication using Keycloak as the identity provider. The authentication flow includes:

1. **Client Authentication**: Users authenticate with Keycloak and receive access tokens
2. **Token Validation**: Gateway validates tokens using Keycloak's JWKS endpoint
3. **On-Behalf-Of (OBO)**: Gateway exchanges user tokens for service-specific tokens
4. **Service Authentication**: Gateway authenticates with MCP services using OBO tokens

## Keycloak Configuration

### 1. Create a Realm

1. Log into Keycloak Admin Console
2. Create a new realm (e.g., `mcp-gateway`)
3. Configure the realm settings:
   - Display name: "MCP Gateway"
   - Enabled: Yes
   - User registration: Configure as needed
   - Login settings: Configure as needed

### 2. Create Client for End Users (Public Client)

1. Navigate to Clients → Create Client
2. Configure the client:
   - **Client ID**: `mcp-web-client` (or your application name)
   - **Client Type**: Public
   - **Standard Flow**: Enabled
   - **Direct Access Grants**: Enabled (if needed)
   - **Valid Redirect URIs**: Add your application URLs
   - **Web Origins**: Add your application domains

### 3. Create Client for MCP Gateway (Confidential Client)

1. Navigate to Clients → Create Client
2. Configure the client:
   - **Client ID**: `mcp-gateway`
   - **Client Type**: Confidential
   - **Service Account**: Enabled
   - **OAuth 2.0 Token Exchange**: Enabled (for OBO flow)
   - **Standard Flow**: Disabled
   - **Direct Access Grants**: Disabled

3. Go to Credentials tab and note the Client Secret

### 4. Configure Token Exchange Policy

1. Navigate to Authorization → Policies
2. Create a new Token Exchange Policy:
   - **Name**: `mcp-gateway-token-exchange`
   - **Description**: Allow token exchange for MCP Gateway
   - **Client**: Select `mcp-gateway`
   - **Target Client**: All clients or specific MCP service clients

### 5. Create Scopes (Optional)

1. Navigate to Client Scopes
2. Create scopes for your MCP services:
   - `mcp:read` - Read access to MCP services
   - `mcp:write` - Write access to MCP services
   - `mcp:call` - Make MCP protocol calls

### 6. Configure Client Scope Mappings

1. For the `mcp-gateway` client, go to Client Scopes
2. Add the created scopes to Default Client Scopes

## MCP Gateway Configuration

### 1. Environment Variables

Create a `.env` file with the following configuration:

```bash
# Authentication Configuration
ENABLE_AUTH=true
KEYCLOAK_SERVER_URL=https://your-keycloak-server.com
KEYCLOAK_REALM=mcp-gateway
KEYCLOAK_CLIENT_ID=mcp-gateway
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Token Validation
TOKEN_AUDIENCE=mcp-gateway
TOKEN_ISSUER=https://your-keycloak-server.com/realms/mcp-gateway
JWKS_CACHE_TTL=3600

# OBO Configuration
ENABLE_OBO=true
OBO_CACHE_TTL=1800

# Security Settings
CLOCK_SKEW_TOLERANCE=300
REQUIRED_SCOPES=["mcp:read"]
```

### 2. Service Configuration

Update your `config/services.yaml` to include authentication settings for each MCP service:

```yaml
services:
  my-mcp-service:
    name: "My MCP Service"
    transport: "http"
    endpoint: "https://my-mcp-service.com"
    enabled: true
    authentication:
      service_id: "my-mcp-service"
      target_audience: "my-mcp-service"
      required_scopes: ["mcp:call", "mcp:read"]
      auth_strategy: "obo_required"  # Options: none, passthrough_only, obo_preferred, obo_required
      custom_headers:
        X-Service-Version: "1.0"
```

## Authentication Flow

### 1. User Authentication

```bash
# Example using curl to get a token
curl -X POST "https://your-keycloak-server.com/realms/mcp-gateway/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mcp-web-client" \
  -d "username=your-username" \
  -d "password=your-password" \
  -d "scope=openid profile mcp:read mcp:call"
```

### 2. Calling MCP Gateway

```bash
# Use the access token to call the MCP Gateway
curl -X GET "http://localhost:8000/api/v1/services" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Proxy Request to MCP Service

```bash
# Proxy a request to an MCP service
curl -X POST "http://localhost:8000/api/v1/proxy/my-mcp-service/some-endpoint" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data": "example"}'
```

## Security Considerations

### 1. Token Security

- Use HTTPS for all communications
- Configure appropriate token lifetimes in Keycloak
- Enable real-time token validation using JWT signature verification
- Use secure storage for client secrets

### 2. Network Security

- Restrict network access to Keycloak admin console
- Use firewalls to limit access to MCP services
- Implement rate limiting to prevent abuse

### 3. Monitoring and Logging

- Monitor authentication failures
- Log token validation errors
- Set up alerts for unusual access patterns
- Audit token exchange operations

## Troubleshooting

### Common Issues

1. **Token Validation Fails**
   - Check JWKS URL is accessible
   - Verify token issuer matches configuration
   - Check clock synchronization between services

2. **OBO Token Exchange Fails**
   - Verify token exchange policy is configured
   - Check client credentials are correct
   - Ensure target audience is properly set

3. **Service Authentication Fails**
   - Verify service endpoint configuration
   - Check OBO token has correct scopes
   - Review service-specific authentication requirements

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
LOG_LEVEL=DEBUG
```

This will provide detailed logs of the authentication process, including token validation and OBO operations.

## Production Deployment

### Security Checklist

- [ ] Use strong client secrets
- [ ] Enable HTTPS everywhere
- [ ] Configure proper CORS settings
- [ ] Set up monitoring and alerting
- [ ] Regular security updates
- [ ] Backup Keycloak configuration
- [ ] Test disaster recovery procedures

### Performance Optimization

- [ ] Configure appropriate cache TTLs
- [ ] Use Redis for distributed caching
- [ ] Monitor token validation latency
- [ ] Optimize JWKS refresh frequency
- [ ] Set up load balancing for high availability

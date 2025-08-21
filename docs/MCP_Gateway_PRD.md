# Product Requirements Document (PRD): Open-Source MCP Gateway in Python

> **Status Legend:**  
> <span style="color: green">**✅ Completed**</span> - <span style- <span style="color: orange">**🟡 Full MCP Protocol Compliance:** Complete initialize handshake, session management, single /mcp endpoint</span>
- <span style="color: orange">**🟡 Production-Ready Streaming:** SSE responses with connection management, client disconnect handling, idle timeouts</span>color: orange">**🟡 Add MCP Session Management:** Per-client session isolation with connection pooling and TTL</span> *(ClientSession wrapping with proper lifecycle)*
- <span style="color: orange">**🟡 Implement Initialize Handshake:** Required MCP initialize/initialized flow</span> *(200 + 202 semantics with SDK)*
- <span style="color: orange">**🟡 Add Streamable HTTP Support:** Single /mcp endpoint with JSON or SSE responses per MCP spec</span> *(AsyncGenerator with backpressure controls)*
- <span style="color: orange">**🟡 Integrate Rate Limiting System:** Redis-based rate limiting with dual placement</span> *(Before session + after OBO)*pan style="color: orange">**🟡 In Progress**</span> | <span style="color: red">**🔴 Not Started**</span>

## 1. Overview
The goal is to design and implement an open-source MCP (Model Context Protocol) Gateway in Python. The gateway will act as a centralized proxy and security layer for MCP servers, enabling secure access control, authentication, monitoring, and protocol bridging for AI model interactions.

## 2. Objectives
- Provide a secure, scalable gateway for MCP server access with enterprise-grade features
- Enable centralized authentication, authorization, and audit logging for MCP interactions
- Support HTTP and stdio transport protocols with seamless bridging
- Implement dynamic service discovery and policy-based access control
- Foster open-source community adoption with comprehensive documentation and examples

## 3. Stakeholders
- AI application developers using MCP for model interactions
- DevOps teams deploying and managing MCP infrastructure
- Security teams requiring audit trails and access control
- Open-source community contributors
- Organizations adopting MCP at enterprise scale

## 4. Functional Requirements

### Core Gateway Features
- <span style="color: orange">**� MCP Protocol Compliance:** Full support for Model Context Protocol specification</span> *(Implementation plan finalized, SDK integration ready)*
- <span style="color: green">**✅ Transport Support:** HTTP/REST API and stdio transport bridging</span> *(HTTP complete with full proxy functionality)*
- <span style="color: green">**✅ Service Registry:** Static configuration and dynamic service discovery for MCP servers</span> *(YAML-based registry with validation)*
- <span style="color: green">**✅ Request Proxying:** Transparent pass-through of MCP calls with minimal latency overhead</span>
- <span style="color: orange">**🟡 MCP Session Management:** Per-client session isolation with connection pooling</span> *(Design complete, ready for implementation)*
- <span style="color: orange">**🟡 Streamable HTTP Support:** Single /mcp endpoint with JSON or SSE responses per MCP spec</span> *(Architecture planned with backpressure controls)*

### Authentication & Authorization  
- <span style="color: red">**🔴 API Key Authentication:** Simple token-based authentication for development environments</span>
- <span style="color: green">**✅ OAuth 2.0 / OIDC:** Integration with Keycloak identity provider for enterprise SSO</span> *(Complete OIDC implementation with JWT validation)*
- <span style="color: green">**✅ On-Behalf-Of (OBO) Token Flow:** Secure token exchange for downstream service calls</span> *(OAuth2 token exchange implemented with caching)*
- <span style="color: green">**✅ Service-Level Authentication:** Configuration-driven authentication strategies per service</span> *(ServiceRegistry integration with YAML-based auth configs)*
- <span style="color: red">**🔴 Role-Based Access Control (RBAC):** Fine-grained permissions for MCP resources and operations</span>

### Security & Policy
- <span style="color: red">**🔴 Policy Engine:** Integration with Open Policy Agent (OPA) or custom policy modules</span>
- <span style="color: orange">**� Rate Limiting:** Configurable rate limits per client, service, or operation</span> *(System implemented on feature/rate-limiter branch)*
- <span style="color: red">**🔴 Input Validation:** Request sanitization and schema validation</span>
- <span style="color: red">**🔴 Data Masking:** Configurable PII/sensitive data redaction in logs and responses</span>
- <span style="color: orange">**🟡 Circuit Breakers:** Per-client failure protection with configurable thresholds</span> *(Design complete for MCP compliance)*
- <span style="color: orange">**🟡 Size Guards:** Request and response size limits to prevent memory spikes</span> *(Production hardening planned)*

### Observability & Monitoring
- <span style="color: green">**✅ Structured Logging:** JSON-formatted logs with correlation IDs and request tracing</span> *(JSON logging implemented with Pydantic V2)*
- <span style="color: red">**🔴 Metrics Export:** Prometheus-compatible metrics for performance monitoring</span>
- <span style="color: green">**✅ Health Checks:** Service health endpoints and dependency status monitoring</span>
- <span style="color: green">**✅ Audit Logging:** Compliance-grade audit trails for all MCP interactions</span> *(Comprehensive audit system implemented)*
- <span style="color: orange">**🟡 Enhanced Observability:** Correlation IDs, retry tracking, and circuit breaker metrics</span> *(Production monitoring patterns designed)*
- <span style="color: orange">**🟡 Stream Monitoring:** SSE response tracking, idle detection, and client disconnect handling</span> *(Streamable HTTP observability planned)*

## 5. Non-Functional Requirements
- **Performance:** Sub-100ms proxy latency for MCP calls under normal load
- **Scalability:** Support for 1000+ concurrent connections and horizontal scaling
- **Reliability:** 99.9% uptime with graceful degradation and circuit breaker patterns
- **Security:** Secure defaults, zero-trust architecture, and regular security audits
- **Maintainability:** Clean code architecture with comprehensive test coverage (90%+)
- **Documentation:** Complete API documentation, deployment guides, and community resources

## 6. Development Phases

### Phase 1 – MVP (Core Connectivity & Auth)
**Scope:** Pass-through MCP calls, static service registry, basic API key or OIDC auth  
**Status:** ✅ **COMPLETED** 🎯

**Main Tasks:**
- <span style="color: green">**✅ Scaffold FastAPI-based gateway project with async support**</span>
- <span style="color: green">**✅ Implement HTTP proxy to MCP servers with request/response forwarding**</span>
- <span style="color: green">**✅ Create comprehensive service registry configuration (YAML)**</span> *(Enhanced with authentication config support)*
- <span style="color: green">**✅ Add OIDC authentication with Keycloak integration**</span> *(Complete OAuth2/OIDC implementation)*
- <span style="color: green">**✅ Implement OAuth2 On-Behalf-Of (OBO) token flow**</span> *(Token exchange with caching)*
- <span style="color: green">**✅ Implement basic structured logging with correlation IDs**</span> *(JSON logging with Pydantic V2 validation)*
- <span style="color: green">**✅ Create Docker containerization and basic deployment documentation**</span>

**Recent Major Accomplishments:**
- ✅ **Complete OIDC Authentication System** with Keycloak and JWT validation
- ✅ **OAuth2 On-Behalf-Of Flow** with automatic token exchange and caching
- ✅ **ServiceRegistry Integration** bridging YAML configuration with authentication models
- ✅ **Configuration-Driven Authentication** supporting multiple strategies per service (NO_AUTH, PASSTHROUGH, OBO_PREFERRED, OBO_REQUIRED)
- ✅ **Production-grade HTTP proxy** with timeout handling and error management
- ✅ **Comprehensive API endpoints** (`/services`, `/proxy`, `/mcp`, `/health`)
- ✅ **Service registry validation** with Pydantic V2 models and cross-field validation
- ✅ **Health monitoring** with real-time service status checking
- ✅ **Error handling** with proper HTTP status codes and structured responses
- ✅ **Security middleware** with CORS, trusted hosts, and request validation
- ✅ **Rate Limiting System** implemented on feature/rate-limiter branch
- ✅ **Comprehensive Audit System** with structured logging and event tracking
- ✅ **Dashboard Frontend** with React/TypeScript for service management
- ✅ **MCP Compliance Implementation Plan** finalized and production-ready

**Deliverables:**
- <span style="color: green">**✅ Working gateway that can proxy MCP calls to registered servers**</span> *(Full HTTP proxy with error handling and validation)*
- <span style="color: green">**✅ Complete OIDC authentication with Keycloak integration**</span> *(JWT validation and OBO flow)*
- <span style="color: green">**✅ ServiceRegistry with configuration-driven authentication**</span> *(YAML-based auth strategies per service)*
- <span style="color: green">**✅ Container deployment with docker-compose example**</span>
- <span style="color: green">**✅ Comprehensive project documentation and README**</span>

## Current Status & Immediate Next Steps

### 🎯 **Current Focus: MCP Protocol Compliance (Phase 2)**
**Branch:** `mcp-spec-compliance` (created from develop)  
**Implementation Plan:** [MCP_Compliance_Implementation_Plan.md](./MCP_Compliance_Implementation_Plan.md) - **Production-ready and approved** ✅

### 🚀 **Ready to Start: Phase 0-1 Implementation**
**Timeline:** 4-6 days for core MCP compliance  
**Dependencies:** Python MCP SDK integration

#### **Immediate Tasks (Next 2 weeks):**
1. **Phase 0 - MCP SDK Integration** (1-2 days)
   - Integrate official Python MCP client SDK  
   - Set up transport and ClientSession patterns
   - Add SDK version management and startup logging

2. **Phase 1 - Session Management** (3-4 days)
   - Implement MCPSessionManager with per-client isolation
   - Add session TTL and cleanup mechanisms
   - Create MCPClientWrapper for context management

3. **Phase 2 - Initialize Handshake** (2-3 days) 
   - Implement required initialize/initialized flow
   - Add proper 200 + 202 response semantics
   - Integrate with existing proxy infrastructure

#### **Following Phases (Weeks 3-4):**
4. **Phase 3 - Streamable HTTP Support** (2-3 days)
   - Single /mcp endpoint with JSON/SSE response modes
   - Client disconnect handling and connection management
   - Size guards and backpressure controls

5. **Phase 4-7 - Production Hardening** (4-5 days)
   - Header management and retry logic
   - Circuit breaker integration
   - Enhanced observability and monitoring

### 📊 **Current Architecture Status:**
- ✅ **Foundation:** FastAPI, OIDC auth, OBO flow, service registry
- ✅ **Security:** Authentication, authorization, audit logging  
- ✅ **Monitoring:** Health checks, structured logging, dashboard
- ✅ **Scaling:** Rate limiting system, Redis integration ready
- 🟡 **MCP Compliance:** Implementation plan finalized, ready to execute
- 🔴 **Advanced Features:** RBAC, policy engine, metrics (Phase 3+)

### Phase 2 – MCP Protocol Compliance & Enhanced Security
**Scope:** Full MCP specification support, streaming, session management, rate limiting  
**Status:** 🟡 **IN PROGRESS** 🚧 *(Implementation plan finalized, SDK integration ready)*

**Main Tasks:**
- <span style="color: orange">**🟡 Implement MCP Client SDK Integration:** Use official Python MCP SDK for protocol compliance</span> *(Phase 0-1: Foundation and session management)*
- <span style="color: orange">**🟡 Add MCP Session Management:** Per-client session isolation with connection pooling and TTL</span> *(ClientSession wrapping with proper lifecycle)*
- <span style="color: orange">**� Implement Initialize Handshake:** Required MCP initialize/initialized flow</span> *(200 + 202 semantics with SDK)*
- <span style="color: orange">**🟡 Add Streaming Response Support:** Server-Sent Events for real-time MCP interactions</span> *(AsyncGenerator with backpressure controls)*
- <span style="color: orange">**� Integrate Rate Limiting System:** Redis-based rate limiting with dual placement</span> *(Before session + after OBO)*
- <span style="color: orange">**🟡 Add Circuit Breaker Protection:** Per-client failure isolation with configurable thresholds</span> *(Prevent cascade failures)*
- <span style="color: orange">**� Implement Retry Logic:** Category-based retry with OBO token refresh</span> *(Auth vs session vs network errors)*
- <span style="color: red">**🔴 Add Role-Based Access Control (RBAC) with configurable permissions**</span>
- <span style="color: red">**🔴 Add input validation and basic security headers**</span>

**Deliverables:**
- <span style="color: orange">**🟡 Full MCP Protocol Compliance:** Complete initialize handshake, session management, streamable HTTP support</span>
- <span style="color: orange">**🟡 Production-Ready Streaming:** SSE with connection management, client disconnect handling, idle timeouts</span>
- <span style="color: orange">**🟡 Enhanced Error Recovery:** Categorized retries, circuit breakers, graceful degradation</span>
- <span style="color: orange">**🟡 Comprehensive Rate Limiting:** Dual-layer protection with Redis scaling</span>
- <span style="color: red">**🔴 RBAC system with role definitions and permission enforcement**</span>
- <span style="color: orange">**� Production Hardening:** Size guards, correlation tracking, enhanced observability</span>

**Key Implementation Phases:**
- **Phase 0:** MCP Client SDK Integration (1-2 days) - *Ready to start*
- **Phase 1:** Session Management (3-4 days) - *Architecture complete*
- **Phase 2:** Initialize Handshake (2-3 days) - *SDK patterns defined*
- **Phase 3:** Streaming Support (2-3 days) - *Streamable HTTP hardening planned*
- **Phase 4-7:** Header management, retry logic, concurrency, observability (1-2 days each)

### Phase 3 – Enterprise Features & Advanced Policy
**Scope:** Dynamic service discovery, policy engine, metrics, transport bridging, RBAC

**Main Tasks:**
- <span style="color: red">**🔴 Complete Role-Based Access Control (RBAC):** Fine-grained permissions and policy enforcement</span> *(Moved from Phase 2)*
- <span style="color: red">**🔴 Implement self-registration API for MCP servers with health checking**</span>
- <span style="color: red">**🔴 Integrate Open Policy Agent (OPA) or custom policy evaluation engine**</span>
- <span style="color: red">**🔴 Add Prometheus metrics export and Grafana dashboard templates**</span>
- <span style="color: red">**🔴 Implement HTTP ↔ stdio transport bridging for protocol interoperability**</span>
- <span style="color: red">**🔴 Add load balancing algorithms (round-robin, weighted, health-based)**</span>
- <span style="color: red">**🔴 Add input validation and security header enhancement**</span> *(Moved from Phase 2)*

**Deliverables:**
- <span style="color: red">**🔴 Complete RBAC system with MCP-aware permissions**</span>
- <span style="color: red">**🔴 Dynamic service discovery with automatic health monitoring**</span>
- <span style="color: red">**🔴 Policy-based access control with fine-grained rule evaluation**</span>
- <span style="color: red">**🔴 Production-grade monitoring with Prometheus/Grafana integration**</span>
- <span style="color: red">**🔴 Transport protocol bridging capabilities**</span>

### Phase 4 – Advanced Operations
**Scope:** Multi-tenancy, caching, advanced analytics, ecosystem integration

**Main Tasks:**
- <span style="color: red">**🔴 Add multi-tenancy support with tenant isolation and resource quotas**</span>
- <span style="color: red">**🔴 Implement intelligent caching strategies for frequently accessed resources**</span>
- <span style="color: red">**🔴 Build advanced analytics dashboard with usage patterns and cost optimization**</span>
- <span style="color: red">**🔴 Add plugin architecture for third-party integrations**</span>
- <span style="color: red">**🔴 Implement blue-green deployment support and A/B testing capabilities**</span>
- <span style="color: red">**🔴 Add comprehensive API versioning and backward compatibility**</span>

**Deliverables:**
- <span style="color: red">**🔴 Multi-tenant gateway with enterprise SLA support**</span>
- <span style="color: red">**🔴 Advanced caching and performance optimization features**</span>
- <span style="color: red">**🔴 Analytics platform with business intelligence capabilities**</span>
- <span style="color: red">**🔴 Extensible plugin ecosystem for community contributions**</span>

## 7. Technical Architecture

### Core Components
- **API Gateway Server:** FastAPI-based async HTTP server with MCP protocol support
- **MCP Session Manager:** Per-client session isolation with SDK integration and connection pooling
- **Service Registry:** Dynamic discovery and health checking for MCP servers  
- **Authentication Layer:** Pluggable auth modules (API key, OAuth, OIDC) with OBO token flow
- **Authorization Engine:** RBAC with policy evaluation (OPA integration)
- **Proxy Engine:** MCP-compliant request forwarding with streaming support and load balancing
- **Rate Limiting System:** Redis-based distributed rate limiting with dual-layer protection
- **Circuit Breaker:** Per-client failure isolation with configurable thresholds and recovery
- **Observability Stack:** Structured logging, metrics, tracing, health checks, and audit trails

### Technology Stack
- **Framework:** FastAPI with async/await support and MCP protocol compliance
- **MCP Integration:** Official Python MCP SDK with ClientSession management and streaming support
- **Authentication:** Authlib for OAuth/OIDC, custom API key handling, OBO token exchange
- **Session Management:** Per-client MCP session isolation with TTL and connection pooling
- **Streaming:** Streamable HTTP with backpressure controls and client disconnect handling
- **Rate Limiting:** Redis for distributed rate limiting with configurable policies
- **Circuit Breakers:** Per-client failure protection with exponential backoff and recovery
- **Policy Engine:** Open Policy Agent (OPA) Python SDK for fine-grained access control
- **Caching/State:** Redis for distributed session management and horizontal scaling
- **Metrics:** Prometheus client for metrics export with MCP-specific monitoring
- **Logging:** Structlog for JSON-formatted logging with correlation IDs and retry tracking
- **Configuration:** Pydantic for settings validation, environment variables, and size guards

## 8. Success Metrics
- **Functional:** Successfully proxy 100% of valid MCP protocol calls with full initialize/initialized handshake support
- **Performance:** Achieve <100ms p95 latency for proxy requests, <200ms for streamable HTTP first-byte
- **Reliability:** Maintain 99.9% uptime with circuit breaker protection and graceful degradation
- **MCP Compliance:** 100% adherence to MCP specification including session management and streamable HTTP
- **Security:** Zero critical security vulnerabilities with comprehensive audit trails
- **Adoption:** 100+ GitHub stars and 10+ community contributors within 6 months
- **Quality:** Maintain 90%+ test coverage with contract tests for MCP protocol compliance

## 9. Risks & Mitigations
- **MCP Protocol Evolution:** Risk of MCP specification changes breaking compatibility
  - *Mitigation:* SDK version pinning, protocol version negotiation, and comprehensive contract testing
- **Session Management Complexity:** Risk of memory leaks or connection exhaustion with per-client sessions
  - *Mitigation:* Proper session TTL, connection pooling limits, circuit breakers, and monitoring
- **Streaming Performance:** Risk of backpressure issues or client disconnect handling failures with streamable HTTP
  - *Mitigation:* Size guards, idle timeouts, connection management, and comprehensive stream monitoring
- **Security Vulnerabilities:** Potential for authentication bypass or data leakage  
  - *Mitigation:* Regular security audits, dependency scanning, OBO token scoping, and audit trails
- **Performance Bottlenecks:** Gateway becoming a single point of failure under high load
  - *Mitigation:* Horizontal scaling with Redis, rate limiting, circuit breakers, and load balancing
- **Community Adoption:** Risk of limited community engagement and contributions
  - *Mitigation:* Comprehensive documentation, MCP compliance examples, and active community outreach

## 10. Open Source Strategy
- **License:** Apache 2.0 for maximum commercial adoption and contribution flexibility
- **Repository:** Public GitHub repository with clear contribution guidelines
- **Documentation:** Comprehensive docs site with tutorials, API reference, and deployment guides
- **Community:** Discord/Slack community, regular contributor meetings, and responsive issue triage
- **Release Cadence:** Monthly releases with semantic versioning and detailed changelogs

## 11. MCP Protocol Compliance Notes

**Transport Evolution**: SSE as a standalone (two-endpoint) transport is deprecated as of 2024-11-05. The replacement is Streamable HTTP (2025-03-26), which uses a single `/mcp` endpoint that can return `application/json` or `text/event-stream` responses as needed.

**GET vs POST Roles**:
- **POST**: Primary method for MCP requests/notifications with `Accept: application/json, text/event-stream` header
- **GET**: Optional for server-initiated notifications/events via SSE; return 405 Method Not Allowed if not supported

**Response Modes**:
- **JSON**: `application/json` for standard request/response cycles  
- **SSE**: `text/event-stream` for streamable responses within the Streamable HTTP transport

---
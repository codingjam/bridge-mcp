// TypeScript interfaces for the MCP Gateway Dashboard

export interface DashboardMetrics {
  activeServices: number;
  rateLimitUsage: number;
  activeUsers: number;
  avgResponseTime: number;
  totalRequests: number;
  errorRate: number;
  uptime: string;
}

export interface ServiceHealth {
  serviceId: string;
  serviceName: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  lastCheck: string;
  responseTime: number;
  errorRate: number;
  endpoint: string;
  transport: 'http' | 'stdio';
  enabled: boolean;
}

export interface Service {
  service_id: string;
  name: string;
  description: string;
  connection_type: string;
  status: string;
}

export interface ServiceListResponse {
  services: Service[];
}

export interface CreateServiceRequest {
  name: string;
  description?: string;
  transport: 'http' | 'stdio';
  enabled?: boolean;
  endpoint?: string;
  timeout?: number;
  health_check_path?: string;
  command?: string[];
  working_directory?: string;
  auth?: Record<string, any>;
  tags?: string[];
}

export interface RateLimitStatus {
  userId: string;
  serviceId: string;
  toolName: string;
  currentUsage: number;
  limit: number;
  windowEnd: string;
  blocked: boolean;
  resetTime: string;
}

export interface RateLimitConfig {
  enabled: boolean;
  defaultLimit: number;
  windowSeconds: number;
  backend: 'memory' | 'redis';
}

export interface RecentActivity {
  id: string;
  timestamp: string;
  userId: string;
  serviceId: string;
  action: string;
  status: 'success' | 'error' | 'blocked';
  responseTime: number;
  details?: string;
}

export interface AuthConfig {
  enabled: boolean;
  provider: string;
  keycloakUrl?: string;
  realm?: string;
  clientId?: string;
  status: 'connected' | 'disconnected' | 'error';
}

export interface UserSession {
  userId: string;
  username: string;
  sessionId: string;
  startTime: string;
  lastActivity: string;
  expiresAt: string;
  ipAddress: string;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  service: string;
  message: string;
  details?: any;
  correlationId?: string;
}

export interface GatewayConfig {
  host: string;
  port: number;
  debug: boolean;
  logLevel: string;
  logFormat: string;
  enableAuth: boolean;
  enableRateLimit: boolean;
  enableAudit: boolean;
}

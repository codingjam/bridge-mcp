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
  id: string;
  name: string;
  description: string;
  endpoint: string;
  transport: 'http' | 'stdio';
  enabled: boolean;
  timeout: number;
  tags: string[];
  command?: string[];
  health?: ServiceHealth;
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

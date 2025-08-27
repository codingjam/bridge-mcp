import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import type {
  Service,
  ServiceListResponse,
  CreateServiceRequest,
  RateLimitStatus,
  RateLimitConfig,
  RecentActivity,
  AuthConfig,
  UserSession,
  LogEntry,
  GatewayConfig,
} from '../types';

// Dashboard Overview APIs
export const useDashboardMetrics = () => {
  return useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: async (): Promise<any> => {
      const { data } = await apiClient.get('/dashboard/overview');
      return data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });
};

export const useServiceHealth = () => {
  return useQuery({
    queryKey: ['dashboard', 'services', 'health'],
    queryFn: async (): Promise<any> => {
      const { data } = await apiClient.get('/dashboard/services/health');
      return data;
    },
    refetchInterval: 15000, // Refetch every 15 seconds
  });
};

export const useRecentActivity = () => {
  return useQuery({
    queryKey: ['dashboard', 'activity'],
    queryFn: async (): Promise<RecentActivity[]> => {
      const { data } = await apiClient.get('/dashboard/activity');
      return data;
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  });
};

// Services Management APIs
export const useServices = () => {
  return useQuery({
    queryKey: ['services'],
    queryFn: async (): Promise<Service[]> => {
      const { data } = await apiClient.get('/dashboard/services');
      return data.services || [];
    },
  });
};

export const useCreateService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (service: CreateServiceRequest): Promise<{ id: string; status: string; message: string }> => {
      const { data } = await apiClient.post('/dashboard/services', service);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'services', 'health'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'overview'] });
    },
  });
};

export const useDeleteService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (serviceId: string): Promise<{ id: string; status: string; message: string }> => {
      const { data } = await apiClient.delete(`/dashboard/services/${serviceId}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'services', 'health'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'overview'] });
    },
  });
};

export const useTestService = () => {
  return useMutation({
    mutationFn: async (testRequest: { transport: 'http' | 'stdio'; endpoint?: string; command?: string[]; timeout?: number }): Promise<{ success: boolean; message: string; responseTime?: number; details?: any }> => {
      const { data } = await apiClient.post('/dashboard/services/test', testRequest);
      return data;
    },
  });
};

// Rate Limiting APIs
export const useRateLimitStatus = () => {
  return useQuery({
    queryKey: ['rate-limits', 'status'],
    queryFn: async (): Promise<RateLimitStatus[]> => {
      const { data } = await apiClient.get('/dashboard/rate-limits/status');
      return data;
    },
    refetchInterval: 10000, // Refetch every 10 seconds
  });
};

export const useRateLimitConfig = () => {
  return useQuery({
    queryKey: ['rate-limits', 'config'],
    queryFn: async (): Promise<RateLimitConfig> => {
      const { data } = await apiClient.get('/dashboard/rate-limits/config');
      return data;
    },
  });
};

export const useUpdateRateLimitConfig = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (config: RateLimitConfig): Promise<RateLimitConfig> => {
      const { data } = await apiClient.put('/dashboard/rate-limits/config', config);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rate-limits'] });
    },
  });
};

// Authentication APIs
export const useAuthConfig = () => {
  return useQuery({
    queryKey: ['auth', 'config'],
    queryFn: async (): Promise<AuthConfig> => {
      const { data } = await apiClient.get('/dashboard/auth/config');
      return data;
    },
  });
};

export const useActiveSessions = () => {
  return useQuery({
    queryKey: ['auth', 'sessions'],
    queryFn: async (): Promise<UserSession[]> => {
      const { data } = await apiClient.get('/dashboard/auth/sessions');
      return data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });
};

// Logs APIs
export const useLogs = (filters?: { level?: string; service?: string; search?: string; limit?: number }) => {
  return useQuery({
    queryKey: ['logs', filters],
    queryFn: async (): Promise<LogEntry[]> => {
      const { data } = await apiClient.get('/dashboard/logs', { params: filters });
      return data;
    },
    refetchInterval: 5000, // Refetch every 5 seconds
  });
};

export const useExportLogs = () => {
  return useMutation({
    mutationFn: async (filters: { 
      startDate: string; 
      endDate: string; 
      level?: string; 
      service?: string; 
      format: 'csv' | 'json' 
    }): Promise<Blob> => {
      const { data } = await apiClient.get('/dashboard/logs/export', { 
        params: filters,
        responseType: 'blob'
      });
      return data;
    },
  });
};

// Configuration APIs
export const useGatewayConfig = () => {
  return useQuery({
    queryKey: ['config'],
    queryFn: async (): Promise<GatewayConfig> => {
      const { data } = await apiClient.get('/dashboard/config');
      return data;
    },
  });
};

export const useUpdateGatewayConfig = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (config: Partial<GatewayConfig>): Promise<GatewayConfig> => {
      const { data } = await apiClient.put('/dashboard/config', config);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
  });
};

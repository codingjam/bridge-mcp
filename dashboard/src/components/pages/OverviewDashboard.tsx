import React from 'react';
import { Card, Statistic, Typography, Alert, Spin } from '../ui';
import { useDashboardMetrics, useServiceHealth } from '../../hooks/useApi';

const { Title } = Typography;

export const OverviewDashboard: React.FC = () => {
  const { data: overviewData, isLoading: overviewLoading, error: overviewError } = useDashboardMetrics();
  const { data: healthData, isLoading: healthLoading, error: healthError } = useServiceHealth();

  if (overviewLoading || healthLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Title level={2}>Dashboard Overview</Title>
          <p className="text-gray-600">Welcome to the Bridge MCP Gateway Control Panel</p>
        </div>
        <div className="flex items-center justify-center h-64">
          <Spin size="large" />
        </div>
      </div>
    );
  }

  if (overviewError || healthError) {
    return (
      <div className="space-y-6">
        <div>
          <Title level={2}>Dashboard Overview</Title>
          <p className="text-gray-600">Welcome to the Bridge MCP Gateway Control Panel</p>
        </div>
        <Alert
          message="Error Loading Dashboard Data"
          description="Unable to load dashboard metrics. Please check your connection to the backend service."
          type="error"
          showIcon
        />
      </div>
    );
  }

  // Extract data with fallbacks
  const services = overviewData?.services || {};
  const performance = overviewData?.performance || {};
  const rateLimiting = overviewData?.rateLimiting || {};
  const systemStatus = overviewData?.systemStatus || {};

  return (
    <div className="space-y-6">
      <div>
        <Title level={2}>Dashboard Overview</Title>
        <p className="text-gray-600">Welcome to the Bridge MCP Gateway Control Panel</p>
      </div>
      
      {/* System Status Alert */}
      {systemStatus.status && systemStatus.status !== 'operational' && (
        <Alert
          message={`System Status: ${systemStatus.status}`}
          description={systemStatus.message}
          type={systemStatus.severity === 'error' ? 'error' : 'warning'}
          showIcon
        />
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <Statistic
            title="Total Requests"
            value={rateLimiting.totalRequests || 0}
            suffix="total"
            className="text-center"
          />
        </Card>
        
        <Card>
          <Statistic
            title="Active Services"
            value={services.healthy || 0}
            suffix={`/ ${services.total || 0}`}
            className="text-center"
          />
        </Card>
        
        <Card>
          <Statistic
            title="Response Time"
            value={performance.averageResponseTime || 0}
            suffix="ms"
            precision={1}
            className="text-center"
          />
        </Card>
        
        <Card>
          <Statistic
            title="Success Rate"
            value={performance.successRate || 0}
            suffix="%"
            precision={1}
            className="text-center"
          />
        </Card>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="System Status" className="h-96">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Statistic
                title="Healthy Services"
                value={services.healthy || 0}
                valueStyle={{ color: '#3f8600' }}
              />
              <Statistic
                title="Unhealthy Services"
                value={services.unhealthy || 0}
                valueStyle={{ color: services.unhealthy > 0 ? '#cf1322' : '#3f8600' }}
              />
              <Statistic
                title="Current RPS"
                value={rateLimiting.currentRps || 0}
                precision={1}
              />
              <Statistic
                title="CPU Usage"
                value={performance.cpuUsage || 0}
                suffix="%"
                precision={1}
              />
            </div>
            {systemStatus.status && (
              <div className="mt-4 p-3 bg-gray-50 rounded">
                <div className="text-sm font-medium">System Status: {systemStatus.status}</div>
                <div className="text-xs text-gray-600 mt-1">{systemStatus.message}</div>
                <div className="text-xs text-gray-500 mt-1">
                  Last checked: {new Date(systemStatus.lastChecked).toLocaleTimeString()}
                </div>
              </div>
            )}
          </div>
        </Card>
        
        <Card title="Service Health" className="h-96">
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {healthData?.services?.map((service: any) => (
              <div key={service.id} className="flex items-center justify-between p-2 border rounded">
                <div className="flex-1">
                  <div className="font-medium text-sm">{service.name}</div>
                  <div className="text-xs text-gray-500">{service.transport}</div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 text-xs rounded ${
                    service.status === 'healthy' 
                      ? 'bg-green-100 text-green-800'
                      : service.status === 'unhealthy'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}>
                    {service.status}
                  </span>
                </div>
              </div>
            )) || (
              <div className="flex items-center justify-center h-full text-gray-500">
                No service data available
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

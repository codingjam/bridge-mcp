import React from 'react';
import { Card, Table, Typography, Alert, Spin, Button, Tag } from '../ui';
import { useServiceHealth } from '../../hooks/useApi';
import { ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import type { TableColumn } from '../ui/types';

const { Title } = Typography;

interface ServiceData {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  transport: 'http' | 'stdio';
  enabled: boolean;
  timeout: number;
  tags: string[];
  status: 'healthy' | 'unhealthy' | 'disabled' | 'unknown';
  lastChecked?: string;
}

export const Services: React.FC = () => {
  const { data: healthData, isLoading: healthLoading, error: healthError } = useServiceHealth();

  if (healthLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Title level={2}>Services Management</Title>
          <p className="text-gray-600">Manage and monitor MCP services</p>
        </div>
        <div className="flex items-center justify-center h-64">
          <Spin size="large" />
        </div>
      </div>
    );
  }

  if (healthError) {
    return (
      <div className="space-y-6">
        <div>
          <Title level={2}>Services Management</Title>
          <p className="text-gray-600">Manage and monitor MCP services</p>
        </div>
        <Alert
          message="Error Loading Services"
          description="Unable to load service data. Please check your connection to the backend service."
          type="error"
          showIcon
        />
      </div>
    );
  }

  // Transform health data into table format
  const services: ServiceData[] = healthData?.services?.map((service: any) => ({
    id: service.id,
    name: service.name,
    description: `${service.transport.toUpperCase()} service`, // We'll enhance this later
    endpoint: service.endpoint || 'N/A',
    transport: service.transport,
    enabled: service.enabled,
    timeout: 30, // Default, we'll get real data later
    tags: service.tags || [],
    status: service.enabled ? (service.healthy ? 'healthy' : 'unhealthy') : 'disabled',
    lastChecked: service.lastChecked,
  })) || [];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'green';
      case 'unhealthy': return 'red';
      case 'disabled': return 'gray';
      default: return 'orange';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return '🟢';
      case 'unhealthy': return '🔴';
      case 'disabled': return '⭕';
      default: return '🟡';
    }
  };

  const columns: TableColumn<ServiceData>[] = [
    {
      key: 'status',
      title: 'Status',
      width: 100,
      render: (_, record) => (
        <div className="flex items-center space-x-2">
          <span>{getStatusIcon(record.status)}</span>
          <Tag color={getStatusColor(record.status)}>
            {record.status.toUpperCase()}
          </Tag>
        </div>
      ),
    },
    {
      key: 'name',
      title: 'Service Name',
      dataIndex: 'name',
      render: (name, record) => (
        <div>
          <div className="font-medium text-gray-900">{name}</div>
          <div className="text-sm text-gray-500">{record.id}</div>
        </div>
      ),
    },
    {
      key: 'transport',
      title: 'Type',
      dataIndex: 'transport',
      width: 80,
      render: (transport) => (
        <Tag color={transport === 'http' ? 'blue' : 'purple'}>
          {transport.toUpperCase()}
        </Tag>
      ),
    },
    {
      key: 'endpoint',
      title: 'Endpoint',
      dataIndex: 'endpoint',
      render: (endpoint, record) => (
        <div className="max-w-xs">
          <div className="truncate text-sm font-mono text-gray-700">
            {endpoint}
          </div>
          {record.transport === 'http' && (
            <div className="text-xs text-gray-500">
              Timeout: {record.timeout}s
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'tags',
      title: 'Tags',
      dataIndex: 'tags',
      render: (tags: string[]) => (
        <div className="flex flex-wrap gap-1">
          {tags?.slice(0, 2).map((tag, index) => (
            <Tag key={index} size="small" className="text-xs">
              {tag}
            </Tag>
          ))}
          {tags?.length > 2 && (
            <Tag size="small" className="text-xs text-gray-500">
              +{tags.length - 2} more
            </Tag>
          )}
        </div>
      ),
    },
    {
      key: 'lastChecked',
      title: 'Last Checked',
      dataIndex: 'lastChecked',
      width: 150,
      render: (lastChecked) => (
        <div className="text-sm text-gray-500">
          {lastChecked ? new Date(lastChecked).toLocaleTimeString() : 'Never'}
        </div>
      ),
    },
    {
      key: 'actions',
      title: 'Actions',
      width: 150,
      render: (_, record) => (
        <div className="flex space-x-2">
          <Button 
            type="text" 
            size="small"
            icon={record.enabled ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => console.log('Toggle service:', record.id)}
          >
            {record.enabled ? 'Disable' : 'Enable'}
          </Button>
          <Button 
            type="text" 
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => console.log('Test service:', record.id)}
          >
            Test
          </Button>
        </div>
      ),
    },
  ];

  const handleRefresh = () => {
    // Force refresh of health data
    window.location.reload(); // Temporary - we'll implement proper refresh later
  };

  const summary = healthData?.summary || {
    total: 0,
    healthy: 0,
    unhealthy: 0,
    disabled: 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Title level={2}>Services Management</Title>
          <p className="text-gray-600">Manage and monitor MCP services</p>
        </div>
        <Button 
          type="primary" 
          icon={<ReloadOutlined />}
          onClick={handleRefresh}
        >
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-2xl font-bold text-gray-900">{summary.total}</div>
          <div className="text-sm text-gray-500">Total Services</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-600">{summary.healthy}</div>
          <div className="text-sm text-gray-500">Healthy</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-red-600">{summary.unhealthy}</div>
          <div className="text-sm text-gray-500">Unhealthy</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-gray-600">{summary.disabled}</div>
          <div className="text-sm text-gray-500">Disabled</div>
        </Card>
      </div>

      {/* Services Table */}
      <Card title="Services" className="w-full">
        <Table
          dataSource={services}
          columns={columns}
          rowKey="id"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => 
              `${range[0]}-${range[1]} of ${total} services`,
          }}
          size="medium"
          className="w-full"
        />
      </Card>
    </div>
  );
};

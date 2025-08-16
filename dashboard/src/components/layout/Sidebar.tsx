import React, { useContext } from 'react';
import { 
  DashboardOutlined, 
  ApiOutlined, 
  SettingOutlined,
  SecurityScanOutlined,
  FileTextOutlined,
  MonitorOutlined 
} from '@ant-design/icons';
import { Sider, Menu } from '../ui';
import { AppContext } from '../../context/AppContext';
import type { MenuItem } from '../ui';

export const Sidebar: React.FC = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('Sidebar must be used within AppProvider');
  }
  
  const { sidebarCollapsed, currentPage, setCurrentPage } = context;

  const menuItems: MenuItem[] = [
    {
      key: 'overview',
      label: 'Overview',
      icon: <DashboardOutlined />,
    },
    {
      key: 'services',
      label: 'Services',
      icon: <ApiOutlined />,
    },
    {
      key: 'rate-limits',
      label: 'Rate Limits',
      icon: <SecurityScanOutlined />,
    },
    {
      key: 'monitoring',
      label: 'Monitoring',
      icon: <MonitorOutlined />,
    },
    {
      key: 'authentication',
      label: 'Authentication',
      icon: <SecurityScanOutlined />,
    },
    {
      key: 'logs',
      label: 'Logs',
      icon: <FileTextOutlined />,
    },
    {
      key: 'settings',
      label: 'Settings',
      icon: <SettingOutlined />,
    },
  ];

  const handleMenuClick = (info: { key: string }) => {
    setCurrentPage(info.key);
  };

  return (
    <Sider
      collapsed={sidebarCollapsed}
      width={250}
      className="bg-white border-r border-gray-200"
    >
      <div className="p-4">
        <div className={`text-center ${sidebarCollapsed ? 'hidden' : 'block'}`}>
          <h2 className="text-lg font-semibold text-gray-800">Bridge MCP Gateway</h2>
          <p className="text-sm text-gray-500">Control Panel</p>
        </div>
        {sidebarCollapsed && (
          <div className="text-center">
            <div className="w-8 h-8 bg-blue-500 rounded text-white flex items-center justify-center mx-auto">
              BMG
            </div>
          </div>
        )}
      </div>
      
      <Menu
        items={menuItems}
        mode="inline"
        selectedKeys={[currentPage]}
        onClick={handleMenuClick}
        className="border-none"
      />
    </Sider>
  );
};

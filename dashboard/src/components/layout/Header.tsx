import React, { useContext } from 'react';
import { MenuFoldOutlined, MenuUnfoldOutlined, UserOutlined, BellOutlined, SettingOutlined, LogoutOutlined } from '@ant-design/icons';
import { Header as UIHeader, Button, Avatar, Badge, Dropdown, Space, Typography } from '../ui';
import { AppContext } from '../../context/AppContext';

export const Header: React.FC = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('Header must be used within AppProvider');
  }
  
  const { user, sidebarCollapsed, setSidebarCollapsed, notifications } = context;

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: 'Profile',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: 'Settings',
    },
    {
      key: 'divider',
      label: '',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      danger: true,
    },
  ];

  const notificationMenuItems = notifications.slice(0, 5).map((notification: any, index: number) => ({
    key: `notification-${index}`,
    label: (
      <div className="max-w-xs">
        <Typography.Text strong className="block">{notification.title}</Typography.Text>
        <Typography.Text type="secondary" className="text-xs">{notification.message}</Typography.Text>
        <Typography.Text type="secondary" className="text-xs block">{notification.timestamp}</Typography.Text>
      </div>
    ),
  }));

  return (
    <UIHeader className="bg-white border-b border-gray-200 px-6 flex items-center justify-between shadow-sm">
      <div className="flex items-center space-x-4">
        <Button
          type="text"
          icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="text-gray-600 hover:text-gray-800"
        />
        <div>
          <Typography.Text className="text-xl font-semibold text-gray-800">Bridge MCP Gateway Dashboard</Typography.Text>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        <Dropdown
          menu={{ items: notificationMenuItems }}
          placement="bottomRight"
          trigger={['click']}
        >
          <Badge count={notifications.filter((n: any) => !n.read).length} size="small">
            <Button type="text" icon={<BellOutlined />} className="text-gray-600 hover:text-gray-800" />
          </Badge>
        </Dropdown>

        <Dropdown
          menu={{ items: userMenuItems }}
          placement="bottomRight"
          trigger={['click']}
        >
          <Space className="cursor-pointer hover:bg-gray-50 px-2 py-1 rounded">
            <Avatar size="small" icon={<UserOutlined />} />
            <Typography.Text className="text-gray-700">{user?.name || 'User'}</Typography.Text>
          </Space>
        </Dropdown>
      </div>
    </UIHeader>
  );
};

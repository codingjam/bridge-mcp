import React from 'react';
import { Content } from '../ui';
import { OverviewDashboard } from '../pages/OverviewDashboard';

export const MainContent: React.FC = () => {
  return (
    <Content className="p-6 bg-gray-50 min-h-screen">
      <OverviewDashboard />
    </Content>
  );
};

import React, { useContext } from 'react';
import { Content } from '../ui';
import { AppContext } from '../../context/AppContext';
import { OverviewDashboard } from '../pages/OverviewDashboard';
import { Services } from '../pages/Services';

export const MainContent: React.FC = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('MainContent must be used within AppProvider');
  }
  
  const { currentPage } = context;

  const renderPage = () => {
    switch (currentPage) {
      case 'overview':
        return <OverviewDashboard />;
      case 'services':
        return <Services />;
      case 'rate-limits':
        return <div className="p-8 text-center text-gray-500">Rate Limits page coming soon...</div>;
      case 'monitoring':
        return <div className="p-8 text-center text-gray-500">Monitoring page coming soon...</div>;
      case 'authentication':
        return <div className="p-8 text-center text-gray-500">Authentication page coming soon...</div>;
      case 'logs':
        return <div className="p-8 text-center text-gray-500">Logs page coming soon...</div>;
      case 'settings':
        return <div className="p-8 text-center text-gray-500">Settings page coming soon...</div>;
      default:
        return <OverviewDashboard />;
    }
  };

  return (
    <Content className="p-6 bg-gray-50 min-h-screen">
      {renderPage()}
    </Content>
  );
};

import React, { useState } from 'react';
import Navbar from './components/Navbar';
import DashboardPage from './pages/DashboardPage';
import DataPrepPage from './pages/DataPrepPage';
import SqlAgentPage from './pages/SqlAgentPage';
import QueryHistoryPage from './pages/QueryHistoryPage';
import { ThemeProvider } from './context/ThemeContext';

function AppContent() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [activeDataset, setActiveDataset] = useState(null);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors duration-200">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeDataset={activeDataset}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-12">
        {activeTab === 'dashboard' && (
          <DashboardPage
            onStartPrep={() => setActiveTab('prep')}
            onStartSql={() => setActiveTab('sql')}
            activeDataset={activeDataset}
          />
        )}

        {activeTab === 'prep' && (
          <DataPrepPage
            activeDataset={activeDataset}
            setActiveDataset={setActiveDataset}
            onNavigateToSql={() => setActiveTab('sql')}
          />
        )}

        {activeTab === 'sql' && (
          <SqlAgentPage
            activeDataset={activeDataset}
          />
        )}

        {activeTab === 'history' && (
          <QueryHistoryPage />
        )}
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-900 bg-white dark:bg-slate-950 py-6 text-center text-xs text-slate-500 transition-colors">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>DataPilot AI Platform &copy; 2026</div>
          <div className="flex items-center space-x-4 text-slate-500 dark:text-slate-400">
            <span>Agent 1: Data Preparation</span>
            <span>•</span>
            <span>Human Approval Layer</span>
            <span>•</span>
            <span>Agent 2: SQL Agent</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}

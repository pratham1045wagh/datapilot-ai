import React from 'react';
import { Database, Sparkles, Brain, History, FileSpreadsheet, CheckCircle2, Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function Navbar({ activeTab, setActiveTab, activeDataset }) {
  const { darkMode, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-200 dark:border-slate-800/80 bg-white/90 dark:bg-slate-950/80 backdrop-blur-xl transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Title */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-slate-900 dark:text-white">
                  DataPilot AI
                </span>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30">
                  Platform
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">AI-Powered Data Prep & Natural Language SQL Agent</p>
            </div>
          </div>

          {/* Nav Tabs */}
          <nav className="flex items-center space-x-1 sm:space-x-2">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'dashboard'
                  ? 'bg-indigo-50 dark:bg-indigo-600/20 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-500/30 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
              }`}
            >
              <Database className="w-4 h-4" />
              <span className="hidden sm:inline">Dashboard</span>
            </button>

            <button
              onClick={() => setActiveTab('prep')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'prep'
                  ? 'bg-purple-50 dark:bg-purple-600/20 text-purple-600 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
              }`}
            >
              <Sparkles className="w-4 h-4 text-purple-500 dark:text-purple-400" />
              <span>Data Prep Agent</span>
            </button>

            <button
              onClick={() => setActiveTab('sql')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'sql'
                  ? 'bg-emerald-50 dark:bg-emerald-600/20 text-emerald-600 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
              }`}
            >
              <Database className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />
              <span>Ask Your Data</span>
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'history'
                  ? 'bg-amber-50 dark:bg-amber-600/20 text-amber-600 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/50'
              }`}
            >
              <History className="w-4 h-4 text-amber-500 dark:text-amber-400" />
              <span className="hidden sm:inline">History</span>
            </button>
          </nav>

          {/* Theme Toggle & Active Dataset Status */}
          <div className="flex items-center space-x-3">
            {activeDataset ? (
              <div className="hidden lg:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-900 border border-emerald-500/30 text-xs">
                <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                <span className="text-slate-700 dark:text-slate-300 truncate max-w-[130px] font-mono">{activeDataset.filename}</span>
                {activeDataset.isCleaned ? (
                  <span className="flex items-center text-emerald-600 dark:text-emerald-400 font-semibold text-[10px] bg-emerald-500/10 px-1.5 py-0.5 rounded">
                    <CheckCircle2 className="w-3 h-3 mr-0.5" /> Cleaned
                  </span>
                ) : (
                  <span className="text-amber-600 dark:text-amber-400 text-[10px] bg-amber-500/10 px-1.5 py-0.5 rounded">
                    Raw
                  </span>
                )}
              </div>
            ) : null}

            {/* Light / Dark Mode Toggle Button */}
            <button
              onClick={toggleTheme}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-xs font-semibold shadow-sm"
              title="Toggle Light / Dark Theme"
            >
              {darkMode ? (
                <>
                  <Sun className="w-4 h-4 text-amber-400" />
                  <span>Light Mode</span>
                </>
              ) : (
                <>
                  <Moon className="w-4 h-4 text-indigo-600" />
                  <span>Dark Mode</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

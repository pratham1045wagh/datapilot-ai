import React from 'react';
import { Sparkles, Database, ShieldCheck, Cpu, ArrowRight, Upload, CheckCircle2, Layers, LineChart } from 'lucide-react';

export default function DashboardPage({ onStartPrep, onStartSql, activeDataset }) {
  return (
    <div className="space-y-8 pb-12">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl glass-panel p-8 sm:p-12 border border-indigo-200 dark:border-indigo-500/20 bg-gradient-to-br from-indigo-50/90 via-purple-50/50 to-white dark:from-slate-900/90 dark:via-indigo-950/40 dark:to-slate-900/90 shadow-sm">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-12 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-600 dark:text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Dual Agentic AI Architecture</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white leading-tight">
            Autonomous Data Preparation & Natural Language SQL Agent
          </h1>

          <p className="text-slate-700 dark:text-slate-300 text-base sm:text-lg leading-relaxed">
            Transform messy, unformatted datasets into clean, validated SQLite tables with human-in-the-loop AI recommendations & natural language suggestions, then query your database instantly using natural English.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              onClick={onStartPrep}
              className="flex items-center space-x-2 px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold shadow-lg shadow-indigo-500/25 transition-all transform hover:-translate-y-0.5"
            >
              <Upload className="w-5 h-5" />
              <span>Upload & Prepare Dataset</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </button>

            {activeDataset && (
              <button
                onClick={onStartSql}
                className="flex items-center space-x-2 px-6 py-3 rounded-xl glass-card hover:bg-slate-200 dark:hover:bg-slate-800/80 text-emerald-600 dark:text-emerald-300 font-semibold border border-emerald-500/30 transition-all"
              >
                <Database className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
                <span>Ask SQL Agent</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Two Logically Separate Agents Banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Agent 1 Card */}
        <div className="glass-panel p-6 rounded-2xl border border-purple-500/20 bg-white dark:bg-slate-900/60 space-y-4 hover:border-purple-500/40 transition-all">
          <div className="flex items-center justify-between">
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-500 dark:text-purple-400">
              <Sparkles className="w-6 h-6" />
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-300 border border-purple-500/20">
              Agent 1
            </span>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">Data Preparation Agent</h3>
            <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
              Profiles dataset quality, detects duplicate rows, missing values, invalid strings & casing errors, accepts natural language user suggestions, and executes deterministic Pandas transformations with verification.
            </p>
          </div>
          <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-purple-500 dark:text-purple-400 mr-2" /> Profiling & Invalid String Detection</li>
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-purple-400 mr-2" /> Natural Language User Suggestions</li>
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-purple-400 mr-2" /> Preprocessing Verification Engine</li>
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-purple-400 mr-2" /> On-Screen Clean Dataset Preview & PDF Report</li>
          </ul>
        </div>

        {/* Agent 2 Card */}
        <div className="glass-panel p-6 rounded-2xl border border-emerald-500/20 bg-white dark:bg-slate-900/60 space-y-4 hover:border-emerald-500/40 transition-all">
          <div className="flex items-center justify-between">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-500 dark:text-emerald-400">
              <Database className="w-6 h-6" />
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border border-emerald-500/20">
              Agent 2
            </span>
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">Natural Language SQL Agent</h3>
            <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
              Inspects SQLite table schema, creates query execution plans, generates safe read-only SQL, executes queries against SQLite, and self-corrects on errors automatically.
            </p>
          </div>
          <ul className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400 mr-2" /> English Question to SQL Generation</li>
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400 mr-2" /> Strict Read-Only Security Validator</li>
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400 mr-2" /> Autonomous Self-Correction Loop</li>
            <li className="flex items-center"><CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400 mr-2" /> Dynamic Recharts Visualizations</li>
          </ul>
        </div>
      </div>

      {/* Interactive Process Workflow */}
      <div className="glass-panel p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-6">
        <div className="flex items-center space-x-3">
          <Layers className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">Platform End-to-End Workflow</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card p-4 rounded-xl space-y-2 relative bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
            <div className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">Step 1</div>
            <div className="font-bold text-slate-900 dark:text-white text-sm">Upload Dataset</div>
            <p className="text-slate-600 dark:text-slate-400 text-xs">CSV or Excel format with automatic statistical profiling & invalid string detection.</p>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-2 relative bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
            <div className="text-xs font-semibold text-purple-600 dark:text-purple-400">Step 2</div>
            <div className="font-bold text-slate-900 dark:text-white text-sm">AI Recs & User Suggestions</div>
            <p className="text-slate-600 dark:text-slate-400 text-xs">Review AI recs, add natural language custom rules, preview before applying.</p>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-2 relative bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
            <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">Step 3</div>
            <div className="font-bold text-slate-900 dark:text-white text-sm">Clean, Verify & Preview</div>
            <p className="text-slate-600 dark:text-slate-400 text-xs">Pandas cleans data, verification engine verifies rules, on-screen preview & PDF report generated.</p>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-2 relative bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
            <div className="text-xs font-semibold text-amber-600 dark:text-amber-400">Step 4</div>
            <div className="font-bold text-slate-900 dark:text-white text-sm">Ask NL Questions</div>
            <p className="text-slate-600 dark:text-slate-400 text-xs">SQL Agent generates, validates, executes, & self-corrects SQL on SQLite DB.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

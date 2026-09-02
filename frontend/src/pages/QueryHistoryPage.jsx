import React, { useState, useEffect } from 'react';
import { History, Search, RefreshCw, CheckCircle2, AlertTriangle, Database, Code, FileText } from 'lucide-react';
import { api } from '../services/api';

export default function QueryHistoryPage() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await api.getQueryHistory();
      setHistory(res.history || []);
    } catch (err) {
      console.error("Failed to fetch query history:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = async () => {
    if (history.length === 0) return;
    const datasetId = history[0].dataset_id;
    setDownloadingReport(true);
    setError(null);
    try {
      const res = await api.downloadSqlReport(datasetId);
      if (!res.data) throw new Error("No report data returned.");

      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const safeId = datasetId.slice(0, 8);
      link.setAttribute('download', `sql_session_report_${safeId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download SQL report:", err);
      let errMsg = "Unable to generate SQL report. Please try again.";
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const json = JSON.parse(text);
          if (json.detail) errMsg = json.detail;
        } catch (_) {}
      } else if (err.response?.data?.detail) {
        errMsg = err.response.data.detail;
      }
      setError(errMsg);
    } finally {
      setDownloadingReport(false);
    }
  };

  const filteredHistory = history.filter(item => 
    item.user_question.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.generated_sql.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-8 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white flex items-center space-x-3">
            <History className="w-7 h-7 text-amber-500 dark:text-amber-400" />
            <span>Query Execution History</span>
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Audit log of all natural language questions, generated SQL, execution metrics, and self-correction attempts.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {history.length > 0 && (
            <button
              onClick={handleDownloadReport}
              disabled={downloadingReport}
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all flex items-center space-x-2 border border-slate-700 dark:border-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {downloadingReport ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Generating Report...</span>
                </>
              ) : (
                <>
                  <FileText className="w-4 h-4 text-emerald-400 dark:text-white" />
                  <span>Download SQL Report</span>
                </>
              )}
            </button>
          )}

          <button
            onClick={fetchHistory}
            className="px-4 py-2 rounded-xl glass-card text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white flex items-center space-x-2 border border-slate-300 dark:border-slate-800"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Refresh History</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-300 text-sm flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Input */}
      <div className="glass-panel p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 flex items-center space-x-3">
        <Search className="w-5 h-5 text-slate-400" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filter query history by question or SQL keyword..."
          className="flex-1 bg-transparent border-none text-slate-900 dark:text-slate-100 placeholder-slate-400 text-sm focus:outline-none"
        />
      </div>

      {/* History List */}
      {loading ? (
        <div className="glass-panel p-12 rounded-2xl text-center space-y-3 bg-white dark:bg-slate-900/40">
          <RefreshCw className="w-8 h-8 text-amber-500 dark:text-amber-400 animate-spin mx-auto" />
          <p className="text-slate-600 dark:text-slate-400 text-sm">Loading query history...</p>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="glass-panel p-12 rounded-2xl text-center space-y-2 bg-white dark:bg-slate-900/40">
          <Database className="w-10 h-10 text-slate-400 mx-auto" />
          <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">No Query History Found</h3>
          <p className="text-slate-500 text-xs">Run a query in the "Ask Your Data" tab to generate execution logs.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredHistory.map((item, idx) => (
            <div key={idx} className="glass-panel p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
                <div className="flex items-center space-x-3">
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">{item.timestamp || 'Recent'}</span>
                  <span className="font-bold text-slate-900 dark:text-white text-base">"{item.user_question}"</span>
                </div>

                <div className="flex items-center space-x-2">
                  {item.retries > 0 && (
                    <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-semibold">
                      Self-Corrected ({item.retries} retries)
                    </span>
                  )}

                  {item.executed ? (
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-semibold flex items-center">
                      <CheckCircle2 className="w-3 h-3 mr-1" /> Executed ({item.row_count} rows)
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20 font-semibold flex items-center">
                      <AlertTriangle className="w-3 h-3 mr-1" /> Failed
                    </span>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Generated SQL:</div>
                <pre className="p-3 rounded-xl bg-slate-900 font-mono text-xs text-emerald-400 overflow-x-auto border border-slate-800 whitespace-pre">
                  {item.formatted_sql || item.executed_sql || item.generated_sql}
                </pre>
              </div>

              {item.explanation && (
                <p className="text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/40 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                  {item.explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

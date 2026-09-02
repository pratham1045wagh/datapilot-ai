import React, { useState, useEffect } from 'react';
import { 
  Database, Send, Sparkles, AlertTriangle, CheckCircle2, Copy, Check, RefreshCw, 
  BarChart2, Layers, ShieldCheck, CornerDownRight, FileText
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '../services/api';
import { useTheme } from '../context/ThemeContext';

export default function SqlAgentPage({ activeDataset }) {
  const { darkMode } = useTheme();
  const [userQuestion, setUserQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [schemaData, setSchemaData] = useState(null);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [queryCount, setQueryCount] = useState(0);
  const [downloadingReport, setDownloadingReport] = useState(false);

  // Suggested questions
  const sampleQuestions = [
    "How many products are there?",
    "What is the average price?",
    "Which category has the highest sales?",
    "Give me total sales for each city.",
    "Show top 5 products by price."
  ];

  // Fetch SQLite schema & query history count when active dataset changes
  useEffect(() => {
    if (activeDataset?.dataset_id) {
      api.getSchema(activeDataset.dataset_id)
        .then(data => setSchemaData(data))
        .catch(err => console.error("Failed to load schema:", err));

      fetchQueryHistoryCount();
    } else {
      setQueryCount(0);
    }
  }, [activeDataset]);

  const fetchQueryHistoryCount = async () => {
    if (activeDataset?.dataset_id) {
      try {
        const res = await api.getQueryHistory(activeDataset.dataset_id);
        setQueryCount(res.history ? res.history.length : 0);
      } catch (err) {
        console.error("Failed to fetch query history count:", err);
      }
    }
  };

  const handleAsk = async (questionToAsk) => {
    const q = questionToAsk || userQuestion;
    if (!q.trim() || !activeDataset) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await api.executeQuery(q, activeDataset.dataset_id);
      setResponse(res);
      await fetchQueryHistoryCount();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Query execution failed');
      await fetchQueryHistoryCount();
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadSqlReport = async () => {
    if (!activeDataset?.dataset_id || queryCount === 0) return;
    setDownloadingReport(true);
    setError(null);
    try {
      const res = await api.downloadSqlReport(activeDataset.dataset_id);
      if (!res.data) throw new Error("No report data returned.");

      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const safeId = activeDataset.dataset_id.slice(0, 8);
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

  const handleCopySql = () => {
    const rawSql = response?.executed_sql || response?.generated_sql;
    if (rawSql) {
      navigator.clipboard.writeText(rawSql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const chartGridStroke = darkMode ? "#334155" : "#e2e8f0";
  const chartTextStroke = darkMode ? "#94a3b8" : "#475569";
  const tooltipStyle = darkMode 
    ? { backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', color: '#f8fafc' }
    : { backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '12px', color: '#0f172a', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)' };

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white flex items-center space-x-3">
            <Database className="w-7 h-7 text-emerald-500 dark:text-emerald-400" />
            <span>Natural Language SQL Agent</span>
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Ask questions in normal English — the agent inspects schema, plans queries, generates read-only SQL, executes against SQLite, & self-corrects on errors.
          </p>
        </div>

        {activeDataset && (
          <button
            onClick={handleDownloadSqlReport}
            disabled={queryCount === 0 || downloadingReport}
            title={queryCount === 0 ? "No SQL queries have been executed yet." : "Download complete SQL session PDF report"}
            className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white font-bold text-xs shadow-md transition-all flex items-center space-x-2 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 dark:border-emerald-500 self-start sm:self-auto"
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
      </div>

      {!activeDataset && (
        <div className="glass-panel p-8 rounded-2xl border border-amber-300 dark:border-amber-500/30 text-amber-900 dark:text-amber-300 text-sm flex items-center space-x-3 bg-amber-50 dark:bg-amber-500/10">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-500" />
          <span>No active dataset loaded. Please upload and clean a dataset first in the <strong>Data Prep Agent</strong> tab.</span>
        </div>
      )}

      {activeDataset && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Left Column: Schema Inspector */}
          <div className="lg:col-span-1 glass-panel p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-6 h-fit">
            <div className="flex items-center space-x-2 border-b border-slate-200 dark:border-slate-800 pb-3">
              <Layers className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />
              <h3 className="font-bold text-slate-900 dark:text-white text-sm">SQLite Schema Inspector</h3>
            </div>

            {schemaData ? (
              <div className="space-y-4 text-xs">
                <div>
                  <div className="text-slate-500 dark:text-slate-400 font-medium">Table Name:</div>
                  <div className="font-mono text-emerald-600 dark:text-emerald-400 font-bold mt-0.5 truncate">{schemaData.table_name}</div>
                </div>

                <div>
                  <div className="text-slate-500 dark:text-slate-400 font-medium mb-2">Columns & Data Types:</div>
                  <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                    {schemaData.schema.map((col, idx) => (
                      <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800">
                        <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">{col.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-mono">
                          {col.type}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-200 dark:border-slate-800">
                  <div className="flex items-center space-x-1.5 text-emerald-600 dark:text-emerald-400 text-[11px] font-semibold">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Security: Read-Only SQLite Validation Active</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-slate-400 text-xs py-4">Loading SQLite table schema...</div>
            )}
          </div>

          {/* Right Column: Query Interface & Execution Results */}
          <div className="lg:col-span-3 space-y-6">
            {/* Input Box */}
            <div className="glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-4 shadow-sm">
              <label className="block text-sm font-bold text-slate-900 dark:text-white">Ask your dataset a question in English:</label>
              
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  value={userQuestion}
                  onChange={(e) => setUserQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                  placeholder="e.g. Which category generated the highest total revenue?"
                  className="flex-1 px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                />
                <button
                  onClick={() => handleAsk()}
                  disabled={loading || !userQuestion.trim()}
                  className="px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-sm shadow-lg shadow-indigo-500/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Reasoning...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Ask SQL Agent</span>
                    </>
                  )}
                </button>
              </div>

              {/* Sample Questions Pills */}
              <div className="pt-2">
                <div className="text-xs text-slate-500 dark:text-slate-400 mb-2 font-medium">Suggested Sample Questions:</div>
                <div className="flex flex-wrap gap-2">
                  {sampleQuestions.map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => { setUserQuestion(q); handleAsk(q); }}
                      className="px-3 py-1.5 rounded-lg text-xs bg-slate-100 dark:bg-slate-800/80 hover:bg-indigo-500/10 dark:hover:bg-indigo-500/20 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 transition-all flex items-center space-x-1"
                    >
                      <CornerDownRight className="w-3 h-3 text-indigo-500 dark:text-indigo-400" />
                      <span>{q}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-300 text-sm flex items-center space-x-3">
                <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Agent Results Display */}
            {response && (
              <div className="space-y-6">
                {/* Reasoning & Generated SQL Card */}
                <div className="glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-5 h-5 text-purple-500 dark:text-purple-400" />
                      <h3 className="font-bold text-slate-900 dark:text-white text-base">SQL Agent Reasoning & Generated Query</h3>
                    </div>
                    {response.attempts > 1 && (
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                        Autonomous Self-Corrected ({response.attempts} attempts)
                      </span>
                    )}
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="text-slate-600 dark:text-slate-400 font-medium">Query Plan / Reasoning:</div>
                    <p className="text-slate-800 dark:text-slate-200 bg-slate-50 dark:bg-slate-900/80 p-3 rounded-xl border border-slate-200 dark:border-slate-800 font-sans">
                      {response.query_plan}
                    </p>
                  </div>

                  {/* SQL Code Block */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-600 dark:text-slate-400 font-medium">Validated Read-Only SQLite SQL:</span>
                      <button
                        onClick={handleCopySql}
                        className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline flex items-center space-x-1"
                      >
                        {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copied ? 'Copied!' : 'Copy SQL'}</span>
                      </button>
                    </div>
                    <pre className="p-4 rounded-xl bg-slate-900 dark:bg-slate-950 text-emerald-400 font-mono text-xs overflow-x-auto border border-slate-800 whitespace-pre">
                      <code>{response.formatted_sql || response.executed_sql || response.generated_sql}</code>
                    </pre>
                  </div>

                  {/* Explanation Summary */}
                  {response.explanation && (
                    <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-800 dark:text-emerald-300">
                      <strong>AI Summary:</strong> {response.explanation}
                    </div>
                  )}
                </div>

                {/* Visualization & Table Card */}
                {response.rows && response.rows.length > 0 && (
                  <div className="glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-6">
                    <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
                      <div className="flex items-center space-x-2">
                        <BarChart2 className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                        <h3 className="font-bold text-slate-900 dark:text-white text-base">Query Execution Results ({response.row_count} rows)</h3>
                      </div>
                    </div>

                    {/* Chart Visualization */}
                    {(() => {
                      const xAxisKey = response.x_axis || response.chart_config?.x_axis || (response.columns && response.columns[0]);
                      const yAxisKey = response.y_axis || response.chart_config?.y_axis || (response.columns && response.columns[1]) || (response.columns && response.columns[0]);
                      if (response.visualization_type === 'bar' && xAxisKey && yAxisKey && response.rows.length > 0) {
                        return (
                          <div className="h-64 w-full pt-4">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={response.rows}>
                                <CartesianGrid strokeDasharray="3 3" stroke={chartGridStroke} opacity={0.5} />
                                <XAxis dataKey={xAxisKey} stroke={chartTextStroke} fontSize={11} />
                                <YAxis stroke={chartTextStroke} fontSize={11} />
                                <Tooltip contentStyle={tooltipStyle} />
                                <Bar dataKey={yAxisKey} fill="#6366f1" radius={[4, 4, 0, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        );
                      }
                      return null;
                    })()}

                    {/* Results Table */}
                    <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 uppercase font-semibold">
                          <tr>
                            {response.columns.map((col, idx) => (
                              <th key={idx} className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200 font-mono">
                          {response.rows.map((row, rIdx) => (
                            <tr key={rIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                              {response.columns.map((col, cIdx) => (
                                <td key={cIdx} className="px-4 py-2.5 whitespace-nowrap">
                                  {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-slate-400 italic">null</span>}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

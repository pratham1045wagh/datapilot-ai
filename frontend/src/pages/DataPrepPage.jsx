import React, { useState, useEffect } from 'react';
import { 
  Upload, Sparkles, AlertTriangle, CheckCircle2, XCircle, FileSpreadsheet, 
  ArrowRight, Download, RefreshCw, Eye, Sliders, CheckSquare, Square, FileText, Info, MessageSquare, Search, ChevronLeft, ChevronRight
} from 'lucide-react';
import { api } from '../services/api';

export default function DataPrepPage({ activeDataset, setActiveDataset, onNavigateToSql }) {
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  
  // Data prep state
  const [profile, setProfile] = useState(activeDataset?.profile || null);
  const [issues, setIssues] = useState(activeDataset?.issues || []);
  const [recommendations, setRecommendations] = useState([]);
  const [userApprovals, setUserApprovals] = useState({}); // { rec_id: { approved: bool, strategy: str } }
  const [previewItems, setPreviewItems] = useState(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [report, setReport] = useState(null);
  const [cleaningComplete, setCleaningComplete] = useState(false);

  // User Suggestion State
  const [userInstruction, setUserInstruction] = useState('');
  const [analyzingSuggestion, setAnalyzingSuggestion] = useState(false);
  const [suggestionResult, setSuggestionResult] = useState(null);

  // On-screen Cleaned Dataset Preview State
  const [datasetPreview, setDatasetPreview] = useState(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageSize, setPreviewPageSize] = useState(10);
  const [previewSearch, setPreviewSearch] = useState('');
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Post-Preprocessing User Feedback & Suggestion State
  const [postInstruction, setPostInstruction] = useState('');
  const [analyzingPost, setAnalyzingPost] = useState(false);
  const [postAnalysis, setPostAnalysis] = useState(null);
  const [applyingPost, setApplyingPost] = useState(false);
  const [postResult, setPostResult] = useState(null);

  // Reset dataset state to upload a new file
  const handleResetDataset = () => {
    setActiveDataset(null);
    setProfile(null);
    setIssues([]);
    setRecommendations([]);
    setUserApprovals({});
    setPreviewItems(null);
    setShowPreviewModal(false);
    setReport(null);
    setCleaningComplete(false);
    setUserInstruction('');
    setSuggestionResult(null);
    setDatasetPreview(null);
    setPostInstruction('');
    setPostAnalysis(null);
    setPostResult(null);
    setError(null);
  };

  // Handle post-preprocessing instruction analysis
  const handleAnalyzePostSuggestion = async () => {
    const datasetId = activeDataset?.dataset_id || profile?.dataset_id || report?.dataset_id;
    if (!postInstruction.trim()) return;

    if (!datasetId) {
      setError('Dataset ID is missing. Please upload or select a dataset first.');
      return;
    }

    setAnalyzingPost(true);
    setError(null);
    setPostAnalysis(null);
    setPostResult(null);

    try {
      const res = await api.analyzePostCleanSuggestion(datasetId, postInstruction);
      setPostAnalysis(res);
    } catch (err) {
      console.error('Post clean analysis error:', err);
      const errMsg = err.response?.data?.detail || err.message || 'Failed to analyze post-preprocessing suggestion';
      setError(errMsg);
      setPostAnalysis({
        supported: false,
        unsupported_reason: errMsg
      });
    } finally {
      setAnalyzingPost(false);
    }
  };

  // Handle post-preprocessing suggestion approval & application
  const handleApplyPostSuggestion = async (approved) => {
    const datasetId = activeDataset?.dataset_id || profile?.dataset_id || report?.dataset_id;
    if (!datasetId || !postAnalysis) return;

    if (!approved) {
      setPostAnalysis(null);
      setPostInstruction('');
      return;
    }

    setApplyingPost(true);
    setError(null);

    try {
      const payload = {
        user_instruction: postInstruction,
        requested_change: postAnalysis.requested_change,
        column: postAnalysis.column,
        operation: postAnalysis.operation,
        mapping: postAnalysis.mapping,
        strategy: postAnalysis.strategy,
        approved: true
      };

      const res = await api.applyPostCleanSuggestion(datasetId, payload);
      setPostResult(res);
      if (res.report) {
        setReport(res.report);
        setProfile(prev => ({
          ...prev,
          row_count: res.report.final_rows,
          column_count: res.report.final_cols,
          total_missing: res.report.before_after_comparison?.find(c => c.metric.includes('Missing'))?.after ?? prev?.total_missing,
          total_duplicates: res.report.before_after_comparison?.find(c => c.metric.includes('Duplicate'))?.after ?? prev?.total_duplicates,
        }));
        setActiveDataset(prev => ({
          ...prev,
          isCleaned: true,
          profile: {
            ...prev?.profile,
            row_count: res.report.final_rows,
            column_count: res.report.final_cols,
          }
        }));
      }

      // Automatically refresh PREPROCESSED DATASET PREVIEW table
      fetchDatasetPreview(datasetId, previewPage, previewPageSize, previewSearch);

      setPostAnalysis(null);
      setPostInstruction('');
    } catch (err) {
      console.error('Post clean apply error:', err);
      const errMsg = err.response?.data?.detail || err.message || 'Failed to apply post-preprocessing suggestion';
      setError(errMsg);
    } finally {
      setApplyingPost(false);
    }
  };

  // Handle File Upload
  const handleFileUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setCleaningComplete(false);
    setReport(null);
    setPreviewItems(null);
    setSuggestionResult(null);
    setDatasetPreview(null);

    try {
      const data = await api.uploadFile(file);
      setProfile(data.profile);
      setIssues(data.issues);
      setActiveDataset({
        dataset_id: data.dataset_id,
        filename: data.filename,
        isCleaned: false,
        profile: data.profile,
        issues: data.issues
      });

      // Fetch AI recommendations
      fetchRecommendations(data.dataset_id);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'File upload failed');
    } finally {
      setUploading(false);
    }
  };

  // Fetch AI Recommendations
  const fetchRecommendations = async (datasetId) => {
    setLoading(true);
    try {
      const res = await api.getRecommendations(datasetId);
      setRecommendations(res.recommendations);
      
      // Initialize approval state: auto-check low & med risk, leave high-risk (outliers) unchecked by default
      const initialApprovals = {};
      res.recommendations.forEach(r => {
        initialApprovals[r.id] = {
          approved: r.risk_level !== 'high', // High-risk operations (outliers) require explicit user check!
          strategy: r.recommended_strategy
        };
      });
      setUserApprovals(initialApprovals);
    } catch (err) {
      setError('Failed to fetch AI cleaning recommendations');
    } finally {
      setLoading(false);
    }
  };

  // Handle User Natural Language Preprocessing Suggestion
  const handleAnalyzeSuggestion = async () => {
    if (!userInstruction.trim() || !activeDataset) return;
    setAnalyzingSuggestion(true);
    setError(null);
    setSuggestionResult(null);

    try {
      const res = await api.addUserSuggestion(activeDataset.dataset_id, userInstruction);
      setSuggestionResult(res);

      if (res.supported && res.recommendation) {
        const newRec = res.recommendation;
        setRecommendations(prev => [...prev.filter(r => r.id !== newRec.id), newRec]);
        setUserApprovals(prev => ({
          ...prev,
          [newRec.id]: {
            approved: true,
            strategy: newRec.recommended_strategy
          }
        }));
      }
    } catch (err) {
      setError('Failed to analyze user suggestion');
    } finally {
      setAnalyzingSuggestion(false);
    }
  };

  // Toggle approval for single recommendation
  const toggleApproval = (recId) => {
    setUserApprovals(prev => ({
      ...prev,
      [recId]: {
        ...prev[recId],
        approved: !prev[recId]?.approved
      }
    }));
  };

  // Change strategy for single recommendation
  const changeStrategy = (recId, strategy) => {
    setUserApprovals(prev => ({
      ...prev,
      [recId]: {
        ...prev[recId],
        strategy
      }
    }));
  };

  // Select all or clear selection
  const selectAll = (status) => {
    const updated = {};
    recommendations.forEach(r => {
      updated[r.id] = {
        approved: status,
        strategy: userApprovals[r.id]?.strategy || r.recommended_strategy
      };
    });
    setUserApprovals(updated);
  };

  // Generate preview of changes
  const handlePreview = async () => {
    if (!activeDataset) return;
    setLoading(true);
    try {
      const actions = Object.entries(userApprovals).map(([rec_id, val]) => ({
        recommendation_id: rec_id,
        approved: val.approved,
        selected_strategy: val.strategy
      }));

      const res = await api.previewCleaning(activeDataset.dataset_id, actions);
      setPreviewItems(res.previews);
      setShowPreviewModal(true);
    } catch (err) {
      setError('Failed to calculate cleaning preview');
    } finally {
      setLoading(false);
    }
  };

  // Apply approved cleaning actions
  const handleApplyCleaning = async () => {
    if (!activeDataset) return;
    setLoading(true);
    setError(null);
    setShowPreviewModal(false);

    try {
      const actions = Object.entries(userApprovals).map(([rec_id, val]) => ({
        recommendation_id: rec_id,
        approved: val.approved,
        selected_strategy: val.strategy
      }));

      const res = await api.cleanDataset(activeDataset.dataset_id, actions);
      setReport(res.report);
      setCleaningComplete(true);

      if (res.report) {
        setProfile(prev => ({
          ...prev,
          row_count: res.report.final_rows,
          column_count: res.report.final_cols,
          total_missing: res.report.before_after_comparison?.find(c => c.metric.includes('Missing'))?.after ?? prev?.total_missing,
          total_duplicates: res.report.before_after_comparison?.find(c => c.metric.includes('Duplicate'))?.after ?? prev?.total_duplicates,
        }));
      }

      setActiveDataset(prev => ({
        ...prev,
        isCleaned: true,
        profile: {
          ...prev?.profile,
          row_count: res.report?.final_rows ?? prev?.profile?.row_count,
          column_count: res.report?.final_cols ?? prev?.profile?.column_count,
        }
      }));

      // Fetch initial page of cleaned dataset preview
      fetchDatasetPreview(activeDataset.dataset_id, 1, previewPageSize, '');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Cleaning execution failed');
    } finally {
      setLoading(false);
    }
  };

  // Fetch On-Screen Cleaned Dataset Preview
  const fetchDatasetPreview = async (datasetId, page, pageSize, search) => {
    setLoadingPreview(true);
    try {
      const res = await api.getCleanedPreview(datasetId, page, pageSize, search);
      setDatasetPreview(res);
      setPreviewPage(res.page);
    } catch (err) {
      console.error('Failed to load dataset preview:', err);
    } finally {
      setLoadingPreview(false);
    }
  };

  // Trigger preview page or size update
  const handlePreviewPageChange = (e, newPage) => {
    if (e && e.preventDefault) e.preventDefault();
    const datasetId = activeDataset?.dataset_id || profile?.dataset_id || report?.dataset_id;
    if (!datasetId || !datasetPreview) return;
    if (newPage < 1 || newPage > datasetPreview.total_pages) return;
    fetchDatasetPreview(datasetId, newPage, previewPageSize, previewSearch);
  };

  const handlePreviewPageSizeChange = (newSize) => {
    setPreviewPageSize(newSize);
    const datasetId = activeDataset?.dataset_id || profile?.dataset_id || report?.dataset_id;
    if (!datasetId) return;
    fetchDatasetPreview(datasetId, 1, newSize, previewSearch);
  };

  const handlePreviewSearchSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    const datasetId = activeDataset?.dataset_id || profile?.dataset_id || report?.dataset_id;
    if (!datasetId) return;
    fetchDatasetPreview(datasetId, 1, previewPageSize, previewSearch);
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white flex items-center space-x-3">
            <Sparkles className="w-7 h-7 text-purple-500 dark:text-purple-400" />
            <span>Data Preparation Agent</span>
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Profiling, quality analysis, AI recommendations, natural language suggestions, & verification engine.
          </p>
        </div>

        {activeDataset && (
          <div className="flex items-center space-x-3">
            <button
              onClick={handleResetDataset}
              className="px-4 py-2 rounded-xl glass-card text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white flex items-center space-x-2 border border-slate-300 dark:border-slate-800"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Different File</span>
            </button>
          </div>
        )}
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-300 text-sm flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 1. Upload Dropzone if no dataset active */}
      {!profile && (
        <div className="glass-panel p-12 rounded-3xl border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500/50 transition-all text-center space-y-6 bg-white dark:bg-slate-900/40">
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center mx-auto text-indigo-500 dark:text-indigo-400 shadow-lg shadow-indigo-500/10">
            <FileSpreadsheet className="w-8 h-8" />
          </div>

          <div className="max-w-md mx-auto space-y-2">
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">Upload Your Dataset</h3>
            <p className="text-slate-600 dark:text-slate-400 text-sm">
              Drag and drop your CSV or Excel (.xlsx, .xls) file here, or click to browse.
            </p>
          </div>

          <div className="flex justify-center items-center space-x-4">
            <label className="cursor-pointer px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-lg shadow-indigo-500/25 transition-all inline-flex items-center space-x-2">
              <Upload className="w-4 h-4" />
              <span>Select CSV / Excel File</span>
              <input
                type="file"
                accept=".csv, .xlsx, .xls"
                className="hidden"
                onChange={(e) => handleFileUpload(e.target.files[0])}
              />
            </label>
          </div>

          {uploading && (
            <div className="flex items-center justify-center space-x-2 text-indigo-600 dark:text-indigo-400 text-sm">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Uploading & profiling dataset...</span>
            </div>
          )}
        </div>
      )}

      {/* 2. Dataset Profiling Overview Header */}
      {profile && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">Total Rows</div>
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{profile.row_count.toLocaleString()}</div>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">Total Columns</div>
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{profile.column_count}</div>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">Total Missing</div>
            <div className={`text-2xl font-bold ${profile.total_missing > 0 ? 'text-amber-500 dark:text-amber-400' : 'text-emerald-500 dark:text-emerald-400'}`}>
              {profile.total_missing}
            </div>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">Duplicate Rows</div>
            <div className={`text-2xl font-bold ${profile.total_duplicates > 0 ? 'text-amber-500 dark:text-amber-400' : 'text-emerald-500 dark:text-emerald-400'}`}>
              {profile.total_duplicates}
            </div>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">Memory Usage</div>
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{profile.memory_kb} KB</div>
          </div>

          <div className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">Issues Detected</div>
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">{issues.length}</div>
          </div>
        </div>
      )}

      {/* 3. USER PREPROCESSING SUGGESTIONS SECTION (UPDATE 2) */}
      {profile && !cleaningComplete && (
        <div className="glass-panel p-6 rounded-2xl border border-indigo-500/30 bg-indigo-50/50 dark:bg-indigo-950/20 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">💡 ADD YOUR OWN PREPROCESSING INSTRUCTIONS</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400">Tell the AI how you want the dataset processed in plain English.</p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={userInstruction}
              onChange={(e) => setUserInstruction(e.target.value)}
              placeholder="e.g. Convert the sale_date column to YYYY/MM/DD format, or Remove rows where quantity is negative"
              className="flex-1 px-4 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={handleAnalyzeSuggestion}
              disabled={analyzingSuggestion || !userInstruction.trim()}
              className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-lg shadow-indigo-500/20 flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              {analyzingSuggestion ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Analyze Suggestion</span>
                </>
              )}
            </button>
          </div>

          {/* Render User Suggestion Response Analysis */}
          {suggestionResult && (
            <div className="pt-2">
              {suggestionResult.supported ? (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-2 text-xs">
                  <div className="flex items-center justify-between font-bold text-emerald-700 dark:text-emerald-300 text-sm">
                    <span>AI INTERPRETATION SUCCESS</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-mono">
                      👤 User Requested Action Added
                    </span>
                  </div>
                  {suggestionResult.interpretation && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-700 dark:text-slate-300 mt-2">
                      <div><b>Requested Action:</b> {suggestionResult.interpretation.requested_action}</div>
                      <div><b>Detected Column:</b> {suggestionResult.interpretation.detected_column || 'Dataset'}</div>
                      <div><b>Proposed Format:</b> {suggestionResult.interpretation.proposed_format}</div>
                      <div><b>Risk Level:</b> {suggestionResult.interpretation.risk_level?.toUpperCase()}</div>
                      <div className="col-span-2"><b>Expected Result:</b> {suggestionResult.interpretation.expected_result}</div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2 text-xs text-amber-800 dark:text-amber-300">
                  <div className="font-bold flex items-center space-x-2 text-sm">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    <span>⚠ Unsupported Instruction</span>
                  </div>
                  <p>{suggestionResult.unsupported_reason}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 4. Unified Proposed Cleaning Plan (AI Recommendations + User Suggestions) */}
      {profile && !cleaningComplete && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel p-4 rounded-xl bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
            <div className="flex items-center space-x-3">
              <Sliders className="w-5 h-5 text-purple-500 dark:text-purple-400" />
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Unified Proposed Cleaning Plan</h2>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => selectAll(true)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 flex items-center space-x-1"
              >
                <CheckSquare className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
                <span>Select All</span>
              </button>

              <button
                onClick={() => selectAll(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 flex items-center space-x-1"
              >
                <Square className="w-3.5 h-3.5 text-slate-400" />
                <span>Clear Selection</span>
              </button>

              <button
                onClick={handlePreview}
                disabled={loading}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/10 dark:bg-indigo-600/20 text-indigo-600 dark:text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/20 flex items-center space-x-1.5"
              >
                <Eye className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
                <span>Preview Selected Changes</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="glass-panel p-12 rounded-2xl text-center space-y-4 bg-white dark:bg-slate-900/40">
              <RefreshCw className="w-8 h-8 text-purple-500 dark:text-purple-400 animate-spin mx-auto" />
              <p className="text-slate-600 dark:text-slate-300 text-sm">Processing proposed operations...</p>
            </div>
          ) : (
            <div className="space-y-4">
              {recommendations.map(rec => {
                const currentApp = userApprovals[rec.id] || { approved: rec.recommended, strategy: rec.recommended_strategy };
                const isApproved = currentApp.approved;
                const isUserRequested = rec.source === 'user_requested';

                return (
                  <div
                    key={rec.id}
                    className={`glass-panel p-5 rounded-2xl border transition-all ${
                      isApproved 
                        ? (isUserRequested ? 'border-purple-500/40 bg-purple-50/30 dark:bg-purple-950/10' : 'border-indigo-500/40 bg-indigo-50/30 dark:bg-indigo-950/10')
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Left: Checkbox & Info */}
                      <div className="flex items-start space-x-4">
                        <button
                          onClick={() => toggleApproval(rec.id)}
                          className="mt-1 flex-shrink-0 text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        >
                          {isApproved ? (
                            <CheckSquare className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
                          ) : (
                            <Square className="w-6 h-6 text-slate-400 dark:text-slate-600" />
                          )}
                        </button>

                        <div className="space-y-2">
                          <div className="flex items-center space-x-3">
                            <span className="font-bold text-slate-900 dark:text-white text-base">
                              {rec.operation.replace('_', ' ').toUpperCase()}
                            </span>

                            {/* Source Tag */}
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              isUserRequested
                                ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/30'
                                : 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30'
                            }`}>
                              {isUserRequested ? '👤 User Requested' : '🤖 AI Recommended'}
                            </span>

                            {rec.column && (
                              <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-mono">
                                Column: {rec.column}
                              </span>
                            )}

                            {/* Risk Badge */}
                            <span
                              className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                                rec.risk_level === 'low'
                                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                                  : rec.risk_level === 'medium'
                                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                                  : 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30'
                              }`}
                            >
                              {rec.risk_level === 'low' ? '🟢 Low Risk' : rec.risk_level === 'medium' ? '🟡 Med Risk' : '🔴 High Risk'}
                            </span>
                          </div>

                          <p className="text-slate-700 dark:text-slate-300 text-sm">{rec.reason}</p>

                          <div className="text-xs text-indigo-600 dark:text-indigo-300 font-medium">
                            Expected Impact: {rec.expected_impact}
                          </div>
                        </div>
                      </div>

                      {/* Right: Strategy Customization */}
                      {rec.available_strategies && rec.available_strategies.length > 1 && (
                        <div className="flex items-center space-x-2 bg-slate-100 dark:bg-slate-900/80 p-2 rounded-xl border border-slate-200 dark:border-slate-800">
                          <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Strategy:</span>
                          <select
                            value={currentApp.strategy}
                            onChange={(e) => changeStrategy(rec.id, e.target.value)}
                            className="bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs rounded-lg px-2.5 py-1.5 border border-slate-300 dark:border-slate-700 focus:outline-none focus:border-indigo-500"
                          >
                            {rec.available_strategies.map(s => (
                              <option key={s} value={s}>{s.replace('_', ' ').toUpperCase()}</option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Action Trigger */}
              <div className="pt-4 flex justify-end">
                <button
                  onClick={handleApplyCleaning}
                  disabled={loading}
                  className="px-8 py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 text-white font-bold text-sm shadow-xl shadow-indigo-500/20 transition-all flex items-center space-x-2"
                >
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Apply Approved Changes</span>
                  <ArrowRight className="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Proposed Changes Modal */}
      {showPreviewModal && previewItems && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
          <div className="glass-panel max-w-2xl w-full p-6 rounded-3xl border border-indigo-500/30 bg-white dark:bg-slate-900 space-y-6 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                <Eye className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                <span>Proposed Changes Preview</span>
              </h3>
              <button onClick={() => setShowPreviewModal(false)} className="text-slate-400 hover:text-slate-900 dark:hover:text-white">
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-3">
              {previewItems.map((item, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs space-y-1">
                  <div className="flex items-center justify-between font-bold text-slate-900 dark:text-white">
                    <span>{item.operation.toUpperCase()}</span>
                    <span className="text-indigo-600 dark:text-indigo-400 font-mono">Strategy: {item.strategy}</span>
                  </div>
                  <p className="text-slate-700 dark:text-slate-300">{item.expected_effect}</p>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => setShowPreviewModal(false)}
                className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700"
              >
                Cancel
              </button>

              <button
                onClick={handleApplyCleaning}
                className="px-6 py-2.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
              >
                Confirm & Apply Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. CLEANED DATASET RESULTS & ON-SCREEN PREVIEW (UPDATE 1 & UPDATE 5 & UPDATE 4) */}
      {cleaningComplete && report && (
        <div className="space-y-8">
          {/* Verification Status Banner */}
          <div className={`glass-panel p-6 rounded-3xl border ${
            report.agent_state === 'PASSED' || report.agent_state === 'VERIFIED'
              ? 'border-emerald-500/40 bg-emerald-500/10'
              : report.agent_state === 'WARNING'
              ? 'border-amber-500/40 bg-amber-500/10'
              : 'border-red-500/40 bg-red-500/10'
          }`}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center space-x-4">
                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-white font-bold text-xl ${
                  report.agent_state === 'PASSED' || report.agent_state === 'VERIFIED'
                    ? 'bg-emerald-600'
                    : report.agent_state === 'WARNING'
                    ? 'bg-amber-600'
                    : 'bg-red-600'
                }`}>
                  {report.agent_state === 'PASSED' || report.agent_state === 'VERIFIED' ? '✓' : report.agent_state === 'WARNING' ? '⚠' : '✕'}
                </div>
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900 dark:text-white flex items-center space-x-2">
                    <span>
                      {report.agent_state === 'PASSED' || report.agent_state === 'VERIFIED'
                        ? '✅ VERIFIED CLEAN DATASET'
                        : report.agent_state === 'WARNING'
                        ? '⚠ CLEAN DATASET — WARNINGS'
                        : '❌ DATASET VERIFICATION FAILED'}
                    </span>
                  </h2>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                    SQLite Table: <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">{report.sqlite_table_name}</span>
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={onNavigateToSql}
                  className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-lg shadow-emerald-500/25 flex items-center space-x-2"
                >
                  <span>Ask SQL Agent Now</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* ON-SCREEN PREVIEW COMPONENT (UPDATE 1) */}
          <div className="glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-extrabold text-slate-900 dark:text-white flex items-center space-x-2">
                  <Eye className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                  <span>PREPROCESSED DATASET PREVIEW</span>
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Showing {datasetPreview ? datasetPreview.rows.length : 0} of {datasetPreview ? datasetPreview.total_rows : 0} rows | Rows: {datasetPreview ? datasetPreview.total_rows : 0} | Columns: {datasetPreview ? datasetPreview.total_cols : 0}
                </p>
              </div>

              {/* Search & Page Size Select */}
              <div className="flex items-center space-x-3">
                <form onSubmit={handlePreviewSearchSubmit} className="relative">
                  <input
                    type="text"
                    value={previewSearch}
                    onChange={(e) => setPreviewSearch(e.target.value)}
                    placeholder="Search preview..."
                    className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs text-slate-900 dark:text-slate-100 border border-slate-300 dark:border-slate-700 focus:outline-none"
                  />
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                </form>

                <div className="flex items-center space-x-1.5 text-xs text-slate-500 dark:text-slate-400">
                  <span>Rows:</span>
                  <select
                    value={previewPageSize}
                    onChange={(e) => handlePreviewPageSizeChange(Number(e.target.value))}
                    className="bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs rounded-lg px-2 py-1 border border-slate-300 dark:border-slate-700 focus:outline-none"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Table Container */}
            <div className="relative overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl min-h-[300px]">
              {loadingPreview && (
                <div className="absolute inset-0 bg-white/70 dark:bg-slate-900/70 backdrop-blur-[1px] z-10 flex items-center justify-center space-x-2 text-indigo-600 dark:text-indigo-400 text-xs font-semibold">
                  <RefreshCw className="w-4 h-4 animate-spin text-indigo-500" />
                  <span>Loading dataset preview...</span>
                </div>
              )}

              {datasetPreview && datasetPreview.rows.length > 0 ? (
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 uppercase font-semibold">
                    <tr>
                      <th className="px-3 py-2.5 border-b border-slate-200 dark:border-slate-700">#</th>
                      {datasetPreview.columns.map((col, idx) => (
                        <th key={idx} className="px-3 py-2.5 border-b border-slate-200 dark:border-slate-700 whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
                    {datasetPreview.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="px-3 py-2 font-mono text-slate-400">
                          {(datasetPreview.page - 1) * datasetPreview.page_size + rIdx + 1}
                        </td>
                        {datasetPreview.columns.map((col, cIdx) => (
                          <td key={cIdx} className="px-3 py-2 whitespace-nowrap font-mono">
                            {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-slate-400 italic">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : !loadingPreview ? (
                <div className="py-12 text-center text-slate-400 text-xs">
                  No matching dataset rows found.
                </div>
              ) : null}
            </div>

            {/* Pagination Controls */}
            {datasetPreview && (
              <div className="flex items-center justify-between pt-2 text-xs">
                <span className="text-slate-500 dark:text-slate-400">
                  Page {datasetPreview.page} of {datasetPreview.total_pages}
                </span>

                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={(e) => handlePreviewPageChange(e, previewPage - 1)}
                    disabled={previewPage <= 1 || loadingPreview}
                    className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 flex items-center space-x-1"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                    <span>Previous</span>
                  </button>

                  <span className="px-3 py-1.5 rounded-lg font-bold bg-indigo-600 text-white">
                    {datasetPreview.page}
                  </span>

                  <button
                    type="button"
                    onClick={(e) => handlePreviewPageChange(e, previewPage + 1)}
                    disabled={previewPage >= datasetPreview.total_pages || loadingPreview}
                    className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-40 flex items-center space-x-1"
                  >
                    <span>Next</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* POST-PREPROCESSING USER FEEDBACK & SUGGESTION SECTION */}
          <div className="glass-panel p-6 rounded-3xl border border-purple-500/30 bg-purple-50/40 dark:bg-purple-950/20 space-y-6">
            <div className="flex items-start space-x-3">
              <div className="w-10 h-10 rounded-2xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-600 dark:text-purple-400 shadow-md flex-shrink-0">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">Need Further Changes?</h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                  Review the preprocessed dataset above. If you want any additional cleaning, formatting, or standardization, describe it below.
                </p>
              </div>
            </div>

            {/* Input & Examples */}
            <div className="space-y-3">
              <textarea
                value={postInstruction}
                onChange={(e) => setPostInstruction(e.target.value)}
                rows={3}
                placeholder="Describe an additional preprocessing or cleaning change..."
                className="w-full px-4 py-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all resize-none font-sans"
              />

              {/* Quick Prompt Examples */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-bold text-slate-500 dark:text-slate-400">Examples:</div>
                <div className="flex flex-wrap gap-2">
                  {[
                    "Convert M and F to Male and Female",
                    "Standardize gender values to Male/Female",
                    "Convert dates to YYYY-MM-DD",
                    "Remove extra spaces from branch names",
                    "Standardize account type values to lowercase"
                  ].map((ex, idx) => (
                    <button
                      key={idx}
                      onClick={() => setPostInstruction(ex)}
                      className="px-3 py-1.5 rounded-xl bg-white/80 dark:bg-slate-800/80 hover:bg-purple-500/10 border border-slate-200 dark:border-slate-700 hover:border-purple-500/40 text-[11px] text-slate-700 dark:text-slate-300 transition-all"
                    >
                      • {ex}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={handleAnalyzePostSuggestion}
                  disabled={analyzingPost || !postInstruction.trim()}
                  className="px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs shadow-lg shadow-purple-500/25 flex items-center space-x-2 disabled:opacity-50 transition-all"
                >
                  {analyzingPost ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Analyze Suggestion</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* AI Interpretation Proposal Card */}
            {postAnalysis && (
              <div className="pt-2 border-t border-purple-500/20">
                {postAnalysis.supported ? (
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-purple-500/30 space-y-4 shadow-lg">
                    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                      <div className="flex items-center space-x-2">
                        <Sparkles className="w-4 h-4 text-purple-500" />
                        <span className="font-extrabold text-sm text-slate-900 dark:text-white uppercase tracking-wider">
                          AI INTERPRETATION
                        </span>
                      </div>
                      <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                        postAnalysis.risk === 'high'
                          ? 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30'
                          : postAnalysis.risk === 'medium'
                          ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                          : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                      }`}>
                        {postAnalysis.risk === 'high' ? '🔴 Risk: HIGH' : postAnalysis.risk === 'medium' ? '🟡 Risk: MEDIUM' : '🟢 Risk: LOW'}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Requested Change:</span>
                        <span className="font-bold text-slate-900 dark:text-white text-sm">{postAnalysis.requested_change}</span>
                      </div>

                      <div>
                        <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Column:</span>
                        <span className="font-mono font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">
                          {postAnalysis.column || 'Dataset'}
                        </span>
                      </div>

                      {postAnalysis.current_values && postAnalysis.current_values.length > 0 && (
                        <div>
                          <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Current values detected:</span>
                          <div className="flex flex-wrap gap-1 font-mono">
                            {postAnalysis.current_values.slice(0, 8).map((val, idx) => (
                              <span key={idx} className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded">
                                {val}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {postAnalysis.mapping && Object.keys(postAnalysis.mapping).length > 0 && (
                        <div>
                          <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Proposed transformation:</span>
                          <div className="space-y-1 font-mono text-[11px]">
                            {Object.entries(postAnalysis.mapping).map(([k, v], idx) => (
                              <div key={idx} className="flex items-center space-x-2 text-slate-800 dark:text-slate-200">
                                <span className="text-amber-600 dark:text-amber-400 font-bold">{k}</span>
                                <span className="text-slate-400">→</span>
                                <span className="text-emerald-600 dark:text-emerald-400 font-bold">{v}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="md:col-span-2">
                        <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Expected result / impact:</span>
                        <span className="text-slate-800 dark:text-slate-200">{postAnalysis.expected_impact}</span>
                      </div>

                      <div>
                        <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Affected rows:</span>
                        <span className="font-bold text-slate-900 dark:text-white">{postAnalysis.affected_rows}</span>
                      </div>

                      <div>
                        <span className="text-slate-500 dark:text-slate-400 block mb-0.5">Reason:</span>
                        <span className="text-slate-700 dark:text-slate-300">{postAnalysis.reason}</span>
                      </div>
                    </div>

                    {/* Human Approval Action Buttons */}
                    <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                      <button
                        onClick={() => handleApplyPostSuggestion(false)}
                        disabled={applyingPost}
                        className="px-5 py-2 rounded-xl text-xs font-semibold bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300"
                      >
                        Reject
                      </button>

                      <button
                        onClick={() => handleApplyPostSuggestion(true)}
                        disabled={applyingPost}
                        className="px-6 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 flex items-center space-x-2 disabled:opacity-50"
                      >
                        {applyingPost ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            <span>Applying...</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-4 h-4" />
                            <span>Approve & Apply</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-300 space-y-1 text-xs">
                    <div className="font-bold flex items-center space-x-2 text-sm">
                      <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                      <span>Could not process suggestion</span>
                    </div>
                    <p>{postAnalysis.unsupported_reason}</p>
                  </div>
                )}
              </div>
            )}

            {/* Verification Success Result Section */}
            {postResult && (
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 space-y-2 text-xs text-emerald-800 dark:text-emerald-300">
                <div className="flex items-center justify-between font-bold text-emerald-700 dark:text-emerald-300 text-sm">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    <span>✓ CHANGE VERIFIED</span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-mono text-xs">
                    Verification: PASSED
                  </span>
                </div>
                <p>{postResult.message}</p>
                {postResult.affected_rows > 0 && (
                  <div className="flex items-center space-x-4 text-[11px] pt-1">
                    <span>Rows affected: <b>{postResult.affected_rows}</b></span>
                    {postResult.before_values && postResult.before_values.length > 0 && (
                      <span>Before: <code className="font-mono">{postResult.before_values.join(', ')}</code></span>
                    )}
                    {postResult.after_values && postResult.after_values.length > 0 && (
                      <span>After: <code className="font-mono">{postResult.after_values.join(', ')}</code></span>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Verification Results Checklist */}
          {report.verification_report && (
            <div className="glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span>PREPROCESSING VERIFICATION CHECKLIST</span>
              </h3>

              <div className="space-y-2">
                {report.verification_report.checks.map((check, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs flex items-center justify-between">
                    <div>
                      <div className="font-bold text-slate-900 dark:text-white">{check.check_name}</div>
                      <div className="text-slate-500 dark:text-slate-400 text-[11px] mt-0.5">{check.details}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                      check.status === 'PASSED'
                        ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                        : check.status === 'WARNING'
                        ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                        : 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20'
                    }`}>
                      {check.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* OVERALL CLEANING OPERATIONS LOG (START & AFTER USER SUGGESTIONS) */}
          {report.operations_applied && report.operations_applied.length > 0 && (
            <div className="glass-panel p-6 rounded-3xl border border-indigo-500/30 bg-white dark:bg-slate-900/60 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-indigo-500" />
                  <span>OVERALL CLEANING OPERATIONS LOG (START & USER SUGGESTIONS)</span>
                </h3>
                <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-mono text-xs font-bold border border-indigo-500/20">
                  {report.operations_applied.length} Operation(s) Executed
                </span>
              </div>

              <div className="space-y-2.5">
                {report.operations_applied.map((op, idx) => (
                  <div key={idx} className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2 font-bold text-slate-900 dark:text-white">
                        <span className={`px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider ${
                          op.source === 'user_requested'
                            ? 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/30'
                            : 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30'
                        }`}>
                          {op.source === 'user_requested' ? '👤 User Requested' : '🤖 AI Recommended'}
                        </span>
                        <span>{op.operation.replace(/_/g, ' ').toUpperCase()}</span>
                        {op.column && (
                          <span className="px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[11px]">
                            Column: {op.column}
                          </span>
                        )}
                      </div>

                      <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono text-[10px] font-bold">
                        {op.execution_status.toUpperCase()}
                      </span>
                    </div>

                    <p className="text-slate-600 dark:text-slate-300 text-xs">{op.details}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Before/After Stats */}
          <div className="glass-panel p-6 rounded-3xl border border-slate-200 dark:border-slate-800 space-y-4">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Before / After Quality Comparison</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {report.before_after_comparison.map((comp, idx) => (
                <div key={idx} className="glass-card p-4 rounded-xl space-y-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs text-slate-500 dark:text-slate-400">{comp.metric}</div>
                  <div className="flex items-baseline space-x-2">
                    <span className="text-slate-400 text-sm line-through">{comp.before}</span>
                    <span className="text-xl font-bold text-emerald-600 dark:text-emerald-400">{comp.after}</span>
                  </div>
                  <div className="text-[11px] text-indigo-600 dark:text-indigo-300">{comp.improvement}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Download Buttons */}
          <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-slate-200 dark:border-slate-800">
            <a
              href={api.getDownloadUrl(report.dataset_id)}
              download
              className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-lg shadow-indigo-500/20 flex items-center space-x-2"
            >
              <Download className="w-4 h-4" />
              <span>Download Clean Excel Dataset (.xlsx)</span>
            </a>

            <a
              href={`${api.getDownloadUrl(report.dataset_id)}?format=csv`}
              download
              className="px-6 py-3 rounded-xl bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-semibold text-xs flex items-center space-x-2"
            >
              <Download className="w-4 h-4" />
              <span>Download Clean CSV (.csv)</span>
            </a>

            <a
              href={api.getReportUrl(report.dataset_id)}
              download
              className="px-6 py-3 rounded-xl glass-card hover:bg-slate-200 dark:hover:bg-slate-800 text-purple-600 dark:text-purple-300 border border-purple-500/30 font-semibold text-xs flex items-center space-x-2"
            >
              <FileText className="w-4 h-4 text-purple-500" />
              <span>Download PDF Cleaning Report (.pdf)</span>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

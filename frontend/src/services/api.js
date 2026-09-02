import axios from 'axios';

const baseUrl = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/\/$/, '') : '';
const API_BASE = `${baseUrl}/api`;

export const api = {
  // Upload CSV or Excel file
  uploadFile: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API_BASE}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  // Get profiling details
  getProfile: async (datasetId) => {
    const response = await axios.get(`${API_BASE}/dataset/${datasetId}/profile`);
    return response.data;
  },

  // Get AI recommendations
  getRecommendations: async (datasetId) => {
    const response = await axios.get(`${API_BASE}/dataset/${datasetId}/recommendations`);
    return response.data;
  },

  // Add natural language user preprocessing suggestion
  addUserSuggestion: async (datasetId, userInstruction) => {
    const response = await axios.post(`${API_BASE}/dataset/${datasetId}/user-suggestion`, {
      user_instruction: userInstruction
    });
    return response.data;
  },

  // Analyze post-preprocessing user feedback suggestion
  analyzePostCleanSuggestion: async (datasetId, userInstruction) => {
    const response = await axios.post(`${API_BASE}/dataset/${datasetId}/post-clean-suggestion/analyze`, {
      user_instruction: userInstruction
    });
    return response.data;
  },

  // Apply approved post-preprocessing user feedback suggestion
  applyPostCleanSuggestion: async (datasetId, payload) => {
    const response = await axios.post(`${API_BASE}/dataset/${datasetId}/post-clean-suggestion/apply`, payload);
    return response.data;
  },

  // Get paginated on-screen preview of cleaned dataset
  getCleanedPreview: async (datasetId, page = 1, pageSize = 10, search = '') => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString()
    });
    if (search && search.trim()) {
      params.append('search', search.trim());
    }
    const response = await axios.get(`${API_BASE}/dataset/${datasetId}/preview?${params.toString()}`);
    return response.data;
  },

  // Preview selected cleaning operations
  previewCleaning: async (datasetId, actions) => {
    const response = await axios.post(`${API_BASE}/dataset/${datasetId}/preview-cleaning`, { actions });
    return response.data;
  },

  // Execute approved cleaning operations
  cleanDataset: async (datasetId, actions) => {
    const response = await axios.post(`${API_BASE}/dataset/${datasetId}/clean`, { actions });
    return response.data;
  },

  // Get SQLite table schema and sample data
  getSchema: async (datasetId) => {
    const response = await axios.get(`${API_BASE}/dataset/${datasetId}/schema`);
    return response.data;
  },

  // Download cleaned dataset file URL
  getDownloadUrl: (datasetId) => {
    return `${API_BASE}/dataset/${datasetId}/download`;
  },

  // Download cleaning PDF report URL
  getReportUrl: (datasetId) => {
    return `${API_BASE}/dataset/${datasetId}/cleaning-report`;
  },

  // Download SQL Query Session PDF report URL
  getSqlReportUrl: (datasetId) => {
    return `${API_BASE}/dataset/${datasetId}/sql-report`;
  },

  // Download SQL Query Session PDF report as Blob
  downloadSqlReport: async (datasetId) => {
    const response = await axios.get(`${API_BASE}/dataset/${datasetId}/sql-report`, {
      responseType: 'blob'
    });
    return response;
  },

  // Execute NL SQL Query
  executeQuery: async (userQuestion, datasetId) => {
    const response = await axios.post(`${API_BASE}/query`, {
      user_question: userQuestion,
      dataset_id: datasetId
    });
    return response.data;
  },

  // Query History
  getQueryHistory: async (datasetId) => {
    const url = datasetId ? `${API_BASE}/query-history?dataset_id=${datasetId}` : `${API_BASE}/query-history`;
    const response = await axios.get(url);
    return response.data;
  }
};

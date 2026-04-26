import { useEffect, useState } from 'react';
import api, { frontendRuntimeConfig, getApiErrorMessage } from '../api';

interface DatasetRecord {
  id: string;
  file: string;
  owner_username: string;
  tenant_id: string;
  created_at: string;
}

interface AskResponse {
  answer: string;
  dataset_id: string;
  mode: string;
  answer_source: 'llm' | 'local_fallback';
  rag_used: boolean;
  latency_ms: {
    total: number;
    rag: number;
    llm: number;
  };
  requested_by: string;
}

interface UploadResponse {
  dataset_id: string;
  filename: string;
  rows?: number;
  columns?: string[];
  reused?: boolean;
  message: string;
}

interface SystemStatusResponse {
  service: {
    name: string;
    version: string;
    environment: string;
    docs_enabled: boolean;
  };
  capabilities: {
    live_llm_configured: boolean;
    rag_enabled: boolean;
    rag_dependencies_available: boolean;
  };
  storage: {
    dataset_count: number;
    user_count: number;
    audit_log_count: number;
  };
  runtime: {
    uptime_seconds: number;
    total_requests: number;
    last_response_time_ms: number;
  };
}

export const QueryInterface = () => {
  const [question, setQuestion] = useState('');
  const [datasetId, setDatasetId] = useState('');
  const [queryMode, setQueryMode] = useState<'dataset' | 'general'>('dataset');
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [queryError, setQueryError] = useState('');
  const [datasetError, setDatasetError] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploadTone, setUploadTone] = useState<'neutral' | 'success' | 'error'>('neutral');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
  const [statusError, setStatusError] = useState('');

  const loadDatasets = async (preferredDatasetId?: string) => {
    setDatasetError('');

    try {
      const { data } = await api.get('/datasets');
      const nextDatasets = (data.datasets ?? []) as DatasetRecord[];
      setDatasets(nextDatasets);

      if (preferredDatasetId && nextDatasets.some((dataset) => dataset.id === preferredDatasetId)) {
        setDatasetId(preferredDatasetId);
      } else if (!nextDatasets.some((dataset) => dataset.id === datasetId)) {
        setDatasetId(nextDatasets[0]?.id ?? '');
      }
    } catch (loadError) {
      console.error(loadError);
      setDatasets([]);
      setDatasetId('');
      setDatasetError(getApiErrorMessage(loadError, 'Unable to load datasets. Log in with a user that has dataset access.'));
    } finally {
      setIsLoadingDatasets(false);
    }
  };

  useEffect(() => {
    void loadDatasets();
    const loadSystemStatus = async () => {
      try {
        const { data } = await api.get<SystemStatusResponse>('/system/status');
        setSystemStatus(data);
      } catch (error) {
        console.error(error);
        setStatusError(getApiErrorMessage(error, 'Unable to load backend system status.'));
      }
    };

    void loadSystemStatus();
  }, []);

  const handleAsk = async () => {
    if (queryMode === 'dataset' && !datasetId) {
      setQueryError('Choose a dataset before asking a question.');
      return;
    }

    if (!question.trim()) {
      setQueryError('Enter a question first.');
      return;
    }

    setIsSubmitting(true);
    setQueryError('');
    setResponse(null);

    try {
      const { data } =
        queryMode === 'dataset'
          ? await api.post<AskResponse>('/ask', { question, dataset_id: datasetId })
          : await api.post<AskResponse>('/chat', { question });
      setResponse(data);
    } catch (error) {
      console.error(error);
      setQueryError(getApiErrorMessage(error, 'Error querying data. Check that the backend is running and your token is valid.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Choose a CSV file first.');
      return;
    }

    setIsUploading(true);
    setUploadStatus('');
    setDatasetError('');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const { data } = await api.post<UploadResponse>('/upload-csv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const message = data.reused
        ? `Reused existing dataset ${data.dataset_id} from ${data.filename}.`
        : `Uploaded ${data.filename} as dataset ${data.dataset_id}${data.rows ? ` with ${data.rows} rows` : ''}.`;
      setUploadTone('success');
      setUploadStatus(message);
      setSelectedFile(null);
      await loadDatasets(data.dataset_id);
    } catch (error) {
      console.error(error);
      setUploadTone('error');
      setUploadStatus(getApiErrorMessage(error, 'Upload failed. Make sure you are signed in and selected a valid CSV file.'));
    } finally {
      setIsUploading(false);
    }
  };

  const selectedDataset = datasets.find((dataset) => dataset.id === datasetId) ?? null;

  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Demo flow</h2>
            <p>
              The React frontend is the main demo surface. It still talks to the FastAPI backend for login, uploads, dataset access, and answers.
            </p>
          </div>
          <span className="pill">Swagger optional</span>
        </div>
        <div className="info-card">
          <span>1. Sign in from the frontend.</span>
          <span>2. Upload a CSV here. The file is posted to the backend API.</span>
          <span>3. Select the dataset and ask a question.</span>
          <span>4. Use Swagger only as a backup inspection surface at `/docs`.</span>
        </div>
        <div className="info-card">
          <span>Frontend API target: {frontendRuntimeConfig.apiBaseUrl}</span>
          <span>
            Swagger/docs: <a href={frontendRuntimeConfig.docsUrl} target="_blank" rel="noreferrer">{frontendRuntimeConfig.docsUrl}</a>
          </span>
        </div>
        {systemStatus ? (
          <div className="response-card system-status-card">
            <div className="metrics-row">
              <span className="pill">Backend: {systemStatus.service.environment}</span>
              <span className="pill">Version: {systemStatus.service.version}</span>
              <span className={`pill ${systemStatus.capabilities.live_llm_configured ? 'pill-success' : 'pill-warning'}`}>
                LLM: {systemStatus.capabilities.live_llm_configured ? 'Configured' : 'Fallback only'}
              </span>
              <span className={`pill ${systemStatus.capabilities.rag_enabled ? 'pill-success' : 'pill-warning'}`}>
                RAG: {systemStatus.capabilities.rag_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <div className="response-meta">
              <span>Datasets tracked: {systemStatus.storage.dataset_count}</span>
              <span>Users: {systemStatus.storage.user_count}</span>
              <span>Audit events: {systemStatus.storage.audit_log_count}</span>
              <span>Total requests: {systemStatus.runtime.total_requests}</span>
              <span>Uptime: {Math.round(systemStatus.runtime.uptime_seconds)} s</span>
            </div>
          </div>
        ) : null}
        {statusError ? <p className="status error">{statusError}</p> : null}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Datasets</h2>
            <p>
              These entries come from the backend dataset registry and are filtered by your tenant and access rights.
            </p>
          </div>
          <span className="pill">{datasets.length} available</span>
        </div>

        <div className="panel-grid">
          <label className="field">
            <span>Available datasets</span>
            <select
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              disabled={isLoadingDatasets || datasets.length === 0}
            >
              <option value="">
                {isLoadingDatasets ? 'Loading datasets...' : datasets.length === 0 ? 'No datasets available' : 'Select a dataset'}
              </option>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.file} ({dataset.owner_username})
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Upload CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        <div className="button-row">
          <button className="secondary-button" onClick={() => void loadDatasets(datasetId)} disabled={isLoadingDatasets}>
            Refresh datasets
          </button>
          <button className="primary-button" onClick={handleUpload} disabled={isUploading}>
            {isUploading ? 'Uploading...' : 'Upload CSV'}
          </button>
        </div>

        {selectedDataset ? (
          <div className="info-card">
            <strong>{selectedDataset.file}</strong>
            <span>Dataset ID: {selectedDataset.id}</span>
            <span>Owner: {selectedDataset.owner_username}</span>
            <span>Created: {new Date(selectedDataset.created_at).toLocaleString()}</span>
          </div>
        ) : null}

        {datasetError ? <p className="status error">{datasetError}</p> : null}
        {uploadStatus ? <p className={`status ${uploadTone === 'error' ? 'error' : uploadTone === 'success' ? 'success' : ''}`}>{uploadStatus}</p> : null}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Ask the copilot</h2>
            <p>
              Use dataset mode for grounded analysis, or switch to general mode for broader operational questions.
            </p>
          </div>
        </div>

        <div className="button-row">
          <button
            className={queryMode === 'dataset' ? 'primary-button' : 'secondary-button'}
            onClick={() => setQueryMode('dataset')}
            type="button"
          >
            Dataset mode
          </button>
          <button
            className={queryMode === 'general' ? 'primary-button' : 'secondary-button'}
            onClick={() => setQueryMode('general')}
            type="button"
          >
            General mode
          </button>
        </div>

        {queryMode === 'dataset' ? (
          <p className="status">Dataset mode uses the selected CSV and optional RAG context.</p>
        ) : (
          <p className="status">General mode answers broader questions without requiring a selected dataset.</p>
        )}

        <label className="field">
          <span>Question</span>
          <textarea
            value={question}
            placeholder={
              queryMode === 'dataset'
                ? 'Example: Summarize the revenue trend and explain any anomalies.'
                : 'Example: What should I monitor first when API latency spikes in production?'
            }
            onChange={(e) => setQuestion(e.target.value)}
            rows={5}
          />
        </label>

        <button className="primary-button" onClick={handleAsk} disabled={isSubmitting}>
          {isSubmitting ? 'Asking...' : 'Ask'}
        </button>

        {queryError ? <p className="status error">{queryError}</p> : null}
        {response ? (
          <div className="response-card">
            <div className="metrics-row">
              <span className="pill">Mode: {response.mode}</span>
              <span className={`pill ${response.answer_source === 'llm' ? 'pill-success' : 'pill-warning'}`}>
                Source: {response.answer_source === 'llm' ? 'Live LLM' : 'Local fallback'}
              </span>
              <span className="pill">RAG: {response.rag_used ? 'Context used' : 'No context'}</span>
              <span className="pill">Total: {response.latency_ms.total} ms</span>
              <span className="pill">RAG time: {response.latency_ms.rag} ms</span>
              <span className="pill">LLM: {response.latency_ms.llm} ms</span>
            </div>
            <p className="response-text">{response.answer}</p>
            <div className="response-meta">
              <span>Dataset: {response.dataset_id ?? 'General copilot mode'}</span>
              <span>Requested by: {response.requested_by}</span>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
};

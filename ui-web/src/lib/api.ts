import type {
  HealthResponse,
  HardwareStatus,
  RegistryModel,
  RouterDecision,
  AgentState,
  EgressStatus,
  Certificate,
  ApprovalRequest,
  AuditEvent,
} from './types';

const API_BASE = '/api';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail?.message || error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>('/health');
}

export async function getHardwareStatus(): Promise<HardwareStatus> {
  return fetchApi<HardwareStatus>('/hardware/status');
}

export async function getRegistry(): Promise<{ models: RegistryModel[] }> {
  return fetchApi<{ models: RegistryModel[] }>('/registry');
}

export async function decideRouter(taskDescription: string, taskType?: string): Promise<RouterDecision> {
  return fetchApi<RouterDecision>('/router/decide', {
    method: 'POST',
    body: JSON.stringify({ task_description: taskDescription, task_type: taskType }),
  });
}

export interface IngestResult {
  document_id: string;
  pages_processed: number;
  ocr_results: any[];
  indexed: boolean;
  extracted_preview?: string;
  filename?: string;
}

export async function ingestDocument(file: File, userId: string, role: string): Promise<IngestResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_id', userId);
  formData.append('role', role);

  const response = await fetch(`${API_BASE}/ingest/document`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail?.message || error.detail || 'Upload failed');
  }

  return response.json();
}

export interface RunSummary {
  run_id: string;
  task: string;
  status: string;
  started_at: string;
  completed_at?: string;
  model_used?: string;
  artifacts?: string[];
}

export async function listRuns(): Promise<{ runs: RunSummary[]; total: number }> {
  return fetchApi<{ runs: RunSummary[]; total: number }>('/runs');
}

export async function startAgentRun(
  taskDescription: string,
  userId: string,
  role: string,
  sourceDocuments?: string[]
): Promise<{ run_id: string; status: string }> {
  return fetchApi<{ run_id: string; status: string }>('/agent/run', {
    method: 'POST',
    body: JSON.stringify({
      task_description: taskDescription,
      user_id: userId,
      role: role,
      source_documents: sourceDocuments,
    }),
  });
}

export async function getAgentTrace(runId: string): Promise<AgentState> {
  return fetchApi<AgentState>(`/agent/trace/${runId}`);
}

export async function getApprovals(): Promise<ApprovalRequest[]> {
  const data = await fetchApi<{ pending: ApprovalRequest[]; count: number } | ApprovalRequest[]>('/approvals');
  const items = Array.isArray(data) ? data : data?.pending || [];
  return items.map((item) => ({
    ...item,
    status: item.status || 'pending',
  }));
}

export async function approveRequest(approvalId: string, reviewerId: string, comments?: string): Promise<{ success: boolean }> {
  return fetchApi<{ success: boolean }>(`/approvals/${approvalId}`, {
    method: 'POST',
    body: JSON.stringify({ approved: true, reviewer_id: reviewerId, comments }),
  });
}

export async function denyRequest(approvalId: string, reviewerId: string, comments?: string): Promise<{ success: boolean }> {
  return fetchApi<{ success: boolean }>(`/approvals/${approvalId}`, {
    method: 'POST',
    body: JSON.stringify({ approved: false, reviewer_id: reviewerId, comments }),
  });
}

export async function getCertificate(runId: string): Promise<Certificate> {
  return fetchApi<Certificate>(`/certificate/${runId}`);
}

export async function verifyCertificate(certificatePath: string): Promise<{ valid: boolean; reason?: string }> {
  return fetchApi<{ valid: boolean; reason?: string }>('/certificate/verify', {
    method: 'POST',
    body: JSON.stringify({ certificate_path: certificatePath }),
  });
}

export async function getAuditEvents(runId?: string): Promise<AuditEvent[]> {
  const url = runId ? `/audit/events?run_id=${runId}` : '/audit/events';
  return fetchApi<AuditEvent[]>(url);
}

export async function getEgressStatus(runId: string): Promise<EgressStatus> {
  return fetchApi<EgressStatus>(`/egress/status?run_id=${runId}`);
}

export function createEgressStream(runId: string, onEvent: (event: EgressStatus) => void): () => void {
  const eventSource = new EventSource(`${API_BASE}/egress/stream?run_id=${runId}`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as EgressStatus;
      onEvent(data);
    } catch {
      // Ignore parse errors
    }
  };

  return () => {
    eventSource.close();
  };
}

export function createAgentStream(runId: string, onEvent: (state: AgentState) => void): () => void {
  const eventSource = new EventSource(`${API_BASE}/agent/stream/${runId}`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as AgentState;
      onEvent(data);
    } catch {
      // Ignore parse errors
    }
  };

  return () => {
    eventSource.close();
  };
}

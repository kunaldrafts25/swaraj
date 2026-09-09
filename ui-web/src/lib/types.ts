// Backend API types mirroring Pydantic schemas

export interface HealthResponse {
  app_name: string;
  version: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  registry_ready: boolean;
  model_artifact_present: boolean;
  checksum_verification_state: 'verified' | 'pending' | 'missing' | 'mismatch' | 'artifact_missing';
  fail_closed: boolean;
  details?: {
    total_manifests: number;
    verified_models: number;
    models: ModelStatus[];
  };
}

export interface ModelStatus {
  name: string;
  version: string;
  gguf_path: string;
  checksum_status: 'verified' | 'pending' | 'missing' | 'mismatch';
  verified: boolean;
}

export interface HardwareStatus {
  tier: 'gpu_tier1' | 'gpu_tier2' | 'cpu_only' | 'unknown';
  vram_usable_mb: number | null;
  measured_latency_ms_per_500_tokens: number | null;
  calibrated: boolean;
}

export interface RouterDecision {
  selected_model: string;
  confidence: number;
  reasoning: string;
  capability_scores: {
    code: number | null;
    summary: number | null;
    ocr_extract: number | null;
  };
  hardware_tier: string;
}

export interface AgentPlan {
  steps: PlannedStep[];
}

export interface PlannedStep {
  id: string;
  action: string;
  tool?: string;
  parameters?: Record<string, unknown>;
  authorized?: boolean;
  pruned?: boolean;
  approval_required?: boolean;
}

export interface AgentState {
  run_id: string;
  status: 'running' | 'completed' | 'failed' | 'security_failed' | string;
  current_step?: string | null;
  plan?: AgentPlan | null;
  observations?: Observation[];
  self_check_iterations?: number;
  self_check_valid?: boolean | null;
  self_check_errors?: ValidationError[] | null;
  certificate_eligible?: boolean;
  security_status?: 'clean' | 'failed' | string;
  state?: Record<string, any>;
  transitions?: any[];
  iterations?: number;
  steps?: any[];
  planning_result?: any;
  rbac_result?: any;
  self_check_result?: any;
  selected_model?: string;
  hardware_tier?: string;
  generated_artifacts?: string[];
  failure_reason?: string;
  artifact_content?: string | null;
  artifact_filename?: string | null;
  task_description?: string | null;
}

export interface Observation {
  step_id: string;
  tool_result?: unknown;
  error?: string;
  timestamp: string;
}

export interface ValidationError {
  field: string;
  issue: string;
  severity: 'critical' | 'warning';
}

export interface EgressEvent {
  event_type: 'heartbeat' | 'connection_opened' | 'connection_closed' | 'security_alert';
  address?: string;
  port?: number;
  status?: string;
  is_loopback: boolean;
  timestamp: string;
  run_id: string;
}

export interface EgressStatus {
  run_id: string;
  security_status: 'clean' | 'failed';
  kill_switch_triggered: boolean;
  event_count: number;
  events: EgressEvent[];
  latest_heartbeat: string | null;
  certificate_eligible: boolean;
}

export interface Certificate {
  run_id: string;
  started_at: string;
  ended_at: string;
  model_used: string;
  egress_events: EgressEvent[];
  hash_chain_head: string;
  signature: string;
  signer_pubkey: string;
}

export interface ApprovalRequest {
  approval_id: string;
  run_id: string;
  user_id: string;
  role: string;
  action: string;
  artifact?: string;
  policy_reason: string;
  requested_at: string;
  status: 'pending' | 'approved' | 'denied';
}

export interface RegistryModel {
  name: string;
  version: string;
  gguf_path: string;
  sha256: string | null;
  quant: string;
  context_length: number;
  hardware_tier_min: string;
  capability_vector: {
    code: number | null;
    summary: number | null;
    ocr_extract: number | null;
    has_real_benchmark: boolean;
  } | null;
  signed_at: string | null;
  signature: string | null;
  checksum_status?: 'verified' | 'pending' | 'missing' | 'mismatch';
  verified?: boolean;
}

export interface AuditEvent {
  id: string;
  run_id: string | null;
  user: string | null;
  role: string | null;
  event_type: string;
  details: Record<string, unknown>;
  timestamp: string;
  previous_hash: string | null;
  entry_hash: string;
}

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'backend_error' | 'stream_error';

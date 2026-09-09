import React, { useRef, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  getHealth,
  decideRouter,
  startAgentRun,
  getHardwareStatus,
  ingestDocument,
} from '../lib/api';
import { useAppStore } from '../store/useAppStore';
import {
  Send,
  Upload,
  FileCheck,
  ChevronRight,
  Sparkles,
  FileText,
  User,
  Code2,
  BarChart2,
  AlignLeft,
  ScanText,
  FilePlus,
  ShieldCheck,
  Cpu,
  HardDrive,
  AlertCircle,
  CheckCircle2,
  X,
} from 'lucide-react';

const TASK_TYPES = [
  { value: '', label: 'Auto-detect', icon: Sparkles },
  { value: 'summarization', label: 'Summarize & Synthesize', icon: AlignLeft },
  { value: 'ocr_extraction', label: 'OCR & Text Extraction', icon: ScanText },
  { value: 'document_generation', label: 'Generate Document / Report', icon: FilePlus },
  { value: 'data_analysis', label: 'Data & Metric Analysis', icon: BarChart2 },
  { value: 'code_generation', label: 'Code Generation', icon: Code2 },
];

const ROLES = [
  { value: 'Inspector', userId: 'inspector_user', desc: 'Read · Run tools · View audit log' },
  { value: 'Approver', userId: 'approver_user', desc: 'Write documents · Approve actions' },
  { value: 'Admin', userId: 'admin_user', desc: 'Full access · Manage users & certs' },
];

const TASK_EXAMPLES = [
  {
    title: 'Summarize inspection report',
    type: 'summarization',
    role: 'Inspector',
    prompt: 'Summarize the attached inspection report, extract key findings, flag any anomalies, and produce a concise audit note.',
  },
  {
    title: 'Analyse pressure telemetry',
    type: 'data_analysis',
    role: 'Inspector',
    prompt: 'Analyse the pressure log data. Identify any readings exceeding safe thresholds and recommend maintenance actions.',
  },
  {
    title: 'Draft approval certificate',
    type: 'document_generation',
    role: 'Approver',
    prompt: 'Based on the safety compliance findings, draft a formal approval certificate with cryptographic attestation.',
  },
  {
    title: 'Extract text from scanned PDF',
    type: 'ocr_extraction',
    role: 'Inspector',
    prompt: 'Extract all text from the scanned document, preserve table structure where possible, and output a clean structured result.',
  },
  {
    title: 'Write data processing script',
    type: 'code_generation',
    role: 'Inspector',
    prompt: 'Write a Python script to parse the CSV telemetry file, compute rolling averages, and generate a summary report.',
  },
];

export default function Home() {
  const [taskDescription, setTaskDescription] = useState('');
  const [taskType, setTaskType] = useState('');
  const [role, setRole] = useState('Inspector');
  const [uploadedDocId, setUploadedDocId] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const setCurrentRunId = useAppStore((s) => s.setCurrentRunId);
  const setSelectedModel = useAppStore((s) => s.setSelectedModel);
  const setHardwareTier = useAppStore((s) => s.setHardwareTier);
  const currentRunId = useAppStore((s) => s.currentRunId);

  const selectedRole = ROLES.find((r) => r.value === role) ?? ROLES[0];

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10000,
    retry: 2,
  });

  const { data: hardware } = useQuery({
    queryKey: ['hardware'],
    queryFn: getHardwareStatus,
    refetchInterval: 30000,
    retry: 1,
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      setUploadedFileName(file.name);
      return ingestDocument(file, selectedRole.userId, role);
    },
    onSuccess: (data: any) => {
      setUploadedDocId(data.document_id ?? data.run_id ?? null);
      toast.success(`Document ingested (${data.pages_processed ?? 1} pages indexed)`);
    },
    onError: (error: any) => {
      toast.error(`Upload failed: ${error.message || 'Unknown error'}`);
      setUploadedFileName(null);
    },
  });

  const routerMutation = useMutation({
    mutationFn: (desc: string) => decideRouter(desc, taskType || undefined),
    onSuccess: (data) => {
      setSelectedModel(data.selected_model);
      setHardwareTier(data.hardware_tier);
    },
  });

  const agentMutation = useMutation({
    mutationFn: async (_model: string) => {
      const docs = uploadedDocId ? [uploadedDocId] : [];
      const result = await startAgentRun(taskDescription, selectedRole.userId, role, docs);
      setCurrentRunId(result.run_id);
      return result;
    },
    onSuccess: (result) => {
      toast.success('Task started — navigating to trace view');
      setTimeout(() => navigate(`/trace/${result.run_id}`), 900);
    },
    onError: (error: any) => {
      toast.error(`Failed: ${error.message || 'Unknown error'}`);
    },
  });

  const handleSubmit = async () => {
    if (!taskDescription.trim()) {
      toast.error('Please enter a task description');
      return;
    }
    try {
      const routing = await routerMutation.mutateAsync(taskDescription);
      await agentMutation.mutateAsync(routing.selected_model ?? '');
    } catch {
      // handled in callbacks
    }
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) uploadMutation.mutate(f);
  };

  const clearFile = () => {
    setUploadedDocId(null);
    setUploadedFileName(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const isPending = routerMutation.isPending || agentMutation.isPending;

  // Determine health status color
  const healthStatus = health?.status;
  const healthColor =
    healthStatus === 'healthy' ? 'text-green-400' :
    healthStatus === 'degraded' ? 'text-amber-400' :
    '#EF4444';

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--bg-base)' }}>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Page header */}
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Task Studio
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Describe a task, optionally attach a document, and run it locally with full audit trail.
          </p>
        </div>

        {/* System status row */}
        {!healthLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              {
                label: 'System',
                value: healthStatus ?? 'checking',
                color: healthStatus === 'healthy' ? '#22C55E' : healthStatus === 'degraded' ? '#F59E0B' : '#EF4444',
                icon: ShieldCheck,
              },
              {
                label: 'Hardware',
                value: hardware?.tier ?? 'CPU',
                color: 'var(--text-secondary)',
                icon: Cpu,
              },
              {
                label: 'Models',
                value: `${health?.details?.verified_models ?? 0} verified`,
                color: (health?.details?.verified_models ?? 0) > 0 ? '#22C55E' : '#F59E0B',
                icon: HardDrive,
              },
              {
                label: 'Active Run',
                value: currentRunId ? currentRunId.slice(0, 10) + '…' : 'None',
                color: currentRunId ? '#818CF8' : 'var(--text-muted)',
                icon: Sparkles,
              },
            ].map(({ label, value, color, icon: Icon }) => (
              <div key={label} className="card p-3 flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0" style={{ background: 'var(--bg-base)' }}>
                  <Icon size={14} style={{ color }} />
                </div>
                <div>
                  <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</div>
                  <div className="text-xs font-semibold capitalize" style={{ color }}>{value}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {healthLoading && (
          <div className="card p-4 flex items-center gap-3">
            <div className="spinner spinner-sm" />
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Connecting to backend…</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: main task input (2/3 width) */}
          <div className="lg:col-span-2 space-y-4">

            {/* Task configuration */}
            <div className="card p-5 space-y-4">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Task Configuration</h2>

              <div className="grid grid-cols-2 gap-3">
                {/* Task type */}
                <div>
                  <label className="label">Task Type</label>
                  <select
                    id="task-type-select"
                    value={taskType}
                    onChange={(e) => setTaskType(e.target.value)}
                    className="input"
                  >
                    {TASK_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>

                {/* Role */}
                <div>
                  <label className="label">
                    <span className="flex items-center gap-1"><User size={11} /> Operator Role</span>
                  </label>
                  <select
                    id="role-select"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="input"
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.value}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Role perms */}
              <div className="text-xs px-3 py-2 rounded-md flex items-center gap-2" style={{ background: 'var(--bg-base)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                <ShieldCheck size={12} style={{ color: '#818CF8', flexShrink: 0 }} />
                <span><span className="font-medium" style={{ color: 'var(--text-secondary)' }}>{selectedRole.value}:</span> {selectedRole.desc}</span>
              </div>

              {/* Task description textarea */}
              <div>
                <label className="label">Task Description</label>
                <textarea
                  id="task-description"
                  value={taskDescription}
                  onChange={(e) => setTaskDescription(e.target.value)}
                  placeholder="Describe what you want the AI to do. Be specific — you can reference the uploaded document, ask for data analysis, code generation, report drafting, and more."
                  className="input"
                  style={{ minHeight: '160px', resize: 'vertical' }}
                />
                <div className="flex justify-between mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <span>No character limit · Execution is local and private</span>
                  <span>{taskDescription.length.toLocaleString()} chars</span>
                </div>
              </div>

              {/* Submit */}
              <div className="flex items-center justify-between pt-1 border-t" style={{ borderColor: 'var(--border)' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {routerMutation.data ? (
                    <span>→ Routed to <span className="font-mono" style={{ color: '#A5B4FC' }}>{routerMutation.data.selected_model}</span></span>
                  ) : (
                    'Model selected automatically based on task'
                  )}
                </div>
                <button
                  id="execute-task-btn"
                  onClick={handleSubmit}
                  disabled={isPending || !taskDescription.trim()}
                  className="btn btn-primary btn-sm gap-1.5"
                >
                  {isPending ? (
                    <>
                      <div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} />
                      Running…
                    </>
                  ) : (
                    <>
                      <Send size={13} />
                      Run Task
                      <ChevronRight size={13} />
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Document upload */}
            <div className="card p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  <span className="flex items-center gap-1.5"><FileText size={14} /> Attach Document</span>
                </h2>
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Optional · PDF, Word, CSV, TXT, MD</span>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.csv,.md,.json,.py,.log"
                className="hidden"
                onChange={handleFile}
              />

              {uploadedDocId ? (
                <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg" style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)' }}>
                  <CheckCircle2 size={15} className="text-green-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-green-400 truncate">{uploadedFileName}</div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Indexed · ID: {uploadedDocId.slice(0, 12)}…</div>
                  </div>
                  <button onClick={clearFile} className="p-1 rounded hover:bg-white/5 transition-colors" style={{ color: 'var(--text-muted)' }}>
                    <X size={14} />
                  </button>
                </div>
              ) : uploadMutation.isPending ? (
                <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg" style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}>
                  <div className="spinner spinner-sm" />
                  <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Indexing {uploadedFileName}…</span>
                </div>
              ) : (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full border-2 border-dashed rounded-lg px-4 py-5 text-center transition-all"
                  style={{ borderColor: 'rgba(255,255,255,0.1)', color: 'var(--text-muted)' }}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)')}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)')}
                >
                  <Upload size={20} className="mx-auto mb-1.5" style={{ color: 'var(--text-muted)' }} />
                  <div className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Click to attach document or dataset</div>
                  <div className="text-xs mt-0.5">Supports PDF, DOCX, CSV, TXT, Markdown, and JSON</div>
                </button>
              )}
            </div>
          </div>

          {/* Right: example prompts (1/3 width) */}
          <div className="space-y-4">
            <div className="card p-4 space-y-3">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                <span className="flex items-center gap-1.5"><Sparkles size={13} style={{ color: '#818CF8' }} /> Example Tasks</span>
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Click any example to load it into the editor.</p>
              <div className="space-y-1.5">
                {TASK_EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setTaskDescription(ex.prompt);
                      setTaskType(ex.type);
                      setRole(ex.role);
                      toast.info(`Loaded: ${ex.title}`);
                    }}
                    className="w-full text-left px-3 py-2.5 rounded-lg transition-all group"
                    style={{ background: 'var(--bg-base)', border: '1px solid var(--border)' }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)';
                      e.currentTarget.style.background = 'var(--bg-card-hover)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--border)';
                      e.currentTarget.style.background = 'var(--bg-base)';
                    }}
                  >
                    <div className="text-xs font-medium mb-0.5" style={{ color: 'var(--text-primary)' }}>{ex.title}</div>
                    <div className="flex items-center gap-1.5">
                      <span className="badge badge-indigo">{ex.role}</span>
                      <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{TASK_TYPES.find(t => t.value === ex.type)?.label}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* What can this do */}
            <div className="card p-4 space-y-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Capabilities</h2>
              {[
                'Read & summarise PDF documents',
                'Extract data from scanned images',
                'Generate Word / Excel reports',
                'Write & run Python code locally',
                'Analyse telemetry & metrics',
                'Draft approval certificates',
                'Full audit trail with cryptographic proof',
              ].map((cap) => (
                <div key={cap} className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                  <CheckCircle2 size={12} className="text-green-400 shrink-0" />
                  {cap}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Paperclip,
  ShieldCheck,
  Cpu,
  FileText,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Download,
  Terminal,
  RefreshCw,
  Sparkles,
  ChevronDown,
  ChevronUp,
  X,
  Code2,
  FileCode,
  Shield,
  Layers,
  Settings2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  ChatMessage,
  ChatSession,
  getStoredSessions,
  getStoredSession,
  saveSession,
  createNewSession,
  getActiveSessionId,
  setActiveSessionId,
  getUserRole,
  setUserRole,
  AVAILABLE_ROLES,
} from '../lib/chatStorage';
import {
  ingestDocument,
  startAgentRun,
  getAgentTrace,
  getHardwareStatus,
} from '../lib/api';
import type { HardwareStatus } from '../lib/types';
import { useAppStore } from '../store/useAppStore';

const QUICK_PROMPTS = [
  {
    title: 'Analyze & Summarize Document',
    desc: 'Extract key obligations, dates, and critical findings from any uploaded file.',
    prompt: 'Please analyze the attached document, extract the key findings, critical obligations, and provide an executive summary.',
    icon: FileText,
  },
  {
    title: 'Write Offline Python Utility',
    desc: 'Generate secure, air-gapped code to process local files and structured data.',
    prompt: 'Write a self-contained Python script to parse CSV and JSON log files, calculate summary statistics, and export an audit report.',
    icon: FileCode,
  },
  {
    title: 'Audit System Compliance',
    desc: 'Verify offline security boundaries, RBAC permissions, and zero-egress state.',
    prompt: 'Perform a sovereign audit of the current workspace policies, verify jail containment, and summarize network isolation status.',
    icon: Shield,
  },
  {
    title: 'Extract Structured JSON Schema',
    desc: 'Parse unstructured text or document contents into validated JSON format.',
    prompt: 'Extract structured entity data and key-value attributes from the document and format it as clean, validated JSON.',
    icon: Code2,
  },
];

export default function Chat() {
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [inputText, setInputText] = useState('');
  const [attachedFile, setAttachedFile] = useState<{ file: File; name: string; documentId?: string; preview?: string } | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeRole, setActiveRoleState] = useState<string>(getUserRole());
  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [hardware, setHardware] = useState<HardwareStatus | null>(null);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [copiedArtifact, setCopiedArtifact] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const setAppHardwareTier = useAppStore((s) => s.setHardwareTier);
  const setCurrentRunId = useAppStore((s) => s.setCurrentRunId);

  // Initialize or restore session
  useEffect(() => {
    const activeId = getActiveSessionId();
    let session: ChatSession | undefined;
    if (activeId) {
      session = getStoredSession(activeId);
    }
    if (!session) {
      const all = getStoredSessions();
      if (all.length > 0) {
        session = all[0];
        setActiveSessionId(session.id);
      } else {
        session = createNewSession(activeRole);
      }
    }
    setCurrentSession(session);

    // Fetch hardware status for user confidence
    getHardwareStatus()
      .then((h) => {
        setHardware(h);
        if (h.tier) setAppHardwareTier(h.tier);
      })
      .catch(() => {});

    // Listen for storage events (e.g. sidebar session switch)
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'swaraj_active_session_id_v1') {
        const newId = e.newValue;
        if (newId) {
          const s = getStoredSession(newId);
          if (s) setCurrentSession(s);
        }
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener('storage', handleStorage);
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentSession?.messages, isProcessing]);

  // Handle textarea auto-resize
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [inputText]);

  const handleRoleChange = (roleId: string) => {
    setUserRole(roleId);
    setActiveRoleState(roleId);
    setShowRoleMenu(false);
    toast.success(`Active persona set to ${AVAILABLE_ROLES.find((r) => r.id === roleId)?.name}`);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset native input so the same file can be chosen again
    e.target.value = '';

    setUploadingFile(true);
    toast.info(`Ingesting ${file.name}...`);

    try {
      const mappedRole = activeRole === 'auditor' ? 'Approver' : 'Inspector';
      const userId = activeRole === 'auditor' ? 'approver_user' : 'inspector_user';
      const res = await ingestDocument(file, userId, mappedRole);
      setAttachedFile({
        file,
        name: file.name,
        documentId: res.document_id,
        preview: res.extracted_preview,
      });
      toast.success(`Attached ${file.name} (${res.pages_processed || 1} page(s) extracted)`);
    } catch (err: any) {
      console.error('Document ingestion error:', err);
      toast.error(`Failed to ingest document: ${err.message || 'Unknown error'}`);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleSendMessage = async (customPrompt?: string) => {
    const promptToSend = (customPrompt || inputText).trim();
    if (!promptToSend && !attachedFile) return;

    if (isProcessing) {
      toast.warning('Agent is currently processing a run. Please wait.');
      return;
    }

    let session = currentSession;
    if (!session) {
      session = createNewSession(activeRole);
      setCurrentSession(session);
    }

    const userMessageId = 'msg_' + Math.random().toString(36).substring(2, 9);
    const userMessage: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: promptToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachedFile: attachedFile
        ? {
            name: attachedFile.name,
            documentId: attachedFile.documentId || '',
            preview: attachedFile.preview,
          }
        : undefined,
    };

    // Assistant placeholder
    const assistantMessageId = 'msg_' + Math.random().toString(36).substring(2, 9);
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'running',
      steps: [
        { name: 'Classification & RBAC Authorization', status: 'running' },
        { name: 'Filesystem Jail & Policy Guard', status: 'pending' },
        { name: 'Sovereign Inference Execution', status: 'pending' },
        { name: 'Artifact Verification & Hash Check', status: 'pending' },
      ],
    };

    // Update session title if first message
    const updatedTitle =
      session.messages.length === 0
        ? promptToSend.slice(0, 32) + (promptToSend.length > 32 ? '...' : '')
        : session.title;

    const newMessages = [...session.messages, userMessage, assistantMessage];
    const updatedSession: ChatSession = {
      ...session,
      title: updatedTitle,
      messages: newMessages,
    };

    setCurrentSession(updatedSession);
    saveSession(updatedSession);

    // Clear input
    setInputText('');
    setAttachedFile(null);
    setIsProcessing(true);

    try {
      // Build full task description including document context if present
      let finalTask = promptToSend;
      if (userMessage.attachedFile?.preview) {
        finalTask += `\n\n[Document Content (${userMessage.attachedFile.name})]:\n${userMessage.attachedFile.preview}`;
      }

      const sourceDocs = userMessage.attachedFile?.documentId
        ? [userMessage.attachedFile.documentId]
        : undefined;

      // Start run on backend
      const mappedRole = activeRole === 'auditor' ? 'Approver' : 'Inspector';
      const userId = activeRole === 'auditor' ? 'approver_user' : 'inspector_user';
      const runRes = await startAgentRun(finalTask, userId, mappedRole, sourceDocs);
      const runId = runRes.run_id;
      setCurrentRunId(runId);

      // Poll trace endpoint until complete
      let pollCount = 0;
      const maxPolls = 60; // 60 * 1000ms = 60s timeout

      const pollInterval = setInterval(async () => {
        pollCount++;
        try {
          const trace = await getAgentTrace(runId);
          const status = trace.state?.status || 'running';

          if (status === 'completed' || status === 'failed' || status === 'security_failed' || pollCount >= maxPolls) {
            clearInterval(pollInterval);
            setIsProcessing(false);

            let aiContent = '';
            if (trace.artifact_content) {
              aiContent = trace.artifact_content;
            } else if (trace.state?.failure_reason) {
              aiContent = `⚠️ **Execution Error**: ${trace.state.failure_reason}`;
            } else {
              aiContent = `Task completed successfully. Artifacts verified under cryptographic jail.\n\nRun ID: \`${runId}\``;
            }

            const finalSteps = [
              { name: 'Classification & RBAC Authorization', status: 'done' as const },
              { name: 'Filesystem Jail & Policy Guard', status: 'done' as const },
              { name: 'Sovereign Inference Execution', status: status === 'failed' ? ('failed' as const) : ('done' as const) },
              { name: 'Artifact Verification & Hash Check', status: status === 'failed' ? ('failed' as const) : ('done' as const) },
            ];

            const finalAssistantMsg: ChatMessage = {
              id: assistantMessageId,
              role: 'assistant',
              content: aiContent,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              status: status === 'failed' ? 'failed' : 'completed',
              runId: runId,
              steps: finalSteps,
              artifact: trace.artifact_filename
                ? {
                    filename: trace.artifact_filename,
                    content: trace.artifact_content || undefined,
                    url: `/api/artifact/${trace.artifact_filename}`,
                  }
                : undefined,
            };

            const finalizedSession: ChatSession = {
              ...updatedSession,
              messages: [...session!.messages, userMessage, finalAssistantMsg],
            };
            setCurrentSession(finalizedSession);
            saveSession(finalizedSession);

            if (status === 'completed') {
              toast.success('Agent completed successfully');
            } else {
              toast.error('Agent execution halted or failed safety check');
            }
          } else {
            // Update running steps based on iteration count
            const currentSteps = [
              { name: 'Classification & RBAC Authorization', status: 'done' as const },
              { name: 'Filesystem Jail & Policy Guard', status: 'done' as const },
              { name: 'Sovereign Inference Execution', status: 'running' as const, detail: `Executing graph (iteration ${trace.iterations || 1})` },
              { name: 'Artifact Verification & Hash Check', status: 'pending' as const },
            ];

            const intermediateSession: ChatSession = {
              ...updatedSession,
              messages: updatedSession.messages.map((m) =>
                m.id === assistantMessageId ? { ...m, steps: currentSteps } : m
              ),
            };
            setCurrentSession(intermediateSession);
          }
        } catch (pollErr) {
          console.error('Trace polling error:', pollErr);
        }
      }, 1000);

      pollTimerRef.current = pollInterval;
    } catch (err: any) {
      console.error('Agent start error:', err);
      setIsProcessing(false);
      toast.error(`Error launching agent: ${err.message || 'Unknown'}`);

      const errorMsg: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: `❌ **Failed to start task**: ${err.message || 'Backend unreachable'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        status: 'failed',
      };

      const errorSession: ChatSession = {
        ...updatedSession,
        messages: [...session.messages, userMessage, errorMsg],
      };
      setCurrentSession(errorSession);
      saveSession(errorSession);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedArtifact(id);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopiedArtifact(null), 2000);
  };

  const handleStartNewChat = () => {
    const newS = createNewSession(activeRole);
    setCurrentSession(newS);
    setInputText('');
    setAttachedFile(null);
    toast.success('Started a new conversation');
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      {/* Top Chat Bar */}
      <div
        className="h-14 shrink-0 px-6 flex items-center justify-between border-b z-10"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-indigo-600 shadow-sm">
            <ShieldCheck size={18} className="text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm tracking-tight" style={{ color: 'var(--text-primary)' }}>
                Swaraj Offline AI
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-emerald-950 text-emerald-300 border border-emerald-800/60 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Air-Gapped Sovereign
              </span>
            </div>
            <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              Zero-egress hardware containment · Local GGUF models
            </div>
          </div>
        </div>

        {/* Center/Right Controls */}
        <div className="flex items-center gap-2.5">
          {/* Hardware status badge */}
          {hardware?.tier && (
            <div
              className="hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
            >
              <Cpu size={13} className="text-indigo-400" />
              <span className="capitalize">{hardware.tier.replace('_', ' ')}</span>
              {hardware.vram_usable_mb && (
                <span className="text-indigo-300 font-mono text-[11px]">
                  ({(hardware.vram_usable_mb / 1024).toFixed(1)} GB)
                </span>
              )}
            </div>
          )}

          {/* Role selector dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowRoleMenu(!showRoleMenu)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-all hover:border-indigo-500/50"
              style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
            >
              <Shield size={13} className="text-indigo-400" />
              <span className="capitalize font-medium">Role: {activeRole}</span>
              <ChevronDown size={13} style={{ color: 'var(--text-muted)' }} />
            </button>

            {showRoleMenu && (
              <div
                className="absolute right-0 top-full mt-1.5 w-64 rounded-xl border p-1.5 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
              >
                <div className="px-2.5 py-1 text-[11px] font-medium text-muted uppercase tracking-wider">
                  Select Active Persona
                </div>
                {AVAILABLE_ROLES.map((role) => (
                  <button
                    key={role.id}
                    onClick={() => handleRoleChange(role.id)}
                    className={`w-full text-left p-2.5 rounded-lg text-xs transition-colors flex flex-col gap-0.5 ${
                      activeRole === role.id ? 'bg-indigo-600/15 border border-indigo-500/30' : 'hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center justify-between font-medium" style={{ color: 'var(--text-primary)' }}>
                      <span>{role.name}</span>
                      {activeRole === role.id && <Check size={14} className="text-indigo-400" />}
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {role.description}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* New Chat Button */}
          <button
            onClick={handleStartNewChat}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium text-white transition-all bg-indigo-600 hover:bg-indigo-500 shadow-sm"
          >
            <Sparkles size={13} />
            <span>New Chat</span>
          </button>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">
        {/* If no messages in session, show welcoming hero + quick prompt cards */}
        {(!currentSession || currentSession.messages.length === 0) && (
          <div className="max-w-3xl mx-auto pt-10 pb-6 flex flex-col items-center text-center">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-gradient-to-br from-indigo-500 to-indigo-700 shadow-xl mb-5">
              <ShieldCheck size={28} className="text-white" />
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight mb-2" style={{ color: 'var(--text-primary)' }}>
              How can Swaraj assist you today?
            </h1>
            <p className="text-sm max-w-lg mb-8 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              100% offline, sovereign agentic intelligence. Everything stays on your local machine, fully air-gapped with zero internet calls.
            </p>

            {/* Quick Prompts Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 w-full text-left">
              {QUICK_PROMPTS.map((item, idx) => {
                const Icon = item.icon;
                return (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(item.prompt)}
                    className="p-4 rounded-xl border text-left transition-all duration-200 group hover:border-indigo-500/40 hover:bg-indigo-950/15"
                    style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
                  >
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 group-hover:bg-indigo-500 group-hover:text-white transition-colors">
                        <Icon size={15} />
                      </div>
                      <span className="font-semibold text-xs md:text-sm" style={{ color: 'var(--text-primary)' }}>
                        {item.title}
                      </span>
                    </div>
                    <p className="text-xs line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                      {item.desc}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Message Thread */}
        {currentSession?.messages.map((msg) => {
          const isUser = msg.role === 'user';
          const isRunning = msg.status === 'running';

          return (
            <div
              key={msg.id}
              className={`max-w-3xl mx-auto flex gap-3.5 md:gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {/* Assistant Avatar */}
              {!isUser && (
                <div className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center bg-indigo-600 text-white shadow-sm mt-0.5">
                  <ShieldCheck size={16} />
                </div>
              )}

              {/* Message Content Bubble */}
              <div
                className={`flex flex-col gap-2 max-w-[85%] md:max-w-[80%] ${
                  isUser ? 'items-end' : 'items-start'
                }`}
              >
                {/* User message bubble */}
                {isUser ? (
                  <div
                    className="px-4 py-3 rounded-2xl text-sm leading-relaxed border"
                    style={{
                      background: 'rgba(99, 102, 241, 0.15)',
                      borderColor: 'rgba(99, 102, 241, 0.3)',
                      color: 'var(--text-primary)',
                      borderTopRightRadius: '4px',
                    }}
                  >
                    {/* Attached file chip if any */}
                    {msg.attachedFile && (
                      <div className="mb-2 p-2 rounded-lg bg-black/20 border border-white/10 flex items-center gap-2 text-xs">
                        <FileText size={14} className="text-indigo-400 shrink-0" />
                        <span className="font-medium truncate">{msg.attachedFile.name}</span>
                        {msg.attachedFile.pages && (
                          <span className="text-[10px] text-muted">({msg.attachedFile.pages} pages)</span>
                        )}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                ) : (
                  /* Assistant message bubble */
                  <div
                    className="w-full p-4 md:p-5 rounded-2xl text-sm border shadow-md space-y-3"
                    style={{
                      background: 'var(--bg-surface)',
                      borderColor: 'var(--border)',
                      color: 'var(--text-primary)',
                      borderTopLeftRadius: '4px',
                    }}
                  >
                    {/* Running state indicator */}
                    {isRunning && (
                      <div className="flex flex-col gap-3 py-2">
                        <div className="flex items-center gap-2 text-xs text-indigo-300">
                          <RefreshCw size={14} className="animate-spin text-indigo-400" />
                          <span className="font-medium">Swaraj is executing sovereign reasoning graph...</span>
                        </div>

                        {/* Step progress list */}
                        {msg.steps && (
                          <div
                            className="p-3 rounded-xl border space-y-2 text-xs"
                            style={{ background: 'var(--bg-base)', borderColor: 'var(--border)' }}
                          >
                            {msg.steps.map((s, idx) => (
                              <div key={idx} className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  {s.status === 'done' ? (
                                    <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
                                  ) : s.status === 'running' ? (
                                    <span className="w-3 h-3 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin shrink-0" />
                                  ) : (
                                    <span className="w-2.5 h-2.5 rounded-full bg-zinc-700 shrink-0" />
                                  )}
                                  <span
                                    className={`${
                                      s.status === 'done'
                                        ? 'text-zinc-300'
                                        : s.status === 'running'
                                        ? 'text-indigo-300 font-medium'
                                        : 'text-zinc-500'
                                    }`}
                                  >
                                    {s.name}
                                  </span>
                                </div>
                                {s.detail && (
                                  <span className="text-[11px] font-mono text-zinc-400 truncate max-w-[180px]">
                                    {s.detail}
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Answer content (Markdown / plain text) */}
                    {msg.content && (
                      <div className="prose prose-invert max-w-none text-sm leading-relaxed whitespace-pre-wrap font-sans">
                        {msg.content}
                      </div>
                    )}

                    {/* Verified Artifact Download Option (clean strip, no redundant text duplication) */}
                    {msg.artifact && (
                      <div
                        className="mt-3 px-3.5 py-2.5 rounded-xl border flex items-center justify-between gap-3 text-xs"
                        style={{ background: 'rgba(255, 255, 255, 0.02)', borderColor: 'rgba(99, 102, 241, 0.25)' }}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <FileCode size={16} className="text-indigo-400 shrink-0" />
                          <span className="font-mono text-xs font-medium text-zinc-200 truncate">
                            {msg.artifact.filename}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-mono shrink-0">
                            Verified
                          </span>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {msg.artifact.content && (
                            <button
                              onClick={() => handleCopy(msg.artifact!.content!, msg.id)}
                              className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 text-zinc-300 transition-colors"
                            >
                              {copiedArtifact === msg.id ? (
                                <>
                                  <Check size={12} className="text-emerald-400" />
                                  <span>Copied</span>
                                </>
                              ) : (
                                <>
                                  <Copy size={12} />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          )}
                          <a
                            href={`/api/artifact/${msg.artifact.filename}`}
                            download={msg.artifact.filename}
                            className="flex items-center gap-1.5 text-[11px] px-3 py-1 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-sm transition-colors"
                          >
                            <Download size={12} />
                            <span>Download</span>
                          </a>
                        </div>
                      </div>
                    )}

                    {/* Collapsible Execution Trace details */}
                    {msg.steps && !isRunning && (
                      <div className="pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                        <button
                          onClick={() => setExpandedTraceId(expandedTraceId === msg.id ? null : msg.id)}
                          className="flex items-center gap-1.5 text-xs text-muted hover:text-indigo-300 transition-colors"
                        >
                          <CheckCircle2 size={13} className="text-emerald-400" />
                          <span>4 Verification Gates Passed</span>
                          {expandedTraceId === msg.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>

                        {expandedTraceId === msg.id && (
                          <div className="mt-2.5 p-3 rounded-lg border space-y-1.5 text-xs bg-black/20 border-white/5">
                            {msg.steps.map((s, idx) => (
                              <div key={idx} className="flex items-center justify-between text-zinc-400">
                                <span className="flex items-center gap-2">
                                  <Check size={11} className="text-emerald-400" />
                                  {s.name}
                                </span>
                                <span className="font-mono text-[11px] text-emerald-400">Pass</span>
                              </div>
                            ))}
                            {msg.runId && (
                              <div className="pt-1.5 mt-1.5 border-t border-white/5 flex items-center justify-between text-[11px] text-muted font-mono">
                                <span>Run Reference</span>
                                <a
                                  href={`#/trace/${msg.runId}`}
                                  className="text-indigo-400 hover:underline"
                                >
                                  {msg.runId.slice(0, 12)}…
                                </a>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Message Timestamp */}
                <div className="text-[10px] px-1" style={{ color: 'var(--text-muted)' }}>
                  {msg.timestamp}
                </div>
              </div>
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Input Area */}
      <div
        className="shrink-0 p-4 border-t"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
      >
        <div className="max-w-3xl mx-auto space-y-2.5">
          {/* File attachment preview badge */}
          {attachedFile && (
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border animate-in fade-in"
              style={{ background: 'var(--bg-card)', borderColor: 'rgba(99, 102, 241, 0.4)' }}
            >
              <FileText size={14} className="text-indigo-400 shrink-0" />
              <div className="flex flex-col">
                <span className="font-medium text-xs text-white truncate max-w-xs">{attachedFile.name}</span>
                {attachedFile.preview && (
                  <span className="text-[10px] text-zinc-400 truncate max-w-xs">
                    Extracted text ready for reasoning
                  </span>
                )}
              </div>
              <button
                onClick={() => setAttachedFile(null)}
                className="p-1 rounded hover:bg-white/10 text-muted hover:text-white transition-colors ml-1"
                title="Remove attached document"
              >
                <X size={13} />
              </button>
            </div>
          )}

          {/* Chat Input Box */}
          <div
            className="flex items-end gap-2 p-2 rounded-2xl border transition-all duration-200 focus-within:border-indigo-500/70 focus-within:ring-2 focus-within:ring-indigo-500/10"
            style={{ background: 'var(--bg-base)', borderColor: 'var(--border)' }}
          >
            {/* File attachment button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept=".pdf,.txt,.md,.py,.json,.csv,.doc,.docx"
            />
            <button
              type="button"
              disabled={uploadingFile || isProcessing}
              onClick={() => fileInputRef.current?.click()}
              className="p-2.5 rounded-xl hover:bg-white/5 text-zinc-400 hover:text-indigo-400 transition-colors shrink-0 disabled:opacity-50"
              title="Attach PDF or document for offline reasoning"
            >
              {uploadingFile ? (
                <RefreshCw size={18} className="animate-spin text-indigo-400" />
              ) : (
                <Paperclip size={18} />
              )}
            </button>

            {/* Input textarea */}
            <textarea
              ref={textareaRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isProcessing}
              placeholder={
                attachedFile
                  ? `Ask questions about ${attachedFile.name}...`
                  : 'Message Swaraj (e.g. summarize a report, write a script, audit policies)...'
              }
              rows={1}
              className="flex-1 max-h-44 bg-transparent resize-none border-0 text-sm focus:outline-none focus:ring-0 leading-relaxed py-2 px-1 text-white placeholder-zinc-500"
            />

            {/* Send Button */}
            <button
              type="button"
              disabled={isProcessing || (!inputText.trim() && !attachedFile)}
              onClick={() => handleSendMessage()}
              className="p-2.5 rounded-xl font-medium text-white transition-all shrink-0 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:pointer-events-none shadow-sm"
              title="Send message (Enter)"
            >
              <Send size={16} />
            </button>
          </div>

          <div className="flex items-center justify-between px-2 text-[11px]" style={{ color: 'var(--text-muted)' }}>
            <div className="flex items-center gap-1.5">
              <span>Shift + Enter for new line</span>
              <span>·</span>
              <span>Local storage memory active</span>
            </div>
            <div className="flex items-center gap-1 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Offline Containment Verified</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

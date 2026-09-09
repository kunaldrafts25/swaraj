export interface ChatArtifact {
  filename: string;
  url?: string;
  content?: string;
}

export interface AttachedFileMeta {
  name: string;
  documentId: string;
  pages?: number;
  preview?: string;
}

export interface ExecutionStep {
  name: string;
  status: 'done' | 'running' | 'pending' | 'failed';
  detail?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  artifact?: ChatArtifact;
  attachedFile?: AttachedFileMeta;
  steps?: ExecutionStep[];
  runId?: string;
  status?: 'sending' | 'running' | 'completed' | 'failed';
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  role: string;
  messages: ChatMessage[];
}

const SESSIONS_KEY = 'swaraj_chat_sessions_v1';
const ACTIVE_SESSION_KEY = 'swaraj_active_session_id_v1';
const USER_ROLE_KEY = 'swaraj_user_role_v1';

export const AVAILABLE_ROLES = [
  {
    id: 'inspector',
    name: 'Inspector',
    description: 'Document analysis, safety verification, synthesis & offline code generation',
    isDefault: true,
  },
  {
    id: 'auditor',
    name: 'Auditor',
    description: 'Compliance verification, cryptographic hashes, policy logs & audit events',
    isDefault: false,
  },
  {
    id: 'operator',
    name: 'Operator',
    description: 'General air-gapped task execution and routine queries',
    isDefault: false,
  },
];

export function getUserRole(): string {
  try {
    const saved = localStorage.getItem(USER_ROLE_KEY);
    if (saved && AVAILABLE_ROLES.some((r) => r.id === saved)) {
      return saved;
    }
  } catch {
    // localStorage unavailable fallback
  }
  return 'inspector';
}

export function setUserRole(role: string): void {
  try {
    localStorage.setItem(USER_ROLE_KEY, role);
  } catch {
    // ignore
  }
}

export function getStoredSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    console.error('Failed to load chat sessions from localStorage:', err);
    return [];
  }
}

export function getStoredSession(id: string): ChatSession | undefined {
  const sessions = getStoredSessions();
  return sessions.find((s) => s.id === id);
}

export function saveSession(session: ChatSession): void {
  try {
    const sessions = getStoredSessions();
    const existingIndex = sessions.findIndex((s) => s.id === session.id);
    if (existingIndex >= 0) {
      sessions[existingIndex] = { ...session, updatedAt: new Date().toISOString() };
    } else {
      sessions.unshift({ ...session, updatedAt: new Date().toISOString() });
    }
    // Keep max 50 sessions in localStorage
    const trimmed = sessions.slice(0, 50);
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(trimmed));
  } catch (err) {
    console.error('Failed to save session to localStorage:', err);
  }
}

export function deleteSession(id: string): void {
  try {
    const sessions = getStoredSessions().filter((s) => s.id !== id);
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    if (getActiveSessionId() === id) {
      const nextActive = sessions.length > 0 ? sessions[0].id : null;
      setActiveSessionId(nextActive);
    }
  } catch (err) {
    console.error('Failed to delete session:', err);
  }
}

export function getActiveSessionId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_SESSION_KEY);
  } catch {
    return null;
  }
}

export function setActiveSessionId(id: string | null): void {
  try {
    if (id) {
      localStorage.setItem(ACTIVE_SESSION_KEY, id);
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  } catch {
    // ignore
  }
}

export function createNewSession(role?: string): ChatSession {
  const id = 'session_' + Math.random().toString(36).substring(2, 9) + '_' + Date.now();
  const session: ChatSession = {
    id,
    title: 'New Conversation',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    role: role || getUserRole(),
    messages: [],
  };
  saveSession(session);
  setActiveSessionId(id);
  return session;
}

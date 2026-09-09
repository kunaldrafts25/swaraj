import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HashRouter, Routes, Route, Outlet } from 'react-router-dom';
import { Toaster } from 'sonner';
import Home from './pages/Home';
import Chat from './pages/Chat';
import Trace from './pages/Trace';
import Egress from './pages/Egress';
import Registry from './pages/Registry';
import Approvals from './pages/Approvals';
import { Sidebar } from './components/shell/Sidebar';
import { TopBar } from './components/shell/TopBar';
import { StatusBar } from './components/shell/StatusBar';
import { useAppStore } from './store/useAppStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function AppShell() {
  const hardwareTier = useAppStore((s) => s.hardwareTier);
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-auto flex flex-col">
          <Outlet />
        </main>
        <StatusBar hardwareTier={hardwareTier} />
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Chat />} />
            <Route path="/studio" element={<Home />} />
            <Route path="/trace" element={<Trace />} />
            <Route path="/trace/:runId" element={<Trace />} />
            <Route path="/egress" element={<Egress />} />
            <Route path="/registry" element={<Registry />} />
            <Route path="/approvals" element={<Approvals />} />
          </Route>
        </Routes>
      </HashRouter>
      <Toaster position="bottom-right" theme="dark" />
    </QueryClientProvider>
  );
}

export default App;


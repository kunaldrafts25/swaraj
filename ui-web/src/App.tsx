import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HashRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import Home from './pages/Home';
import Trace from './pages/Trace';
import Egress from './pages/Egress';
import Registry from './pages/Registry';
import Approvals from './pages/Approvals';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/trace" element={<Trace />} />
          <Route path="/egress" element={<Egress />} />
          <Route path="/registry" element={<Registry />} />
          <Route path="/approvals" element={<Approvals />} />
        </Routes>
      </HashRouter>
      <Toaster position="bottom-right" theme="dark" />
    </QueryClientProvider>
  );
}

export default App;

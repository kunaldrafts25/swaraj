import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRegistry } from '../lib/api';
import { SectionCard } from '../components/ui/SectionCard';
import { StatusPill } from '../components/ui/StatusPill';
import { MonoValue } from '../components/ui/MonoValue';
import { Database, AlertCircle } from 'lucide-react';

export default function Registry() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['registry'],
    queryFn: getRegistry,
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <div className="flex-1 p-6">
        <p className="text-sovereign-muted">Loading registry...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-6">
        <SectionCard title="Registry Error">
          <div className="flex items-center gap-2 text-sovereign-error">
            <AlertCircle size={16} />
            <span>{(error as Error).message}</span>
          </div>
        </SectionCard>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-4">
        <SectionCard title="Model Registry">
          {data && data.models.length === 0 ? (
            <div className="flex items-center gap-2 text-sovereign-muted">
              <Database size={16} />
              <span>No models registered</span>
            </div>
          ) : (
            <div className="space-y-4">
              {data?.models.map((model, idx) => (
                <div key={idx} className="p-4 bg-sovereign-card2 rounded-lg border border-white/10">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sovereign-text font-medium">{model.name} v{model.version}</h4>
                    <StatusPill
                      status={model.verified ? 'success' : 'error'}
                      label={model.verified ? 'Verified' : 'Not Verified'}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-sovereign-muted mb-1">GGUF Path</p>
                      <MonoValue value={model.gguf_path} maxLength={40} />
                    </div>
                    <div>
                      <p className="text-sovereign-muted mb-1">Quantization</p>
                      <span className="font-mono text-sovereign-text">{model.quant}</span>
                    </div>
                    <div>
                      <p className="text-sovereign-muted mb-1">Context Length</p>
                      <span className="font-mono text-sovereign-text">{model.context_length}</span>
                    </div>
                    <div>
                      <p className="text-sovereign-muted mb-1">Hardware Tier Min</p>
                      <span className="font-mono text-sovereign-text">{model.hardware_tier_min}</span>
                    </div>
                    <div className="col-span-2">
                      <p className="text-sovereign-muted mb-1">SHA256</p>
                      {model.sha256 ? (
                        <MonoValue value={model.sha256} />
                      ) : (
                        <span className="font-mono text-sovereign-error">MISSING</span>
                      )}
                    </div>
                    {model.capability_vector && (
                      <>
                        <div>
                          <p className="text-sovereign-muted mb-1">Code Score</p>
                          <span className="font-mono text-sovereign-text">
                            {model.capability_vector.code !== null ? `${(model.capability_vector.code * 100).toFixed(0)}%` : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <p className="text-sovereign-muted mb-1">Summary Score</p>
                          <span className="font-mono text-sovereign-text">
                            {model.capability_vector.summary !== null ? `${(model.capability_vector.summary * 100).toFixed(0)}%` : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <p className="text-sovereign-muted mb-1">OCR Extract Score</p>
                          <span className="font-mono text-sovereign-text">
                            {model.capability_vector.ocr_extract !== null ? `${(model.capability_vector.ocr_extract * 100).toFixed(0)}%` : 'N/A'}
                          </span>
                        </div>
                        <div>
                          <p className="text-sovereign-muted mb-1">Real Benchmark</p>
                          <StatusPill
                            status={model.capability_vector.has_real_benchmark ? 'success' : 'warning'}
                            label={model.capability_vector.has_real_benchmark ? 'Yes' : 'No'}
                          />
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

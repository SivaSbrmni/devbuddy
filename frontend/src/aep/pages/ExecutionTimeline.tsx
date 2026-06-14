/**
 * Execution Timeline — Phase 5.
 *
 * Visualises the step-by-step progress of an AEP execution including
 * state transitions, agent invocations, and timing.
 */
import { useEffect, useState } from 'react';
import { useExecution } from '../hooks/useAepData';

interface TimelineStep {
  step_index: number;
  agent_name: string;
  state: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
}

const STATE_ICONS: Record<string, string> = {
  PENDING: '○',
  RUNNING: '◉',
  SUCCEEDED: '●',
  FAILED: '✕',
  SKIPPED: '◌',
};

const STATE_COLORS: Record<string, string> = {
  PENDING: 'text-gray-400',
  RUNNING: 'text-blue-500',
  SUCCEEDED: 'text-green-500',
  FAILED: 'text-red-500',
  SKIPPED: 'text-gray-300',
};

export function ExecutionTimeline({ executionId }: { executionId: string }) {
  const { execution, loading, error } = useExecution(executionId);
  const [steps, setSteps] = useState<TimelineStep[]>([]);

  useEffect(() => {
    if (!execution) return;
    // Fetch steps from execution details
    const apiBase = import.meta.env.VITE_API_URL || '';
    const token = localStorage.getItem('auth_token');
    fetch(`${apiBase}/api/v1/aep/executions/${executionId}/steps`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : { steps: [] })
      .then(data => setSteps(data.steps || []))
      .catch(() => setSteps([]));
  }, [execution, executionId]);

  if (loading) return <div className="p-6">Loading timeline...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;
  if (!execution) return <div className="p-6">Execution not found</div>;

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{execution.title}</h1>
        <p className="text-sm text-gray-500 mt-1">
          State: <span className="font-medium">{execution.state}</span>
          {execution.started_at && (
            <> · Started: {new Date(execution.started_at).toLocaleString()}</>
          )}
        </p>
      </div>

      {/* State transition line */}
      <div className="mb-8">
        <h2 className="text-sm font-medium text-gray-500 mb-3">Execution State</h2>
        <div className="flex items-center gap-1 text-xs overflow-x-auto">
          {['PENDING', 'PLANNING', 'AWAITING_APPROVAL', 'EXECUTING', 'VALIDATING', 'REVIEWING', 'COMPLETED'].map(state => (
            <div key={state} className="flex items-center">
              <span className={`px-2 py-1 rounded ${
                execution.state === state
                  ? 'bg-blue-100 text-blue-700 font-medium'
                  : isStatePast(execution.state, state)
                    ? 'bg-green-50 text-green-600'
                    : 'bg-gray-50 text-gray-400'
              }`}>
                {state.replace('_', ' ')}
              </span>
              {state !== 'COMPLETED' && <span className="mx-1 text-gray-300">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Steps timeline */}
      <div>
        <h2 className="text-sm font-medium text-gray-500 mb-3">Agent Steps</h2>
        {steps.length === 0 ? (
          <p className="text-gray-400 text-sm">No steps recorded yet.</p>
        ) : (
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-200" />
            <div className="space-y-4">
              {steps.map(step => (
                <div key={step.step_index} className="relative pl-10">
                  <span className={`absolute left-2.5 top-1 text-lg ${STATE_COLORS[step.state] || 'text-gray-400'}`}>
                    {STATE_ICONS[step.state] || '○'}
                  </span>
                  <div className="border rounded-lg p-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="font-medium text-sm">
                          Step {step.step_index}: {step.agent_name}
                        </span>
                        <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${
                          step.state === 'SUCCEEDED' ? 'bg-green-50 text-green-700' :
                          step.state === 'FAILED' ? 'bg-red-50 text-red-700' :
                          step.state === 'RUNNING' ? 'bg-blue-50 text-blue-700' :
                          'bg-gray-50 text-gray-500'
                        }`}>
                          {step.state}
                        </span>
                      </div>
                      {step.duration_ms != null && (
                        <span className="text-xs text-gray-400">
                          {step.duration_ms < 1000
                            ? `${Math.round(step.duration_ms)}ms`
                            : `${(step.duration_ms / 1000).toFixed(1)}s`}
                        </span>
                      )}
                    </div>
                    {step.error && (
                      <p className="text-xs text-red-600 mt-1">{step.error}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const STATE_ORDER = ['PENDING', 'PLANNING', 'AWAITING_APPROVAL', 'EXECUTING', 'VALIDATING', 'REVIEWING', 'COMPLETED'];

function isStatePast(current: string, target: string): boolean {
  return STATE_ORDER.indexOf(current) > STATE_ORDER.indexOf(target);
}

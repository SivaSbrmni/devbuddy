/**
 * Workflow Graph — Phase 5.
 *
 * Renders the ExecutionPlan as a DAG showing agent dependencies,
 * execution status, and data flow between steps.
 */
import { useEffect, useState } from 'react';

interface PlanStep {
  step_index: number;
  agent_name: string;
  description: string;
  depends_on: number[];
  estimated_tokens: number;
  requires_github_actions: boolean;
  state?: string;
}

const AGENT_COLORS: Record<string, string> = {
  planner: 'border-blue-400 bg-blue-50',
  coder: 'border-purple-400 bg-purple-50',
  tester: 'border-green-400 bg-green-50',
  reviewer: 'border-yellow-400 bg-yellow-50',
  debugger: 'border-red-400 bg-red-50',
  security_audit: 'border-orange-400 bg-orange-50',
  documentation: 'border-teal-400 bg-teal-50',
  devops: 'border-indigo-400 bg-indigo-50',
  coordinator: 'border-pink-400 bg-pink-50',
};

export function WorkflowGraph({ executionId }: { executionId: string }) {
  const [steps, setSteps] = useState<PlanStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    const token = localStorage.getItem('auth_token');
    fetch(`${apiBase}/api/v1/aep/executions/${executionId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => {
        if (!r.ok) throw new Error('Failed to load execution');
        return r.json();
      })
      .then(data => {
        const plan = data.plan || data.result?.steps || [];
        setSteps(Array.isArray(plan) ? plan : plan.steps || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [executionId]);

  if (loading) return <div className="p-6">Loading workflow...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  // Group steps by dependency depth (BFS layers)
  const layers = computeLayers(steps);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Workflow Graph</h1>
      {steps.length === 0 ? (
        <p className="text-gray-500">No execution plan available. Run planning first.</p>
      ) : (
        <div className="space-y-8">
          {layers.map((layer, depth) => (
            <div key={depth} className="flex flex-wrap gap-4 justify-center">
              {layer.map(step => (
                <div
                  key={step.step_index}
                  className={`border-2 rounded-lg p-4 w-64 ${AGENT_COLORS[step.agent_name] || 'border-gray-300 bg-gray-50'}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono text-gray-500">#{step.step_index}</span>
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-white">
                      {step.agent_name}
                    </span>
                  </div>
                  <p className="text-sm">{step.description}</p>
                  <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                    {step.estimated_tokens > 0 && (
                      <span>~{step.estimated_tokens} tok</span>
                    )}
                    {step.requires_github_actions && (
                      <span className="px-1 py-0.5 bg-gray-200 rounded">GHA</span>
                    )}
                  </div>
                  {step.depends_on.length > 0 && (
                    <div className="mt-2 text-xs text-gray-400">
                      Depends on: {step.depends_on.map(d => `#${d}`).join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
          {/* Legend */}
          <div className="border-t pt-4">
            <p className="text-xs text-gray-400 mb-2">Agent Legend:</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(AGENT_COLORS).map(([name, cls]) => (
                <span key={name} className={`text-xs px-2 py-1 border rounded ${cls}`}>
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function computeLayers(steps: PlanStep[]): PlanStep[][] {
  if (steps.length === 0) return [];
  const stepMap = new Map(steps.map(s => [s.step_index, s]));
  const depths = new Map<number, number>();

  function getDepth(idx: number): number {
    if (depths.has(idx)) return depths.get(idx)!;
    const step = stepMap.get(idx);
    if (!step || step.depends_on.length === 0) {
      depths.set(idx, 0);
      return 0;
    }
    const maxDep = Math.max(...step.depends_on.map(d => getDepth(d)));
    const depth = maxDep + 1;
    depths.set(idx, depth);
    return depth;
  }

  steps.forEach(s => getDepth(s.step_index));

  const maxDepth = Math.max(...Array.from(depths.values()));
  const layers: PlanStep[][] = Array.from({ length: maxDepth + 1 }, () => []);
  steps.forEach(s => {
    layers[depths.get(s.step_index) || 0].push(s);
  });
  return layers;
}

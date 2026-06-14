/**
 * Reasoning Trace — Phase 5.
 *
 * Shows the chain-of-thought reasoning from each agent invocation,
 * including LLM prompts, responses, and decision points.
 */
import { useEffect, useState } from 'react';

interface TraceSpan {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  operation: string;
  service: string;
  attributes: Record<string, unknown>;
  start_time: number;
  end_time: number | null;
  duration_ms: number;
  status: string;
  events: Array<{
    name: string;
    timestamp: number;
    attributes: Record<string, unknown>;
  }>;
}

export function ReasoningTrace({ executionId }: { executionId: string }) {
  const [spans, setSpans] = useState<TraceSpan[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    const token = localStorage.getItem('auth_token');
    fetch(`${apiBase}/api/v1/aep/observability/traces`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : { spans: [] })
      .then(data => {
        // Filter spans for this execution
        const allSpans = data.spans || [];
        const relevant = allSpans.filter(
          (s: TraceSpan) => s.attributes?.execution_id === executionId || !executionId
        );
        setSpans(relevant.length > 0 ? relevant : allSpans.slice(0, 50));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [executionId]);

  if (loading) return <div className="p-6">Loading traces...</div>;

  // Build tree structure from parent_span_id
  const rootSpans = spans.filter(s => !s.parent_span_id);
  const childMap = new Map<string, TraceSpan[]>();
  spans.forEach(s => {
    if (s.parent_span_id) {
      const children = childMap.get(s.parent_span_id) || [];
      children.push(s);
      childMap.set(s.parent_span_id, children);
    }
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Reasoning Trace</h1>
      {spans.length === 0 ? (
        <p className="text-gray-500">No trace data available. Traces are recorded during agent execution.</p>
      ) : (
        <div className="flex gap-4">
          {/* Trace tree */}
          <div className="flex-1 space-y-1">
            {rootSpans.map(span => (
              <SpanNode
                key={span.span_id}
                span={span}
                childMap={childMap}
                selected={selectedSpan?.span_id}
                onSelect={setSelectedSpan}
                depth={0}
              />
            ))}
          </div>

          {/* Detail panel */}
          {selectedSpan && (
            <div className="w-96 border rounded-lg p-4 sticky top-6 h-fit">
              <h3 className="font-medium mb-3">{selectedSpan.operation}</h3>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-gray-500 text-xs">Duration</dt>
                  <dd className="font-mono">{selectedSpan.duration_ms.toFixed(1)}ms</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Status</dt>
                  <dd className={selectedSpan.status === 'ok' ? 'text-green-600' : 'text-red-600'}>
                    {selectedSpan.status}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs">Trace ID</dt>
                  <dd className="font-mono text-xs truncate">{selectedSpan.trace_id}</dd>
                </div>
                {Object.entries(selectedSpan.attributes).length > 0 && (
                  <div>
                    <dt className="text-gray-500 text-xs mb-1">Attributes</dt>
                    <dd className="bg-gray-50 rounded p-2 text-xs font-mono overflow-auto max-h-48">
                      {JSON.stringify(selectedSpan.attributes, null, 2)}
                    </dd>
                  </div>
                )}
                {selectedSpan.events.length > 0 && (
                  <div>
                    <dt className="text-gray-500 text-xs mb-1">Events</dt>
                    <dd className="space-y-1">
                      {selectedSpan.events.map((event, i) => (
                        <div key={i} className="text-xs bg-gray-50 rounded p-1">
                          <span className="font-medium">{event.name}</span>
                        </div>
                      ))}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SpanNode({
  span,
  childMap,
  selected,
  onSelect,
  depth,
}: {
  span: TraceSpan;
  childMap: Map<string, TraceSpan[]>;
  selected: string | undefined;
  onSelect: (s: TraceSpan) => void;
  depth: number;
}) {
  const children = childMap.get(span.span_id) || [];
  const isSelected = selected === span.span_id;

  return (
    <div style={{ marginLeft: depth * 16 }}>
      <button
        onClick={() => onSelect(span)}
        className={`w-full text-left px-2 py-1 rounded text-sm flex items-center gap-2 ${
          isSelected ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50'
        }`}
      >
        <span className={`w-2 h-2 rounded-full ${
          span.status === 'ok' ? 'bg-green-400' : 'bg-red-400'
        }`} />
        <span className="font-mono text-xs flex-1 truncate">{span.operation}</span>
        <span className="text-xs text-gray-400">{span.duration_ms.toFixed(0)}ms</span>
      </button>
      {children.map(child => (
        <SpanNode
          key={child.span_id}
          span={child}
          childMap={childMap}
          selected={selected}
          onSelect={onSelect}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

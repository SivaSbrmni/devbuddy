/**
 * Live Log Viewer — Phase 5.
 *
 * Streams execution logs in real-time via WebSocket. Shows structured
 * log entries with severity, agent name, and timestamps.
 */
import { useEffect, useRef, useState } from 'react';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  agent: string;
  message: string;
  metadata?: Record<string, unknown>;
}

const LEVEL_STYLES: Record<string, string> = {
  debug: 'text-gray-400',
  info: 'text-blue-600',
  warning: 'text-yellow-600',
  error: 'text-red-600',
};

export function LiveLogViewer({ executionId }: { executionId: string }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    const wsUrl = apiBase.replace(/^http/, 'ws') + `/api/v1/aep/ws/logs/${executionId}`;
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onmessage = (event) => {
        try {
          const entry = JSON.parse(event.data) as LogEntry;
          setLogs(prev => [...prev, entry].slice(-1000));
        } catch {
          // Ignore malformed messages
        }
      };
    } catch {
      // WebSocket not available
    }

    return () => { ws?.close(); };
  }, [executionId]);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filteredLogs = filter === 'all'
    ? logs
    : logs.filter(l => l.level === filter);

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Logs</h1>
          <span className={`px-2 py-0.5 rounded text-xs ${connected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="text-sm border rounded px-2 py-1"
          >
            <option value="all">All levels</option>
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={e => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
          <button
            onClick={() => setLogs([])}
            className="text-sm px-2 py-1 border rounded hover:bg-gray-50"
          >
            Clear
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto bg-gray-900 rounded-lg p-4 font-mono text-xs"
      >
        {filteredLogs.length === 0 ? (
          <p className="text-gray-500">Waiting for log entries...</p>
        ) : (
          filteredLogs.map(entry => (
            <div key={entry.id} className="flex gap-2 py-0.5 hover:bg-gray-800">
              <span className="text-gray-500 shrink-0">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
              <span className={`shrink-0 uppercase w-6 ${LEVEL_STYLES[entry.level]}`}>
                {entry.level.charAt(0)}
              </span>
              <span className="text-purple-400 shrink-0 w-20 truncate">
                {entry.agent}
              </span>
              <span className="text-gray-200">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

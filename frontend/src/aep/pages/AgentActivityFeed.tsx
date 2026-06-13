/**
 * Agent Activity Feed — Phase 5.
 *
 * Real-time feed of agent invocations and state changes.
 */
import { useEffect, useState } from 'react';
import { usePlugins } from '../hooks/useAepData';

interface ActivityEvent {
  id: string;
  timestamp: string;
  agent: string;
  event_type: 'invocation' | 'state_change' | 'message' | 'error';
  description: string;
  metadata?: Record<string, unknown>;
}

export function AgentActivityFeed() {
  const { plugins } = usePlugins();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    const wsUrl = apiBase.replace(/^http/, 'ws') + '/api/v1/aep/ws/activity';
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as ActivityEvent;
          setEvents(prev => [data, ...prev].slice(0, 100));
        } catch {
          // Ignore malformed messages
        }
      };
    } catch {
      // WebSocket not available — fallback to polling would go here
    }

    return () => { ws?.close(); };
  }, []);

  const eventIcon = (type: string) => {
    switch (type) {
      case 'invocation': return '▶';
      case 'state_change': return '↻';
      case 'message': return '💬';
      case 'error': return '⚠';
      default: return '•';
    }
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Agent Activity</h1>
        <span className={`px-2 py-1 rounded text-xs ${connected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
          {connected ? 'Live' : 'Disconnected'}
        </span>
      </div>
      <div className="mb-4">
        <h2 className="text-sm font-medium text-gray-500 mb-2">Active Agents</h2>
        <div className="flex flex-wrap gap-2">
          {plugins.filter(p => p.active).map(plugin => (
            <span key={plugin.name} className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">
              {plugin.name}
            </span>
          ))}
          {plugins.filter(p => p.active).length === 0 && (
            <span className="text-gray-400 text-sm">No agents active</span>
          )}
        </div>
      </div>
      <div className="space-y-2">
        {events.length === 0 ? (
          <p className="text-gray-500 text-sm">No activity yet. Submit a task to see agent activity.</p>
        ) : (
          events.map(event => (
            <div key={event.id} className="flex items-start gap-3 p-2 border-b">
              <span className="text-lg">{eventIcon(event.event_type)}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{event.agent}</span>
                  <span className="text-xs text-gray-400">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-gray-600 truncate">{event.description}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

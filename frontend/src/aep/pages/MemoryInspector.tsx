/**
 * Memory Inspector — Phase 5.
 *
 * Browse and search the AEP memory system — repo summaries, execution
 * history, debug patterns, and code patterns stored as embeddings.
 */
import { useEffect, useState } from 'react';

interface MemoryEntry {
  id: string;
  tenant_id: string;
  memory_type: string;
  content: string;
  source: string | null;
  embedding_model: string | null;
  token_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

const TYPE_STYLES: Record<string, string> = {
  repo_summary: 'bg-blue-50 text-blue-700',
  execution_history: 'bg-purple-50 text-purple-700',
  debug_pattern: 'bg-red-50 text-red-700',
  code_pattern: 'bg-green-50 text-green-700',
  failure: 'bg-orange-50 text-orange-700',
};

export function MemoryInspector() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MemoryEntry[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    const token = localStorage.getItem('auth_token');
    fetch(`${apiBase}/api/v1/aep/memory/entries`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : { entries: [] })
      .then(data => {
        setEntries(data.entries || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    const apiBase = import.meta.env.VITE_API_URL || '';
    const token = localStorage.getItem('auth_token');
    try {
      const resp = await fetch(`${apiBase}/api/v1/aep/memory/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: searchQuery, top_k: 20 }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setSearchResults(data.results || []);
      }
    } catch {
      // Search failed silently
    } finally {
      setSearching(false);
    }
  };

  if (loading) return <div className="p-6">Loading memory...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  const displayEntries = searchResults || entries;
  const filtered = typeFilter === 'all'
    ? displayEntries
    : displayEntries.filter(e => e.memory_type === typeFilter);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Memory Inspector</h1>

      {/* Search bar */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="Semantic search across memory..."
          className="flex-1 px-3 py-2 border rounded-md"
        />
        <button
          onClick={handleSearch}
          disabled={searching}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
        {searchResults && (
          <button
            onClick={() => setSearchResults(null)}
            className="px-3 py-2 border rounded hover:bg-gray-50"
          >
            Clear
          </button>
        )}
      </div>

      {/* Type filter */}
      <div className="flex gap-2 mb-4">
        {['all', 'repo_summary', 'execution_history', 'debug_pattern', 'code_pattern', 'failure'].map(type => (
          <button
            key={type}
            onClick={() => setTypeFilter(type)}
            className={`px-2 py-1 rounded text-xs ${
              typeFilter === type ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'
            }`}
          >
            {type === 'all' ? 'All' : type.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="text-sm text-gray-500 mb-4">
        {searchResults ? `${filtered.length} search results` : `${filtered.length} entries`}
        {' · '}
        Total tokens: {filtered.reduce((sum, e) => sum + e.token_count, 0).toLocaleString()}
      </div>

      {/* Entries */}
      {filtered.length === 0 ? (
        <p className="text-gray-500">No memory entries found.</p>
      ) : (
        <div className="space-y-3">
          {filtered.map(entry => (
            <div key={entry.id} className="border rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${TYPE_STYLES[entry.memory_type] || 'bg-gray-100'}`}>
                    {entry.memory_type}
                  </span>
                  {entry.source && (
                    <span className="text-xs text-gray-400 font-mono">{entry.source}</span>
                  )}
                </div>
                <span className="text-xs text-gray-400">
                  {entry.token_count} tokens · {new Date(entry.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-sm text-gray-700 line-clamp-3">{entry.content}</p>
              {entry.embedding_model && (
                <span className="text-xs text-gray-400 mt-1 inline-block">
                  Embedded: {entry.embedding_model}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

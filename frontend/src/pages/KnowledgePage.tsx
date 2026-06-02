import { useState } from 'react'
import { searchKnowledge } from '../api/client'

export default function KnowledgePage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[]>([])

  const handleSearch = async () => {
    if (!query) return
    const res = await searchKnowledge(query)
    setResults(res)
  }

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Knowledge Base</h2>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 12 }}>Semantic Search</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <input placeholder="Search knowledge..." value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          <button onClick={handleSearch} disabled={!query}>Search</button>
        </div>
      </div>

      {results.length > 0 && (
        <div style={{ display: 'grid', gap: 12 }}>
          {results.map((r, i) => (
            <div key={i} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>{r.title}</span>
                <span className="badge info">{r.category}</span>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>{r.content}</p>
              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
                <span>Distance: {r.distance?.toFixed(3)}</span>
                <span>Used: {r.usage_count}x</span>
                {Array.isArray(r.tags) && r.tags.length > 0 && <span>Tags: {r.tags.join(', ')}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getProject, listTasks, listRuns, runPipeline, runCodingTask } from '../api/client'

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<any>(null)
  const [tasks, setTasks] = useState<any[]>([])
  const [runs, setRuns] = useState<any[]>([])
  const [tab, setTab] = useState<'pipeline' | 'code' | 'tasks' | 'runs'>('pipeline')
  const [requirements, setRequirements] = useState('')
  const [codeTask, setCodeTask] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    if (!id) return
    getProject(id).then(setProject).catch(() => {})
    listTasks(id).then(setTasks).catch(() => {})
    listRuns(id).then(setRuns).catch(() => {})
  }, [id])

  const handlePipeline = async () => {
    if (!id) return
    setLoading(true)
    setResult(null)
    try {
      const res = await runPipeline(id, { requirements })
      setResult(res)
      listTasks(id).then(setTasks)
    } catch (e: any) {
      setResult({ error: e.message })
    }
    setLoading(false)
  }

  const handleCode = async () => {
    if (!id) return
    setLoading(true)
    setResult(null)
    try {
      const res = await runCodingTask(id, { task_description: codeTask })
      setResult(res)
      listTasks(id).then(setTasks)
    } catch (e: any) {
      setResult({ error: e.message })
    }
    setLoading(false)
  }

  if (!project) return <p style={{ color: 'var(--text-muted)' }}>Loading...</p>

  const statusColor = (s: string) =>
    s === 'completed' || s === 'success' ? 'success' :
    s === 'failed' ? 'error' :
    s === 'in_progress' || s === 'running' ? 'warning' : 'info'

  return (
    <div>
      <h2 style={{ marginBottom: 8 }}>{project.name}</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>{project.description}</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
        {(['pipeline', 'code', 'tasks', 'runs'] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setResult(null) }}
            style={{ background: tab === t ? 'var(--accent)' : 'var(--bg-hover)', flex: '1 1 auto', minWidth: 70 }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'pipeline' && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>Run Pipeline (Requirements &rarr; Architecture)</h3>
          <textarea rows={6} placeholder="Enter requirements..." value={requirements}
            onChange={e => setRequirements(e.target.value)} style={{ marginBottom: 12 }} />
          <button onClick={handlePipeline} disabled={loading || !requirements}>
            {loading ? 'Running...' : 'Run Pipeline'}
          </button>
        </div>
      )}

      {tab === 'code' && (
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>Coding Task (Code &rarr; Review &rarr; Test)</h3>
          <textarea rows={4} placeholder="Describe the coding task..." value={codeTask}
            onChange={e => setCodeTask(e.target.value)} style={{ marginBottom: 12 }} />
          <button onClick={handleCode} disabled={loading || !codeTask}>
            {loading ? 'Generating...' : 'Run Coding Task'}
          </button>
        </div>
      )}

      {tab === 'tasks' && (
        <div>
          <h3 style={{ marginBottom: 16 }}>Tasks</h3>
          {tasks.map(t => (
            <div key={t.id} className="card" style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{t.title}</span>
                <span className={`badge ${statusColor(t.status)}`}>{t.status}</span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>{t.task_type}</p>
            </div>
          ))}
          {tasks.length === 0 && <p style={{ color: 'var(--text-muted)' }}>No tasks yet.</p>}
        </div>
      )}

      {tab === 'runs' && (
        <div>
          <h3 style={{ marginBottom: 16 }}>Execution Runs</h3>
          {runs.map(r => (
            <div key={r.id} className="card" style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{r.run_type} — {r.trigger}</span>
                <span className={`badge ${statusColor(r.status)}`}>{r.status}</span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                Retries: {r.retry_count} | {new Date(r.created_at).toLocaleString()}
              </p>
            </div>
          ))}
          {runs.length === 0 && <p style={{ color: 'var(--text-muted)' }}>No runs yet.</p>}
        </div>
      )}

      {result && (
        <div className="card" style={{ marginTop: 24, borderColor: result.error ? 'var(--error)' : 'var(--border)' }}>
          <h3 style={{ marginBottom: 12, color: result.error ? 'var(--error)' : 'var(--text)' }}>
            {result.error ? 'Error' : 'Result'}
          </h3>
          {result.error ? (
            <p style={{ color: 'var(--error)', fontSize: 14, wordBreak: 'break-word' }}>{result.error}</p>
          ) : (
            <pre style={{ background: 'var(--bg)', padding: 12, borderRadius: 'var(--radius)', overflow: 'auto', maxHeight: 400, fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { createWorkspace, execCommand, listFiles } from '../api/client'

export default function WorkspacePage() {
  const [wsId, setWsId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [command, setCommand] = useState('')
  const [output, setOutput] = useState<any>(null)
  const [files, setFiles] = useState<string[]>([])

  const handleCreate = async () => {
    const ws = await createWorkspace(projectId)
    setWsId(ws.workspace_id)
  }

  const handleExec = async () => {
    if (!wsId || !command) return
    const res = await execCommand(wsId, command)
    setOutput(res)
  }

  const handleListFiles = async () => {
    if (!wsId) return
    const res = await listFiles(wsId)
    setFiles(res.files || [])
  }

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Engineering Workspace</h2>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 12 }}>Create Workspace</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <input placeholder="Project ID" value={projectId}
            onChange={e => setProjectId(e.target.value)} />
          <button onClick={handleCreate} disabled={!projectId}>Create</button>
        </div>
        {wsId && <p style={{ marginTop: 8, color: 'var(--success)', fontSize: 13 }}>Workspace: {wsId}</p>}
      </div>

      {wsId && (
        <>
          <div className="card" style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 12 }}>Terminal</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input placeholder="Command..." value={command}
                onChange={e => setCommand(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleExec()} />
              <button onClick={handleExec}>Run</button>
            </div>
            {output && (
              <pre style={{ background: 'var(--bg)', padding: 12, borderRadius: 'var(--radius)', overflow: 'auto', maxHeight: 300, fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)' }}>exit: {output.exit_code} ({output.duration_ms}ms)</span>
                {'\n'}{output.stdout}
                {output.stderr && <span style={{ color: 'var(--error)' }}>{'\n'}{output.stderr}</span>}
              </pre>
            )}
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3>Files</h3>
              <button onClick={handleListFiles} style={{ padding: '4px 12px', fontSize: 13 }}>Refresh</button>
            </div>
            {files.length > 0 ? (
              <ul style={{ listStyle: 'none', fontSize: 13 }}>
                {files.map(f => <li key={f} style={{ padding: '4px 0', color: 'var(--text-muted)' }}>{f}</li>)}
              </ul>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Click refresh to load files.</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

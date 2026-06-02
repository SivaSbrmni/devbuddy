import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { createProject, deleteProject, listProjects } from '../api/client'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', repo_url: '' })

  const load = () => { listProjects().then(setProjects).catch(() => {}) }
  useEffect(load, [])

  const handleCreate = async () => {
    await createProject(form)
    setForm({ name: '', description: '', repo_url: '' })
    setShowCreate(false)
    load()
  }

  const handleDelete = async (id: string) => {
    if (confirm('Delete this project?')) {
      await deleteProject(id)
      load()
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2>Projects</h2>
        <button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ New Project'}
        </button>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input placeholder="Project name" value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })} />
            <input placeholder="Description" value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })} />
            <input placeholder="Repository URL (optional)" value={form.repo_url}
              onChange={e => setForm({ ...form, repo_url: e.target.value })} />
            <button onClick={handleCreate} disabled={!form.name}>Create Project</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {projects.map(p => (
          <div key={p.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Link to={`/projects/${p.id}`} style={{ fontSize: 16, fontWeight: 600 }}>{p.name}</Link>
              <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>{p.description}</p>
              {p.repo_url && <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>{p.repo_url}</p>}
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className={`badge ${p.status === 'active' ? 'success' : 'info'}`}>{p.status}</span>
              <button onClick={() => handleDelete(p.id)} style={{ background: 'var(--error)', padding: '4px 10px', fontSize: 12 }}>Delete</button>
            </div>
          </div>
        ))}
        {projects.length === 0 && <p style={{ color: 'var(--text-muted)' }}>No projects yet. Create one to get started.</p>}
      </div>
    </div>
  )
}

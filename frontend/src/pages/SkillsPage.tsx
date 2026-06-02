import { useEffect, useState } from 'react'
import { listSkills, seedSkills } from '../api/client'

export default function SkillsPage() {
  const [skills, setSkills] = useState<any[]>([])
  const [seeded, setSeeded] = useState(false)

  const load = () => { listSkills().then(setSkills).catch(() => {}) }
  useEffect(load, [])

  const handleSeed = async () => {
    await seedSkills()
    setSeeded(true)
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2>Skills</h2>
        <button onClick={handleSeed}>{seeded ? 'Seeded!' : 'Seed Built-in Skills'}</button>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        {skills.map(s => (
          <div key={s.id} className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 600 }}>{s.name}</span>
              <span className="badge info">{s.category}</span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>{s.description}</p>
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
              <span>Steps: {Array.isArray(s.steps) ? s.steps.length : 0}</span>
              <span>Used: {s.usage_count}x</span>
              {s.success_rate !== null && <span>Success: {(s.success_rate * 100).toFixed(0)}%</span>}
            </div>
          </div>
        ))}
        {skills.length === 0 && <p style={{ color: 'var(--text-muted)' }}>No skills yet. Click "Seed Built-in Skills" to get started.</p>}
      </div>
    </div>
  )
}

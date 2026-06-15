import { useState } from 'react'

interface FileEntry {
  name: string
  content?: string
}

interface WorkspacePanelProps {
  files: FileEntry[]
  onDownload: (files: FileEntry[]) => void
  onDownloadOne: (file: FileEntry) => void
  isOpen: boolean
  onToggle: () => void
}

export default function WorkspacePanel({ files, onDownload, onDownloadOne, isOpen, onToggle }: WorkspacePanelProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)

  const selected = files.find(f => f.name === selectedFile)

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="db-btn"
        title="Workspace"
        style={{
          position: 'fixed',
          right: 16,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: files.length > 0 ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
          border: files.length > 0 ? '1px solid rgba(99,102,241,0.3)' : '1px solid #2a2d3a',
          color: files.length > 0 ? '#818cf8' : '#6b7280',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          zIndex: 30,
          transition: 'all var(--transition-base)',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.2)'; e.currentTarget.style.transform = 'translateY(-50%) scale(1.1)' }}
        onMouseLeave={e => { e.currentTarget.style.background = files.length > 0 ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)'; e.currentTarget.style.transform = 'translateY(-50%) scale(1)' }}
      >
        📁
        {files.length > 0 && (
          <span style={{
            position: 'absolute',
            top: -4,
            right: -4,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: '#6366f1',
            color: 'white',
            fontSize: 10,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>{files.length}</span>
        )}
      </button>
    )
  }

  return (
    <div style={{
      width: 340,
      background: '#111318',
      borderLeft: '1px solid #1e2130',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      animation: 'slideInRight 0.25s ease',
    }}>
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid #1e2130', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#e4e6eb', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>📁</span> Workspace
          {files.length > 0 && <span style={{ fontSize: 11, color: '#6b7280', fontWeight: 400 }}>({files.length})</span>}
        </div>
        <button onClick={onToggle} className="db-btn" style={{ background: 'none', border: 'none', color: '#4b4f63', cursor: 'pointer', fontSize: 16, padding: '2px 6px', borderRadius: 'var(--radius-sm)' }}>×</button>
      </div>

      {/* File list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
        {files.length === 0 && (
          <div style={{ padding: 24, textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📂</div>
            <div style={{ fontSize: 13, color: '#6b7280' }}>No files yet</div>
            <div style={{ fontSize: 12, color: '#4b4f63', marginTop: 4 }}>Ask DevBuddy to build something</div>
          </div>
        )}

        {files.map(file => (
          <div
            key={file.name}
            onClick={() => { setSelectedFile(file.name); setExpanded(true) }}
            className="db-btn"
            style={{
              padding: '8px 10px',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              marginBottom: 2,
              background: selectedFile === file.name ? 'rgba(99,102,241,0.1)' : 'transparent',
              border: selectedFile === file.name ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              transition: 'all var(--transition-fast)',
            }}
          >
            <span style={{ fontSize: 14 }}>📄</span>
            <span style={{ flex: 1, fontSize: 12, color: selectedFile === file.name ? '#c7d2fe' : '#9ca3af', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</span>
            <button
              onClick={e => { e.stopPropagation(); onDownloadOne(file) }}
              className="db-btn"
              title="Download"
              style={{ background: 'none', border: 'none', color: '#4b4f63', cursor: 'pointer', fontSize: 12, padding: '2px 6px', borderRadius: 'var(--radius-sm)', transition: 'all var(--transition-fast)' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#818cf8' }}
              onMouseLeave={e => { e.currentTarget.style.color = '#4b4f63' }}
            >
              ↓
            </button>
          </div>
        ))}
      </div>

      {/* Preview panel */}
      {selected && expanded && selected.content && (
        <div style={{
          borderTop: '1px solid #1e2130',
          maxHeight: 300,
          display: 'flex',
          flexDirection: 'column',
          animation: 'fadeIn 0.2s ease',
        }}>
          <div style={{ padding: '8px 12px', borderBottom: '1px solid #1e2130', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, color: '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selected.name}</span>
            <button onClick={() => setExpanded(false)} className="db-btn" style={{ background: 'none', border: 'none', color: '#4b4f63', cursor: 'pointer', fontSize: 12 }}>−</button>
          </div>
          <pre style={{
            flex: 1,
            overflow: 'auto',
            padding: 12,
            margin: 0,
            fontSize: 12,
            lineHeight: 1.5,
            color: '#9ca3af',
            background: '#0d0f14',
            fontFamily: 'monospace',
          }}>
            {selected.content.slice(0, 2000)}{selected.content.length > 2000 ? '\n\n... (truncated)' : ''}
          </pre>
        </div>
      )}

      {/* Actions */}
      {files.length > 0 && (
        <div style={{ padding: '10px 12px', borderTop: '1px solid #1e2130', display: 'flex', gap: 8 }}>
          <button
            onClick={() => onDownload(files)}
            className="db-btn db-focus"
            style={{
              flex: 1,
              padding: '6px 10px',
              background: 'rgba(99,102,241,0.12)',
              border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: 'var(--radius-md)',
              color: '#818cf8',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              textAlign: 'center',
              transition: 'all var(--transition-base)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.2)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.12)' }}
          >
            📦 Download All
          </button>
        </div>
      )}
    </div>
  )
}

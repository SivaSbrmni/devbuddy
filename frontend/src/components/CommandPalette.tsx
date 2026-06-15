import { useState, useEffect, useRef, useCallback } from 'react'

interface Command {
  id: string
  label: string
  shortcut?: string
  icon: string
  action: () => void
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  commands: Command[]
}

export default function CommandPalette({ isOpen, onClose, commands }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const filtered = query.trim()
    ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : commands

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => (i + 1) % filtered.length)
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => (i - 1 + filtered.length) % filtered.length)
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      const cmd = filtered[selectedIndex]
      if (cmd) {
        cmd.action()
        onClose()
      }
      return
    }
  }, [filtered, selectedIndex, onClose])

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.5)',
        backdropFilter: 'blur(6px)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '15vh',
        animation: 'fadeIn 0.15s ease',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 520,
          background: '#111318',
          border: '1px solid #2a2d3a',
          borderRadius: 'var(--radius-xl)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)',
          overflow: 'hidden',
          animation: 'modalContent 0.2s ease',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #1e2130', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: '#4b4f63', fontSize: 16 }}>⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            style={{
              flex: 1,
              background: 'none',
              border: 'none',
              outline: 'none',
              color: '#e4e6eb',
              fontSize: 15,
              fontFamily: 'inherit',
            }}
          />
          <span style={{ fontSize: 11, color: '#4b4f63', background: '#1a1d27', padding: '2px 8px', borderRadius: 4 }}>ESC</span>
        </div>
        <div style={{ maxHeight: 320, overflowY: 'auto', padding: '6px' }}>
          {filtered.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', color: '#4b4f63', fontSize: 13 }}>No commands found</div>
          )}
          {filtered.map((cmd, i) => (
            <div
              key={cmd.id}
              onClick={() => { cmd.action(); onClose() }}
              onMouseEnter={() => setSelectedIndex(i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 12px',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                background: i === selectedIndex ? 'rgba(99,102,241,0.12)' : 'transparent',
                border: i === selectedIndex ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent',
                transition: 'all 0.1s ease',
              }}
            >
              <span style={{ fontSize: 16, width: 24, textAlign: 'center' }}>{cmd.icon}</span>
              <span style={{ flex: 1, fontSize: 14, color: '#e4e6eb' }}>{cmd.label}</span>
              {cmd.shortcut && (
                <span style={{ fontSize: 11, color: '#4b4f63', background: '#1a1d27', padding: '2px 8px', borderRadius: 4, fontFamily: 'monospace' }}>{cmd.shortcut}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

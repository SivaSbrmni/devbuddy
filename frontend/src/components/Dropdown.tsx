import { useState, useRef, useEffect } from 'react'
import Icon from './Icon'

interface DropdownOption {
  value: string
  label: string
  description?: string
}

interface DropdownProps {
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function Dropdown({ value, options, onChange, disabled, placeholder }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = options.find(o => o.value === value)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className="db-btn db-focus"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '5px 10px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-muted)',
          fontSize: 11,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          transition: 'all var(--transition-base)',
        }}
        onMouseEnter={e => { if (!disabled) e.currentTarget.style.borderColor = 'var(--text-faint)' }}
        onMouseLeave={e => { if (!disabled) e.currentTarget.style.borderColor = 'var(--border)' }}
      >
        <span>{selected?.label || placeholder || 'Select...'}</span>
        <Icon name="chevron-down" size={12} style={{ transition: 'transform var(--transition-fast)', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }} />
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          bottom: 'calc(100% + 6px)',
          right: 0,
          minWidth: 220,
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          padding: '6px',
          zIndex: 100,
          boxShadow: 'var(--shadow-lg)',
          animation: 'dropdownIn 0.15s ease',
        }}>
          {options.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false) }}
              className="db-btn"
              style={{
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                gap: 2,
                padding: '8px 10px',
                borderRadius: 'var(--radius-sm)',
                background: opt.value === value ? 'rgba(99,102,241,0.1)' : 'transparent',
                border: 'none',
                color: opt.value === value ? 'var(--accent-hover)' : 'var(--text-muted)',
                fontSize: 12,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all var(--transition-fast)',
              }}
              onMouseEnter={e => { if (opt.value !== value) { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text)' } }}
              onMouseLeave={e => { if (opt.value !== value) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)' } }}
            >
              <span style={{ fontWeight: opt.value === value ? 600 : 500 }}>{opt.label}</span>
              {opt.description && <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{opt.description}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

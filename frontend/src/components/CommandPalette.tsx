import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import Icon from './Icon'

interface Command {
  id: string
  label: string
  shortcut?: string
  icon: string
  action: () => void
}

interface ConversationItem {
  id: string
  title: string
  messageCount: number
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  commands: Command[]
  conversations?: ConversationItem[]
  onSelectConversation?: (id: string) => void
}

type SectionType = 'command' | 'conversation'

interface ListItem {
  type: SectionType
  index: number
  data: Command | ConversationItem
}

export default function CommandPalette({ isOpen, onClose, commands, conversations = [], onSelectConversation }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const q = query.trim().toLowerCase()

  const filteredCommands = useMemo(() =>
    q ? commands.filter(c => c.label.toLowerCase().includes(q)) : commands,
    [commands, q]
  )

  const filteredConversations = useMemo(() =>
    q ? conversations.filter(c => c.title.toLowerCase().includes(q)) : conversations.slice(0, 5),
    [conversations, q]
  )

  const items: ListItem[] = useMemo(() => {
    const list: ListItem[] = []
    filteredCommands.forEach((c, i) => list.push({ type: 'command', index: i, data: c }))
    filteredConversations.forEach((c, i) => list.push({ type: 'conversation', index: i, data: c }))
    return list
  }, [filteredCommands, filteredConversations])

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

  // Scroll selected into view
  useEffect(() => {
    if (listRef.current) {
      const selectedEl = listRef.current.querySelector('[data-selected="true"]') as HTMLElement
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [selectedIndex])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return }
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(i => (i + 1) % items.length); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex(i => (i - 1 + items.length) % items.length); return }
    if (e.key === 'Enter') {
      e.preventDefault()
      const item = items[selectedIndex]
      if (!item) return
      if (item.type === 'command') {
        (item.data as Command).action()
      } else {
        onSelectConversation?.((item.data as ConversationItem).id)
      }
      onClose()
      return
    }
  }, [items, selectedIndex, onClose, onSelectConversation])

  if (!isOpen) return null

  const renderSectionHeader = (label: string, icon: string) => (
    <div style={{ padding: '6px 12px 4px', fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
      <Icon name={icon as any} size={10} /> {label}
    </div>
  )

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(6px)', zIndex: 200, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh', animation: 'fadeIn 0.15s ease' }} onClick={onClose}>
      <div style={{ width: '100%', maxWidth: 560, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)', boxShadow: '0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)', overflow: 'hidden', animation: 'modalContent 0.2s ease' }} onClick={e => e.stopPropagation()}>
        {/* Search input */}
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Icon name="search" size={18} style={{ color: 'var(--text-faint)' }} />
          <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} placeholder="Search commands, conversations, files..." style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 16, fontFamily: 'inherit' }} />
          <span style={{ fontSize: 11, color: 'var(--text-faint)', background: 'var(--bg-card)', padding: '3px 8px', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace' }}>ESC</span>
        </div>

        {/* Results */}
        <div ref={listRef} style={{ maxHeight: 380, overflowY: 'auto', padding: '6px' }}>
          {items.length === 0 && (
            <div style={{ padding: '32px', textAlign: 'center' }}>
              <Icon name="search" size={32} style={{ color: 'var(--border)', marginBottom: 12 }} />
              <div style={{ color: 'var(--text-faint)', fontSize: 14 }}>No results for &quot;{query}&quot;</div>
            </div>
          )}

          {filteredCommands.length > 0 && (
            <>
              {renderSectionHeader('Actions', 'zap')}
              {filteredCommands.map((cmd, i) => {
                const globalIndex = items.findIndex(it => it.type === 'command' && it.index === i)
                const isSelected = globalIndex === selectedIndex
                return (
                  <div key={cmd.id} data-selected={isSelected} onClick={() => { cmd.action(); onClose() }} onMouseEnter={() => setSelectedIndex(globalIndex)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', background: isSelected ? 'rgba(99,102,241,0.12)' : 'transparent', border: isSelected ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent', transition: 'all 0.08s ease' }}>
                    <Icon name={cmd.icon as any} size={18} style={{ color: isSelected ? 'var(--accent-hover)' : 'var(--text-dim)' }} />
                    <span style={{ flex: 1, fontSize: 14, color: 'var(--text)' }}>{cmd.label}</span>
                    {cmd.shortcut && <span style={{ fontSize: 11, color: 'var(--text-faint)', background: 'var(--bg-card)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace' }}>{cmd.shortcut}</span>}
                  </div>
                )
              })}
            </>
          )}

          {filteredConversations.length > 0 && (
            <>
              {renderSectionHeader('Conversations', 'chat')}
              {filteredConversations.map((conv, i) => {
                const globalIndex = items.findIndex(it => it.type === 'conversation' && it.index === i)
                const isSelected = globalIndex === selectedIndex
                return (
                  <div key={conv.id} data-selected={isSelected} onClick={() => { onSelectConversation?.(conv.id); onClose() }} onMouseEnter={() => setSelectedIndex(globalIndex)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', background: isSelected ? 'rgba(99,102,241,0.12)' : 'transparent', border: isSelected ? '1px solid rgba(99,102,241,0.2)' : '1px solid transparent', transition: 'all 0.08s ease' }}>
                    <div style={{ width: 28, height: 28, borderRadius: '50%', background: isSelected ? `hsl(${conv.title.split('').reduce((a, ch) => a + ch.charCodeAt(0), 0) % 360}, 70%, 55%)` : `hsl(${conv.title.split('').reduce((a, ch) => a + ch.charCodeAt(0), 0) % 360}, 50%, 20%)`, border: isSelected ? 'none' : '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'white', flexShrink: 0 }}>
                      {conv.title.charAt(0).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{conv.title}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{conv.messageCount} message{conv.messageCount !== 1 ? 's' : ''}</div>
                    </div>
                    <span style={{ color: isSelected ? 'var(--accent-hover)' : 'var(--text-faint)', opacity: isSelected ? 1 : 0, fontSize: 14 }}>→</span>
                  </div>
                )
              })}
            </>
          )}
        </div>

        {/* Footer shortcuts */}
        <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 16, fontSize: 11, color: 'var(--text-faint)' }}>
          <span><kbd style={{ background: 'var(--bg-card)', padding: '1px 5px', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace', border: '1px solid var(--border)' }}>↑↓</kbd> Navigate</span>
          <span><kbd style={{ background: 'var(--bg-card)', padding: '1px 5px', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace', border: '1px solid var(--border)' }}>↵</kbd> Select</span>
          <span><kbd style={{ background: 'var(--bg-card)', padding: '1px 5px', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace', border: '1px solid var(--border)' }}>esc</kbd> Close</span>
          <div style={{ flex: 1 }} />
          <span>{items.length} results</span>
        </div>
      </div>
    </div>
  )
}

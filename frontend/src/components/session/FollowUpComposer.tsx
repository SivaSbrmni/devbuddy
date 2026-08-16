import { useState } from 'react'
import Icon from '../Icon'
import { toast } from '../Toast'

interface Props {
  disabled?: boolean
  onSend: (message: string) => Promise<void>
}

export default function FollowUpComposer({ disabled, onSend }: Props) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)

  const handleSubmit = async () => {
    const trimmed = text.trim()
    if (!trimmed || sending || disabled) return
    setSending(true)
    try {
      await onSend(trimmed)
      setText('')
      toast('Follow-up sent — session restarted', 'success')
    } catch (e) {
      toast(e instanceof Error ? e.message : 'Failed to send follow-up', 'error')
    } finally {
      setSending(false)
    }
  }

  return (
    <div style={{
      padding: '12px 14px',
      borderTop: '1px solid var(--border-subtle)',
      background: 'var(--bg-elevated)',
    }}>
      <div style={{
        display: 'flex',
        gap: 8,
        alignItems: 'flex-end',
        padding: '10px 12px',
        borderRadius: 12,
        border: '1px solid var(--border)',
        background: 'var(--bg-card)',
      }}>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSubmit()
            }
          }}
          placeholder={disabled ? 'Follow-ups available after session completes' : 'Send a follow-up instruction…'}
          disabled={disabled || sending}
          rows={2}
          style={{
            flex: 1,
            resize: 'none',
            border: 'none',
            background: 'transparent',
            color: 'var(--text)',
            fontSize: 13,
            lineHeight: 1.5,
            outline: 'none',
            fontFamily: 'inherit',
          }}
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!text.trim() || disabled || sending}
          aria-label="Send follow-up"
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            border: 'none',
            background: text.trim() && !disabled ? 'var(--accent)' : 'var(--bg-hover)',
            color: text.trim() && !disabled ? '#fff' : 'var(--text-faint)',
            cursor: text.trim() && !disabled ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'all var(--transition-fast)',
          }}
        >
          <Icon name="send" size={16} />
        </button>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 8, paddingLeft: 4 }}>
        Shift+Enter for new line · Enter to send
      </div>
    </div>
  )
}

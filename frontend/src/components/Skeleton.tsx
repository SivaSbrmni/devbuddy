interface SkeletonProps {
  width?: string | number
  height?: string | number
  circle?: boolean
  style?: React.CSSProperties
}

export default function Skeleton({ width = '100%', height = 16, circle = false, style }: SkeletonProps) {
  return (
    <div
      className="db-skeleton"
      style={{
        width,
        height,
        borderRadius: circle ? '50%' : undefined,
        ...style,
      }}
    />
  )
}

export function MessageSkeleton() {
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 24, animation: 'fadeIn 0.4s ease' }}>
      <div className="db-skeleton" style={{ width: 28, height: 28, borderRadius: '50%', flexShrink: 0 }} />
      <div style={{ flex: 1, maxWidth: '85%' }}>
        <div className="db-skeleton" style={{ width: '70%', height: 14, marginBottom: 10 }} />
        <div className="db-skeleton" style={{ width: '100%', height: 12, marginBottom: 8 }} />
        <div className="db-skeleton" style={{ width: '90%', height: 12, marginBottom: 8 }} />
        <div className="db-skeleton" style={{ width: '60%', height: 12 }} />
      </div>
    </div>
  )
}

export function TypingIndicator() {
  return (
    <div style={{
      display: 'flex',
      gap: 12,
      marginBottom: 24,
      animation: 'fadeIn 0.3s ease',
    }}>
      <div style={{
        width: 28, height: 28,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #6366f1, #818cf8)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 12 }}>🤖</span>
      </div>
      <div style={{
        background: 'var(--db-bg-card)',
        border: '1px solid var(--db-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 7, height: 7,
            borderRadius: '50%',
            background: 'var(--db-text-faint)',
            animation: `typing-dot 1.4s ease-in-out ${i * 0.16}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

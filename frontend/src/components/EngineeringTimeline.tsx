// @ts-nocheck
/**
 * Engineering Timeline - Professional execution experience
 * 
 * Transforms CI logs into senior engineer supervision.
 * 
 * Design Principles:
 * - One parent card per execution
 * - 6 high-level phases (Intent → Planning → Implementation → Validation → Delivery)
 * - Expandable details (hidden by default)
 * - Live thinking instead of "Loading..."
 * - Semantic branch names (human-readable)
 * - Smooth 150-250ms animations
 * - 70% less visual density
 */

import { useState, useEffect } from 'react'
import Icon from './Icon'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export type Phase = 
  | 'understanding'    // Understanding request
  | 'planning'         // Analyzing architecture, planning implementation
  | 'implementing'     // Updating files, creating code
  | 'validating'       // Running tests, validation suite
  | 'delivering'       // Creating PR, final review
  | 'completed'        // Task done

export interface FileChange {
  path: string
  status: 'created' | 'modified' | 'deleted'
  additions?: number
  deletions?: number
}

export interface ExecutionPhase {
  id: Phase
  label: string
  status: 'pending' | 'active' | 'completed' | 'error'
  startedAt?: string
  completedAt?: string
  thinking?: string[]        // Live thinking messages
  currentFile?: string       // What's being worked on now
  files?: FileChange[]      // Files in this phase
  stats?: {
    filesChanged?: number
    testsPassed?: number
    testsTotal?: number
    duration?: number        // seconds
  }
}

export interface EngineeringTask {
  id: string
  title: string
  repository: {
    name: string
    owner: string
    fullName: string
  }
  branch: string            // Semantic: devbuddy/feature/name
  baseBranch: string
  status: 'working' | 'completed' | 'error'
  startedAt: string
  completedAt?: string
  phases: ExecutionPhase[]
  currentPhase: Phase
  summary?: {
    filesChanged: number
    testsPassed: number
    testsTotal: number
    prNumber?: number
    prUrl?: string
    commitHash?: string
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// PHASE CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════════

const PHASES_CONFIG: Record<Phase, { label: string; description: string; icon: string }> = {
  understanding: {
    label: 'Understanding',
    description: 'Analyzing request context',
    icon: 'target',
  },
  planning: {
    label: 'Planning',
    description: 'Designing implementation approach',
    icon: 'map',
  },
  implementing: {
    label: 'Implementation',
    description: 'Writing and updating code',
    icon: 'code',
  },
  validating: {
    label: 'Validation',
    description: 'Running tests and checks',
    icon: 'shield',
  },
  delivering: {
    label: 'Delivery',
    description: 'Creating pull request',
    icon: 'git-pull',
  },
  completed: {
    label: 'Completed',
    description: 'Task delivered successfully',
    icon: 'check-circle',
  },
}

const PHASE_ORDER: Phase[] = [
  'understanding',
  'planning',
  'implementing',
  'validating',
  'delivering',
  'completed',
]

// ═══════════════════════════════════════════════════════════════════════════════
// LIVE THINKING MESSAGES
// ═══════════════════════════════════════════════════════════════════════════════

const THINKING_MESSAGES: Record<Phase, string[]> = {
  understanding: [
    'Analyzing project structure...',
    'Reviewing existing implementation...',
    'Understanding requirements...',
    'Identifying affected components...',
  ],
  planning: [
    'Comparing implementation patterns...',
    'Planning minimal change set...',
    'Designing test strategy...',
    'Evaluating edge cases...',
  ],
  implementing: [
    'Preparing isolated workspace...',
    'Updating configuration...',
    'Implementing core logic...',
    'Adding error handling...',
  ],
  validating: [
    'Running test suite...',
    'Checking code coverage...',
    'Validating edge cases...',
    'Verifying no regressions...',
  ],
  delivering: [
    'Preparing commit message...',
    'Creating pull request...',
    'Adding PR description...',
    'Requesting review...',
  ],
  completed: [
    'Task completed successfully',
  ],
}

// ═══════════════════════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
  
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`
  return `${Math.floor(diff / 86400)} days ago`
}

// ═══════════════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

function PhaseStepper({ 
  phases, 
  currentPhase,
  expandedPhase,
  onPhaseClick,
}: { 
  phases: ExecutionPhase[]
  currentPhase: Phase
  expandedPhase: Phase | null
  onPhaseClick: (phase: Phase) => void
}) {
  const currentIndex = PHASE_ORDER.indexOf(currentPhase)
  
  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center',
      gap: 4,
      padding: '12px 0',
    }}>
      {PHASE_ORDER.map((phaseId, index) => {
        const phase = phases.find(p => p.id === phaseId)
        const config = PHASES_CONFIG[phaseId]
        const isCompleted = index < currentIndex
        const isActive = phaseId === currentPhase
        const isExpanded = expandedPhase === phaseId
        
        // Calculate progress for active phase
        const progress = isActive && phase?.stats?.duration 
          ? Math.min((phase.stats.duration / 60) * 100, 95) // Assume 60s per phase max
          : isCompleted ? 100 : 0
        
        return (
          <div 
            key={phaseId}
            onClick={() => onPhaseClick(phaseId)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              cursor: 'pointer',
              position: 'relative',
              flex: 1,
            }}
          >
            {/* Step Circle */}
            <div style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isCompleted 
                ? 'linear-gradient(135deg, #22c55e, #16a34a)'
                : isActive 
                  ? 'linear-gradient(135deg, #6366f1, #4f46e5)'
                  : 'var(--bg-card)',
              border: isActive 
                ? '2px solid #6366f1'
                : isCompleted 
                  ? '2px solid #22c55e'
                  : '2px solid var(--border)',
              transition: 'all 200ms ease-in-out',
              boxShadow: isActive 
                ? '0 0 20px rgba(99, 102, 241, 0.4)'
                : 'none',
            }}>
              {isCompleted ? (
                <Icon name="check" size={16} color="#fff" />
              ) : isActive ? (
                <div 
                  className="shimmer"
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: '#fff',
                  }}
                />
              ) : (
                <span style={{ 
                  fontSize: 12, 
                      color: 'var(--text-muted)',
                      fontWeight: 600,
                }}>
                  {index + 1}
                </span>
              )}
            </div>
            
            {/* Progress Bar */}
            {isActive && (
              <div style={{
                position: 'absolute',
                bottom: -4,
                left: '50%',
                transform: 'translateX(-50%)',
                width: 40,
                height: 3,
                background: 'var(--border)',
                borderRadius: 2,
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${progress}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                  borderRadius: 2,
                  transition: 'width 300ms ease-out',
                }} />
              </div>
            )}
            
            {/* Connector Line */}
            {index < PHASE_ORDER.length - 1 && (
              <div style={{
                position: 'absolute',
                top: 15,
                right: -50,
                width: 40,
                height: 2,
                background: index < currentIndex 
                  ? 'linear-gradient(90deg, #22c55e, #22c55e)'
                  : 'var(--border)',
                transition: 'all 200ms ease-in-out',
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function LiveThinking({ phase }: { phase: ExecutionPhase }) {
  const [messageIndex, setMessageIndex] = useState(0)
  
  const messages = phase.thinking || THINKING_MESSAGES[phase.id] || ['Processing...']
  
  useEffect(() => {
    if (phase.status !== 'active') return
    
    const interval = setInterval(() => {
      setMessageIndex(prev => (prev + 1) % messages.length)
    }, 3000)
    
    return () => clearInterval(interval)
  }, [phase.status, messages.length])
  
  if (phase.status !== 'active') return null
  
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '8px 12px',
      background: 'rgba(99, 102, 241, 0.08)',
      borderRadius: 8,
      fontSize: 13,
      color: '#6366f1',
    }}>
      <div 
        className="pulse"
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: '#6366f1',
        }}
      />
      <span style={{ fontWeight: 500 }}>
        {messages[messageIndex]}
      </span>
    </div>
  )
}

function PhaseDetails({ phase }: { phase: ExecutionPhase }) {
  if (!phase.files || phase.files.length === 0) {
    return (
      <div style={{
        padding: 16,
        color: 'var(--text-muted)',
        fontSize: 13,
        textAlign: 'center',
      }}>
        {phase.status === 'active' ? (
          <LiveThinking phase={phase} />
        ) : phase.status === 'pending' ? (
          'Waiting to start...'
        ) : (
          'No details available'
        )}
      </div>
    )
  }
  
  return (
    <div style={{ padding: 12 }}>
      {/* Current File (if active) */}
      {phase.status === 'active' && phase.currentFile && (
        <div style={{
          marginBottom: 16,
          padding: 12,
          background: 'rgba(99, 102, 241, 0.05)',
          borderRadius: 8,
          border: '1px solid rgba(99, 102, 241, 0.2)',
        }}>
          <div style={{
            fontSize: 11,
            textTransform: 'uppercase',
            color: '#6366f1',
            fontWeight: 600,
            marginBottom: 4,
          }}>
            Currently Working
          </div>
          <div style={{
            fontSize: 14,
            fontFamily: 'monospace',
            color: 'var(--text)',
          }}>
            {phase.currentFile}
          </div>
          <LiveThinking phase={phase} />
        </div>
      )}
      
      {/* Files List */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}>
        {phase.files.map((file, i) => (
          <div 
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 10px',
              borderRadius: 6,
              background: 'var(--bg-hover)',
              fontSize: 13,
              fontFamily: 'monospace',
            }}
          >
            <span style={{
              color: file.status === 'created' ? '#22c55e' 
                : file.status === 'deleted' ? '#ef4444' 
                : '#6366f1',
              fontWeight: 600,
              fontSize: 11,
              textTransform: 'uppercase',
            }}>
              {file.status === 'created' ? '+' : file.status === 'deleted' ? '−' : '•'}
            </span>
            <span style={{ 
              flex: 1,
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {file.path}
            </span>
            {(file.additions || file.deletions) && (
              <span style={{
                fontSize: 11,
                color: 'var(--text-muted)',
              }}>
                <span style={{ color: '#22c55e' }}>+{file.additions || 0}</span>
                {' '}
                <span style={{ color: '#ef4444' }}>-{file.deletions || 0}</span>
              </span>
            )}
          </div>
        ))}
      </div>
      
      {/* Phase Stats */}
      {phase.stats && (
        <div style={{
          marginTop: 12,
          paddingTop: 12,
          borderTop: '1px solid var(--border)',
          display: 'flex',
          gap: 16,
          fontSize: 12,
          color: 'var(--text-muted)',
        }}>
          {phase.stats.filesChanged !== undefined && (
            <span>{phase.stats.filesChanged} files</span>
          )}
          {phase.stats.duration !== undefined && (
            <span>{formatDuration(phase.stats.duration)}</span>
          )}
        </div>
      )}
    </div>
  )
}

function TaskCard({ task, expandedPhase, onPhaseClick }: { 
  task: EngineeringTask
  expandedPhase: Phase | null
  onPhaseClick: (phase: Phase) => void
}) {
  const isCompleted = task.status === 'completed'
  const isError = task.status === 'error'
  
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid ${isError ? '#ef4444' : isCompleted ? '#22c55e' : 'var(--border)'}`,
      borderRadius: 12,
      overflow: 'hidden',
      transition: 'all 200ms ease-in-out',
      boxShadow: isError 
        ? '0 0 0 1px rgba(239, 68, 68, 0.2)'
        : isCompleted 
          ? '0 0 0 1px rgba(34, 197, 94, 0.2)'
          : 'none',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border)',
      }}>
        {/* Title & Status */}
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}>
          <h3 style={{
            margin: 0,
            fontSize: 16,
            fontWeight: 600,
            color: 'var(--text)',
            lineHeight: 1.4,
          }}>
            {task.title}
          </h3>
          <span style={{
            padding: '4px 10px',
            borderRadius: 20,
            fontSize: 11,
            fontWeight: 600,
            textTransform: 'uppercase',
            background: isError 
              ? 'rgba(239, 68, 68, 0.1)'
              : isCompleted 
                ? 'rgba(34, 197, 94, 0.1)'
                : 'rgba(99, 102, 241, 0.1)',
            color: isError ? '#ef4444' : isCompleted ? '#22c55e' : '#6366f1',
          }}>
            {isError ? 'Error' : isCompleted ? 'Completed' : 'Working'}
          </span>
        </div>
        
        {/* Repository & Branch */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          fontSize: 13,
          color: 'var(--text-muted)',
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="repo" size={14} />
            {task.repository.name}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon name="git-branch" size={14} />
            <code style={{ 
              fontFamily: 'monospace',
              background: 'var(--bg-hover)',
              padding: '2px 6px',
              borderRadius: 4,
              fontSize: 12,
            }}>
              {task.branch.replace('devbuddy/', '')}
            </code>
          </span>
          <span>
            Started {formatTimeAgo(task.startedAt)}
          </span>
        </div>
      </div>
      
      {/* Stepper */}
      <div style={{ padding: '0 20px' }}>
        <PhaseStepper 
          phases={task.phases}
          currentPhase={task.currentPhase}
          expandedPhase={expandedPhase}
          onPhaseClick={onPhaseClick}
        />
      </div>
      
      {/* Phase Details (Expandable) */}
      {expandedPhase && (
        <div 
          className="expand-animation"
          style={{
            borderTop: '1px solid var(--border)',
            background: 'rgba(0, 0, 0, 0.02)',
          }}
        >
          <PhaseDetails 
            phase={task.phases.find(p => p.id === expandedPhase)!}
          />
        </div>
      )}
      
      {/* Summary Footer (if completed) */}
      {isCompleted && task.summary && (
        <div style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--border)',
          background: 'rgba(34, 197, 94, 0.03)',
        }}>
          <div style={{
            display: 'flex',
            gap: 24,
            fontSize: 13,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon name="file" size={14} color="#22c55e" />
              <span style={{ fontWeight: 600 }}>{task.summary.filesChanged}</span>
              <span style={{ color: 'var(--text-muted)' }}>files</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon name="check" size={14} color="#22c55e" />
              <span style={{ fontWeight: 600 }}>{task.summary.testsPassed}</span>
              <span style={{ color: 'var(--text-muted)' }}>tests</span>
            </div>
            {task.summary.prNumber && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Icon name="git-pull" size={14} color="#6366f1" />
                <span style={{ fontWeight: 600 }}>#{task.summary.prNumber}</span>
              </div>
            )}
          </div>
          
          {/* Action Buttons */}
          <div style={{
            display: 'flex',
            gap: 12,
            marginTop: 16,
          }}>
            {task.summary.prUrl && (
              <a 
                href={task.summary.prUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="db-btn"
                style={{
                  padding: '8px 16px',
                  background: '#6366f1',
                  color: '#fff',
                  textDecoration: 'none',
                  fontSize: 13,
                  fontWeight: 500,
                }}
              >
                Review PR →
              </a>
            )}
            <button 
              className="db-btn"
              style={{
                padding: '8px 16px',
                fontSize: 13,
              }}
            >
              Continue Working →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

interface EngineeringTimelineProps {
  tasks: EngineeringTask[]
}

export default function EngineeringTimeline({ tasks }: EngineeringTimelineProps) {
  const [expandedPhase, setExpandedPhase] = useState<Phase | null>(null)
  
  const handlePhaseClick = (phase: Phase) => {
    setExpandedPhase(expandedPhase === phase ? null : phase)
  }
  
  if (tasks.length === 0) {
    return (
      <div style={{
        padding: 40,
        textAlign: 'center',
        color: 'var(--text-muted)',
      }}>
        <Icon name="clock" size={48} style={{ marginBottom: 16, opacity: 0.5 }} />
        <p>No active engineering tasks</p>
        <p style={{ fontSize: 13, marginTop: 8 }}>
          Start a conversation to begin engineering work
        </p>
      </div>
    )
  }
  
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      padding: 16,
    }}>
      {tasks.map(task => (
        <TaskCard 
          key={task.id}
          task={task}
          expandedPhase={expandedPhase}
          onPhaseClick={handlePhaseClick}
        />
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// EXPORT TYPES FOR USE IN OTHER COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

export type { EngineeringTask, ExecutionPhase, FileChange }

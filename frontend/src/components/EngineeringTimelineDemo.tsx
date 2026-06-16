/**
 * Engineering Timeline Demo
 * 
 * Shows the new execution experience with sample data.
 * This demonstrates the professional senior engineer supervision UI.
 */

import { useState } from 'react'
import EngineeringTimeline, { EngineeringTask, Phase } from './EngineeringTimeline'

// Sample tasks demonstrating the new experience
const SAMPLE_TASKS: EngineeringTask[] = [
  {
    id: '1',
    title: 'Implement JWT Authentication',
    repository: {
      name: 'payment-service',
      owner: 'acme-corp',
      fullName: 'acme-corp/payment-service',
    },
    branch: 'devbuddy/feature/jwt-auth',
    baseBranch: 'main',
    status: 'working',
    startedAt: new Date(Date.now() - 120000).toISOString(), // 2 min ago
    currentPhase: 'implementing',
    phases: [
      {
        id: 'understanding',
        label: 'Understanding',
        status: 'completed',
        startedAt: new Date(Date.now() - 120000).toISOString(),
        completedAt: new Date(Date.now() - 90000).toISOString(),
        stats: { duration: 30 },
      },
      {
        id: 'planning',
        label: 'Planning',
        status: 'completed',
        startedAt: new Date(Date.now() - 90000).toISOString(),
        completedAt: new Date(Date.now() - 60000).toISOString(),
        stats: { duration: 30 },
      },
      {
        id: 'implementing',
        label: 'Implementation',
        status: 'active',
        startedAt: new Date(Date.now() - 60000).toISOString(),
        currentFile: 'src/auth/JwtFilter.java',
        thinking: [
          'Updating SecurityConfig.java...',
          'Implementing JwtTokenProvider...',
          'Adding authentication filter...',
          'Creating user details service...',
        ],
        files: [
          { path: 'src/config/SecurityConfig.java', status: 'modified', additions: 45, deletions: 12 },
          { path: 'src/auth/JwtTokenProvider.java', status: 'created', additions: 128 },
          { path: 'src/auth/JwtAuthenticationFilter.java', status: 'created', additions: 67 },
        ],
        stats: { 
          duration: 60,
          filesChanged: 3,
        },
      },
      {
        id: 'validating',
        label: 'Validation',
        status: 'pending',
        files: [],
      },
      {
        id: 'delivering',
        label: 'Delivery',
        status: 'pending',
        files: [],
      },
      {
        id: 'completed',
        label: 'Completed',
        status: 'pending',
        files: [],
      },
    ],
  },
  {
    id: '2',
    title: 'Add Image Copy Support',
    repository: {
      name: 'mobile-app',
      owner: 'acme-corp',
      fullName: 'acme-corp/mobile-app',
    },
    branch: 'devbuddy/feature/image-copy',
    baseBranch: 'main',
    status: 'completed',
    startedAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    completedAt: new Date(Date.now() - 1800000).toISOString(), // 30 min ago
    currentPhase: 'completed',
    phases: [
      {
        id: 'understanding',
        label: 'Understanding',
        status: 'completed',
        stats: { duration: 45 },
      },
      {
        id: 'planning',
        label: 'Planning',
        status: 'completed',
        stats: { duration: 60 },
      },
      {
        id: 'implementing',
        label: 'Implementation',
        status: 'completed',
        files: [
          { path: 'src/components/ImageViewer.tsx', status: 'modified', additions: 34, deletions: 8 },
          { path: 'src/utils/clipboard.ts', status: 'created', additions: 56 },
          { path: 'src/hooks/useImageCopy.ts', status: 'created', additions: 89 },
        ],
        stats: { duration: 180, filesChanged: 3 },
      },
      {
        id: 'validating',
        label: 'Validation',
        status: 'completed',
        stats: { duration: 120, filesChanged: 0 },
      },
      {
        id: 'delivering',
        label: 'Delivery',
        status: 'completed',
        stats: { duration: 30 },
      },
      {
        id: 'completed',
        label: 'Completed',
        status: 'completed',
      },
    ],
    summary: {
      filesChanged: 3,
      testsPassed: 42,
      testsTotal: 42,
      prNumber: 24,
      prUrl: 'https://github.com/acme-corp/mobile-app/pull/24',
      commitHash: 'a1b2c3d',
    },
  },
]

export default function EngineeringTimelineDemo() {
  const [showDemo, setShowDemo] = useState(true)
  
  if (!showDemo) {
    return (
      <div style={{ padding: 20 }}>
        <button 
          onClick={() => setShowDemo(true)}
          className="db-btn"
          style={{
            padding: '12px 20px',
            background: 'var(--accent)',
            color: 'white',
          }}
        >
          Show Engineering Timeline Demo
        </button>
      </div>
    )
  }
  
  return (
    <div style={{ 
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
            Engineering Timeline
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>
            New professional execution experience
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <span style={{
            padding: '6px 12px',
            background: 'rgba(34, 197, 94, 0.1)',
            borderRadius: 20,
            fontSize: 12,
            color: '#22c55e',
          }}>
            ✅ Rule 1: Hidden implementation details
          </span>
          <span style={{
            padding: '6px 12px',
            background: 'rgba(99, 102, 241, 0.1)',
            borderRadius: 20,
            fontSize: 12,
            color: '#6366f1',
          }}>
            ✅ Rule 4: Semantic branches
          </span>
        </div>
      </div>
      
      {/* Timeline */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <EngineeringTimeline tasks={SAMPLE_TASKS} />
      </div>
      
      {/* Design Notes */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
      }}>
        <h4 style={{ margin: '0 0 12px', fontSize: 13, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
          Design Principles Implemented
        </h4>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
          fontSize: 12,
        }}>
          <div style={{ 
            padding: 12, 
            background: 'var(--bg-card)', 
            borderRadius: 8,
          }}>
            <strong style={{ color: 'var(--text)' }}>Rule 1:</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>
              Hidden implementation details by default. No "Creating branch", "Runner ready" logs.
            </p>
          </div>
          <div style={{ 
            padding: 12, 
            background: 'var(--bg-card)', 
            borderRadius: 8,
          }}>
            <strong style={{ color: 'var(--text)' }}>Rule 2:</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>
              One parent card per execution with 6 high-level phases.
            </p>
          </div>
          <div style={{ 
            padding: 12, 
            background: 'var(--bg-card)', 
            borderRadius: 8,
          }}>
            <strong style={{ color: 'var(--text)' }}>Rule 3:</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>
              Expandable timeline. Click any phase to see file details.
            </p>
          </div>
          <div style={{ 
            padding: 12, 
            background: 'var(--bg-card)', 
            borderRadius: 8,
          }}>
            <strong style={{ color: 'var(--text)' }}>Rule 4:</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>
              Semantic branch names: devbuddy/feature/jwt-auth (no random hashes).
            </p>
          </div>
          <div style={{ 
            padding: 12, 
            background: 'var(--bg-card)', 
            borderRadius: 8,
          }}>
            <strong style={{ color: 'var(--text)' }}>Rule 5:</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>
              Live thinking: "Analyzing project structure..." instead of "Loading..."
            </p>
          </div>
          <div style={{ 
            padding: 12, 
            background: 'var(--bg-card)', 
            borderRadius: 8,
          }}>
            <strong style={{ color: 'var(--text)' }}>Rule 6-10:</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--text-muted)' }}>
              Elegant stepper, 70% less density, sticky activity, artifacts, completion experience.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

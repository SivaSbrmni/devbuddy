/**
 * ConversationMemory - Show and edit conversation memory
 * 
 * Displays:
 * - Conversation summary
 * - Current goal
 * - Completed tasks
 * - Open tasks
 * - Important decisions
 */

import { useState } from 'react'
import { useMemoryContext } from '../hooks/useMemoryContext'
import Icon from './Icon'

interface ConversationMemoryProps {
  conversationId: string | null
}

export default function ConversationMemory({ conversationId }: ConversationMemoryProps) {
  const { memory, loading, error, setGoal, recordDecision, addOpenTask } = useMemoryContext(conversationId)
  const [editingGoal, setEditingGoal] = useState(false)
  const [newGoal, setNewGoal] = useState('')
  const [newDecision, setNewDecision] = useState('')
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskDesc, setNewTaskDesc] = useState('')
  const [showAddDecision, setShowAddDecision] = useState(false)
  const [showAddTask, setShowAddTask] = useState(false)

  if (!conversationId) {
    return (
      <div style={{ padding: 20, color: 'var(--text-muted)', textAlign: 'center' }}>
        Select a conversation to view memory
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: 20, textAlign: 'center' }}>
        <Icon name="refresh" size={20} className="spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: 20, color: '#ef4444' }}>
        Error: {error}
      </div>
    )
  }

  if (!memory) {
    return null
  }

  const handleSaveGoal = async () => {
    await setGoal(newGoal)
    setEditingGoal(false)
  }

  const handleAddDecision = async () => {
    if (!newDecision.trim()) return
    await recordDecision(newDecision)
    setNewDecision('')
    setShowAddDecision(false)
  }

  const handleAddTask = async () => {
    if (!newTaskTitle.trim()) return
    await addOpenTask(newTaskTitle, newTaskDesc)
    setNewTaskTitle('')
    setNewTaskDesc('')
    setShowAddTask(false)
  }

  return (
    <div style={{ padding: 16, fontSize: 13 }}>
      {/* Summary */}
      {memory.conversation_memory.summary && (
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ margin: '0 0 8px', fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Summary
          </h4>
          <p style={{ margin: 0, lineHeight: 1.5, color: 'var(--text)' }}>
            {memory.conversation_memory.summary}
          </p>
        </div>
      )}

      {/* Current Goal */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h4 style={{ margin: 0, fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Current Goal
          </h4>
          <button
            onClick={() => {
              setNewGoal(memory.conversation_memory.current_goal)
              setEditingGoal(true)
            }}
            className="db-btn"
            style={{ padding: '2px 8px', fontSize: 11 }}
          >
            <Icon name="edit" size={12} />
          </button>
        </div>
        
        {editingGoal ? (
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={newGoal}
              onChange={e => setNewGoal(e.target.value)}
              style={{
                flex: 1,
                padding: '6px 10px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: 'var(--bg-input)',
                color: 'var(--text)',
                fontSize: 13,
              }}
            />
            <button onClick={handleSaveGoal} className="db-btn" style={{ padding: '6px 12px' }}>
              Save
            </button>
          </div>
        ) : memory.conversation_memory.current_goal ? (
          <p style={{ margin: 0, lineHeight: 1.5, color: 'var(--text)' }}>
            {memory.conversation_memory.current_goal}
          </p>
        ) : (
          <p style={{ margin: 0, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            No goal set. Click edit to add one.
          </p>
        )}
      </div>

      {/* Completed Tasks */}
      {memory.conversation_memory.completed_tasks?.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ margin: '0 0 8px', fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Completed ({memory.conversation_memory.completed_tasks.length})
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {memory.conversation_memory.completed_tasks.slice(-5).map((task, i) => (
              <div
                key={i}
                style={{
                  padding: '8px 12px',
                  background: 'rgba(34,197,94,0.1)',
                  borderRadius: 6,
                  borderLeft: '3px solid #22c55e',
                }}
              >
                <div style={{ fontWeight: 500 }}>{task.title}</div>
                {task.summary && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    {task.summary.slice(0, 100)}{task.summary.length > 100 ? '...' : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Open Tasks */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h4 style={{ margin: 0, fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Open Tasks ({memory.conversation_memory.open_tasks?.length || 0})
          </h4>
          <button
            onClick={() => setShowAddTask(true)}
            className="db-btn"
            style={{ padding: '2px 8px', fontSize: 11 }}
          >
            <Icon name="plus" size={12} />
          </button>
        </div>

        {showAddTask && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--bg-hover)', borderRadius: 6 }}>
            <input
              type="text"
              value={newTaskTitle}
              onChange={e => setNewTaskTitle(e.target.value)}
              placeholder="Task title"
              style={{
                width: '100%',
                padding: '6px 10px',
                marginBottom: 8,
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: 'var(--bg-input)',
                color: 'var(--text)',
                fontSize: 13,
              }}
            />
            <textarea
              value={newTaskDesc}
              onChange={e => setNewTaskDesc(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
              style={{
                width: '100%',
                padding: '6px 10px',
                marginBottom: 8,
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: 'var(--bg-input)',
                color: 'var(--text)',
                fontSize: 13,
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowAddTask(false)} className="db-btn" style={{ padding: '4px 12px' }}>
                Cancel
              </button>
              <button onClick={handleAddTask} className="db-btn" style={{ padding: '4px 12px', background: 'var(--accent)', color: 'white' }}>
                Add
              </button>
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {memory.conversation_memory.open_tasks?.map((task, i) => (
            <div
              key={i}
              style={{
                padding: '8px 12px',
                background: 'var(--bg-hover)',
                borderRadius: 6,
                borderLeft: '3px solid var(--accent)',
              }}
            >
              <div style={{ fontWeight: 500 }}>{task.title}</div>
              {task.description && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {task.description}
                </div>
              )}
            </div>
          ))}
          {(!memory.conversation_memory.open_tasks || memory.conversation_memory.open_tasks.length === 0) && !showAddTask && (
            <p style={{ margin: 0, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              No open tasks. Add one to track work.
            </p>
          )}
        </div>
      </div>

      {/* Important Decisions */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h4 style={{ margin: 0, fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Key Decisions ({memory.conversation_memory.important_decisions?.length || 0})
          </h4>
          <button
            onClick={() => setShowAddDecision(true)}
            className="db-btn"
            style={{ padding: '2px 8px', fontSize: 11 }}
          >
            <Icon name="plus" size={12} />
          </button>
        </div>

        {showAddDecision && (
          <div style={{ marginBottom: 12, padding: 12, background: 'var(--bg-hover)', borderRadius: 6 }}>
            <textarea
              value={newDecision}
              onChange={e => setNewDecision(e.target.value)}
              placeholder="Record an important architectural decision..."
              rows={3}
              style={{
                width: '100%',
                padding: '6px 10px',
                marginBottom: 8,
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: 'var(--bg-input)',
                color: 'var(--text)',
                fontSize: 13,
                resize: 'vertical',
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowAddDecision(false)} className="db-btn" style={{ padding: '4px 12px' }}>
                Cancel
              </button>
              <button onClick={handleAddDecision} className="db-btn" style={{ padding: '4px 12px', background: 'var(--accent)', color: 'white' }}>
                Record
              </button>
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {memory.conversation_memory.important_decisions?.map((decision, i) => (
            <div
              key={i}
              style={{
                padding: '8px 12px',
                background: 'rgba(99,102,241,0.1)',
                borderRadius: 6,
                borderLeft: '3px solid var(--accent)',
              }}
            >
              <div>{decision.content}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                {new Date(decision.timestamp).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Modified Files */}
      {memory.conversation_memory.modified_files?.length > 0 && (
        <div>
          <h4 style={{ margin: '0 0 8px', fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Modified Files ({memory.conversation_memory.modified_files.length})
          </h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {memory.conversation_memory.modified_files.slice(-10).map((file, i) => (
              <code
                key={i}
                style={{
                  padding: '2px 8px',
                  background: 'var(--bg-hover)',
                  borderRadius: 4,
                  fontSize: 11,
                  fontFamily: 'monospace',
                }}
              >
                {file.split('/').pop()}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

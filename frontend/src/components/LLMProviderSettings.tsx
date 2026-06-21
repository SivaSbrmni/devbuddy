// @ts-nocheck
/**
 * LLM Provider Settings - Universal endpoint configuration UI
 * 
 * Users can add custom LLM endpoints (Ollama, OpenRouter, etc.)
 * without code changes.
 */

import { useState, useEffect } from 'react'
import { useLLMProviders } from '../hooks/useLLMProviders'
import {
  CreateProviderRequest,
  PROVIDER_PRESETS,
  LLMProvider,
} from '../api/llmProviders'
import Icon from './Icon'

interface LLMProviderSettingsProps {
  isOpen: boolean
  onClose: () => void
}

type Tab = 'providers' | 'add' | 'edit'

export default function LLMProviderSettings({ isOpen, onClose }: LLMProviderSettingsProps) {
  const {
    providers,
    defaultProvider,
    loading,
    testing,
    error,
    testResult,
    refresh,
    addProvider,
    editProvider,
    removeProvider,
    testNewConnection,
    testExistingProvider,
    setDefaultProvider,
  } = useLLMProviders()

  const [activeTab, setActiveTab] = useState<Tab>('providers')
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Form state for new provider
  const [formData, setFormData] = useState<CreateProviderRequest>({
    name: '',
    provider_type: 'openai-compatible',
    base_url: '',
    api_key: '',
    default_model: '',
    available_models: [],
    supports_streaming: true,
    supports_tools: true,
    supports_vision: false,
    context_size: 8192,
    max_tokens: 4096,
    cost_per_1k_input: 0,
    cost_per_1k_output: 0,
    priority: 100,
    is_default: false,
  })

  const applyPreset = (presetKey: string) => {
    const preset = PROVIDER_PRESETS[presetKey]
    if (preset) {
      setFormData(prev => ({
        ...prev,
        ...preset,
        name: presetKey.charAt(0).toUpperCase() + presetKey.slice(1),
        available_models: preset.default_model ? [preset.default_model] : [],
      }))
    }
  }

  const handleTest = async () => {
    if (!formData.base_url || !formData.default_model) return
    const result = await testNewConnection({
      base_url: formData.base_url,
      api_key: formData.api_key || '',
      provider_type: formData.provider_type,
      model: formData.default_model,
    })
    if (result.success && result.models_available && result.models_available.length > 0) {
      const models = result.models_available
      setFormData(prev => ({
        ...prev,
        available_models: models,
        default_model: prev.default_model || models[0],
      }))
    }
  }

  const handleSave = async () => {
    try {
      await addProvider(formData)
      setActiveTab('providers')
      setFormData({
        name: '',
        provider_type: 'openai-compatible',
        base_url: '',
        api_key: '',
        default_model: '',
        available_models: [],
        supports_streaming: true,
        supports_tools: true,
        supports_vision: false,
        context_size: 8192,
        max_tokens: 4096,
        cost_per_1k_input: 0,
        cost_per_1k_output: 0,
        priority: 100,
        is_default: false,
      })
    } catch {
      // Error handled by hook
    }
  }

  const handleUpdate = async () => {
    if (!editingProvider) return
    try {
      await editProvider(editingProvider.id, {
        name: formData.name,
        base_url: formData.base_url,
        api_key: formData.api_key,
        default_model: formData.default_model,
        supports_streaming: formData.supports_streaming,
        supports_tools: formData.supports_tools,
        supports_vision: formData.supports_vision,
        context_size: formData.context_size,
        max_tokens: formData.max_tokens,
        cost_per_1k_input: formData.cost_per_1k_input,
        cost_per_1k_output: formData.cost_per_1k_output,
        priority: formData.priority,
      })
      setActiveTab('providers')
      setEditingProvider(null)
    } catch {
      // Error handled by hook
    }
  }

  const startEdit = (provider: LLMProvider) => {
    setEditingProvider(provider)
    setFormData({
      name: provider.name,
      provider_type: provider.provider_type,
      base_url: provider.base_url,
      api_key: '', // Don't show masked key, user enters new one if changing
      default_model: provider.default_model,
      supports_streaming: provider.supports_streaming,
      supports_tools: provider.supports_tools,
      supports_vision: provider.supports_vision,
      context_size: provider.context_size,
      max_tokens: provider.max_tokens,
      cost_per_1k_input: provider.cost_per_1k_input,
      cost_per_1k_output: provider.cost_per_1k_output,
      priority: provider.priority,
      is_default: provider.is_default,
    })
    setActiveTab('edit')
  }

  const confirmDelete = (id: string) => {
    setDeletingId(id)
  }

  const handleDelete = async () => {
    if (!deletingId) return
    try {
      await removeProvider(deletingId)
      setDeletingId(null)
    } catch {
      // Error handled by hook
    }
  }

  if (!isOpen) return null

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.7)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        width: 600,
        maxWidth: '90vw',
        maxHeight: '90vh',
        overflow: 'auto',
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
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
            LLM Providers
          </h2>
          <button
            onClick={onClose}
            className="db-btn"
            style={{ width: 32, height: 32 }}
          >
            <Icon name="close" size={16} />
          </button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex',
          gap: 4,
          padding: '12px 20px 0',
          borderBottom: '1px solid var(--border)',
        }}>
          <button
            onClick={() => setActiveTab('providers')}
            style={{
              padding: '8px 16px',
              border: 'none',
              background: activeTab === 'providers' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'providers' ? 'white' : 'var(--text)',
              borderRadius: '6px 6px 0 0',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            My Providers
          </button>
          <button
            onClick={() => {
              setActiveTab('add')
              setEditingProvider(null)
              setFormData({
                name: '',
                provider_type: 'openai-compatible',
                base_url: '',
                api_key: '',
                default_model: '',
                supports_streaming: true,
                supports_tools: true,
                supports_vision: false,
                context_size: 8192,
                max_tokens: 4096,
                cost_per_1k_input: 0,
                cost_per_1k_output: 0,
                priority: 100,
                is_default: false,
              })
            }}
            style={{
              padding: '8px 16px',
              border: 'none',
              background: activeTab === 'add' || activeTab === 'edit' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'add' || activeTab === 'edit' ? 'white' : 'var(--text)',
              borderRadius: '6px 6px 0 0',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            {activeTab === 'edit' ? 'Edit Provider' : 'Add Provider'}
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: 20 }}>
          {loading && <div style={{ textAlign: 'center', padding: 40 }}>Loading...</div>}
          
          {error && (
            <div style={{
              padding: 12,
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 8,
              color: '#ef4444',
              marginBottom: 16,
              fontSize: 13,
            }}>
              {error}
            </div>
          )}

          {activeTab === 'providers' && (
            <div>
              {providers.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: 40,
                  color: 'var(--text-muted)',
                }}>
                  <Icon name="bot" size={48} style={{ marginBottom: 16, opacity: 0.5 }} />
                  <p>No LLM providers configured</p>
                  <button
                    onClick={() => setActiveTab('add')}
                    className="db-btn"
                    style={{ marginTop: 16 }}
                  >
                    Add your first provider
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {providers.map(provider => (
                    <div
                      key={provider.id}
                      style={{
                        padding: 16,
                        background: 'var(--bg-hover)',
                        borderRadius: 8,
                        border: provider.is_default ? '2px solid var(--accent)' : '1px solid var(--border)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontWeight: 600 }}>{provider.name}</span>
                            {provider.is_default && (
                              <span style={{
                                fontSize: 11,
                                padding: '2px 8px',
                                background: 'var(--accent)',
                                color: 'white',
                                borderRadius: 4,
                              }}>
                                Default
                              </span>
                            )}
                            <span style={{
                              fontSize: 11,
                              padding: '2px 8px',
                              background: provider.health_status === 'healthy' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)',
                              color: provider.health_status === 'healthy' ? '#22c55e' : '#ef4444',
                              borderRadius: 4,
                            }}>
                              {provider.health_status}
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                            {provider.base_url}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                            Model: {provider.default_model}
                            {provider.latency_ms && ` • ${provider.latency_ms}ms`}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            onClick={() => testExistingProvider(provider.id)}
                            disabled={testing}
                            className="db-btn"
                            style={{ width: 32, height: 32 }}
                            title="Test connection"
                          >
                            <Icon name="refresh" size={14} />
                          </button>
                          <button
                            onClick={() => startEdit(provider)}
                            className="db-btn"
                            style={{ width: 32, height: 32 }}
                            title="Edit"
                          >
                            <Icon name="edit" size={14} />
                          </button>
                          <button
                            onClick={() => confirmDelete(provider.id)}
                            className="db-btn"
                            style={{ width: 32, height: 32 }}
                            title="Delete"
                          >
                            <Icon name="trash" size={14} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {(activeTab === 'add' || activeTab === 'edit') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Presets */}
              {activeTab === 'add' && (
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, display: 'block' }}>
                    Quick Setup (optional)
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {Object.keys(PROVIDER_PRESETS).map(preset => (
                      <button
                        key={preset}
                        onClick={() => applyPreset(preset)}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid var(--border)',
                          background: 'var(--bg-hover)',
                          borderRadius: 6,
                          cursor: 'pointer',
                          fontSize: 12,
                          textTransform: 'capitalize',
                        }}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Name */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, display: 'block' }}>
                  Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  placeholder="My Ollama Server"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    background: 'var(--bg-input)',
                    color: 'var(--text)',
                    fontSize: 14,
                  }}
                />
              </div>

              {/* Base URL */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, display: 'block' }}>
                  Base URL *
                </label>
                <input
                  type="text"
                  value={formData.base_url}
                  onChange={e => setFormData({ ...formData, base_url: e.target.value })}
                  placeholder="http://localhost:11434 or https://api.openai.com/v1"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    background: 'var(--bg-input)',
                    color: 'var(--text)',
                    fontSize: 14,
                    fontFamily: 'monospace',
                  }}
                />
              </div>

              {/* API Key */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, display: 'block' }}>
                  API Key {editingProvider && '(leave blank to keep current)'}
                </label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={e => setFormData({ ...formData, api_key: e.target.value })}
                  placeholder="sk-... or leave blank for no auth"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    background: 'var(--bg-input)',
                    color: 'var(--text)',
                    fontSize: 14,
                    fontFamily: 'monospace',
                  }}
                />
              </div>

              {/* Default Model */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, display: 'block' }}>
                  Default Model *
                </label>
                {formData.available_models && formData.available_models.length > 0 ? (
                  <select
                    value={formData.default_model}
                    onChange={e => setFormData({ ...formData, default_model: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      background: 'var(--bg-input)',
                      color: 'var(--text)',
                      fontSize: 14,
                    }}
                  >
                    {formData.available_models.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={formData.default_model}
                    onChange={e => setFormData({ ...formData, default_model: e.target.value })}
                    placeholder="qwen3-coder:480b or gpt-4o"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      background: 'var(--bg-input)',
                      color: 'var(--text)',
                      fontSize: 14,
                    }}
                  />
                )}
                {formData.available_models && formData.available_models.length > 0 && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    {formData.available_models.length} model{formData.available_models.length !== 1 ? 's' : ''} detected. Test again to refresh.
                  </div>
                )}
              </div>

              {/* Test Result */}
              {testResult && (
                <div style={{
                  padding: 12,
                  background: testResult.success ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                  border: `1px solid ${testResult.success ? '#22c55e' : '#ef4444'}`,
                  borderRadius: 8,
                  fontSize: 13,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Icon name={testResult.success ? 'check' : 'error'} size={16} />
                    <span style={{ fontWeight: 600 }}>
                      {testResult.success ? 'Connected!' : 'Connection failed'}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      ({testResult.latency_ms}ms)
                    </span>
                  </div>
                  <div style={{ marginTop: 4 }}>{testResult.message}</div>
                  {testResult.models_available && testResult.models_available.length > 0 && (
                    <div style={{ marginTop: 8, fontSize: 11 }}>
                      Available models: {testResult.models_available.slice(0, 5).join(', ')}
                      {testResult.models_available.length > 5 && ` +${testResult.models_available.length - 5} more`}
                    </div>
                  )}
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 8 }}>
                <button
                  onClick={handleTest}
                  disabled={testing || !formData.base_url || !formData.default_model}
                  className="db-btn"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    opacity: testing || !formData.base_url || !formData.default_model ? 0.5 : 1,
                  }}
                >
                  <Icon name={testing ? 'loading' : 'refresh'} size={14} />
                  {testing ? 'Testing...' : 'Test Connection'}
                </button>
                <button
                  onClick={activeTab === 'edit' ? handleUpdate : handleSave}
                  disabled={!formData.name || !formData.base_url || !formData.default_model}
                  className="db-btn"
                  style={{
                    background: 'var(--accent)',
                    color: 'white',
                    opacity: !formData.name || !formData.base_url || !formData.default_model ? 0.5 : 1,
                  }}
                >
                  {activeTab === 'edit' ? 'Update Provider' : 'Save Provider'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1100,
        }}>
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            padding: 24,
            width: 400,
          }}>
            <h3 style={{ margin: '0 0 16px' }}>Delete Provider?</h3>
            <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
              This will permanently remove this LLM provider. This action cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setDeletingId(null)}
                className="db-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="db-btn"
                style={{ background: '#ef4444', color: 'white' }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

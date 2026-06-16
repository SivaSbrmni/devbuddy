/**
 * useLLMProviders - React hook for managing LLM providers
 */

import { useState, useEffect, useCallback } from 'react'
import {
  LLMProvider,
  CreateProviderRequest,
  UpdateProviderRequest,
  TestConnectionRequest,
  TestConnectionResponse,
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  testConnection,
  testSavedProvider,
  getAvailableModels,
} from '../api/llmProviders'

interface UseLLMProvidersReturn {
  providers: LLMProvider[]
  defaultProvider: LLMProvider | null
  availableModels: Array<{
    id: string
    provider_id: string
    provider_name: string
    model: string
    provider_type: string
    health_status: string
  }>
  loading: boolean
  testing: boolean
  error: string | null
  testResult: TestConnectionResponse | null
  refresh: () => Promise<void>
  addProvider: (req: CreateProviderRequest) => Promise<LLMProvider>
  editProvider: (id: string, req: UpdateProviderRequest) => Promise<LLMProvider>
  removeProvider: (id: string) => Promise<void>
  testNewConnection: (req: TestConnectionRequest) => Promise<TestConnectionResponse>
  testExistingProvider: (id: string) => Promise<TestConnectionResponse>
  setDefaultProvider: (id: string) => Promise<void>
}

export function useLLMProviders(): UseLLMProvidersReturn {
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [availableModels, setAvailableModels] = useState<UseLLMProvidersReturn['availableModels']>([])
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [providersData, modelsData] = await Promise.all([
        listProviders(),
        getAvailableModels(),
      ])
      setProviders(providersData)
      setAvailableModels(modelsData.models)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load providers')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const defaultProvider = providers.find(p => p.is_default) || providers[0] || null

  const addProvider = useCallback(async (req: CreateProviderRequest) => {
    setLoading(true)
    setError(null)
    try {
      const provider = await createProvider(req)
      setProviders(prev => [...prev, provider])
      return provider
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create provider')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const editProvider = useCallback(async (id: string, req: UpdateProviderRequest) => {
    setLoading(true)
    setError(null)
    try {
      const provider = await updateProvider(id, req)
      setProviders(prev => prev.map(p => p.id === id ? provider : p))
      return provider
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update provider')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const removeProvider = useCallback(async (id: string) => {
    setLoading(true)
    setError(null)
    try {
      await deleteProvider(id)
      setProviders(prev => prev.filter(p => p.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete provider')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  const testNewConnection = useCallback(async (req: TestConnectionRequest) => {
    setTesting(true)
    setTestResult(null)
    setError(null)
    try {
      const result = await testConnection(req)
      setTestResult(result)
      return result
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to test connection')
      throw e
    } finally {
      setTesting(false)
    }
  }, [])

  const testExistingProvider = useCallback(async (id: string) => {
    setTesting(true)
    setTestResult(null)
    setError(null)
    try {
      const result = await testSavedProvider(id)
      setTestResult(result)
      // Refresh to get updated health status
      await refresh()
      return result
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to test provider')
      throw e
    } finally {
      setTesting(false)
    }
  }, [refresh])

  const setDefaultProvider = useCallback(async (id: string) => {
    setLoading(true)
    try {
      await updateProvider(id, { is_default: true })
      setProviders(prev => prev.map(p => ({
        ...p,
        is_default: p.id === id,
      })))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set default')
      throw e
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    providers,
    defaultProvider,
    availableModels,
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
  }
}

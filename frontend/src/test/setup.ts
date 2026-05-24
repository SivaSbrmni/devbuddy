import '@testing-library/jest-dom'

// Mock Vite env variables
declare global {
  interface Window {
    import?: { meta?: { env?: Record<string, string> } }
  }
}

// Setup default env
Object.defineProperty(window, 'import', {
  value: {
    meta: {
      env: {
        VITE_SUPABASE_URL: 'https://test.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'test-key',
        VITE_API_BASE_URL: 'http://localhost:8000',
      },
    },
  },
  writable: true,
})

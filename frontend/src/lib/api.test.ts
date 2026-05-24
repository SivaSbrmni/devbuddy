import { describe, it, expect } from 'vitest'
import { api } from './api'

describe('api utility', () => {
  it('has get, post, patch, delete methods', () => {
    expect(typeof api.get).toBe('function')
    expect(typeof api.post).toBe('function')
    expect(typeof api.patch).toBe('function')
    expect(typeof api.delete).toBe('function')
  })
})

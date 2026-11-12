// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'

import { applyTheme, readTheme, saveTheme } from './theme'

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

describe('theme', () => {
  it('defaults to system and ignores unknown stored values', () => {
    expect(readTheme()).toBe('system')
    localStorage.setItem('theme', 'purple')
    expect(readTheme()).toBe('system')
  })

  it('round-trips a saved theme', () => {
    saveTheme('dark')
    expect(readTheme()).toBe('dark')
  })

  it('sets data-theme only for an explicit choice', () => {
    applyTheme('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    applyTheme('system')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
})

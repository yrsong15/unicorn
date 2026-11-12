import { loadPref, savePref } from './format'

export type Theme = 'system' | 'light' | 'dark'
const THEMES: readonly Theme[] = ['system', 'light', 'dark']

export const readTheme = (): Theme => loadPref('theme', 'system', THEMES)
export const saveTheme = (theme: Theme) => savePref('theme', theme)

export function applyTheme(theme: Theme) {
  if (theme === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', theme)
}

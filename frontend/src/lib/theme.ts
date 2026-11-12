export type Theme = 'system' | 'light' | 'dark'

export function readTheme(): Theme {
  try {
    const saved = localStorage.getItem('theme')
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    return 'system'
  }
}

export function saveTheme(theme: Theme) {
  try {
    localStorage.setItem('theme', theme)
  } catch {
    /* storage unavailable */
  }
}

export function applyTheme(theme: Theme) {
  if (theme === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', theme)
}

import type { Sport } from '../api/types'

export const mi = (miles: number | null | undefined, digits = 1) =>
  miles === null || miles === undefined ? '–' : miles.toFixed(digits)

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '–'
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`
}

export const pace = (secondsPerMile: number | null | undefined) =>
  secondsPerMile ? `${duration(secondsPerMile)}/mi` : '–'

const parseDay = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`)

export const shortDate = (iso: string) => parseDay(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
export const fullDate = (iso: string) =>
  parseDay(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })

/** "Oct 12 – 18, 2026", or with both years when a week spans New Year. */
export function weekRange(startIso: string, endIso: string): string {
  const start = parseDay(startIso)
  const end = parseDay(endIso)
  if (start.getFullYear() !== end.getFullYear()) return `${fullDate(startIso)} – ${fullDate(endIso)}`
  return `${shortDate(startIso)} – ${shortDate(endIso)}, ${end.getFullYear()}`
}

export const longDate = (iso: string) =>
  parseDay(iso).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
export const monthYear = (iso: string) => parseDay(iso).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })

export function relativeTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso.endsWith('Z') ? iso : `${iso}Z`).getTime()
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

export const titleCase = (s: string | null | undefined) =>
  s ? s.replace(/_\d+$/, '').toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : '–'

export const CATEGORY_LABELS = { road: 'Road', treadmill: 'Treadmill', track: 'Track', trail: 'Trail' } as const
export const RIDE_CATEGORY_LABELS = { road: 'Road ride', indoor: 'Indoor ride', mountain: 'Mountain bike', gravel: 'Gravel ride' } as const

export function activityLabel(a: { sport: Sport; category: string }): string {
  if (a.sport === 'sauna') return 'Sauna'
  const labels: Record<string, string> = a.sport === 'ride' ? RIDE_CATEGORY_LABELS : CATEGORY_LABELS
  return labels[a.category] ?? titleCase(a.category)
}

export const mph = (speed: number | null | undefined) => (speed ? `${speed.toFixed(1)} mph` : '–')

/** Pace for runs, speed for rides, nothing for sauna sessions. */
export const paceOrSpeed = (a: { sport: Sport; pace_s_per_mile: number | null; speed_mph: number | null }) =>
  a.sport === 'sauna' ? '–' : a.sport === 'ride' ? mph(a.speed_mph) : pace(a.pace_s_per_mile)

/** Whole minutes, e.g. "45 min" or "1 h 05 min". */
export function minutes(total: number | null | undefined): string {
  if (total === null || total === undefined) return '–'
  const m = Math.round(total)
  const h = Math.floor(m / 60)
  return h > 0 ? `${h} h ${String(m % 60).padStart(2, '0')} min` : `${m} min`
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

/** Read and write a small per-browser preference; storage can be unavailable (private mode). */
export function loadPref<T extends string>(key: string, fallback: T, allowed: readonly T[]): T {
  try {
    const v = localStorage.getItem(key)
    return v !== null && (allowed as readonly string[]).includes(v) ? (v as T) : fallback
  } catch {
    return fallback
  }
}

export function savePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Not persisted; the choice still applies for this visit.
  }
}

import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { useLogout, useSync, useSyncStatus } from '../api/hooks'
import { relativeTime } from '../lib/format'
import { Button } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/runs', label: 'Runs' },
  { to: '/shoes', label: 'Shoes' },
  { to: '/fitness', label: 'Fitness' },
  { to: '/training', label: 'Training' },
  { to: '/records', label: 'Records' },
  { to: '/settings', label: 'Settings' },
]

export function SyncControl() {
  const status = useSyncStatus()
  const sync = useSync()
  const triedOnOpen = useRef(false)

  // Pull new runs whenever the app is opened (the server skips it if synced < 10 min ago).
  useEffect(() => {
    if (triedOnOpen.current || !status.data) return
    triedOnOpen.current = true
    if (status.data.garmin.status === 'ok' && status.data.stale) sync.mutate(true)
  }, [status.data, sync])

  const garmin = status.data?.garmin.status
  const lastSync = status.data?.status
  const when = relativeTime(status.data?.last_sync_at ?? null)
  const label = sync.isPending
    ? 'Syncing…'
    : garmin === 'needs_reconnect'
      ? 'Reconnect Garmin'
      : garmin === 'disconnected'
        ? 'Garmin not connected'
        : lastSync === 'error'
          ? `Sync failed ${when}`
          : lastSync === 'partial'
            ? `Synced ${when}, incomplete`
            : `Synced ${when}`
  const warn = (garmin && garmin !== 'ok') || lastSync === 'error' || lastSync === 'partial'

  return (
    <div className="flex items-center gap-2 text-xs text-nav-ink/80">
      <span className={warn ? 'font-medium text-[#f6c37a]' : ''} title={status.data?.message ?? ''}>
        {label}
      </span>
      <button
        type="button"
        onClick={() => sync.mutate(false)}
        disabled={sync.isPending || garmin !== 'ok'}
        className="rounded-md border border-white/25 px-2 py-1 font-medium text-nav-ink hover:bg-white/10 disabled:opacity-40"
      >
        Sync now
      </button>
    </div>
  )
}

export default function Layout() {
  const logout = useLogout()
  const [open, setOpen] = useState(false)
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm font-medium transition ${isActive ? 'bg-white/15 text-nav-ink' : 'text-nav-ink/75 hover:text-nav-ink hover:bg-white/10'}`

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 bg-nav text-nav-ink shadow-sm">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <img src="/favicon.svg" alt="" className="h-7 w-7 rounded-md ring-1 ring-white/30" />
            <span>Unicorn</span>
          </NavLink>
          <nav className="ml-4 hidden items-center gap-0.5 lg:flex">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={linkClass}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto hidden sm:block">
            <SyncControl />
          </div>
          <button
            type="button"
            className="ml-auto rounded-md p-2 hover:bg-white/10 sm:ml-0 lg:hidden"
            aria-label="Menu"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d={open ? 'M5 5l10 10M15 5L5 15' : 'M3 6h14M3 10h14M3 14h14'} />
            </svg>
          </button>
        </div>
        {open && (
          <nav className="flex flex-col gap-0.5 border-t border-white/10 px-4 py-2 lg:hidden" onClick={() => setOpen(false)}>
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={linkClass}>
                {n.label}
              </NavLink>
            ))}
            <div className="py-2 sm:hidden">
              <SyncControl />
            </div>
          </nav>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-ink-3">
        <Button variant="ghost" className="px-0" onClick={() => logout.mutate()}>
          Log out
        </Button>
      </footer>
    </div>
  )
}

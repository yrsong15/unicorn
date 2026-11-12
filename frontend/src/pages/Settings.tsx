import { useEffect, useState } from 'react'

import { useSync, useSyncStatus } from '../api/hooks'
import { Badge, Button, Card, ErrorNote, PageHeader, Segmented } from '../components/ui'
import { relativeTime } from '../lib/format'
import { applyTheme, readTheme, saveTheme, type Theme } from '../lib/theme'

export default function Settings() {
  const status = useSyncStatus()
  const sync = useSync()
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    applyTheme(theme)
    saveTheme(theme)
  }, [theme])

  const g = status.data?.garmin
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Garmin connection">
          <div className="mb-3 flex items-center gap-2">
            {g?.status === 'ok' && <Badge tone="good">● Connected</Badge>}
            {g?.status === 'needs_reconnect' && <Badge tone="warn">⚠ Needs reconnect</Badge>}
            {g?.status === 'disconnected' && <Badge>Not connected</Badge>}
            <span className="text-sm text-ink-3">Last sync {relativeTime(status.data?.last_sync_at ?? null)}</span>
          </div>
          {status.data?.message && <p className="mb-3 text-sm text-ink-2">{status.data.message}</p>}
          {g?.last_error && g.status !== 'ok' && <p className="mb-3 text-sm text-over">{g.last_error}</p>}
          <p className="text-sm text-ink-2">
            To connect or reconnect, run this on your Mac from the <code className="rounded bg-surface-2 px-1">backend</code> folder. Your
            Garmin password and MFA code stay on your Mac; only encrypted tokens are stored.
          </p>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-surface-2 p-3 text-xs text-ink">uv run python -m app.cli login</pre>
          <div className="mt-3">
            <Button variant="primary" disabled={g?.status !== 'ok' || sync.isPending} onClick={() => sync.mutate(false)}>
              {sync.isPending ? 'Syncing…' : 'Sync now'}
            </Button>
          </div>
          {sync.error && <div className="mt-2"><ErrorNote error={sync.error} /></div>}
        </Card>
        <Card title="Appearance">
          <Segmented
            label="Theme"
            value={theme}
            onChange={setTheme}
            options={[{ key: 'system', label: 'System' }, { key: 'light', label: 'Light' }, { key: 'dark', label: 'Dark' }]}
          />
          <p className="mt-4 text-sm text-ink-2">
            Default shoes are set per shoe on the Shoes page. The app password is the <code className="rounded bg-surface-2 px-1">APP_PASSWORD_HASH</code> environment variable; generate a new one with{' '}
            <code className="rounded bg-surface-2 px-1">uv run python -m app.cli hash-password</code>.
          </p>
        </Card>
      </div>
    </>
  )
}

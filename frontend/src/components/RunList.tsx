import { Link } from 'react-router-dom'

import type { RunSummary } from '../api/types'
import { activityLabel, duration, longDate, mi, minutes, paceOrSpeed } from '../lib/format'
import { Badge, Empty } from './ui'

export function ShoeChips({ run }: { run: RunSummary }) {
  return (
    <div className="flex flex-wrap gap-1">
      {run.shoes.map((s, i) => (
        <Badge key={i}>
          {s.shoe_name} · {mi(s.miles)}
        </Badge>
      ))}
      {run.unassigned_miles > 0.05 && <Badge tone="warn">{mi(run.unassigned_miles)} mi unassigned</Badge>}
    </div>
  )
}

export function RunList({ runs, empty = 'No runs here.' }: { runs: RunSummary[]; empty?: string }) {
  if (!runs.length) return <Empty>{empty}</Empty>
  return (
    <ul className="divide-y divide-border">
      {runs.map((r) => (
        <li key={r.id}>
          <Link to={`/runs/${r.id}`} className="-mx-2 flex flex-col gap-1.5 rounded-lg px-2 py-3 hover:bg-surface-2 sm:flex-row sm:items-center sm:gap-4">
            <div className="min-w-0 sm:w-56">
              <div className="truncate font-medium text-ink">{r.name}</div>
              <div className="text-xs text-ink-3">
                {longDate(r.local_date)} · {activityLabel(r)}
              </div>
            </div>
            {r.sport === 'sauna' ? (
              <div className="tabular flex gap-4 text-sm text-ink-2 sm:w-64">
                <span className="w-16 font-semibold text-ink">{minutes(r.duration_s / 60)}</span>
                <span>{r.avg_hr ? `${Math.round(r.avg_hr)} bpm` : ''}</span>
              </div>
            ) : (
              <div className="tabular flex gap-4 text-sm text-ink-2 sm:w-64">
                <span className="w-16 font-semibold text-ink">{mi(r.miles, 2)} mi</span>
                <span className="w-16">{duration(r.duration_s)}</span>
                <span>{paceOrSpeed(r)}</span>
              </div>
            )}
            <div className="min-w-0 flex-1">
              {r.sport === 'ride' ? <Badge>Ride</Badge> : r.sport === 'sauna' ? <Badge>Sauna</Badge> : <ShoeChips run={r} />}
            </div>
          </Link>
        </li>
      ))}
    </ul>
  )
}

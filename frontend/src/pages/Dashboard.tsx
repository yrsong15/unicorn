import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useDashboard, useRuns, useWeekly } from '../api/hooks'
import type { RangeKey, Week } from '../api/types'
import { SaunaIcon, SaunaWeeklyChart, WeeklyMileageChart } from '../components/charts'
import { RunList } from '../components/RunList'
import { Badge, Card, ErrorNote, Loading, PageHeader, RangePicker, Stat, Switch } from '../components/ui'
import { loadPref, mi, minutes, plural, savePref, shortDate, titleCase, weekRange } from '../lib/format'

const BIKES_PREF = 'unicorn.includeBikes'

function WeekMiles({ week, includeBikes }: { week: Week | undefined; includeBikes: boolean }) {
  return (
    <>
      {mi(week?.run_miles)} mi
      {includeBikes && !!week?.ride_equiv_miles && (
        <span className="block text-sm font-medium text-ink-2 sm:inline sm:text-base">
          <span className="hidden sm:inline"> · </span>
          {mi(week.total_miles)} incl. bike
        </span>
      )}
    </>
  )
}

const countLabel = (w: Week, includeBikes: boolean) =>
  `${w.runs} run${w.runs === 1 ? '' : 's'}${includeBikes && w.rides ? ` · ${w.rides} ride${w.rides === 1 ? '' : 's'}` : ''}`

/** Weekly sauna chart, collapsed until opened. */
function SaunaCard() {
  const [open, setOpen] = useState(false)
  const [range, setRange] = useState<RangeKey>('3m')
  return (
    <section className="mt-4 rounded-xl border border-border bg-surface p-4 sm:p-5">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          aria-controls="sauna-card-body"
          onClick={() => setOpen((o) => !o)}
          className="-m-1 flex items-center gap-2 rounded-lg p-1 text-left hover:bg-surface-2"
        >
          <span aria-hidden className={`inline-block text-ink-3 transition-transform ${open ? 'rotate-90' : ''}`}>
            ▸
          </span>
          <h2 className="flex items-center gap-1.5 text-base font-semibold text-ink">
            <SaunaIcon /> Weekly sauna
          </h2>
        </button>
        {open && <RangePicker value={range} onChange={setRange} />}
      </header>
      {open && (
        <div id="sauna-card-body" className="mt-3">
          <SaunaCardBody range={range} />
        </div>
      )}
    </section>
  )
}

function SaunaCardBody({ range }: { range: RangeKey }) {
  const [selected, setSelected] = useState<Week | null>(null)
  const weekly = useWeekly(range)
  const sessions = useRuns({ ids: selected?.sauna_ids ?? [], sport: 'sauna', limit: 50 }, !!selected?.sauna_ids.length)
  const weeks = weekly.data?.weeks ?? []
  const [last, current] = weeks.slice(-2)
  const diff = current && last ? current.sauna_minutes - last.sauna_minutes : 0
  const avgSessions = weeks.length ? weeks.reduce((s, w) => s + w.saunas, 0) / weeks.length : 0
  const avgMinutes = weeks.length ? weeks.reduce((s, w) => s + w.sauna_minutes, 0) / weeks.length : 0

  if (weekly.error) return <ErrorNote error={weekly.error} />
  if (weekly.isLoading) return <Loading />
  return (
    <>
      {current && (
        <p className="mb-3 text-sm text-ink-2">
          <span className="font-medium text-ink">This week:</span> {plural(current.saunas, 'session')} ·{' '}
          {minutes(current.sauna_minutes)}
          {last && ` (${diff >= 0 ? '+' : '−'}${minutes(Math.abs(diff))} vs last week)`}
        </p>
      )}
      <SaunaWeeklyChart
        weeks={weeks}
        selected={selected?.week_start}
        onSelect={(w) => setSelected((cur) => (cur?.week_start === w.week_start ? null : w))}
      />
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2 text-xs text-ink-3">
        <span>
          Average {avgSessions.toFixed(1)} sessions and {minutes(avgMinutes)} a week over {weeks.length} weeks. Click a bar
          to see that week's sessions.
        </span>
        <Link to="/runs?sport=sauna" className="text-sm text-link">All sauna sessions →</Link>
      </div>
      {selected && (
        <div className="mt-4 border-t border-border pt-3">
          <div className="mb-1 flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-ink">
              {weekRange(selected.week_start, selected.week_end)} · {plural(selected.saunas, 'session')} ·{' '}
              {minutes(selected.sauna_minutes)}
            </h3>
            <button type="button" className="text-sm text-link" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          {selected.sauna_ids.length ? (
            <RunList runs={sessions.data?.items ?? []} />
          ) : (
            <p className="text-sm text-ink-3">No sauna sessions that week.</p>
          )}
        </div>
      )}
    </>
  )
}

export default function Dashboard() {
  const [range, setRange] = useState<RangeKey>('3m')
  const [selected, setSelected] = useState<Week | null>(null)
  const [includeBikes, setIncludeBikes] = useState(() => loadPref(BIKES_PREF, 'on', ['on', 'off'] as const) === 'on')
  const weekly = useWeekly(range)
  const dash = useDashboard()
  const selectedIds = selected
    ? [...selected.run_ids, ...(includeBikes ? selected.ride_ids : []), ...selected.sauna_ids]
    : []
  const weekRuns = useRuns({ ids: selectedIds, sport: 'all', limit: 50 }, selectedIds.length > 0)
  const recent = useRuns({ limit: 5, sport: includeBikes ? 'all' : 'run' })

  const toggleBikes = (on: boolean) => {
    setIncludeBikes(on)
    savePref(BIKES_PREF, on ? 'on' : 'off')
  }
  const miles = (w: Week) => (includeBikes ? w.total_miles : w.run_miles)
  const d = dash.data
  const diff = d ? miles(d.this_week) - miles(d.last_week) : 0
  const weeks = weekly.data?.weeks ?? []
  const avg = weeks.length ? weeks.reduce((s, w) => s + miles(w), 0) / weeks.length : 0
  const perMile = weekly.data?.load_per_run_mile

  return (
    <>
      <PageHeader title="Dashboard" sub="Weeks run Monday through Sunday." />
      {dash.error && <ErrorNote error={dash.error} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="This week"
          value={<WeekMiles week={d?.this_week} includeBikes={includeBikes} />}
          sub={d ? `${countLabel(d.this_week, includeBikes)} · ${diff >= 0 ? '+' : ''}${mi(diff)} vs last week` : '…'}
        />
        <Stat
          label="Last week"
          value={<WeekMiles week={d?.last_week} includeBikes={includeBikes} />}
          sub={d ? countLabel(d.last_week, includeBikes) : '…'}
        />
        <Stat
          label="Training readiness"
          value={d?.today?.readiness_score ?? '–'}
          sub={d?.today?.readiness_level ? titleCase(d.today.readiness_level) : 'From Garmin'}
          tone={(d?.today?.readiness_score ?? 100) < 40 ? 'warn' : undefined}
        />
        <Stat
          label="HRV (last night)"
          value={d?.today?.hrv_last_night ? `${d.today.hrv_last_night} ms` : '–'}
          sub={d?.today?.hrv_status ? titleCase(d.today.hrv_status) : 'From Garmin'}
          tone={d?.today?.hrv_status && d.today.hrv_status !== 'BALANCED' ? 'warn' : undefined}
        />
      </div>

      {!!d?.shoe_alerts.length && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-warn-soft px-4 py-3 text-sm">
          <span aria-hidden>⚠</span>
          <span className="font-medium text-ink">Shoes nearing retirement:</span>
          {d.shoe_alerts.map((s) => (
            <Link key={s.id} to="/shoes">
              <Badge tone={s.wear === 'over' ? 'over' : 'warn'}>
                {s.name} · {Math.round(s.miles)}/{Math.round(s.retire_at_miles)} mi
              </Badge>
            </Link>
          ))}
        </div>
      )}

      <Card
        className="mt-4"
        title="Weekly mileage"
        action={<RangePicker value={range} onChange={(r) => { setRange(r); setSelected(null) }} />}
      >
        {weekly.isLoading ? (
          <Loading />
        ) : (
          <>
            <div className="mb-3">
              <Switch checked={includeBikes} onChange={toggleBikes} label="Include bikes as run-equivalent" />
            </div>
            <WeeklyMileageChart
              weeks={weeks}
              includeBikes={includeBikes}
              selected={selected?.week_start}
              onSelect={(w) => setSelected((cur) => (cur?.week_start === w.week_start ? null : w))}
            />
            <p className="mt-2 text-xs text-ink-3">
              Average {mi(avg)} mi/week{includeBikes ? ' incl. bike' : ''} over {weeks.length} weeks. Click a bar to see
              that week's activities. Under each bar, one sauna icon per session and that week's sauna minutes.
              {includeBikes &&
                (perMile
                  ? ` Rides count as run miles by training load: ${Math.round(perMile)} load = 1 mile, your average per run mile over the last year.`
                  : ' Rides count once your runs have Garmin training load to convert with.')}
            </p>
          </>
        )}
      </Card>

      <SaunaCard />

      <Card
        className="mt-4"
        title={
          selected
            ? `Week of ${shortDate(selected.week_start)} · ${mi(miles(selected))} mi${includeBikes && selected.ride_equiv_miles ? ' incl. bike' : ''}${
                selected.saunas ? ` · ${plural(selected.saunas, 'sauna')} (${minutes(selected.sauna_minutes)})` : ''
              }`
            : includeBikes ? 'Recent activity' : 'Recent runs'
        }
        action={
          selected ? (
            <button type="button" className="text-sm text-link" onClick={() => setSelected(null)}>
              Show recent
            </button>
          ) : (
            <Link to={includeBikes ? '/runs?sport=all' : '/runs'} className="text-sm text-link">
              {includeBikes ? 'All activities →' : 'All runs →'}
            </Link>
          )
        }
      >
        {selected ? (
          selectedIds.length ? (
            <RunList runs={weekRuns.data?.items ?? []} />
          ) : (
            <p className="text-sm text-ink-3">No activities that week.</p>
          )
        ) : (
          <RunList runs={recent.data?.items ?? []} />
        )}
      </Card>
    </>
  )
}

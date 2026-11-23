import { Link, useParams } from 'react-router-dom'

import { useRun } from '../api/hooks'
import { ShoeSplitEditor } from '../components/ShoeSplitEditor'
import { Card, ErrorNote, Loading, PageHeader, Stat } from '../components/ui'
import type { RunDetail as RunDetailData } from '../api/types'
import { activityLabel, duration, longDate, mi, minutes, mph, pace } from '../lib/format'

const ZONE_COLORS = ['#9fb9d9', '#5e8fc7', '#00539b', '#e89923', '#c84e00']

export default function RunDetail() {
  const { id } = useParams()
  const run = useRun(Number(id))
  if (run.isLoading) return <Loading />
  if (run.error || !run.data) return <ErrorNote error={run.error} />
  const r = run.data
  if (r.sport === 'sauna') return <SaunaDetail r={r} />
  const ride = r.sport === 'ride'
  const zoneTotal = (r.hr_zones_s ?? []).reduce((a, b) => a + b, 0)
  const fastestLap = Math.min(...r.laps.filter((l) => l.miles > 0.2).map((l) => l.pace_s_per_mile ?? Infinity))

  return (
    <>
      <Link to={ride ? '/runs?sport=ride' : '/runs'} className="text-sm text-link">{ride ? '← Rides' : '← Runs'}</Link>
      <DetailHeader r={r} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Distance" value={`${mi(r.miles, 2)} mi`} />
        <Stat label="Time" value={duration(r.duration_s)} />
        {ride ? <Stat label="Speed" value={mph(r.speed_mph)} /> : <Stat label="Pace" value={pace(r.pace_s_per_mile)} />}
        <Stat label="Avg HR" value={r.avg_hr ? Math.round(r.avg_hr) : '–'} sub={r.max_hr ? `max ${Math.round(r.max_hr)}` : undefined} />
        <Stat label="Cadence" value={r.avg_cadence ? Math.round(r.avg_cadence) : '–'} sub={ride ? 'rpm' : 'steps/min'} />
        <Stat
          label="Training effect"
          value={r.aerobic_te ?? '–'}
          sub={r.anaerobic_te !== null ? `anaerobic ${r.anaerobic_te}` : undefined}
        />
      </div>

      {!ride && (
        <Card className="mt-4" title="Shoes">
          <ShoeSplitEditor run={r} />
        </Card>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Laps" className="lg:col-span-2">
          {r.laps.length ? (
            <div className="-mx-2 overflow-x-auto">
              <table className="tabular w-full min-w-[28rem] text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-ink-3">
                  <tr>
                    <th className="px-2 py-1.5 font-medium">Lap</th>
                    <th className="px-2 py-1.5 text-right font-medium">Miles</th>
                    <th className="px-2 py-1.5 text-right font-medium">Time</th>
                    <th className="px-2 py-1.5 text-right font-medium">{ride ? 'Speed' : 'Pace'}</th>
                    <th className="px-2 py-1.5 text-right font-medium">HR</th>
                    <th className="px-2 py-1.5 text-right font-medium">Cadence</th>
                    <th className="px-2 py-1.5 text-right font-medium">Elev ft</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {r.laps.map((l) => (
                    <tr key={l.idx} className={l.pace_s_per_mile === fastestLap ? 'bg-primary-soft' : ''}>
                      <td className="px-2 py-1.5 text-ink-2">{l.idx}</td>
                      <td className="px-2 py-1.5 text-right">{mi(l.miles, 2)}</td>
                      <td className="px-2 py-1.5 text-right">{duration(l.duration_s)}</td>
                      <td className="px-2 py-1.5 text-right font-medium">{ride ? mph(l.speed_mph) : pace(l.pace_s_per_mile)}</td>
                      <td className="px-2 py-1.5 text-right">{l.avg_hr ? Math.round(l.avg_hr) : '–'}</td>
                      <td className="px-2 py-1.5 text-right">{l.avg_cadence ? Math.round(l.avg_cadence) : '–'}</td>
                      <td className="px-2 py-1.5 text-right">{l.elev_gain_ft !== null ? Math.round(l.elev_gain_ft) : '–'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-ink-3">No lap data for this {ride ? 'ride' : 'run'}.</p>
          )}
        </Card>

        <Card title="Time in heart-rate zones">
          {zoneTotal > 0 ? (
            <ul className="space-y-2">
              {r.hr_zones_s!.map((s, i) => (
                <li key={i} className="text-sm">
                  <div className="mb-1 flex justify-between text-ink-2">
                    <span>Zone {i + 1}</span>
                    <span className="tabular">
                      {duration(s)} · {Math.round((s / zoneTotal) * 100)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-2">
                    <div className="h-2 rounded-full" style={{ width: `${(s / zoneTotal) * 100}%`, background: ZONE_COLORS[i] }} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-3">No heart-rate zone data.</p>
          )}
          <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-3 text-sm">
            <dt className="text-ink-3">Elevation gain</dt>
            <dd className="tabular text-right">{r.elev_gain_ft !== null ? `${Math.round(r.elev_gain_ft)} ft` : '–'}</dd>
            <dt className="text-ink-3">Moving time</dt>
            <dd className="tabular text-right">{duration(r.moving_s)}</dd>
            <dt className="text-ink-3">Training load</dt>
            <dd className="tabular text-right">{r.training_load ? Math.round(r.training_load) : '–'}</dd>
            <dt className="text-ink-3">VO2 max</dt>
            <dd className="tabular text-right">{r.vo2max ?? '–'}</dd>
          </dl>
        </Card>
      </div>
    </>
  )
}

function DetailHeader({ r }: { r: RunDetailData }) {
  return (
    <PageHeader
      title={r.name}
      sub={`${longDate(r.local_date)} · ${new Date(r.start_local).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })} · ${activityLabel(r)}`}
      action={
        <a className="text-sm text-link" href={`https://connect.garmin.com/modern/activity/${r.garmin_activity_id}`} target="_blank" rel="noreferrer">
          Open in Garmin Connect ↗
        </a>
      }
    />
  )
}

/** Sauna sessions have no distance, pace, shoes or laps: just time and heart rate. */
function SaunaDetail({ r }: { r: RunDetailData }) {
  return (
    <>
      <Link to="/runs?sport=sauna" className="text-sm text-link">← Sauna sessions</Link>
      <DetailHeader r={r} />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Time" value={minutes(r.duration_s / 60)} />
        <Stat label="Avg HR" value={r.avg_hr ? Math.round(r.avg_hr) : '–'} />
        <Stat label="Max HR" value={r.max_hr ? Math.round(r.max_hr) : '–'} />
      </div>
    </>
  )
}

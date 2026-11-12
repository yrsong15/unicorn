import { Link } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { useRecords } from '../api/hooks'
import { ChartTooltip, Legend } from '../components/charts'
import { Card, Empty, ErrorNote, Loading, PageHeader, Stat } from '../components/ui'
import { duration, longDate, mi, shortDate } from '../lib/format'

const MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function Records() {
  const q = useRecords()
  if (q.isLoading) return <Loading />
  if (q.error || !q.data) return <ErrorNote error={q.error} />
  const r = q.data
  if (!r.totals) return <Empty>No runs yet.</Empty>

  // The server decides which year is "this year" (its local date), so take it from the data.
  const thisYear = Math.max(0, ...(r.ytd?.cumulative ?? []).map((p) => p.year))
  const byDay = new Map<number, { day_of_year: number; [k: string]: number }>()
  for (const p of r.ytd?.cumulative ?? []) {
    const row = byDay.get(p.day_of_year) ?? { day_of_year: p.day_of_year }
    row[p.year === thisYear ? 'this' : 'last'] = p.miles
    byDay.set(p.day_of_year, row)
  }
  const ytdData = [...byDay.values()].sort((a, b) => a.day_of_year - b.day_of_year)
  const ahead = r.ytd ? r.ytd.this_year - r.ytd.last_year_to_date : 0

  return (
    <>
      <PageHeader title="Records" sub={`${r.totals.runs} runs and ${Math.round(r.totals.miles).toLocaleString()} miles since ${longDate(r.totals.since)}.`} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Current streak" value={`${r.current_streak_weeks} wk`} sub="Consecutive weeks with a run" />
        <Stat label="Longest streak" value={`${r.longest_streak_weeks} wk`} />
        <Stat
          label="Biggest week"
          value={r.biggest_week ? `${mi(r.biggest_week.miles)} mi` : '–'}
          sub={r.biggest_week ? `Week of ${shortDate(r.biggest_week.week_start)}` : undefined}
        />
        <Stat
          label="Longest run"
          value={r.longest_run ? `${mi(r.longest_run.miles)} mi` : '–'}
          sub={r.longest_run ? <Link className="text-link" to={`/runs/${r.longest_run.run_id}`}>{longDate(r.longest_run.date)}</Link> : undefined}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Personal records (from Garmin)">
          {r.garmin_prs.length ? (
            <ul className="divide-y divide-border text-sm">
              {r.garmin_prs.map((pr) => (
                <li key={pr.type_id} className="flex items-center justify-between py-2">
                  <span className="text-ink-2">{pr.label}</span>
                  <span className="text-right">
                    <span className="tabular block font-semibold text-ink">
                      {pr.type_id === 7 ? `${mi(pr.value / 1609.344)} mi` : duration(pr.value)}
                    </span>
                    {pr.date && <span className="text-xs text-ink-3">{longDate(pr.date)}</span>}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-3">Garmin PRs show up after your first sync.</p>
          )}
        </Card>

        {r.ytd && (
          <Card
            title="Year to date vs. last year"
            className="lg:col-span-2"
            action={
              <span className={`tabular text-sm font-medium ${ahead >= 0 ? 'text-good' : 'text-warn'}`}>
                {ahead >= 0 ? '▲' : '▼'} {mi(Math.abs(ahead))} mi {ahead >= 0 ? 'ahead' : 'behind'}
              </span>
            }
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <Legend items={[{ label: String(thisYear), color: 'var(--series-1)' }, { label: String(thisYear - 1), color: 'var(--series-2)', dashed: true }]} />
              <span className="tabular text-xs text-ink-3">
                {mi(r.ytd.this_year)} mi this year · {mi(r.ytd.last_year_to_date)} by this date last year · {mi(r.ytd.last_year_total)} total last year
              </span>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={ytdData} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis
                    dataKey="day_of_year"
                    type="number"
                    domain={[1, 366]}
                    ticks={MONTH_TICKS}
                    tickFormatter={(d: number) => MONTHS[MONTH_TICKS.indexOf(d)] ?? ''}
                    tick={{ fill: 'var(--ink-3)', fontSize: 12 }}
                    tickLine={false}
                    axisLine={{ stroke: 'var(--grid)' }}
                  />
                  <YAxis tick={{ fill: 'var(--ink-3)', fontSize: 12 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ stroke: 'var(--ink-3)', strokeDasharray: '3 3' }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const p = payload[0].payload as { day_of_year: number; this?: number; last?: number }
                      const date = new Date(thisYear, 0, p.day_of_year)
                      return (
                        <ChartTooltip
                          title={`${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} (${thisYear} vs ${thisYear - 1})`}
                          rows={[
                            ...(p.this !== undefined ? [{ label: String(thisYear), value: `${mi(p.this)} mi`, color: 'var(--series-1)' }] : []),
                            ...(p.last !== undefined ? [{ label: String(thisYear - 1), value: `${mi(p.last)} mi`, color: 'var(--series-2)' }] : []),
                          ]}
                        />
                      )
                    }}
                  />
                  <Line dataKey="last" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="5 3" dot={false} connectNulls isAnimationActive={false} />
                  <Line dataKey="this" stroke="var(--series-1)" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}
      </div>
    </>
  )
}

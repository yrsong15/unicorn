import type { ReactNode } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, LineChart, Rectangle, ReferenceArea, ResponsiveContainer, Tooltip,
  XAxis, YAxis,
} from 'recharts'

import type { SaunaWeek, Week } from '../api/types'
import { fullDate, mi, minutes, monthYear, shortDate, weekRange } from '../lib/format'

const axisTick = { fill: 'var(--ink-3)', fontSize: 12 }

export function ChartTooltip({ title, rows }: { title: ReactNode; rows: { label: string; value: ReactNode; color?: string }[] }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm shadow-lg">
      <div className="mb-1 font-medium text-ink">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 text-ink-2">
          <span className="flex items-center gap-1.5">
            {r.color && <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: r.color }} />}
            {r.label}
          </span>
          <span className="tabular font-medium text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <span
            className="inline-block h-0.5 w-4"
            style={{ background: i.dashed ? `repeating-linear-gradient(90deg, ${i.color} 0 4px, transparent 4px 7px)` : i.color, height: i.dashed ? 2 : 8, borderRadius: i.dashed ? 0 : 2 }}
          />
          {i.label}
        </span>
      ))}
    </div>
  )
}

function tickFormatter(weeks: { week_start: string }[]) {
  const long = weeks.length > 60
  return (iso: string) => (long ? monthYear(iso) : shortDate(iso))
}

export const RUN_COLOR = 'var(--series-1)'
export const BIKE_COLOR = 'var(--series-3)'

export function WeeklyMileageChart({ weeks, includeBikes = false, selected, onSelect }: {
  weeks: Week[]
  includeBikes?: boolean
  selected?: string | null
  onSelect?: (week: Week) => void
}) {
  const dense = weeks.length > 40
  const select = (d: unknown) => onSelect?.((d as { payload: Week }).payload)
  const dim = (w: Week) => (selected && selected !== w.week_start ? 0.4 : 1)
  return (
    <div>
      <div className="mb-2">
        <Legend
          items={[
            { label: includeBikes ? 'Run miles' : 'Weekly miles', color: RUN_COLOR },
            ...(includeBikes ? [{ label: 'Bike (run-equivalent)', color: BIKE_COLOR }] : []),
            { label: includeBikes ? '4-week average (incl. bike)' : '4-week average', color: 'var(--series-2)', dashed: true },
          ]}
        />
      </div>
      <div className="h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={weeks} margin={{ top: 8, right: 4, bottom: 0, left: -18 }} barCategoryGap={dense ? 1 : '18%'}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis
              dataKey="week_start"
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: 'var(--grid)' }}
              tickFormatter={tickFormatter(weeks)}
              minTickGap={24}
            />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: 'var(--surface-2)', opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const w = payload[0].payload as Week
                const rows = includeBikes
                  ? [
                      { label: 'Run miles', value: mi(w.run_miles), color: RUN_COLOR },
                      { label: 'Bike equiv.', value: mi(w.ride_equiv_miles), color: BIKE_COLOR },
                      { label: 'Total', value: mi(w.total_miles) },
                      { label: '4-wk avg', value: mi(w.rolling_avg_total), color: 'var(--series-2)' },
                      { label: 'Runs · rides', value: `${w.runs} · ${w.rides}` },
                    ]
                  : [
                      { label: 'Miles', value: mi(w.run_miles), color: RUN_COLOR },
                      { label: '4-wk avg', value: mi(w.rolling_avg), color: 'var(--series-2)' },
                      { label: 'Runs', value: w.runs },
                    ]
                return (
                  <ChartTooltip
                    title={weekRange(w.week_start, w.week_end)}
                    rows={[...rows, { label: 'Longest', value: `${mi(w.longest_miles)} mi` }]}
                  />
                )
              }}
            />
            <Bar
              dataKey="run_miles"
              stackId="miles"
              fill={RUN_COLOR}
              stroke="var(--surface)"
              strokeWidth={dense ? 0 : 1}
              cursor={onSelect ? 'pointer' : undefined}
              onClick={select}
              // Only the top segment of a stack gets rounded corners.
              shape={(props: unknown) => {
                const p = props as { payload: Week } & Record<string, unknown>
                const top = !includeBikes || p.payload.ride_equiv_miles <= 0
                return <Rectangle {...p} radius={top ? [4, 4, 0, 0] : 0} />
              }}
            >
              {weeks.map((w) => (
                <Cell key={w.week_start} fillOpacity={dim(w)} />
              ))}
            </Bar>
            {includeBikes && (
              <Bar
                dataKey="ride_equiv_miles"
                stackId="miles"
                fill={BIKE_COLOR}
                radius={[4, 4, 0, 0]}
                stroke="var(--surface)"
                strokeWidth={dense ? 0 : 1}
                cursor={onSelect ? 'pointer' : undefined}
                onClick={select}
              >
                {weeks.map((w) => (
                  <Cell key={w.week_start} fillOpacity={dim(w)} />
                ))}
              </Bar>
            )}
            <Line
              dataKey={includeBikes ? 'rolling_avg_total' : 'rolling_avg'}
              stroke="var(--series-2)"
              strokeWidth={2}
              strokeDasharray="5 3"
              dot={false}
              activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export const SAUNA_COLOR = 'var(--series-2)'

/** Sauna minutes per week; the tooltip adds the session count. */
export function SaunaWeeklyChart({ weeks, selected, onSelect }: {
  weeks: SaunaWeek[]
  selected?: string | null
  onSelect?: (week: SaunaWeek) => void
}) {
  const dense = weeks.length > 40
  const dim = (w: SaunaWeek) => (selected && selected !== w.week_start ? 0.4 : 1)
  return (
    <div className="h-48 sm:h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={weeks} margin={{ top: 8, right: 4, bottom: 0, left: -18 }} barCategoryGap={dense ? 1 : '18%'}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="week_start"
            tick={axisTick}
            tickLine={false}
            axisLine={{ stroke: 'var(--grid)' }}
            tickFormatter={tickFormatter(weeks)}
            minTickGap={24}
          />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} allowDecimals={false} unit="m" />
          <Tooltip
            cursor={{ fill: 'var(--surface-2)', opacity: 0.6 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const w = payload[0].payload as SaunaWeek
              return (
                <ChartTooltip
                  title={weekRange(w.week_start, w.week_end)}
                  rows={[
                    { label: 'Sessions', value: w.sessions },
                    { label: 'Total time', value: minutes(w.minutes), color: SAUNA_COLOR },
                  ]}
                />
              )
            }}
          />
          <Bar
            dataKey="minutes"
            fill={SAUNA_COLOR}
            radius={[4, 4, 0, 0]}
            cursor={onSelect ? 'pointer' : undefined}
            onClick={(d: unknown) => onSelect?.((d as { payload: SaunaWeek }).payload)}
          >
            {weeks.map((w) => (
              <Cell key={w.week_start} fillOpacity={dim(w)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export interface DailyLoad { day: string; run: number; ride: number; total: number }

/** Daily Garmin training load, either one total bar or stacked run / ride. */
export function DailyLoadChart({ data, split }: { data: DailyLoad[]; split: boolean }) {
  const long = data.length > 120
  return (
    <div>
      {split && (
        <div className="mb-2">
          <Legend items={[{ label: 'Run', color: RUN_COLOR }, { label: 'Ride', color: BIKE_COLOR }]} />
        </div>
      )}
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={data.length > 60 ? 0 : '15%'}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis
              dataKey="day"
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: 'var(--grid)' }}
              tickFormatter={(d: string) => (long ? monthYear(d) : shortDate(d))}
              minTickGap={32}
            />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} allowDecimals={false} width={44} />
            <Tooltip
              cursor={{ fill: 'var(--surface-2)', opacity: 0.6 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const d = payload[0].payload as DailyLoad
                return (
                  <ChartTooltip
                    title={fullDate(d.day)}
                    rows={[
                      ...(split
                        ? [
                            { label: 'Run', value: Math.round(d.run), color: RUN_COLOR },
                            { label: 'Ride', value: Math.round(d.ride), color: BIKE_COLOR },
                          ]
                        : []),
                      { label: 'Total load', value: Math.round(d.total), color: split ? undefined : RUN_COLOR },
                    ]}
                  />
                )
              }}
            />
            {split ? (
              <>
                <Bar
                  dataKey="run"
                  stackId="load"
                  fill={RUN_COLOR}
                  shape={(props: unknown) => {
                    const p = props as { payload: DailyLoad } & Record<string, unknown>
                    return <Rectangle {...p} radius={p.payload.ride > 0 ? 0 : [3, 3, 0, 0]} />
                  }}
                />
                <Bar dataKey="ride" stackId="load" fill={BIKE_COLOR} radius={[3, 3, 0, 0]} />
              </>
            ) : (
              <Bar dataKey="total" fill={RUN_COLOR} radius={[3, 3, 0, 0]} />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export interface TrendSeries {
  key: string
  label: string
  color: string
  format?: (v: number) => string
  dashed?: boolean
}

export function TrendChart({ data, series, yFormat, height = 220, reversed = false, band, yDomain }: {
  data: Record<string, unknown>[]
  series: TrendSeries[]
  yFormat?: (v: number) => string
  height?: number
  reversed?: boolean
  band?: { y1: number; y2: number; label: string }
  yDomain?: [number | 'auto' | 'dataMin' | 'dataMax', number | 'auto' | 'dataMin' | 'dataMax']
}) {
  const long = data.length > 120
  return (
    <div>
      {series.length > 1 && (
        <div className="mb-2">
          <Legend items={series.map((s) => ({ label: s.label, color: s.color, dashed: s.dashed }))} />
        </div>
      )}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            {band && <ReferenceArea y1={band.y1} y2={band.y2} fill="var(--safe-band)" stroke="none" ifOverflow="extendDomain" />}
            <XAxis
              dataKey="day"
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: 'var(--grid)' }}
              tickFormatter={(d: string) => (long ? monthYear(d) : shortDate(d))}
              minTickGap={32}
            />
            <YAxis
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              reversed={reversed}
              domain={yDomain ?? ['auto', 'auto']}
              tickFormatter={yFormat ?? ((v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1)))}
              width={yFormat ? 52 : 44}
            />
            <Tooltip
              cursor={{ stroke: 'var(--ink-3)', strokeDasharray: '3 3' }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                return (
                  <ChartTooltip
                    title={fullDate(String(label))}
                    rows={series
                      .map((s) => {
                        const v = (payload[0].payload as Record<string, number | null>)[s.key]
                        return v === null || v === undefined
                          ? null
                          : { label: s.label, value: (s.format ?? yFormat ?? String)(v), color: s.color }
                      })
                      .filter((r): r is NonNullable<typeof r> => r !== null)}
                  />
                )
              }}
            />
            {series.map((s) => (
              <Line
                key={s.key}
                dataKey={s.key}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray={s.dashed ? '5 3' : undefined}
                dot={false}
                connectNulls
                activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

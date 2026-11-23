import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useRuns, useShoes } from '../api/hooks'
import type { Sport } from '../api/types'
import { RunList } from '../components/RunList'
import { Button, Card, ErrorNote, Field, inputClass, Loading, PageHeader, Segmented } from '../components/ui'

const PAGE = 25
type SportFilter = Sport | 'all'
const SPORT_OPTIONS: { key: SportFilter; label: string }[] = [
  { key: 'run', label: 'Runs' },
  { key: 'ride', label: 'Rides' },
  { key: 'sauna', label: 'Sauna' },
  { key: 'all', label: 'All' },
]
const NOUNS = {
  run: ['run', 'runs'],
  ride: ['ride', 'rides'],
  sauna: ['sauna session', 'sauna sessions'],
  all: ['activity', 'activities'],
} as const

export default function Runs() {
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState(0)
  const shoes = useShoes()
  const sport = (SPORT_OPTIONS.find((o) => o.key === params.get('sport'))?.key ?? 'run') as SportFilter
  const filters = {
    start: params.get('start') ?? undefined,
    end: params.get('end') ?? undefined,
    // Rides never have shoes, so the shoe filter only applies to runs.
    shoe_id: sport === 'run' && params.get('shoe') ? Number(params.get('shoe')) : undefined,
    sport,
  }
  const runs = useRuns({ ...filters, limit: PAGE, offset: page * PAGE })
  const total = runs.data?.total ?? 0

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value && !(key === 'sport' && value === 'run')) next.set(key, value)
    else next.delete(key)
    setParams(next)
    setPage(0)
  }

  return (
    <>
      <PageHeader
        title={{ run: 'Runs', ride: 'Rides', sauna: 'Sauna sessions', all: 'Activities' }[sport]}
        sub={runs.data ? `${total} ${NOUNS[sport][total === 1 ? 0 : 1]}` : undefined}
        action={<Segmented label="Sport" value={sport} onChange={(v) => set('sport', v)} options={SPORT_OPTIONS} />}
      />
      <Card>
        <div className={`mb-4 grid grid-cols-1 gap-3 ${sport === 'run' ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
          <Field label="From">
            <input type="date" className={inputClass} value={filters.start ?? ''} onChange={(e) => set('start', e.target.value)} />
          </Field>
          <Field label="To">
            <input type="date" className={inputClass} value={filters.end ?? ''} onChange={(e) => set('end', e.target.value)} />
          </Field>
          {sport === 'run' && (
          <Field label="Shoe">
            <select className={inputClass} value={params.get('shoe') ?? ''} onChange={(e) => set('shoe', e.target.value)}>
              <option value="">Any shoe</option>
              {shoes.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.retired_at ? ' (retired)' : ''}
                </option>
              ))}
            </select>
          </Field>
          )}
        </div>
        {runs.error && <ErrorNote error={runs.error} />}
        {runs.isLoading ? <Loading /> : <RunList runs={runs.data?.items ?? []} empty={`No ${NOUNS[sport][1]} here.`} />}
        {total > PAGE && (
          <div className="mt-4 flex items-center justify-between text-sm text-ink-2">
            <Button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              ← Newer
            </Button>
            <span className="tabular">
              {page * PAGE + 1}–{Math.min(total, (page + 1) * PAGE)} of {total}
            </span>
            <Button disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}>
              Older →
            </Button>
          </div>
        )}
      </Card>
    </>
  )
}

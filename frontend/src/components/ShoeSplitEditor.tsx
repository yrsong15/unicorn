import { useMemo, useState } from 'react'

import { useSetRunShoes, useShoes } from '../api/hooks'
import type { RunDetail } from '../api/types'
import { mi } from '../lib/format'
import { Button, ErrorNote, inputBase } from './ui'

interface Row {
  key: number
  shoe_id: number | ''
  miles: string
  lap_from: number | null
  lap_to: number | null
}

let nextKey = 1
const toRows = (run: RunDetail): Row[] =>
  run.shoes.map((s) => ({ key: nextKey++, shoe_id: s.shoe_id, miles: s.miles.toFixed(2), lap_from: s.lap_from, lap_to: s.lap_to }))

export function ShoeSplitEditor({ run }: { run: RunDetail }) {
  const shoes = useShoes()
  const save = useSetRunShoes(run.id)
  const [rows, setRows] = useState<Row[]>(() => toRows(run))
  const [dirty, setDirty] = useState(false)
  const [shownRun, setShownRun] = useState(run)

  // Follow a refetched run unless the user is mid-edit. Adjusting state during
  // render (rather than in an effect) avoids rendering stale rows first.
  if (!dirty && run !== shownRun) {
    setShownRun(run)
    setRows(toRows(run))
  }

  const lapMiles = (from: number, to: number) =>
    run.laps.filter((l) => l.idx >= from && l.idx <= to).reduce((s, l) => s + l.miles, 0)

  const assigned = rows.reduce((s, r) => s + (parseFloat(r.miles) || 0), 0)
  const remaining = run.miles - assigned
  const over = remaining < -0.05

  const activeShoes = useMemo(
    () => (shoes.data ?? []).filter((s) => !s.retired_at || rows.some((r) => r.shoe_id === s.id)),
    [shoes.data, rows],
  )

  const update = (key: number, patch: Partial<Row>) => {
    setDirty(true)
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  }

  const setLaps = (row: Row, from: number | null, to: number | null) => {
    if (from === null) return update(row.key, { lap_from: null, lap_to: null })
    const end = Math.max(from, to ?? from)
    update(row.key, { lap_from: from, lap_to: end, miles: lapMiles(from, end).toFixed(2) })
  }

  const addRow = () => {
    setDirty(true)
    const fallback = activeShoes.find((s) => s.is_default) ?? activeShoes[0]
    setRows((rs) => [
      ...rs,
      { key: nextKey++, shoe_id: fallback?.id ?? '', miles: Math.max(0, remaining).toFixed(2), lap_from: null, lap_to: null },
    ])
  }

  const submit = () =>
    save.mutate(
      rows
        .filter((r) => r.shoe_id !== '')
        .map((r) => ({
          shoe_id: Number(r.shoe_id),
          miles: parseFloat(r.miles) || null,
          lap_from: r.lap_from,
          lap_to: r.lap_to,
        })),
      { onSuccess: () => setDirty(false) },
    )

  const hasLaps = run.laps.length > 1

  return (
    <div>
      {rows.length === 0 && <p className="mb-3 text-sm text-ink-3">No shoes assigned yet.</p>}
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.key} className="flex flex-wrap items-center gap-2 rounded-lg bg-surface-2 p-2">
            <select
              aria-label="Shoe"
              className={`${inputBase} min-w-40 flex-1`}
              value={row.shoe_id}
              onChange={(e) => update(row.key, { shoe_id: e.target.value ? Number(e.target.value) : '' })}
            >
              <option value="">Pick a shoe…</option>
              {activeShoes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {hasLaps && (
              <div className="flex items-center gap-1 text-sm text-ink-2">
                <span>Laps</span>
                <select
                  aria-label="From lap"
                  className={`${inputBase} w-16`}
                  value={row.lap_from ?? ''}
                  onChange={(e) => setLaps(row, e.target.value ? Number(e.target.value) : null, row.lap_to)}
                >
                  <option value="">–</option>
                  {run.laps.map((l) => (
                    <option key={l.idx} value={l.idx}>
                      {l.idx}
                    </option>
                  ))}
                </select>
                <span>to</span>
                <select
                  aria-label="To lap"
                  className={`${inputBase} w-16`}
                  value={row.lap_to ?? ''}
                  disabled={row.lap_from === null}
                  onChange={(e) => setLaps(row, row.lap_from, Number(e.target.value))}
                >
                  {row.lap_from === null && <option value="">–</option>}
                  {run.laps
                    .filter((l) => row.lap_from === null || l.idx >= row.lap_from)
                    .map((l) => (
                      <option key={l.idx} value={l.idx}>
                        {l.idx}
                      </option>
                    ))}
                </select>
              </div>
            )}
            <div className="flex items-center gap-1">
              <input
                aria-label="Miles"
                inputMode="decimal"
                className={`${inputBase} tabular w-20 text-right`}
                value={row.miles}
                onChange={(e) => update(row.key, { miles: e.target.value, lap_from: null, lap_to: null })}
              />
              <span className="text-sm text-ink-3">mi</span>
            </div>
            <button
              type="button"
              aria-label="Remove shoe"
              className="rounded-md px-2 py-1 text-ink-3 hover:bg-surface hover:text-over"
              onClick={() => { setDirty(true); setRows((rs) => rs.filter((r) => r.key !== row.key)) }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className={`tabular text-sm ${over ? 'font-medium text-over' : remaining > 0.05 ? 'text-warn' : 'text-ink-2'}`}>
          {over
            ? `${mi(-remaining, 2)} mi more than the run`
            : remaining > 0.05
              ? `${mi(remaining, 2)} of ${mi(run.miles, 2)} mi unassigned`
              : `All ${mi(run.miles, 2)} mi assigned`}
        </div>
        <div className="flex gap-2">
          <Button onClick={addRow} disabled={!activeShoes.length}>
            + Add shoe
          </Button>
          <Button variant="primary" onClick={submit} disabled={!dirty || over || save.isPending}>
            {save.isPending ? 'Saving…' : 'Save shoes'}
          </Button>
        </div>
      </div>
      {!activeShoes.length && shoes.data && <p className="mt-2 text-sm text-ink-3">Add a shoe on the Shoes page first.</p>}
      {save.error && <div className="mt-2"><ErrorNote error={save.error} /></div>}
    </div>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useRetireShoe, useSaveShoe, useShoes } from '../api/hooks'
import type { Category, Shoe } from '../api/types'
import { Badge, Button, Card, Empty, ErrorNote, Field, inputClass, Loading, PageHeader } from '../components/ui'
import { CATEGORY_LABELS, longDate, mi } from '../lib/format'

function WearBar({ shoe }: { shoe: Shoe }) {
  const pct = Math.min(100, (shoe.miles / shoe.retire_at_miles) * 100)
  const color = shoe.wear === 'over' ? 'var(--over)' : shoe.wear === 'warn' ? 'var(--warn)' : 'var(--primary)'
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="tabular text-2xl font-semibold text-ink">{mi(shoe.miles)}</span>
        <span className="tabular text-sm text-ink-3">of {Math.round(shoe.retire_at_miles)} mi</span>
      </div>
      <div className="h-2.5 rounded-full bg-surface-2" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-2.5 rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      {shoe.wear !== 'ok' && (
        <div className={`mt-1.5 text-xs font-medium ${shoe.wear === 'over' ? 'text-over' : 'text-warn'}`}>
          ⚠ {shoe.wear === 'over' ? 'Past its retirement mileage' : `${Math.round(shoe.retire_at_miles - shoe.miles)} mi until retirement`}
        </div>
      )}
    </div>
  )
}

const empty = { name: '', brand: '', model: '', color: '#00539b', start_miles: '0', retire_at_miles: '400', is_default: false, default_for_category: '', notes: '' }
type FormState = typeof empty

function ShoeForm({ shoe, onDone }: { shoe?: Shoe; onDone: () => void }) {
  const save = useSaveShoe()
  const [f, setF] = useState<FormState>(
    shoe
      ? {
          name: shoe.name, brand: shoe.brand ?? '', model: shoe.model ?? '', color: shoe.color ?? '#00539b',
          start_miles: String(shoe.start_miles), retire_at_miles: String(shoe.retire_at_miles), is_default: shoe.is_default,
          default_for_category: shoe.default_for_category ?? '', notes: shoe.notes ?? '',
        }
      : empty,
  )
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((s) => ({ ...s, [k]: v }))
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    save.mutate(
      {
        id: shoe?.id,
        name: f.name.trim(),
        brand: f.brand || null,
        model: f.model || null,
        color: f.color,
        start_miles: parseFloat(f.start_miles) || 0,
        retire_at_miles: parseFloat(f.retire_at_miles) || 400,
        is_default: f.is_default,
        default_for_category: (f.default_for_category || null) as Category | null,
        notes: f.notes || null,
      },
      { onSuccess: onDone },
    )
  }
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
      <Field label="Name">
        <input required className={inputClass} value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="e.g. Pegasus 41 (blue)" />
      </Field>
      <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
        <Field label="Brand">
          <input className={inputClass} value={f.brand} onChange={(e) => set('brand', e.target.value)} />
        </Field>
        <Field label="Model">
          <input className={inputClass} value={f.model} onChange={(e) => set('model', e.target.value)} />
        </Field>
        <Field label="Color">
          <input type="color" className="h-[34px] w-12 rounded-lg border border-border bg-surface" value={f.color} onChange={(e) => set('color', e.target.value)} />
        </Field>
      </div>
      <Field label="Miles already on the shoe" hint="Mileage from before you started using this app.">
        <input inputMode="decimal" className={inputClass} value={f.start_miles} onChange={(e) => set('start_miles', e.target.value)} />
      </Field>
      <Field label="Retire at (miles)" hint="You'll get a warning at 85%.">
        <input inputMode="decimal" className={inputClass} value={f.retire_at_miles} onChange={(e) => set('retire_at_miles', e.target.value)} />
      </Field>
      <Field label="Default for new runs">
        <label className="flex items-center gap-2 py-1.5">
          <input type="checkbox" checked={f.is_default} onChange={(e) => set('is_default', e.target.checked)} />
          <span className="text-ink">Use for every new run</span>
        </label>
      </Field>
      <Field label="Or default for one run type" hint="Overrides the overall default for that type.">
        <select className={inputClass} value={f.default_for_category} onChange={(e) => set('default_for_category', e.target.value)}>
          <option value="">None</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </Field>
      <div className="sm:col-span-2">
        <Field label="Notes">
          <textarea rows={2} className={inputClass} value={f.notes} onChange={(e) => set('notes', e.target.value)} />
        </Field>
      </div>
      {save.error && <div className="sm:col-span-2"><ErrorNote error={save.error} /></div>}
      <div className="flex justify-end gap-2 sm:col-span-2">
        <Button onClick={onDone}>Cancel</Button>
        <Button type="submit" variant="primary" disabled={save.isPending}>
          {shoe ? 'Save' : 'Add shoe'}
        </Button>
      </div>
    </form>
  )
}

function ShoeCard({ shoe, onEdit }: { shoe: Shoe; onEdit: () => void }) {
  const retire = useRetireShoe()
  return (
    <Card>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="h-8 w-1.5 shrink-0 rounded-full" style={{ background: shoe.color ?? 'var(--primary)' }} />
          <div className="min-w-0">
            <div className="truncate font-semibold text-ink">{shoe.name}</div>
            <div className="truncate text-xs text-ink-3">{[shoe.brand, shoe.model].filter(Boolean).join(' ') || '—'}</div>
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-1">
          {shoe.is_default && <Badge tone="primary">Default</Badge>}
          {shoe.default_for_category && <Badge tone="primary">{CATEGORY_LABELS[shoe.default_for_category]} default</Badge>}
          {shoe.retired_at && <Badge>Retired {longDate(shoe.retired_at)}</Badge>}
        </div>
      </div>
      <WearBar shoe={shoe} />
      {shoe.notes && <p className="mt-3 whitespace-pre-line text-sm text-ink-2">{shoe.notes}</p>}
      <div className="mt-3 flex items-center justify-between text-sm">
        <Link to={`/runs?shoe=${shoe.id}`} className="text-link">
          {shoe.run_count} runs →
        </Link>
        <div className="flex gap-1">
          <Button variant="ghost" onClick={onEdit}>Edit</Button>
          <Button variant={shoe.retired_at ? 'ghost' : 'danger'} onClick={() => retire.mutate({ id: shoe.id, retire: !shoe.retired_at })}>
            {shoe.retired_at ? 'Un-retire' : 'Retire'}
          </Button>
        </div>
      </div>
    </Card>
  )
}

export default function Shoes() {
  const shoes = useShoes()
  const [editing, setEditing] = useState<Shoe | 'new' | null>(null)
  const [showRetired, setShowRetired] = useState(false)
  const active = shoes.data?.filter((s) => !s.retired_at) ?? []
  const retired = shoes.data?.filter((s) => s.retired_at) ?? []

  return (
    <>
      <PageHeader
        title="Shoes"
        sub="Each shoe's total is its starting miles plus every run segment assigned to it."
        action={<Button variant="primary" onClick={() => setEditing('new')}>+ Add shoe</Button>}
      />
      {editing && (
        <Card className="mb-4" title={editing === 'new' ? 'New shoe' : `Edit ${editing.name}`}>
          <ShoeForm shoe={editing === 'new' ? undefined : editing} onDone={() => setEditing(null)} />
        </Card>
      )}
      {shoes.isLoading && <Loading />}
      {shoes.error && <ErrorNote error={shoes.error} />}
      {shoes.data && !active.length && <Empty>No active shoes. Add one to start tracking mileage.</Empty>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((s) => <ShoeCard key={s.id} shoe={s} onEdit={() => setEditing(s)} />)}
      </div>
      {!!retired.length && (
        <div className="mt-6">
          <button type="button" className="text-sm font-medium text-link" onClick={() => setShowRetired((v) => !v)}>
            {showRetired ? 'Hide' : 'Show'} {retired.length} retired shoe{retired.length > 1 ? 's' : ''}
          </button>
          {showRetired && (
            <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {retired.map((s) => <ShoeCard key={s.id} shoe={s} onEdit={() => setEditing(s)} />)}
            </div>
          )}
        </div>
      )}
    </>
  )
}

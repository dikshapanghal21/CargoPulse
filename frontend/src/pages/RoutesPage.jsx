import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { api } from '../api'
import { parseApiError } from '../api/client'
import { useApi, useDebounced } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import {
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  ModeTag,
  PageHeader,
  Pagination,
} from '../components/ui'
import { MODES, MODE_META, formatNumber } from '../utils/format'

const EMPTY = {
  code: '',
  origin_city: '',
  origin_country: '',
  destination_city: '',
  destination_country: '',
  mode: 'road',
  distance_km: '',
  estimated_transit_days: '',
  is_active: true,
}

function validate(f) {
  const e = {}
  if (f.code && !/^[A-Za-z0-9-]{3,20}$/.test(f.code.trim())) e.code = 'Use 3–20 letters, numbers or hyphens.'
  if (f.origin_city.trim().length < 2) e.origin_city = 'Enter the origin city.'
  if (!/^[A-Za-z]{2}$/.test(f.origin_country.trim())) e.origin_country = 'Two-letter country code, e.g. DE.'
  if (f.destination_city.trim().length < 2) e.destination_city = 'Enter the destination city.'
  if (!/^[A-Za-z]{2}$/.test(f.destination_country.trim())) e.destination_country = 'Two-letter country code, e.g. US.'
  if (
    !e.origin_city && !e.destination_city &&
    f.origin_city.trim().toLowerCase() === f.destination_city.trim().toLowerCase() &&
    f.origin_country.trim().toUpperCase() === f.destination_country.trim().toUpperCase()
  ) e.destination_city = 'Destination must differ from origin.'
  const d = Number(f.distance_km)
  if (!Number.isInteger(d) || d <= 0 || d > 40000) e.distance_km = 'Whole kilometres between 1 and 40,000.'
  const t = Number(f.estimated_transit_days)
  if (!Number.isInteger(t) || t <= 0 || t > 120) e.estimated_transit_days = 'Whole days between 1 and 120.'
  return e
}

function RouteFormModal({ open, route, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [lastOpen, setLastOpen] = useState(false)

  if (open !== lastOpen) {
    setLastOpen(open)
    if (open) {
      setForm(route ? { ...route, distance_km: String(route.distance_km), estimated_transit_days: String(route.estimated_transit_days) } : EMPTY)
      setErrors({})
      setSubmitError(null)
    }
  }

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [k]: v }))
    setErrors((er) => ({ ...er, [k]: undefined }))
  }

  async function submit(e) {
    e.preventDefault()
    const v = validate(form)
    setErrors(v)
    if (Object.keys(v).length) return
    setSaving(true)
    setSubmitError(null)
    const body = {
      origin_city: form.origin_city.trim(),
      origin_country: form.origin_country.trim().toUpperCase(),
      destination_city: form.destination_city.trim(),
      destination_country: form.destination_country.trim().toUpperCase(),
      mode: form.mode,
      distance_km: Number(form.distance_km),
      estimated_transit_days: Number(form.estimated_transit_days),
      is_active: form.is_active,
    }
    if (form.code.trim()) body.code = form.code.trim().toUpperCase()
    try {
      const saved = route ? await api.routes.update(route.id, body) : await api.routes.create(body)
      onSaved(saved, !route)
    } catch (err) {
      const parsed = parseApiError(err)
      setErrors(parsed.fieldErrors)
      setSubmitError(parsed.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={route ? `Edit route ${route.code}` : 'Add route'}
      width="max-w-xl"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" form="route-form" className="btn btn-primary" disabled={saving}>
            {saving && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {route ? 'Save changes' : 'Add route'}
          </button>
        </>
      }
    >
      <form id="route-form" onSubmit={submit} noValidate className="grid grid-cols-[1fr_96px] gap-4">
        <Field label="Origin city" htmlFor="r-oc" error={errors.origin_city} required>
          <input id="r-oc" className="input" value={form.origin_city} onChange={set('origin_city')} aria-invalid={!!errors.origin_city} />
        </Field>
        <Field label="Country" htmlFor="r-occ" error={errors.origin_country} required>
          <input id="r-occ" className="input code uppercase" maxLength={2} value={form.origin_country} onChange={set('origin_country')} aria-invalid={!!errors.origin_country} />
        </Field>
        <Field label="Destination city" htmlFor="r-dc" error={errors.destination_city} required>
          <input id="r-dc" className="input" value={form.destination_city} onChange={set('destination_city')} aria-invalid={!!errors.destination_city} />
        </Field>
        <Field label="Country" htmlFor="r-dcc" error={errors.destination_country} required>
          <input id="r-dcc" className="input code uppercase" maxLength={2} value={form.destination_country} onChange={set('destination_country')} aria-invalid={!!errors.destination_country} />
        </Field>
        <div className="col-span-2 grid gap-4 sm:grid-cols-3">
          <Field label="Mode" htmlFor="r-mode" required>
            <select id="r-mode" className="input" value={form.mode} onChange={set('mode')}>
              {MODES.map((m) => <option key={m} value={m}>{MODE_META[m].label}</option>)}
            </select>
          </Field>
          <Field label="Distance (km)" htmlFor="r-km" error={errors.distance_km} required>
            <input id="r-km" type="number" min="1" className="input num" value={form.distance_km} onChange={set('distance_km')} aria-invalid={!!errors.distance_km} />
          </Field>
          <Field label="Transit (days)" htmlFor="r-days" error={errors.estimated_transit_days} required>
            <input id="r-days" type="number" min="1" max="120" className="input num" value={form.estimated_transit_days} onChange={set('estimated_transit_days')} aria-invalid={!!errors.estimated_transit_days} />
          </Field>
        </div>
        <div className="col-span-2">
          <Field label="Route code" htmlFor="r-code" error={errors.code} hint={route ? undefined : 'Optional. Generated from the cities and mode, e.g. SHA-LOS-OCN'}>
            <input id="r-code" className="input code uppercase" maxLength={20} value={form.code} onChange={set('code')} aria-invalid={!!errors.code} />
          </Field>
        </div>
        <label className="col-span-2 flex items-center gap-2 text-[0.9rem]">
          <input type="checkbox" checked={form.is_active} onChange={set('is_active')} className="size-4 accent-hull" />
          Active — available for new shipments
        </label>
        {submitError && <p className="col-span-2 text-[0.85rem] text-danger" role="alert">{submitError}</p>}
      </form>
    </Modal>
  )
}

export default function RoutesPage() {
  const { notify } = useToast()
  const [search, setSearch] = useState('')
  const [mode, setMode] = useState('')
  const [page, setPage] = useState(1)
  const q = useDebounced(search, 300)
  const { data, error, loading, reload } = useApi(
    () => api.routes.list({ search: q, mode, page, page_size: 20 }),
    [q, mode, page],
  )
  const [editing, setEditing] = useState(null)
  const [formOpen, setFormOpen] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState(null)

  async function doDelete() {
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await api.routes.remove(deleting.id)
      notify(`Route ${deleting.code} deleted`)
      setDeleting(null)
      reload({ silent: true })
    } catch (err) {
      setDeleteError(parseApiError(err))
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Routes"
        description="The lanes your network serves, with planned transit times used to set ETAs."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setFormOpen(true) }}>
            <Plus className="size-4" aria-hidden /> Add route
          </button>
        }
      />
      <div className="panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-rule p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fog" />
            <input type="search" aria-label="Search routes" className="input pl-9" placeholder="Search code, city or country" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
          </div>
          <select className="input sm:w-44" aria-label="Mode" value={mode} onChange={(e) => { setMode(e.target.value); setPage(1) }}>
            <option value="">All modes</option>
            {MODES.map((m) => <option key={m} value={m}>{MODE_META[m].label}</option>)}
          </select>
        </div>
        {error && <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>}
        {!error && !data && loading && <LoadingState />}
        {data && (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[800px]">
                <thead>
                  <tr>
                    <th>Lane</th>
                    <th>Mode</th>
                    <th className="text-right">Distance</th>
                    <th className="text-right">Transit</th>
                    <th className="text-right">Shipments</th>
                    <th>Availability</th>
                    <th><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <span className="block font-semibold">
                          {r.origin_city}, {r.origin_country} → {r.destination_city}, {r.destination_country}
                        </span>
                        <span className="code text-[0.78rem] text-steel">{r.code}</span>
                      </td>
                      <td><ModeTag mode={r.mode} /></td>
                      <td className="num text-right">{formatNumber(r.distance_km)} km</td>
                      <td className="num text-right">{r.estimated_transit_days} {r.estimated_transit_days === 1 ? 'day' : 'days'}</td>
                      <td className="num text-right">
                        <Link to={`/shipments?route_id=${r.id}`} className="hover:underline">{formatNumber(r.total_shipments)}</Link>
                        <span className="block text-[0.78rem] text-steel">{r.active_shipments} in progress</span>
                      </td>
                      <td>
                        <span className={`inline-flex items-center gap-1.5 text-[0.85rem] ${r.is_active ? 'text-ink' : 'text-fog'}`}>
                          <span className={`size-2 rounded-full ${r.is_active ? 'bg-ok' : 'bg-st-cancelled'}`} aria-hidden />
                          {r.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="text-right whitespace-nowrap">
                        <button type="button" className="btn btn-ghost" onClick={() => { setEditing(r); setFormOpen(true) }} aria-label={`Edit ${r.code}`}>
                          <Pencil className="size-4" />
                        </button>
                        <button type="button" className="btn btn-ghost hover:text-danger" onClick={() => { setDeleteError(null); setDeleting(r) }} aria-label={`Delete ${r.code}`}>
                          <Trash2 className="size-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.items.length === 0 && <EmptyState title="No routes found">Adjust the search or add a route.</EmptyState>}
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
          </>
        )}
      </div>

      <RouteFormModal
        open={formOpen}
        route={editing}
        onClose={() => setFormOpen(false)}
        onSaved={(saved, created) => {
          setFormOpen(false)
          notify(created ? `Route ${saved.code} added` : `Route ${saved.code} updated`)
          reload({ silent: true })
        }}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        title={`Delete route ${deleting?.code ?? ''}?`}
        message="Routes used by shipments cannot be deleted; deactivate them instead."
        confirmLabel="Delete route"
        busy={deleteBusy}
        error={deleteError}
        onConfirm={doDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  )
}

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
  PageHeader,
  Pagination,
} from '../components/ui'
import { formatNumber, formatPercent } from '../utils/format'

const EMPTY = { name: '', code: '', contact_email: '', contact_phone: '', website: '', is_active: true }

function validate(f) {
  const e = {}
  if (f.name.trim().length < 2) e.name = 'Enter a name of at least 2 characters.'
  if (!/^[A-Za-z0-9]{2,10}$/.test(f.code.trim())) e.code = 'Use 2–10 letters or numbers.'
  if (f.contact_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.contact_email.trim())) e.contact_email = 'Enter a valid email address.'
  if (f.contact_phone && !/^\+?[0-9 ()-]{6,40}$/.test(f.contact_phone.trim())) e.contact_phone = 'Use digits, spaces, +, ( ) or -.'
  if (f.website && !/^https?:\/\/\S+$/.test(f.website.trim())) e.website = 'Start with http:// or https://'
  return e
}

export function CarrierFormModal({ open, carrier, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [lastOpen, setLastOpen] = useState(false)

  if (open !== lastOpen) {
    setLastOpen(open)
    if (open) {
      setForm(
        carrier
          ? {
              name: carrier.name,
              code: carrier.code,
              contact_email: carrier.contact_email || '',
              contact_phone: carrier.contact_phone || '',
              website: carrier.website || '',
              is_active: carrier.is_active,
            }
          : EMPTY,
      )
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
      name: form.name.trim(),
      code: form.code.trim().toUpperCase(),
      contact_email: form.contact_email.trim() || null,
      contact_phone: form.contact_phone.trim() || null,
      website: form.website.trim() || null,
      is_active: form.is_active,
    }
    try {
      const saved = carrier ? await api.carriers.update(carrier.id, body) : await api.carriers.create(body)
      onSaved(saved, !carrier)
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
      title={carrier ? `Edit ${carrier.name}` : 'Add carrier'}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="carrier-form" className="btn btn-primary" disabled={saving}>
            {saving && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {carrier ? 'Save changes' : 'Add carrier'}
          </button>
        </>
      }
    >
      <form id="carrier-form" onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-[1fr_140px]">
        <Field label="Name" htmlFor="c-name" error={errors.name} required>
          <input id="c-name" className="input" value={form.name} onChange={set('name')} maxLength={120} aria-invalid={!!errors.name} />
        </Field>
        <Field label="Code" htmlFor="c-code" error={errors.code} required>
          <input id="c-code" className="input code uppercase" value={form.code} onChange={set('code')} maxLength={10} aria-invalid={!!errors.code} />
        </Field>
        <Field label="Contact email" htmlFor="c-email" error={errors.contact_email}>
          <input id="c-email" type="email" className="input" value={form.contact_email} onChange={set('contact_email')} aria-invalid={!!errors.contact_email} />
        </Field>
        <Field label="Phone" htmlFor="c-phone" error={errors.contact_phone}>
          <input id="c-phone" className="input" value={form.contact_phone} onChange={set('contact_phone')} aria-invalid={!!errors.contact_phone} />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Website" htmlFor="c-web" error={errors.website}>
            <input id="c-web" className="input" value={form.website} onChange={set('website')} placeholder="https://" aria-invalid={!!errors.website} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-[0.9rem] sm:col-span-2">
          <input type="checkbox" checked={form.is_active} onChange={set('is_active')} className="size-4 accent-hull" />
          Active — available for new shipments
        </label>
        {submitError && <p className="text-[0.85rem] text-danger sm:col-span-2" role="alert">{submitError}</p>}
      </form>
    </Modal>
  )
}

export default function Carriers() {
  const { notify } = useToast()
  const [search, setSearch] = useState('')
  const [active, setActive] = useState('')
  const [page, setPage] = useState(1)
  const q = useDebounced(search, 300)
  const { data, error, loading, reload } = useApi(
    () => api.carriers.list({ search: q, is_active: active, page, page_size: 20 }),
    [q, active, page],
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
      await api.carriers.remove(deleting.id)
      notify(`${deleting.name} deleted`)
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
        title="Carriers"
        description="Partners that move your freight, with live delivery performance."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setFormOpen(true) }}>
            <Plus className="size-4" aria-hidden /> Add carrier
          </button>
        }
      />
      <div className="panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-rule p-4 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fog" />
            <input
              type="search"
              aria-label="Search carriers"
              className="input pl-9"
              placeholder="Search name, code or email"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <select className="input sm:w-48" aria-label="Availability" value={active} onChange={(e) => { setActive(e.target.value); setPage(1) }}>
            <option value="">Active and inactive</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </div>
        {error && <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>}
        {!error && !data && loading && <LoadingState />}
        {data && (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[760px]">
                <thead>
                  <tr>
                    <th>Carrier</th>
                    <th>Contact</th>
                    <th className="text-right">Shipments</th>
                    <th className="text-right">In progress</th>
                    <th className="text-right">On time</th>
                    <th>Availability</th>
                    <th><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <span className="block font-semibold">{c.name}</span>
                        <span className="code text-[0.78rem] text-steel">{c.code}</span>
                      </td>
                      <td className="text-[0.85rem]">
                        {c.contact_email ? <a href={`mailto:${c.contact_email}`} className="text-harbor hover:underline">{c.contact_email}</a> : <span className="text-fog">No email</span>}
                        {c.contact_phone && <span className="block text-steel">{c.contact_phone}</span>}
                      </td>
                      <td className="num text-right">
                        <Link to={`/shipments?carrier_id=${c.id}`} className="hover:underline">{formatNumber(c.total_shipments)}</Link>
                      </td>
                      <td className="num text-right">
                        {formatNumber(c.active_shipments)}
                        {c.delayed_shipments > 0 && (
                          <span className="block text-[0.78rem] font-semibold text-st-delayed">{c.delayed_shipments} delayed</span>
                        )}
                      </td>
                      <td className="num text-right">{formatPercent(c.on_time_rate)}</td>
                      <td>
                        <span className={`inline-flex items-center gap-1.5 text-[0.85rem] ${c.is_active ? 'text-ink' : 'text-fog'}`}>
                          <span className={`size-2 rounded-full ${c.is_active ? 'bg-ok' : 'bg-st-cancelled'}`} aria-hidden />
                          {c.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="text-right whitespace-nowrap">
                        <button type="button" className="btn btn-ghost" onClick={() => { setEditing(c); setFormOpen(true) }} aria-label={`Edit ${c.name}`}>
                          <Pencil className="size-4" />
                        </button>
                        <button type="button" className="btn btn-ghost hover:text-danger" onClick={() => { setDeleteError(null); setDeleting(c) }} aria-label={`Delete ${c.name}`}>
                          <Trash2 className="size-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.items.length === 0 && <EmptyState title="No carriers found">Adjust the search or add a carrier.</EmptyState>}
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
          </>
        )}
      </div>

      <CarrierFormModal
        open={formOpen}
        carrier={editing}
        onClose={() => setFormOpen(false)}
        onSaved={(saved, created) => {
          setFormOpen(false)
          notify(created ? `${saved.name} added` : `${saved.name} updated`)
          reload({ silent: true })
        }}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        title={`Delete ${deleting?.name ?? 'carrier'}?`}
        message="Carriers with shipments cannot be deleted; deactivate them instead to keep their history."
        confirmLabel="Delete carrier"
        busy={deleteBusy}
        error={deleteError}
        onConfirm={doDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  )
}

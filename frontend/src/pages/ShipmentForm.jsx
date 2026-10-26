import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { api } from '../api'
import { parseApiError } from '../api/client'
import { useApi } from '../hooks/useApi'
import { ErrorState, Field, LoadingState, PageHeader } from '../components/ui'
import { useToast } from '../components/Toast'
import {
  MODE_META,
  PRIORITIES,
  PRIORITY_META,
  STATUS_META,
  formatFull,
  fromLocalInput,
  toLocalInput,
} from '../utils/format'

const INITIAL_STATUSES = ['pending', 'picked_up', 'in_transit', 'out_for_delivery']

const EMPTY = {
  tracking_id: '',
  customer_name: '',
  reference: '',
  description: '',
  carrier_id: '',
  route_id: '',
  status: 'pending',
  priority: 'standard',
  weight_kg: '',
  pieces: '1',
  current_location: '',
  shipped_at: '',
  eta: '',
}

function fromShipment(s) {
  return {
    tracking_id: s.tracking_id,
    customer_name: s.customer_name,
    reference: s.reference || '',
    description: s.description || '',
    carrier_id: String(s.carrier.id),
    route_id: String(s.route.id),
    status: s.status,
    priority: s.priority,
    weight_kg: String(s.weight_kg),
    pieces: String(s.pieces),
    current_location: s.current_location || '',
    shipped_at: toLocalInput(s.shipped_at),
    eta: toLocalInput(s.eta),
  }
}

function validate(form, isEdit) {
  const errors = {}
  if (form.customer_name.trim().length < 2) errors.customer_name = 'Enter the customer name (at least 2 characters).'
  if (!form.carrier_id) errors.carrier_id = 'Choose a carrier.'
  if (!form.route_id) errors.route_id = 'Choose a route.'
  const weight = Number(form.weight_kg)
  if (!form.weight_kg || Number.isNaN(weight) || weight <= 0) errors.weight_kg = 'Weight must be greater than 0.'
  else if (weight > 1_000_000) errors.weight_kg = 'Weight cannot exceed 1,000,000 kg.'
  const pieces = Number(form.pieces)
  if (!Number.isInteger(pieces) || pieces < 1) errors.pieces = 'Pieces must be a whole number of at least 1.'
  if (form.tracking_id && !/^[A-Za-z0-9-]{6,32}$/.test(form.tracking_id.trim())) {
    errors.tracking_id = 'Use 6–32 letters, numbers or hyphens.'
  }
  if (isEdit && !form.eta) errors.eta = 'ETA is required.'
  if (isEdit && !form.shipped_at) errors.shipped_at = 'Shipped date is required.'
  if (form.shipped_at && form.eta && new Date(form.eta) <= new Date(form.shipped_at)) {
    errors.eta = 'ETA must be later than the shipped date.'
  }
  return errors
}

function toPayload(form) {
  return {
    tracking_id: form.tracking_id.trim() || null,
    customer_name: form.customer_name.trim(),
    reference: form.reference.trim() || null,
    description: form.description.trim() || null,
    carrier_id: Number(form.carrier_id),
    route_id: Number(form.route_id),
    status: form.status,
    priority: form.priority,
    weight_kg: Number(form.weight_kg),
    pieces: Number(form.pieces),
    current_location: form.current_location.trim() || null,
    shipped_at: fromLocalInput(form.shipped_at),
    eta: fromLocalInput(form.eta),
  }
}

export default function ShipmentForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const { notify } = useToast()

  const existing = useApi(() => (isEdit ? api.shipments.get(id) : Promise.resolve(null)), [id])
  const carriers = useApi(() => api.carriers.list({ page_size: 100 }), [])
  const routes = useApi(() => api.routes.list({ page_size: 100 }), [])

  const [form, setForm] = useState(EMPTY)
  const [initial, setInitial] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isEdit && existing.data) {
      const f = fromShipment(existing.data)
      setForm(f)
      setInitial(f)
    } else if (!isEdit) {
      setForm({ ...EMPTY, shipped_at: toLocalInput(new Date().toISOString()) })
    }
  }, [isEdit, existing.data])

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setErrors((er) => ({ ...er, [key]: undefined }))
  }

  const currentCarrierId = existing.data?.carrier.id
  const currentRouteId = existing.data?.route.id
  const carrierOptions = (carriers.data?.items || []).filter((c) => c.is_active || c.id === currentCarrierId)
  const routeOptions = (routes.data?.items || []).filter((r) => r.is_active || r.id === currentRouteId)
  const selectedRoute = routeOptions.find((r) => String(r.id) === form.route_id)

  const autoEta = useMemo(() => {
    if (isEdit || form.eta || !selectedRoute) return null
    const start = form.shipped_at ? new Date(form.shipped_at) : new Date()
    return new Date(start.getTime() + selectedRoute.estimated_transit_days * 864e5)
  }, [isEdit, form.eta, form.shipped_at, selectedRoute])

  const terminal = ['delivered', 'cancelled'].includes(existing.data?.status)

  async function onSubmit(e) {
    e.preventDefault()
    const v = validate(form, isEdit)
    setErrors(v)
    setSubmitError(null)
    if (Object.keys(v).length) return

    setSaving(true)
    try {
      let saved
      if (isEdit) {
        const full = toPayload(form)
        const base = toPayload(initial)
        const changes = {}
        Object.keys(full).forEach((k) => {
          if (k === 'status') return
          if (JSON.stringify(full[k]) !== JSON.stringify(base[k])) changes[k] = full[k]
        })
        if (Object.keys(changes).length === 0) {
          navigate(`/shipments/${id}`)
          return
        }
        saved = await api.shipments.update(id, changes)
        notify(`Shipment ${saved.tracking_id} updated`)
      } else {
        const payload = toPayload(form)
        if (!payload.eta) delete payload.eta
        if (!payload.tracking_id) delete payload.tracking_id
        saved = await api.shipments.create(payload)
        notify(`Shipment ${saved.tracking_id} created`)
      }
      navigate(`/shipments/${saved.id}`)
    } catch (err) {
      const parsed = parseApiError(err)
      setErrors(parsed.fieldErrors)
      setSubmitError(parsed)
    } finally {
      setSaving(false)
    }
  }

  const loadError = existing.error || carriers.error || routes.error
  if (loadError) {
    return <ErrorState error={loadError} onRetry={() => { existing.reload(); carriers.reload(); routes.reload() }} />
  }
  if ((isEdit && !existing.data) || !carriers.data || !routes.data) {
    return <LoadingState label="Loading form…" />
  }

  const backTo = isEdit ? `/shipments/${id}` : '/shipments'

  return (
    <div className="max-w-4xl">
      <PageHeader
        back={
          <Link to={backTo} className="mb-2 inline-flex items-center gap-1 text-[0.85rem] font-medium text-steel hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden /> {isEdit ? 'Back to shipment' : 'Back to shipments'}
          </Link>
        }
        title={isEdit ? `Edit ${existing.data.tracking_id}` : 'New shipment'}
        description={
          isEdit
            ? 'Status changes are made from the shipment page so every change is recorded in its history.'
            : 'Book a shipment on a carrier and lane. A tracking ID is generated if you leave it blank.'
        }
      />

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-6">
        {submitError && <ErrorState error={{ ...submitError, status: null, message: submitError.message }} compact />}

        <fieldset className="panel p-5">
          <legend className="sr-only">Customer</legend>
          <h2 className="mb-4 font-bold">Customer and cargo</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Customer name" htmlFor="customer_name" error={errors.customer_name} required>
              <input id="customer_name" className="input" value={form.customer_name} onChange={set('customer_name')} aria-invalid={!!errors.customer_name} maxLength={160} />
            </Field>
            <Field label="Customer reference" htmlFor="reference" error={errors.reference} hint="Purchase order or booking number">
              <input id="reference" className="input" value={form.reference} onChange={set('reference')} maxLength={64} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Cargo description" htmlFor="description" error={errors.description}>
                <textarea id="description" rows={2} className="input" value={form.description} onChange={set('description')} maxLength={2000} />
              </Field>
            </div>
            <Field label="Weight (kg)" htmlFor="weight_kg" error={errors.weight_kg} required>
              <input id="weight_kg" type="number" min="0.01" step="0.01" inputMode="decimal" className="input num" value={form.weight_kg} onChange={set('weight_kg')} aria-invalid={!!errors.weight_kg} />
            </Field>
            <Field label="Pieces" htmlFor="pieces" error={errors.pieces} required>
              <input id="pieces" type="number" min="1" step="1" inputMode="numeric" className="input num" value={form.pieces} onChange={set('pieces')} aria-invalid={!!errors.pieces} />
            </Field>
          </div>
        </fieldset>

        <fieldset className="panel p-5">
          <legend className="sr-only">Routing</legend>
          <h2 className="mb-1 font-bold">Carrier and route</h2>
          {terminal && (
            <p className="mb-3 text-[0.85rem] text-steel">
              This shipment is {existing.data.status}, so its carrier, route and dates are locked.
            </p>
          )}
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <Field label="Carrier" htmlFor="carrier_id" error={errors.carrier_id} required>
              <select id="carrier_id" className="input" value={form.carrier_id} onChange={set('carrier_id')} disabled={terminal} aria-invalid={!!errors.carrier_id}>
                <option value="">Choose a carrier</option>
                {carrierOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code}){c.is_active ? '' : ' – inactive'}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Route" htmlFor="route_id" error={errors.route_id} required>
              <select id="route_id" className="input" value={form.route_id} onChange={set('route_id')} disabled={terminal} aria-invalid={!!errors.route_id}>
                <option value="">Choose a route</option>
                {routeOptions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.origin_city} → {r.destination_city} ({MODE_META[r.mode].label}, {r.estimated_transit_days} d)
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority" htmlFor="priority">
              <select id="priority" className="input" value={form.priority} onChange={set('priority')}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_META[p].label}
                  </option>
                ))}
              </select>
            </Field>
            {!isEdit ? (
              <Field label="Initial status" htmlFor="status" hint="Most new bookings start as pending.">
                <select id="status" className="input" value={form.status} onChange={set('status')}>
                  {INITIAL_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_META[s].label}
                    </option>
                  ))}
                </select>
              </Field>
            ) : (
              <Field label="Current location" htmlFor="current_location" error={errors.current_location}>
                <input id="current_location" className="input" value={form.current_location} onChange={set('current_location')} maxLength={160} />
              </Field>
            )}
            <Field label="Shipped (pickup) time" htmlFor="shipped_at" error={errors.shipped_at} hint={!isEdit ? 'Defaults to now' : undefined} required={isEdit}>
              <input id="shipped_at" type="datetime-local" className="input num" value={form.shipped_at} onChange={set('shipped_at')} disabled={terminal} aria-invalid={!!errors.shipped_at} />
            </Field>
            <Field
              label="Estimated arrival (ETA)"
              htmlFor="eta"
              error={errors.eta}
              required={isEdit}
              hint={autoEta ? `Leave empty to use the route's transit time: ${formatFull(autoEta)}` : undefined}
            >
              <input id="eta" type="datetime-local" className="input num" value={form.eta} onChange={set('eta')} disabled={terminal} aria-invalid={!!errors.eta} />
            </Field>
            <Field label="Tracking ID" htmlFor="tracking_id" error={errors.tracking_id} hint={!isEdit ? 'Optional. Generated automatically, e.g. CP26-7K3M9QX2' : undefined}>
              <input id="tracking_id" className="input code uppercase" value={form.tracking_id} onChange={set('tracking_id')} maxLength={32} aria-invalid={!!errors.tracking_id} />
            </Field>
          </div>
        </fieldset>

        <div className="flex flex-wrap justify-end gap-2">
          <Link to={backTo} className="btn btn-secondary">
            Cancel
          </Link>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {isEdit ? 'Save changes' : 'Create shipment'}
          </button>
        </div>
      </form>
    </div>
  )
}

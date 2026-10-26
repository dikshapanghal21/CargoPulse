import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Bot, CheckCircle2, Loader2, Pencil, Trash2, User } from 'lucide-react'
import { api } from '../api'
import { parseApiError } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import {
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  ModeIcon,
  Panel,
  PriorityTag,
  SeverityBadge,
  StatusBadge,
} from '../components/ui'
import {
  MODE_META,
  STATUS_META,
  formatDuration,
  formatFull,
  formatNumber,
  formatWeight,
  fromLocalInput,
  relativeTime,
  toLocalInput,
} from '../utils/format'

function Voyage({ s }) {
  const start = new Date(s.shipped_at).getTime()
  const end = new Date(s.eta).getTime()
  const now = Date.now()
  let progress
  if (s.status === 'delivered') progress = 1
  else if (s.status === 'cancelled' || s.status === 'pending') progress = 0
  else progress = Math.min(1, Math.max(0, (now - start) / (end - start)))
  const late = s.is_overdue
  return (
    <div className="rounded-lg bg-hull px-5 py-5 text-white">
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[0.8rem] text-white/60">From</p>
          <p className="truncate text-[1.15rem] font-bold">
            {s.route.origin_city}, {s.route.origin_country}
          </p>
          <p className="num text-[0.8rem] text-white/60">{formatFull(s.shipped_at)}</p>
        </div>
        <div className="min-w-0 text-right">
          <p className="text-[0.8rem] text-white/60">{s.status === 'delivered' ? 'Delivered to' : 'To'}</p>
          <p className="truncate text-[1.15rem] font-bold">
            {s.route.destination_city}, {s.route.destination_country}
          </p>
          <p className="num text-[0.8rem] text-white/60">
            {s.status === 'delivered' ? formatFull(s.delivered_at) : `ETA ${formatFull(s.eta)}`}
          </p>
        </div>
      </div>
      <div className="relative mt-5 mb-1 h-8" aria-hidden>
        <div className="absolute top-1/2 right-0 left-0 h-[3px] -translate-y-1/2 rounded bg-white/15" />
        <div
          className={`absolute top-1/2 left-0 h-[3px] -translate-y-1/2 rounded ${late ? 'bg-signal' : 'bg-white'}`}
          style={{ width: `${progress * 100}%` }}
        />
        <span className="absolute top-1/2 left-0 size-3 -translate-y-1/2 rounded-full border-2 border-hull bg-white" />
        <span
          className={`absolute top-1/2 right-0 size-3 -translate-y-1/2 rounded-full border-2 border-hull ${
            s.status === 'delivered' ? 'bg-white' : 'bg-white/30'
          }`}
        />
        {s.status !== 'cancelled' && (
          <span
            className={`absolute top-1/2 flex size-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-hull ${
              late ? 'bg-signal text-hull' : 'bg-white text-hull'
            }`}
            style={{ left: `clamp(16px, ${progress * 100}%, calc(100% - 16px))` }}
          >
            <ModeIcon mode={s.route.mode} className="size-4" />
          </span>
        )}
      </div>
      <p className="mt-2 text-[0.85rem] text-white/75">
        {s.status === 'cancelled'
          ? 'Shipment cancelled.'
          : s.status === 'delivered'
            ? new Date(s.delivered_at) <= new Date(s.eta)
              ? 'Delivered on time.'
              : `Delivered ${formatDuration((new Date(s.delivered_at) - new Date(s.eta)) / 36e5)} after ETA.`
            : late
              ? `${formatDuration(s.hours_overdue)} past ETA.`
              : `Arriving ${relativeTime(s.eta)}${s.current_location ? `. Last seen at ${s.current_location}` : ''}.`}
      </p>
    </div>
  )
}

function Fact({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-[0.78rem] text-steel">{label}</dt>
      <dd className="mt-0.5 text-[0.92rem] text-ink">{children}</dd>
    </div>
  )
}

/** Suggest the most likely next status: resume the pre-delay status, else the next lifecycle step. */
function suggestedStatus(shipment) {
  const options = shipment.allowed_transitions
  if (shipment.status === 'delayed') {
    const latest = shipment.status_history.find((h) => h.to_status === 'delayed')
    if (latest?.from_status && options.includes(latest.from_status)) return latest.from_status
    if (options.includes('in_transit')) return 'in_transit'
  }
  return options.find((o) => o !== 'delayed' && o !== 'cancelled') || options[0] || ''
}

function StatusForm({ shipment, onUpdated }) {
  const options = shipment.allowed_transitions
  const [status, setStatus] = useState(() => suggestedStatus(shipment))
  const [note, setNote] = useState('')
  const [location, setLocation] = useState('')
  const [eta, setEta] = useState('')
  const [deliveredAt, setDeliveredAt] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const { notify } = useToast()

  useEffect(() => {
    setStatus(suggestedStatus(shipment))
    setNote('')
    setLocation('')
    setEta('')
    setDeliveredAt('')
    setError(null)
  }, [shipment])

  if (!options.length) {
    return (
      <p className="flex items-center gap-2 text-[0.9rem] text-steel">
        <CheckCircle2 className="size-4 text-ok" aria-hidden />
        This shipment is {STATUS_META[shipment.status].label.toLowerCase()}. Its lifecycle is complete.
      </p>
    )
  }

  const terminalTarget = status === 'delivered' || status === 'cancelled'
  const needsEta = shipment.status === 'delayed' && !terminalTarget && new Date(shipment.eta) <= new Date()

  async function submit(e) {
    e.preventDefault()
    if (needsEta && !eta) {
      setError({ message: 'Enter a revised ETA to move this shipment out of delayed.', fieldErrors: { eta: 'Required' } })
      return
    }
    setBusy(true)
    setError(null)
    try {
      const body = { status, note: note || null, location: location || null }
      if (eta && !terminalTarget) body.eta = fromLocalInput(eta)
      if (status === 'delivered' && deliveredAt) body.delivered_at = fromLocalInput(deliveredAt)
      const updated = await api.shipments.changeStatus(shipment.id, body)
      notify(`Marked ${STATUS_META[status].label.toLowerCase()}`)
      onUpdated(updated)
    } catch (err) {
      setError(parseApiError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div role="radiogroup" aria-label="New status" className="flex flex-wrap gap-2">
        {options.map((o) => (
          <label
            key={o}
            className={`inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-[0.88rem] font-medium transition-colors ${
              status === o ? 'border-hull bg-hull text-white' : 'border-rule text-ink hover:border-fog'
            }`}
          >
            <input type="radio" name="status" value={o} checked={status === o} onChange={() => setStatus(o)} className="sr-only" />
            <span className="size-2 rounded-full" style={{ background: STATUS_META[o].color }} aria-hidden />
            {STATUS_META[o].label}
          </label>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Location" htmlFor="st-location" hint="Where the shipment is now">
          <input id="st-location" className="input" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={160} placeholder={shipment.current_location || ''} />
        </Field>
        {status === 'delivered' ? (
          <Field label="Delivered at" htmlFor="st-delivered" hint="Defaults to now">
            <input id="st-delivered" type="datetime-local" className="input num" value={deliveredAt} max={toLocalInput(new Date().toISOString())} onChange={(e) => setDeliveredAt(e.target.value)} />
          </Field>
        ) : !terminalTarget ? (
          <Field label={needsEta ? 'Revised ETA' : 'Revised ETA (optional)'} htmlFor="st-eta" error={error?.fieldErrors?.eta} required={needsEta}>
            <input id="st-eta" type="datetime-local" className="input num" value={eta} onChange={(e) => setEta(e.target.value)} aria-invalid={!!error?.fieldErrors?.eta} />
          </Field>
        ) : (
          <div />
        )}
        <div className="sm:col-span-2">
          <Field label="Note" htmlFor="st-note">
            <input id="st-note" className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="e.g. Customs cleared at Rotterdam" />
          </Field>
        </div>
      </div>
      {error && <p className="text-[0.85rem] text-danger" role="alert">{error.message}</p>}
      <div>
        <button type="submit" className="btn btn-primary" disabled={busy || !status}>
          {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
          Mark as {STATUS_META[status]?.label.toLowerCase()}
        </button>
      </div>
    </form>
  )
}

function Timeline({ history }) {
  return (
    <ol className="relative flex flex-col">
      {history.map((h, i) => {
        const system = h.changed_by.startsWith('system')
        return (
          <li key={h.id} className="relative grid grid-cols-[20px_1fr] gap-3 pb-5 last:pb-0">
            {i < history.length - 1 && (
              <span className="absolute top-5 bottom-0 left-[9px] w-px bg-rule" aria-hidden />
            )}
            <span
              className="relative mt-1 size-[18px] rounded-full border-[3px] border-surface ring-1 ring-rule"
              style={{ background: STATUS_META[h.to_status]?.color }}
              aria-hidden
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="font-semibold text-ink">
                  {STATUS_META[h.to_status]?.label}
                  {h.from_status && (
                    <span className="font-normal text-steel"> from {STATUS_META[h.from_status]?.label.toLowerCase()}</span>
                  )}
                </p>
                <time className="num text-[0.8rem] text-steel" dateTime={h.changed_at}>
                  {formatFull(h.changed_at)}
                </time>
              </div>
              {h.location && <p className="text-[0.85rem] text-steel">{h.location}</p>}
              {h.note && <p className="mt-0.5 text-[0.88rem] text-ink">{h.note}</p>}
              <p className="mt-1 flex items-center gap-1 text-[0.75rem] text-fog">
                {system ? <Bot className="size-3.5" aria-hidden /> : <User className="size-3.5" aria-hidden />}
                {system ? 'Overdue monitor' : 'Operator'}
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function AlertList({ alerts, onResolve, resolvingId }) {
  if (!alerts.length) return <EmptyState title="No alerts for this shipment" />
  return (
    <ul className="divide-y divide-rule-soft">
      {alerts.map((a) => (
        <li key={a.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <SeverityBadge severity={a.severity} />
              <span className={`text-[0.78rem] font-semibold ${a.status === 'active' ? 'text-st-delayed' : 'text-steel'}`}>
                {a.status === 'active' ? 'Open' : 'Resolved'}
              </span>
            </div>
            <p className="mt-1 text-[0.88rem] text-ink">{a.message}</p>
            <p className="text-[0.78rem] text-steel">
              Raised {formatFull(a.created_at)}
              {a.resolved_at && `. Resolved ${formatFull(a.resolved_at)}${a.resolution_note ? `: ${a.resolution_note}` : ''}`}
            </p>
          </div>
          {a.status === 'active' && (
            <button type="button" className="btn btn-secondary shrink-0" onClick={() => onResolve(a)} disabled={resolvingId === a.id}>
              {resolvingId === a.id && <Loader2 className="size-4 animate-spin" aria-hidden />}
              Resolve
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

export default function ShipmentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { notify } = useToast()
  const { data: s, error, loading, reload, setData } = useApi(() => api.shipments.get(id), [id])
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)
  const [resolvingId, setResolvingId] = useState(null)

  async function doDelete() {
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.shipments.remove(id)
      notify(`Shipment ${s.tracking_id} deleted`)
      navigate('/shipments')
    } catch (err) {
      setDeleteError(parseApiError(err))
      setDeleting(false)
    }
  }

  async function resolve(alert) {
    setResolvingId(alert.id)
    try {
      await api.alerts.resolve(alert.id, 'Resolved from shipment page')
      notify('Alert resolved')
      await reload({ silent: true })
    } catch (err) {
      notify(parseApiError(err).message, { tone: 'error' })
    } finally {
      setResolvingId(null)
    }
  }

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <Link to="/shipments" className="inline-flex items-center gap-1 text-[0.85rem] font-medium text-steel hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> Back to shipments
        </Link>
        <ErrorState error={error} onRetry={error.status === 404 ? undefined : reload} />
      </div>
    )
  }
  if (!s || loading) return <LoadingState label="Loading shipment…" />

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <Link to="/shipments" className="mb-2 inline-flex items-center gap-1 text-[0.85rem] font-medium text-steel hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden /> Shipments
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="stencil text-[1.9rem] leading-tight font-bold sm:text-[2.2rem]">{s.tracking_id}</h1>
            <StatusBadge status={s.status} />
            {s.is_overdue && (
              <span className="rounded-full bg-signal px-2.5 py-1 text-[0.78rem] font-bold text-hull">
                {formatDuration(s.hours_overdue)} overdue
              </span>
            )}
          </div>
          <p className="mt-1 text-steel">
            {s.customer_name}
            {s.reference && <span>, ref {s.reference}</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/shipments/${s.id}/edit`} className="btn btn-secondary">
            <Pencil className="size-4" aria-hidden /> Edit
          </Link>
          <button type="button" className="btn btn-secondary text-danger" onClick={() => setConfirmDelete(true)}>
            <Trash2 className="size-4" aria-hidden /> Delete
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        <div className="flex min-w-0 flex-col gap-6">
          <Voyage s={s} />

          <Panel title="Update status" subtitle="Each change is recorded in the status history">
            <StatusForm shipment={s} onUpdated={setData} />
          </Panel>

          <Panel title="Alerts" bodyClass="" accent={s.alerts.some((a) => a.status === 'active')}>
            <AlertList alerts={s.alerts} onResolve={resolve} resolvingId={resolvingId} />
          </Panel>
        </div>

        <div className="flex min-w-0 flex-col gap-6">
          <Panel title="Details">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
              <Fact label="Carrier">
                <Link to="/carriers" className="hover:underline">{s.carrier.name}</Link>
              </Fact>
              <Fact label="Route">
                <span className="code text-[0.85rem]">{s.route.code}</span>
              </Fact>
              <Fact label="Mode">
                <span className="inline-flex items-center gap-1.5">
                  <ModeIcon mode={s.route.mode} className="size-4 text-fog" />
                  {MODE_META[s.route.mode]?.label}
                </span>
              </Fact>
              <Fact label="Priority">
                <PriorityTag priority={s.priority} />
              </Fact>
              <Fact label="Weight">
                <span className="num">{formatWeight(s.weight_kg)}</span>
              </Fact>
              <Fact label="Pieces">
                <span className="num">{formatNumber(s.pieces)}</span>
              </Fact>
              <Fact label="Current location">{s.current_location || '—'}</Fact>
              <Fact label="Booked">
                <span className="num">{formatFull(s.created_at)}</span>
              </Fact>
              {s.description && (
                <div className="col-span-2">
                  <Fact label="Cargo">{s.description}</Fact>
                </div>
              )}
            </dl>
          </Panel>

          <Panel title="Status history" subtitle={`${s.status_history.length} events, newest first`}>
            <Timeline history={s.status_history} />
          </Panel>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title={`Delete ${s.tracking_id}?`}
        message="The shipment, its status history and its alerts will be permanently removed."
        confirmLabel="Delete shipment"
        busy={deleting}
        error={deleteError}
        onConfirm={doDelete}
        onClose={() => setConfirmDelete(false)}
      />
    </div>
  )
}

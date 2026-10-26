import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Radar, Search } from 'lucide-react'
import { api } from '../api'
import { parseApiError } from '../api/client'
import { useApi, useDebounced } from '../hooks/useApi'
import { useToast } from '../components/Toast'
import {
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  PageHeader,
  Pagination,
  SeverityBadge,
  StatusBadge,
  TrackingCode,
} from '../components/ui'
import { SEVERITIES, SEVERITY_META, formatFull, relativeTime } from '../utils/format'

const TABS = [
  { value: 'active', label: 'Open' },
  { value: 'resolved', label: 'Resolved' },
  { value: '', label: 'All' },
]

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function ScanPanel({ onFinished }) {
  const { data: last, reload } = useApi(() => api.alerts.lastScan(), [])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const { notify } = useToast()

  async function runScan() {
    setRunning(true)
    setError(null)
    try {
      const { task_id } = await api.alerts.queueScan()
      for (let i = 0; i < 20; i++) {
        await sleep(i < 5 ? 500 : 1000)
        const status = await api.alerts.scanStatus(task_id)
        if (status.state === 'SUCCESS') {
          const r = status.result
          notify(
            r.skipped
              ? 'A scan was already running; results will appear shortly'
              : `Scan finished: ${r.overdue_found} overdue, ${r.alerts_created} new, ${r.alerts_resolved} resolved`,
          )
          reload({ silent: true })
          onFinished()
          return
        }
        if (status.state === 'FAILURE') throw new Error(status.error || 'The scan failed on the worker')
      }
      setError('The scan was queued but no worker picked it up. Check that the Celery worker is running.')
    } catch (err) {
      setError(err?.response ? parseApiError(err).message : err.message)
    } finally {
      setRunning(false)
    }
  }

  const run = last?.last_run
  const minutes = last ? Math.round(last.interval_seconds / 60) : null
  return (
    <div className="panel mb-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <Radar className="mt-0.5 size-5 shrink-0 text-harbor" aria-hidden />
        <div>
          <p className="font-semibold">Overdue monitor</p>
          <p className="text-[0.85rem] text-steel">
            {run ? (
              <>
                Last scan {relativeTime(run.scanned_at)}: {run.overdue_found} overdue shipments, {run.alerts_created} new
                alerts, {run.alerts_resolved} resolved.
              </>
            ) : (
              'No scan has reported yet.'
            )}{' '}
            {minutes !== null && `Runs automatically every ${minutes === 1 ? 'minute' : `${minutes} minutes`}.`}
          </p>
          {error && <p className="mt-1 text-[0.85rem] text-danger" role="alert">{error}</p>}
        </div>
      </div>
      <button type="button" className="btn btn-secondary shrink-0" onClick={runScan} disabled={running}>
        {running ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Radar className="size-4" aria-hidden />}
        {running ? 'Scanning…' : 'Run scan now'}
      </button>
    </div>
  )
}

export default function Alerts() {
  const { notify } = useToast()
  const [status, setStatus] = useState('active')
  const [severity, setSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const q = useDebounced(search, 300)
  const { data, error, loading, reload } = useApi(
    () => api.alerts.list({ status, severity, search: q, page, page_size: 20 }),
    [status, severity, q, page],
  )
  const counts = useApi(() => api.alerts.counts(), [])
  const [resolving, setResolving] = useState(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [resolveError, setResolveError] = useState(null)

  const refreshAll = () => {
    reload({ silent: true })
    counts.reload({ silent: true })
  }

  async function confirmResolve(e) {
    e.preventDefault()
    setBusy(true)
    setResolveError(null)
    try {
      await api.alerts.resolve(resolving.id, note.trim() || null)
      notify(`Alert for ${resolving.shipment.tracking_id} resolved`)
      setResolving(null)
      refreshAll()
    } catch (err) {
      setResolveError(parseApiError(err).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Alerts"
        description="Shipments that missed their ETA. Alerts close on their own when a shipment is delivered or its ETA is revised."
      />
      <ScanPanel onFinished={refreshAll} />

      <div className="panel overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-rule p-4 lg:flex-row lg:items-center">
          <div role="tablist" aria-label="Alert status" className="flex rounded-md border border-rule p-0.5">
            {TABS.map((t) => (
              <button
                key={t.label}
                role="tab"
                type="button"
                aria-selected={status === t.value}
                onClick={() => { setStatus(t.value); setPage(1) }}
                className={`rounded px-3.5 py-1.5 text-[0.85rem] font-semibold transition-colors ${
                  status === t.value ? 'bg-hull text-white' : 'text-steel hover:text-ink'
                }`}
              >
                {t.label}
                {t.value === 'active' && counts.data && <span className="num ml-1.5 opacity-80">{counts.data.active}</span>}
              </button>
            ))}
          </div>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fog" />
            <input type="search" aria-label="Search alerts" className="input pl-9" placeholder="Search tracking ID or customer" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
          </div>
          <select className="input lg:w-44" aria-label="Severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1) }}>
            <option value="">Any severity</option>
            {SEVERITIES.map((s) => <option key={s} value={s}>{SEVERITY_META[s].label}</option>)}
          </select>
        </div>

        {error && <div className="p-4"><ErrorState error={error} onRetry={reload} /></div>}
        {!error && !data && loading && <LoadingState label="Loading alerts…" />}
        {data && (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[860px]">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Shipment</th>
                    <th>Issue</th>
                    <th>Raised</th>
                    <th>Outcome</th>
                    <th><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((a) => (
                    <tr key={a.id}>
                      <td><SeverityBadge severity={a.severity} /></td>
                      <td>
                        <Link to={`/shipments/${a.shipment.id}`} className="hover:underline"><TrackingCode value={a.shipment.tracking_id} /></Link>
                        <span className="block text-[0.8rem] text-steel">{a.shipment.customer_name}</span>
                      </td>
                      <td className="max-w-[340px]">
                        <p className="text-[0.85rem]">{a.message}</p>
                        <div className="mt-1"><StatusBadge status={a.shipment.status} size="sm" /></div>
                      </td>
                      <td className="text-[0.85rem] whitespace-nowrap">
                        <span className="block">{relativeTime(a.created_at)}</span>
                        <span className="num text-steel">{formatFull(a.created_at)}</span>
                      </td>
                      <td className="max-w-[240px] text-[0.85rem]">
                        {a.status === 'active' ? (
                          <span className="font-semibold text-st-delayed">Open</span>
                        ) : (
                          <>
                            <span className="block">{a.resolution_note || 'Resolved'}</span>
                            <span className="text-steel">
                              {a.resolved_by?.startsWith('system') ? 'Automatically' : 'By operator'}, {relativeTime(a.resolved_at)}
                            </span>
                          </>
                        )}
                      </td>
                      <td className="text-right">
                        {a.status === 'active' && (
                          <button type="button" className="btn btn-secondary" onClick={() => { setNote(''); setResolveError(null); setResolving(a) }}>
                            Resolve
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.items.length === 0 && (
                <EmptyState title={status === 'active' ? 'No open alerts' : 'No alerts found'}>
                  {status === 'active' ? 'Every active shipment is within its ETA.' : 'Try another filter.'}
                </EmptyState>
              )}
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={setPage} />
          </>
        )}
      </div>

      <Modal
        open={Boolean(resolving)}
        onClose={() => setResolving(null)}
        title={`Resolve alert for ${resolving?.shipment.tracking_id ?? ''}`}
        footer={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setResolving(null)}>Cancel</button>
            <button type="submit" form="resolve-form" className="btn btn-primary" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
              Resolve alert
            </button>
          </>
        }
      >
        <form id="resolve-form" onSubmit={confirmResolve} className="flex flex-col gap-3">
          <p className="text-[0.88rem] text-steel">
            The monitor will not raise this alert again for the same ETA. Revise the shipment&apos;s ETA if the carrier has
            given a new arrival time.
          </p>
          <Field label="Resolution note" htmlFor="resolve-note">
            <input id="resolve-note" className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="e.g. Customer informed, carrier rebooking" />
          </Field>
          {resolveError && <p className="text-[0.85rem] text-danger" role="alert">{resolveError}</p>}
        </form>
      </Modal>
    </div>
  )
}

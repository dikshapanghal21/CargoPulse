import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, RefreshCw } from 'lucide-react'
import { api } from '../api'
import { useApi } from '../hooks/useApi'
import { CarrierOnTime, ModeMix, StatusBars, VolumeChart } from '../components/charts'
import {
  EmptyState,
  ErrorState,
  ModeIcon,
  Panel,
  SeverityBadge,
  Skeleton,
  StatusBadge,
  TrackingCode,
} from '../components/ui'
import {
  formatDateTime,
  formatDuration,
  formatNumber,
  formatPercent,
  laneLabel,
  relativeTime,
} from '../utils/format'

const REFRESH_MS = 60_000

function Kpi({ label, value, to, note, attention }) {
  return (
    <Link
      to={to}
      className="group flex min-w-0 flex-col justify-between gap-3 px-5 py-5 transition-colors hover:bg-white/[0.04] focus-visible:outline-signal"
    >
      <span className="flex items-center gap-2 text-[0.9rem] font-medium text-white/70 group-hover:text-white">
        {attention && <span className="size-2 rounded-full bg-signal" aria-hidden />}
        {label}
      </span>
      <span className="stencil text-[2.75rem] leading-none font-bold text-white sm:text-[3.1rem]">
        {formatNumber(value)}
      </span>
      <span className="text-[0.82rem] text-white/60">{note}</span>
    </Link>
  )
}

function KpiBand({ summary }) {
  return (
    <section
      aria-label="Shipment totals"
      className="band-in grid grid-cols-2 overflow-hidden rounded-lg bg-hull lg:grid-cols-4 [&>*]:border-white/10 [&>*:nth-child(odd)]:border-r lg:[&>*]:border-r lg:[&>*:last-child]:border-r-0 [&>*:nth-child(-n+2)]:border-b lg:[&>*:nth-child(-n+2)]:border-b-0"
    >
      <Kpi
        label="Total shipments"
        value={summary.total_shipments}
        to="/shipments"
        note={`${formatNumber(summary.pending)} awaiting pickup`}
      />
      <Kpi
        label="In transit"
        value={summary.in_transit}
        to="/shipments?status=picked_up,in_transit,out_for_delivery"
        note={`${formatNumber(summary.due_next_7_days)} due in the next 7 days`}
      />
      <Kpi
        label="Delivered"
        value={summary.delivered}
        to="/shipments?status=delivered"
        note={`${formatPercent(summary.on_time_rate)} on time`}
      />
      <Kpi
        label="Delayed"
        value={summary.delayed}
        to="/shipments?status=delayed"
        attention={summary.delayed > 0}
        note={
          summary.overdue > summary.delayed
            ? `${formatNumber(summary.overdue)} past ETA, awaiting next scan`
            : `${formatNumber(summary.active_alerts)} open alerts`
        }
      />
    </section>
  )
}

function ShipmentRow({ s, right }) {
  const navigate = useNavigate()
  return (
    <tr className="row-link" onClick={() => navigate(`/shipments/${s.id}`)}>
      <td>
        <Link to={`/shipments/${s.id}`} className="block" onClick={(e) => e.stopPropagation()}>
          <TrackingCode value={s.tracking_id} />
        </Link>
        <span className="block truncate text-[0.8rem] text-steel">{s.customer_name}</span>
      </td>
      <td className="hidden sm:table-cell">
        <span className="flex items-center gap-1.5 text-[0.88rem]">
          <ModeIcon mode={s.route.mode} className="size-4 shrink-0 text-fog" />
          <span className="truncate">{laneLabel(s.route)}</span>
        </span>
        <span className="block text-[0.8rem] text-steel">{s.carrier.name}</span>
      </td>
      <td>
        <StatusBadge status={s.status} size="sm" />
      </td>
      <td className="text-right whitespace-nowrap">{right}</td>
    </tr>
  )
}

function ScanNote({ lastScan }) {
  if (!lastScan) return <span>Overdue monitor has not reported yet</span>
  return (
    <span>
      Overdue scan ran {relativeTime(lastScan.scanned_at)}: {lastScan.overdue_found} overdue,{' '}
      {lastScan.alerts_created} new alerts.
    </span>
  )
}

export default function Dashboard() {
  const { data, error, loading, reload } = useApi(() => api.dashboard({ trend_days: 30 }), [])
  const [updatedAt, setUpdatedAt] = useState(null)

  useEffect(() => {
    if (data) setUpdatedAt(new Date())
  }, [data])

  useEffect(() => {
    const t = setInterval(() => reload({ silent: true }), REFRESH_MS)
    return () => clearInterval(t)
  }, [reload])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="condensed text-[1.9rem] leading-tight font-bold tracking-tight">Operations overview</h1>
          <p className="mt-1 text-[0.88rem] text-steel">
            {data ? <ScanNote lastScan={data.last_scan} /> : 'Live figures from the shipment database'}
            {updatedAt && <span className="ml-1">Figures refreshed {formatDateTime(updatedAt)}.</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => reload()} disabled={loading}>
            <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} aria-hidden /> Refresh
          </button>
          <Link to="/shipments/new" className="btn btn-primary">
            <Plus className="size-4" aria-hidden /> New shipment
          </Link>
        </div>
      </div>

      {error && !data && <ErrorState error={error} onRetry={reload} />}

      {!data && loading && (
        <div className="flex flex-col gap-6" aria-busy="true">
          <Skeleton className="h-[148px] rounded-lg" />
          <div className="grid gap-6 lg:grid-cols-3">
            <Skeleton className="h-[320px] lg:col-span-2" />
            <Skeleton className="h-[320px]" />
          </div>
        </div>
      )}

      {data && (
        <>
          {error && <ErrorState error={error} onRetry={reload} compact />}
          <KpiBand summary={data.summary} />

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel
              className="lg:col-span-2"
              title="Shipment volume"
              subtitle="Dispatched and delivered per day, last 30 days"
            >
              <VolumeChart data={data.volume_trend} />
            </Panel>
            <Panel title="By status" subtitle="Select a bar to see those shipments">
              <StatusBars data={data.status_breakdown} />
            </Panel>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Panel
              accent={data.active_alerts.length > 0}
              className="lg:col-span-3"
              title="Active alerts"
              subtitle={`${formatNumber(data.summary.active_alerts)} open, ${formatNumber(
                data.summary.critical_alerts,
              )} critical`}
              actions={
                <Link to="/alerts" className="text-[0.85rem] font-semibold text-harbor hover:underline">
                  Manage alerts
                </Link>
              }
              bodyClass=""
            >
              {data.active_alerts.length === 0 ? (
                <EmptyState title="No open alerts">Every active shipment is on schedule.</EmptyState>
              ) : (
                <ul className="divide-y divide-rule-soft">
                  {data.active_alerts.map((a) => {
                    const hours = (Date.now() - new Date(a.shipment.eta).getTime()) / 36e5
                    return (
                      <li key={a.id}>
                        <Link
                          to={`/shipments/${a.shipment.id}`}
                          className="grid grid-cols-[76px_1fr_auto] items-center gap-3 px-4 py-3 hover:bg-[#f6f9fc] sm:grid-cols-[88px_1fr_auto]"
                        >
                          <SeverityBadge severity={a.severity} />
                          <span className="min-w-0">
                            <TrackingCode value={a.shipment.tracking_id} className="block truncate text-[0.88rem] whitespace-nowrap" />
                            <span className="block truncate text-[0.8rem] text-steel">
                              {a.shipment.customer_name}
                            </span>
                          </span>
                          <span className="text-right text-[0.82rem]">
                            <span className="num block font-semibold text-ink">
                              {hours > 0 ? `${formatDuration(hours)} late` : 'ETA revised'}
                            </span>
                            <span className="hidden text-steel sm:inline">raised {relativeTime(a.created_at)}</span>
                          </span>
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Panel>

            <Panel
              className="lg:col-span-2"
              title="Upcoming deliveries"
              subtitle="Due within 7 days"
              bodyClass=""
              actions={
                <Link
                  to="/shipments?overdue=false&sort_by=eta&sort_order=asc&status=pending,picked_up,in_transit,out_for_delivery"
                  className="text-[0.85rem] font-semibold text-harbor hover:underline"
                >
                  View all
                </Link>
              }
            >
              {data.upcoming_deliveries.length === 0 ? (
                <EmptyState title="Nothing due this week" />
              ) : (
                <ul className="divide-y divide-rule-soft">
                  {data.upcoming_deliveries.map((s) => (
                    <li key={s.id}>
                      <Link
                        to={`/shipments/${s.id}`}
                        className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-[#f6f9fc]"
                      >
                        <span className="min-w-0">
                          <TrackingCode value={s.tracking_id} className="text-[0.88rem]" />
                          <span className="flex items-center gap-1.5 truncate text-[0.8rem] text-steel">
                            <ModeIcon mode={s.route.mode} className="size-3.5 shrink-0" />
                            {s.route.destination_city}
                          </span>
                        </span>
                        <span className="text-right">
                          <span className="num block text-[0.88rem] font-semibold">{relativeTime(s.eta)}</span>
                          <span className="text-[0.78rem] text-steel">{formatDateTime(s.eta)}</span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Panel className="lg:col-span-3" title="Carrier on-time rate" subtitle="Delivered on or before ETA">
              <CarrierOnTime data={data.carrier_performance} />
            </Panel>
            <Panel className="lg:col-span-2" title="Transport mode" subtitle="Share of shipments and performance by mode">
              <ModeMix data={data.mode_breakdown} />
            </Panel>
          </div>

          <Panel
            title="Recent shipments"
            subtitle="Latest bookings"
            bodyClass="overflow-x-auto"
            actions={
              <Link to="/shipments" className="text-[0.85rem] font-semibold text-harbor hover:underline">
                All shipments
              </Link>
            }
          >
            {data.recent_shipments.length === 0 ? (
              <EmptyState
                title="No shipments yet"
                action={
                  <Link to="/shipments/new" className="btn btn-primary">
                    Create the first shipment
                  </Link>
                }
              />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Shipment</th>
                    <th className="hidden sm:table-cell">Lane</th>
                    <th>Status</th>
                    <th className="text-right">ETA</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_shipments.map((s) => (
                    <ShipmentRow
                      key={s.id}
                      s={s}
                      right={
                        <span className={s.is_overdue ? 'font-semibold text-st-delayed' : ''}>
                          {formatDateTime(s.eta)}
                        </span>
                      }
                    />
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </div>
  )
}

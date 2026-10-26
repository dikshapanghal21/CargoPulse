import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, Plus, Search, X } from 'lucide-react'
import { api } from '../api'
import { useApi, useDebounced } from '../hooks/useApi'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  ModeIcon,
  PageHeader,
  Pagination,
  PriorityTag,
  StatusBadge,
  TrackingCode,
} from '../components/ui'
import {
  MODES,
  MODE_META,
  PRIORITIES,
  PRIORITY_META,
  STATUSES,
  STATUS_META,
  formatDateTime,
  formatDuration,
  formatWeight,
} from '../utils/format'

const PAGE_SIZE = 20

const COLUMNS = [
  { key: 'tracking_id', label: 'Shipment', sortable: true },
  { key: 'origin', label: 'Lane', sortable: true },
  { key: 'carrier', label: 'Carrier', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'priority', label: 'Priority', sortable: true },
  { key: 'eta', label: 'ETA', sortable: true },
  { key: 'weight_kg', label: 'Weight', sortable: true, align: 'right' },
]

function SortHeader({ column, sortBy, sortOrder, onSort }) {
  if (!column.sortable) return <th>{column.label}</th>
  const active = sortBy === column.key
  const Icon = !active ? ArrowUpDown : sortOrder === 'asc' ? ArrowUp : ArrowDown
  return (
    <th
      className={column.align === 'right' ? 'text-right' : ''}
      aria-sort={active ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => onSort(column.key)}
        className={`inline-flex items-center gap-1 hover:text-ink ${active ? 'text-ink' : ''}`}
      >
        {column.label}
        <Icon className={`size-3.5 ${active ? '' : 'opacity-40'}`} aria-hidden />
      </button>
    </th>
  )
}

export default function Shipments() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState(params.get('search') || '')
  const debouncedSearch = useDebounced(searchText, 350)

  const filters = {
    search: params.get('search') || '',
    status: params.get('status') || '',
    carrier_id: params.get('carrier_id') || '',
    route_id: params.get('route_id') || '',
    priority: params.get('priority') || '',
    mode: params.get('mode') || '',
    overdue: params.get('overdue') || '',
    sort_by: params.get('sort_by') || 'created_at',
    sort_order: params.get('sort_order') || 'desc',
    page: Number(params.get('page') || 1),
  }
  const selectedStatuses = useMemo(
    () => (filters.status ? filters.status.split(',').filter(Boolean) : []),
    [filters.status],
  )

  function update(patch, { resetPage = true } = {}) {
    const next = new URLSearchParams(params)
    Object.entries(patch).forEach(([k, v]) => {
      if (v === '' || v === null || v === undefined) next.delete(k)
      else next.set(k, String(v))
    })
    if (resetPage && !('page' in patch)) next.delete('page')
    setParams(next, { replace: true })
  }

  useEffect(() => {
    if (debouncedSearch !== filters.search) update({ search: debouncedSearch.trim() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch])

  const { data: carriers } = useApi(() => api.carriers.list({ page_size: 100 }), [])

  const queryKey = params.toString()
  const { data, error, loading, reload } = useApi(
    () =>
      api.shipments.list({
        ...filters,
        page: filters.page,
        page_size: PAGE_SIZE,
      }),
    [queryKey],
  )

  function toggleStatus(status) {
    const set = new Set(selectedStatuses)
    if (set.has(status)) set.delete(status)
    else set.add(status)
    update({ status: STATUSES.filter((s) => set.has(s)).join(',') })
  }

  function onSort(key) {
    if (filters.sort_by === key) update({ sort_order: filters.sort_order === 'asc' ? 'desc' : 'asc' })
    else update({ sort_by: key, sort_order: key === 'eta' ? 'asc' : 'desc' })
  }

  const activeFilterCount = ['search', 'status', 'carrier_id', 'route_id', 'priority', 'mode', 'overdue'].filter(
    (k) => filters[k],
  ).length

  function clearAll() {
    setSearchText('')
    setParams(new URLSearchParams(), { replace: true })
  }

  return (
    <div>
      <PageHeader
        title="Shipments"
        description="Search every booking by tracking ID, customer, reference, city or carrier."
        actions={
          <Link to="/shipments/new" className="btn btn-primary">
            <Plus className="size-4" aria-hidden /> New shipment
          </Link>
        }
      />

      <div className="panel mb-4 flex flex-col gap-4 p-4">
        <div className="grid gap-3 md:grid-cols-[minmax(220px,1.6fr)_repeat(4,minmax(0,1fr))]">
          <div className="relative">
            <label htmlFor="shipment-search" className="sr-only">
              Search shipments
            </label>
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fog" />
            <input
              id="shipment-search"
              type="search"
              className="input pl-9"
              placeholder="Search tracking ID, customer, city…"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </div>
          <select
            className="input"
            aria-label="Carrier"
            value={filters.carrier_id}
            onChange={(e) => update({ carrier_id: e.target.value })}
          >
            <option value="">All carriers</option>
            {carriers?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className="input"
            aria-label="Transport mode"
            value={filters.mode}
            onChange={(e) => update({ mode: e.target.value })}
          >
            <option value="">All modes</option>
            {MODES.map((m) => (
              <option key={m} value={m}>
                {MODE_META[m].label}
              </option>
            ))}
          </select>
          <select
            className="input"
            aria-label="Priority"
            value={filters.priority}
            onChange={(e) => update({ priority: e.target.value })}
          >
            <option value="">Any priority</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_META[p].label}
              </option>
            ))}
          </select>
          <select
            className="input"
            aria-label="Schedule"
            value={filters.overdue}
            onChange={(e) => update({ overdue: e.target.value })}
          >
            <option value="">Any schedule</option>
            <option value="true">Past ETA only</option>
            <option value="false">On schedule only</option>
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
          {STATUSES.map((s) => {
            const on = selectedStatuses.includes(s)
            return (
              <button
                key={s}
                type="button"
                aria-pressed={on}
                onClick={() => toggleStatus(s)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[0.82rem] font-medium transition-colors ${
                  on
                    ? 'border-hull bg-hull text-white'
                    : 'border-rule bg-surface text-steel hover:border-fog hover:text-ink'
                }`}
              >
                <span className="size-2 rounded-full" style={{ background: STATUS_META[s].color }} aria-hidden />
                {STATUS_META[s].label}
              </button>
            )
          })}
          {activeFilterCount > 0 && (
            <button type="button" className="btn btn-ghost ml-auto" onClick={clearAll}>
              <X className="size-4" aria-hidden /> Clear filters
            </button>
          )}
        </div>
      </div>

      <div className="panel overflow-hidden">
        {error && (
          <div className="p-4">
            <ErrorState error={error} onRetry={reload} />
          </div>
        )}
        {!error && !data && loading && <LoadingState label="Loading shipments…" />}
        {data && (
          <>
            <div className={`overflow-x-auto transition-opacity ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
              <table className="table min-w-[920px]">
                <thead>
                  <tr>
                    {COLUMNS.map((c) => (
                      <SortHeader
                        key={c.key}
                        column={c}
                        sortBy={filters.sort_by}
                        sortOrder={filters.sort_order}
                        onSort={onSort}
                      />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((s) => (
                    <tr key={s.id} className="row-link" onClick={() => navigate(`/shipments/${s.id}`)}>
                      <td>
                        <Link to={`/shipments/${s.id}`} onClick={(e) => e.stopPropagation()}>
                          <TrackingCode value={s.tracking_id} />
                        </Link>
                        <span className="block max-w-[220px] truncate text-[0.8rem] text-steel">
                          {s.customer_name}
                          {s.reference ? `, ${s.reference}` : ''}
                        </span>
                      </td>
                      <td>
                        <span className="flex items-center gap-1.5">
                          <ModeIcon mode={s.route.mode} className="size-4 shrink-0 text-fog" />
                          <span className="whitespace-nowrap">
                            {s.route.origin_city} → {s.route.destination_city}
                          </span>
                        </span>
                        <span className="code block text-[0.72rem] font-medium text-fog">{s.route.code}</span>
                      </td>
                      <td className="whitespace-nowrap">{s.carrier.name}</td>
                      <td>
                        <StatusBadge status={s.status} size="sm" />
                      </td>
                      <td>
                        <PriorityTag priority={s.priority} />
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="num">{formatDateTime(s.eta)}</span>
                        {s.is_overdue && (
                          <span className="block text-[0.78rem] font-semibold text-st-delayed">
                            {formatDuration(s.hours_overdue)} overdue
                          </span>
                        )}
                      </td>
                      <td className="num text-right whitespace-nowrap">{formatWeight(s.weight_kg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.items.length === 0 && (
                <EmptyState
                  title="No shipments match these filters"
                  action={
                    activeFilterCount > 0 ? (
                      <button type="button" className="btn btn-secondary" onClick={clearAll}>
                        Clear filters
                      </button>
                    ) : (
                      <Link to="/shipments/new" className="btn btn-primary">
                        Create a shipment
                      </Link>
                    )
                  }
                >
                  Try a different search term or remove a filter.
                </EmptyState>
              )}
            </div>
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              pageSize={data.page_size}
              onPage={(p) => update({ page: p }, { resetPage: false })}
            />
          </>
        )}
      </div>
    </div>
  )
}

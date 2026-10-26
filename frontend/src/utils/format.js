export const STATUS_META = {
  pending: { label: 'Pending', color: 'var(--color-st-pending)' },
  picked_up: { label: 'Picked up', color: 'var(--color-st-picked)' },
  in_transit: { label: 'In transit', color: 'var(--color-st-transit)' },
  out_for_delivery: { label: 'Out for delivery', color: 'var(--color-st-ofd)' },
  delayed: { label: 'Delayed', color: 'var(--color-st-delayed)' },
  delivered: { label: 'Delivered', color: 'var(--color-st-delivered)' },
  cancelled: { label: 'Cancelled', color: 'var(--color-st-cancelled)' },
}
export const STATUSES = Object.keys(STATUS_META)

export const PRIORITY_META = {
  standard: { label: 'Standard' },
  express: { label: 'Express' },
  critical: { label: 'Critical' },
}
export const PRIORITIES = Object.keys(PRIORITY_META)

export const MODE_META = {
  ocean: { label: 'Ocean', series: 'var(--color-series-1)' },
  air: { label: 'Air', series: 'var(--color-series-2)' },
  road: { label: 'Road', series: 'var(--color-series-3)' },
  rail: { label: 'Rail', series: 'var(--color-series-4)' },
}
export const MODES = Object.keys(MODE_META)

export const SEVERITY_META = {
  low: { label: 'Low', color: '#7b8794', rank: 1 },
  medium: { label: 'Medium', color: '#d99a00', rank: 2 },
  high: { label: 'High', color: '#d9622b', rank: 3 },
  critical: { label: 'Critical', color: '#c0262d', rank: 4 },
}
export const SEVERITIES = Object.keys(SEVERITY_META)

export const statusLabel = (s) => STATUS_META[s]?.label ?? s

const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})
const fullFmt = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const numFmt = new Intl.NumberFormat()

export const formatDate = (v) => (v ? dateFmt.format(new Date(v)) : '—')
export const formatDateTime = (v) => (v ? dateTimeFmt.format(new Date(v)) : '—')
export const formatFull = (v) => (v ? fullFmt.format(new Date(v)) : '—')
export const formatNumber = (v) => (v === null || v === undefined ? '—' : numFmt.format(v))
export const formatWeight = (kg) => {
  if (kg === null || kg === undefined) return '—'
  return kg >= 1000 ? `${numFmt.format(Math.round(kg / 100) / 10)} t` : `${numFmt.format(kg)} kg`
}
export const formatPercent = (v) => (v === null || v === undefined ? '—' : `${v.toFixed(1)}%`)

export function formatDuration(hours) {
  if (hours === null || hours === undefined) return '—'
  const h = Math.abs(hours)
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`
  if (h < 48) return `${Math.round(h)} h`
  return `${Math.round(h / 24)} days`
}

export function relativeTime(value, now = Date.now()) {
  if (!value) return '—'
  const diffMs = new Date(value).getTime() - now
  const abs = Math.abs(diffMs)
  const mins = Math.round(abs / 60000)
  let text
  if (mins < 1) text = 'moments'
  else if (mins < 60) text = `${mins} min`
  else if (mins < 60 * 48) text = `${Math.round(mins / 60)} h`
  else text = `${Math.round(mins / 1440)} days`
  if (text === 'moments') return diffMs >= 0 ? 'in moments' : 'just now'
  return diffMs >= 0 ? `in ${text}` : `${text} ago`
}

/** <input type="datetime-local"> value (local time) <-> ISO string (UTC). */
export function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
export function fromLocalInput(value) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

export const laneLabel = (route) =>
  route ? `${route.origin_city} → ${route.destination_city}` : '—'

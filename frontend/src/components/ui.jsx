import { useEffect, useId, useRef } from 'react'
import {
  AlertOctagon,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Info,
  Loader2,
  Plane,
  RefreshCw,
  Ship,
  TrainFront,
  Truck,
  X,
} from 'lucide-react'
import { MODE_META, PRIORITY_META, SEVERITY_META, STATUS_META } from '../utils/format'

export function StatusBadge({ status, size = 'md' }) {
  const meta = STATUS_META[status] || { label: status, color: 'var(--color-fog)' }
  const pad = size === 'sm' ? 'px-2 py-0.5 text-[0.75rem]' : 'px-2.5 py-1 text-[0.8rem]'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-rule bg-surface font-medium whitespace-nowrap text-ink ${pad}`}
    >
      <span className="size-2 shrink-0 rounded-full" style={{ background: meta.color }} aria-hidden />
      {meta.label}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const meta = SEVERITY_META[severity] || SEVERITY_META.low
  const Icon = severity === 'critical' ? AlertOctagon : severity === 'low' ? Info : AlertTriangle
  return (
    <span className="inline-flex items-center gap-1 text-[0.8rem] font-semibold whitespace-nowrap text-ink">
      <Icon className="size-4 shrink-0" style={{ color: meta.color }} aria-hidden />
      {meta.label}
    </span>
  )
}

export function PriorityTag({ priority }) {
  if (!priority || priority === 'standard') {
    return <span className="text-[0.82rem] text-steel">Standard</span>
  }
  const critical = priority === 'critical'
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[0.75rem] font-semibold ${
        critical ? 'bg-danger-soft text-danger' : 'bg-harbor-soft text-harbor'
      }`}
    >
      {PRIORITY_META[priority]?.label ?? priority}
    </span>
  )
}

const MODE_ICONS = { ocean: Ship, air: Plane, road: Truck, rail: TrainFront }

export function ModeIcon({ mode, className = 'size-4' }) {
  const Icon = MODE_ICONS[mode] || Truck
  return <Icon className={className} aria-label={MODE_META[mode]?.label ?? mode} />
}

export function ModeTag({ mode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[0.85rem] text-steel">
      <ModeIcon mode={mode} className="size-4 text-fog" />
      {MODE_META[mode]?.label ?? mode}
    </span>
  )
}

export function TrackingCode({ value, className = '' }) {
  return <span className={`code text-ink ${className}`}>{value}</span>
}

export function LoadingState({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-14 text-steel ${className}`} role="status">
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <span>{label}</span>
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded bg-rule-soft ${className}`} aria-hidden />
}

export function ErrorState({ error, onRetry, compact = false }) {
  return (
    <div
      role="alert"
      className={`flex flex-col items-start gap-3 rounded-md border border-danger/30 bg-danger-soft ${
        compact ? 'p-3' : 'p-5'
      }`}
    >
      <div className="flex items-start gap-2">
        <AlertOctagon className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
        <div>
          <p className="font-semibold text-ink">
            {error?.status === 404 ? 'Not found' : 'Could not load this data'}
          </p>
          <p className="text-sm text-steel">{error?.message || 'Something went wrong.'}</p>
        </div>
      </div>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={() => onRetry()}>
          <RefreshCw className="size-4" aria-hidden /> Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children, action }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <p className="max-w-md text-sm text-steel">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function PageHeader({ title, description, actions, back }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back}
        <h1 className="text-[1.9rem] leading-tight font-bold tracking-tight text-ink condensed">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-steel">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Pagination({ page, pages, total, pageSize, onPage }) {
  if (!total) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-4 py-3 text-sm text-steel">
      <span className="num">
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="btn btn-ghost"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" /> Previous
        </button>
        <span className="num px-2 text-ink">
          Page {page} of {pages}
        </span>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          aria-label="Next page"
        >
          Next <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  )
}

export function Field({ label, error, hint, children, htmlFor, required }) {
  return (
    <div>
      {label && (
        <label className="label" htmlFor={htmlFor}>
          {label}
          {required && <span className="ml-0.5 text-danger" aria-hidden>*</span>}
        </label>
      )}
      {children}
      {error ? <p className="field-error">{error}</p> : hint ? <p className="hint">{hint}</p> : null}
    </div>
  )
}

export function Modal({ open, title, onClose, children, footer, width = 'max-w-lg' }) {
  const titleId = useId()
  const panelRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    const prev = document.activeElement
    const first = panelRef.current?.querySelector('input, select, textarea, button')
    first?.focus()
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      prev?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-hull/50 p-0 sm:items-center sm:p-6">
      <div className="absolute inset-0" onClick={onClose} aria-hidden />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`relative flex max-h-[92vh] w-full ${width} flex-col rounded-t-lg bg-surface shadow-[0_24px_60px_-20px_rgba(19,40,61,0.45)] sm:rounded-lg`}
      >
        <div className="flex items-center justify-between border-b border-rule px-5 py-4">
          <h2 id={titleId} className="text-lg font-bold text-ink">
            {title}
          </h2>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-rule px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onClose, busy, error }) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>
            Keep it
          </button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" />}
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-steel">{message}</p>
      {error && (
        <div className="mt-3">
          <ErrorState error={error} compact />
        </div>
      )}
    </Modal>
  )
}

export function Panel({ title, subtitle, actions, children, className = '', bodyClass = 'p-4', accent }) {
  return (
    <section className={`panel overflow-hidden ${className}`}>
      {(title || actions) && (
        <header
          className={`flex flex-wrap items-start justify-between gap-2 border-b border-rule-soft px-4 py-3 ${
            accent ? 'border-t-[3px] border-t-signal' : ''
          }`}
        >
          <div>
            {title && <h2 className="text-[1rem] font-bold text-ink">{title}</h2>}
            {subtitle && <p className="text-[0.8rem] text-steel">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

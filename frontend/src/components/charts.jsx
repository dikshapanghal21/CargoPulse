import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { MODE_META, STATUS_META, formatNumber } from '../utils/format'
import { ModeIcon } from './ui'

const INK = '#16222e'
const STEEL = '#586a7b'
const FOG = '#8796a4'
const GRID = '#e7ecef'
const AXIS = '#d7dee4'
const SERIES_1 = '#2a78d6'
const SERIES_2 = '#eb6834'
const NEUTRAL_BAR = '#2b4c6b'
const DELAYED = '#c4471d'

const shortDate = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' })
const longDate = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
const parseDay = (d) => new Date(`${d}T00:00:00`)

function TooltipBox({ title, rows }) {
  return (
    <div className="min-w-40 rounded-md border border-rule bg-surface px-3 py-2 text-[0.8rem] shadow-[0_8px_24px_-12px_rgba(19,40,61,0.35)]">
      <p className="mb-1 font-semibold text-ink">{title}</p>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 text-steel">
          <span className="flex items-center gap-1.5">
            {r.color && <span className="h-0.5 w-3 rounded" style={{ background: r.color }} aria-hidden />}
            {r.label}
          </span>
          <span className="num font-semibold text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

function LegendKey({ color, label, value }) {
  return (
    <span className="flex items-center gap-2 text-[0.85rem] text-steel">
      <span className="h-[3px] w-4 rounded-full" style={{ background: color }} aria-hidden />
      {label}
      {value !== undefined && <span className="num font-semibold text-ink">{formatNumber(value)}</span>}
    </span>
  )
}

export function VolumeChart({ data }) {
  const totals = useMemo(
    () =>
      data.reduce(
        (acc, p) => ({ shipped: acc.shipped + p.shipped, delivered: acc.delivered + p.delivered }),
        { shipped: 0, delivered: 0 },
      ),
    [data],
  )
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1" aria-label="Legend">
        <LegendKey color={SERIES_1} label="Dispatched" value={totals.shipped} />
        <LegendKey color={SERIES_2} label="Delivered" value={totals.delivered} />
      </div>
      <div className="h-[240px]" role="img" aria-label="Daily dispatched and delivered shipments">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="date"
              tickFormatter={(d) => shortDate.format(parseDay(d))}
              tick={{ fill: FOG, fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: AXIS }}
              minTickGap={28}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: FOG, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={44}
            />
            <Tooltip
              cursor={{ stroke: AXIS, strokeWidth: 1 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={longDate.format(parseDay(label))}
                    rows={[
                      { label: 'Dispatched', value: payload.find((p) => p.dataKey === 'shipped')?.value ?? 0, color: SERIES_1 },
                      { label: 'Delivered', value: payload.find((p) => p.dataKey === 'delivered')?.value ?? 0, color: SERIES_2 },
                    ]}
                  />
                ) : null
              }
            />
            <Area
              type="monotone"
              dataKey="shipped"
              stroke="none"
              fill={SERIES_1}
              fillOpacity={0.1}
              isAnimationActive={false}
              activeDot={false}
              tooltipType="none"
            />
            <Line
              type="monotone"
              dataKey="shipped"
              stroke={SERIES_1}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4.5, stroke: '#fff', strokeWidth: 2 }}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="delivered"
              stroke={SERIES_2}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4.5, stroke: '#fff', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function StatusBars({ data }) {
  const navigate = useNavigate()
  const rows = data.map((d) => ({ ...d, label: STATUS_META[d.status]?.label ?? d.status }))
  return (
    <div className="h-[262px]" role="img" aria-label="Shipments by status">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 4 }} barCategoryGap={8}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={118}
            tick={{ fill: STEEL, fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: AXIS }}
          />
          <Tooltip
            cursor={{ fill: '#f2f5f7' }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipBox
                  title={payload[0].payload.label}
                  rows={[{ label: 'Shipments', value: formatNumber(payload[0].value) }]}
                />
              ) : null
            }
          />
          <Bar
            dataKey="count"
            barSize={20}
            radius={[0, 4, 4, 0]}
            isAnimationActive={false}
            cursor="pointer"
            onClick={(entry) => navigate(`/shipments?status=${entry.status ?? entry.payload?.status}`)}
          >
            {rows.map((r) => (
              <Cell key={r.status} fill={r.status === 'delayed' ? DELAYED : NEUTRAL_BAR} />
            ))}
            <LabelList dataKey="count" position="right" fill={INK} fontSize={12} fontWeight={600} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function CarrierOnTime({ data }) {
  const rows = data
    .filter((d) => d.on_time_rate !== null)
    .map((d) => ({ ...d, rate: d.on_time_rate }))
    .sort((a, b) => b.rate - a.rate)
  if (!rows.length) {
    return <p className="py-10 text-center text-sm text-steel">No delivered shipments yet.</p>
  }
  return (
    <div style={{ height: Math.max(160, rows.length * 34 + 16) }} role="img" aria-label="On-time delivery rate by carrier">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 52, bottom: 4, left: 4 }} barCategoryGap={8}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis
            type="category"
            dataKey="carrier"
            width={150}
            tick={{ fill: STEEL, fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: AXIS }}
          />
          <Tooltip
            cursor={{ fill: '#f2f5f7' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload
              return (
                <TooltipBox
                  title={p.carrier}
                  rows={[
                    { label: 'On time', value: `${p.rate.toFixed(1)}%` },
                    { label: 'Delivered', value: formatNumber(p.delivered) },
                    { label: 'In progress', value: formatNumber(p.active) },
                    { label: 'Delayed now', value: formatNumber(p.delayed) },
                  ]}
                />
              )
            }}
          />
          <Bar dataKey="rate" barSize={18} radius={[0, 4, 4, 0]} fill={SERIES_1} isAnimationActive={false}>
            <LabelList
              dataKey="rate"
              position="right"
              formatter={(v) => `${Number(v).toFixed(0)}%`}
              fill={INK}
              fontSize={12}
              fontWeight={600}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ModeMix({ data }) {
  const total = data.reduce((s, d) => s + d.count, 0)
  const ordered = Object.keys(MODE_META)
    .map((mode) => data.find((d) => d.mode === mode) ?? { mode, count: 0 })
    .filter((d) => d.count > 0)
  if (!total) return <p className="py-10 text-center text-sm text-steel">No shipments yet.</p>
  const pct = (n) => Math.round((n / total) * 100)
  return (
    <div>
      <div className="flex h-5 w-full gap-[2px]" role="img" aria-label="Share of shipments by transport mode">
        {ordered.map((d, i) => (
          <div
            key={d.mode}
            title={`${MODE_META[d.mode].label}: ${d.count} (${pct(d.count)}%)`}
            className={`h-full ${i === 0 ? 'rounded-l' : ''} ${i === ordered.length - 1 ? 'rounded-r' : ''}`}
            style={{ width: `${(d.count / total) * 100}%`, background: MODE_META[d.mode].series }}
          />
        ))}
      </div>
      <table className="mt-4 w-full text-[0.86rem]">
        <thead>
          <tr className="text-left text-[0.76rem] text-steel">
            <th className="pb-2 font-semibold">Mode</th>
            <th className="pb-2 text-right font-semibold">Share</th>
            <th className="pb-2 text-right font-semibold">In progress</th>
            <th className="pb-2 text-right font-semibold">On time</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((d) => (
            <tr key={d.mode} className="border-t border-rule-soft">
              <td className="py-2.5">
                <span className="flex items-center gap-2">
                  <span className="size-2.5 shrink-0 rounded-sm" style={{ background: MODE_META[d.mode].series }} aria-hidden />
                  <ModeIcon mode={d.mode} className="size-4 text-fog" />
                  <span className="text-ink">{MODE_META[d.mode].label}</span>
                </span>
              </td>
              <td className="num py-2.5 text-right">
                <span className="font-semibold text-ink">{d.count}</span>
                <span className="ml-1.5 text-steel">{pct(d.count)}%</span>
              </td>
              <td className="num py-2.5 text-right text-ink">
                {d.active ?? '—'}
                {d.delayed > 0 && <span className="ml-1 text-[0.78rem] font-semibold text-st-delayed">({d.delayed} late)</span>}
              </td>
              <td className="num py-2.5 text-right text-ink">
                {d.on_time_rate === null || d.on_time_rate === undefined ? '—' : `${Math.round(d.on_time_rate)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

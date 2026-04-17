'use client'

import { useState, useEffect, useRef } from 'react'

const API = 'http://localhost:8000'

/* ── Types ───────────────────────────────────────────────── */
interface FinancialsResponse {
  ticker:  string
  periods: string[]                          // ['Sep \'21', ...] oldest → newest
  rows:    Record<string, (number | null)[]>
}

interface FinancialsPanelProps {
  ticker:      string | null
  metricsDiff?: any   // kept for backwards compat, no longer used
  periods?:    any
}

/* ── Row display config ──────────────────────────────────── */
const INCOME_ROWS: Array<{
  key:       string
  label:     string
  indent:    number
  color?:    'fin-blue' | 'fin-green' | 'red' | 'default'
  bold?:     boolean
  divider?:  boolean
  inverted?: boolean  // true = lower is better (debt, SBC, etc.)
}> = [
  { key: 'Revenue',             label: 'Revenue',              indent: 0, color: 'fin-blue',  bold: true },
  { key: 'Gross Margin %',      label: 'Gross Margin',         indent: 1, color: 'default' },
  { key: 'Operating Income',    label: 'Operating Income',     indent: 0, color: 'fin-green', bold: true, divider: true },
  { key: 'Net Income',          label: 'Net Income',           indent: 0, color: 'fin-green', bold: true },
  { key: 'Operating Cash Flow', label: 'Op. Cash Flow',        indent: 1, color: 'fin-green' },
  { key: 'SBC',                 label: 'Stock-Based Comp',     indent: 1, color: 'default',   divider: true, inverted: true },
  { key: 'SBC / Revenue %',     label: 'SBC / Revenue',        indent: 2, color: 'default',   inverted: true },
  { key: 'D&A',                 label: 'Depreciation & Amort', indent: 1, color: 'default' },
  { key: 'CapEx',               label: 'Capital Expenditure',  indent: 1, color: 'default' },
  { key: 'Shares Outstanding',  label: 'Shares Outstanding',   indent: 0, color: 'default',   divider: true, inverted: true },
  { key: 'Receivables',         label: 'Receivables',          indent: 0, color: 'default',   divider: true },
  { key: 'Inventory',           label: 'Inventory',            indent: 1, color: 'default' },
  { key: 'Long-Term Debt',      label: 'Long-Term Debt',       indent: 0, color: 'default',   divider: true, inverted: true },
  { key: 'Goodwill',            label: 'Goodwill',             indent: 1, color: 'default' },
  { key: 'Goodwill Impairment', label: 'Goodwill Impairment',  indent: 2, color: 'red',        inverted: true },
  { key: 'Backlog',             label: 'Backlog',              indent: 0, color: 'fin-blue',  divider: true },
]

/* ── Helpers ─────────────────────────────────────────────── */
function fmtVal(val: number | null, metric: string): string {
  if (val === null || val === undefined) return '—'
  const abs = Math.abs(val)
  if (metric.includes('%')) return `${val.toFixed(1)}%`
  if (abs >= 1e12) return `$${(val / 1e12).toFixed(2)}T`
  if (abs >= 1e9)  return `$${(val / 1e9).toFixed(2)}B`
  if (abs >= 1e6)  return `$${(val / 1e6).toFixed(1)}M`
  if (abs >= 1e3)  return `$${(val / 1e3).toFixed(1)}K`
  return val.toLocaleString()
}

function trendColor(vals: (number | null)[], inverted = false): string {
  const valid = vals.filter((v): v is number => v !== null)
  if (valid.length < 2) return 'var(--text3)'
  const up = valid[valid.length - 1] > valid[0]
  return (inverted ? !up : up) ? '#44ff88' : '#ff5555'
}

function cagr(vals: (number | null)[]): string | null {
  const valid = vals.filter((v): v is number => v !== null && v > 0)
  if (valid.length < 2) return null
  const n = valid.length - 1
  const r = (valid[valid.length - 1] / valid[0]) ** (1 / n) - 1
  return `${r >= 0 ? '+' : ''}${(r * 100).toFixed(1)}%`
}

/* ── Sparkline ───────────────────────────────────────────── */
function Sparkline({ values, inverted = false }: { values: (number | null)[], inverted?: boolean }) {
  const nums = values.filter((v): v is number => v !== null)
  if (nums.length < 2) return <span style={{ color: 'var(--text4)', fontSize: 9 }}>—</span>

  const W = 52, H = 18, PAD = 2
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const range = max - min || 1

  const points: [number, number][] = []
  values.forEach((v, i) => {
    if (v === null) return
    const x = PAD + (i / (values.length - 1)) * (W - PAD * 2)
    const y = PAD + (1 - (v - min) / range) * (H - PAD * 2)
    points.push([x, y])
  })

  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`)
    .join(' ')

  const color = trendColor(values, inverted)
  const last  = points[points.length - 1]

  return (
    <svg width={W} height={H} style={{ display: 'block', overflow: 'visible' }}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.2" strokeLinejoin="round" opacity="0.7" />
      {last && <circle cx={last[0]} cy={last[1]} r="2" fill={color} />}
    </svg>
  )
}

/* ── Single metric row ───────────────────────────────────── */
function FinRow({
  row, values, periods, colWidth,
}: {
  row:      typeof INCOME_ROWS[0]
  values:   (number | null)[]
  periods:  string[]
  colWidth: number
}) {
  const labelColor =
    row.color === 'fin-blue'  ? '#4499ff' :
    row.color === 'fin-green' ? '#44ff88' :
    row.color === 'red'       ? '#ff6666' : 'var(--text2)'

  const valueColor =
    row.color === 'fin-blue'  ? '#4499ff' :
    row.color === 'fin-green' ? '#44ff88' :
    row.color === 'red'       ? '#ff6666' : 'var(--text)'

  const cagrStr = cagr(values)
  const cagrCol = cagrStr ? trendColor(values, row.inverted) : '#333'

  return (
    <>
      {row.divider && <div style={{ borderTop: '1px solid #1a1a1a', margin: '3px 0' }} />}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '3px 0',
        paddingLeft: row.indent * 12,
        borderBottom: '1px solid #111',
        minWidth: 0,
      }}>
        {/* Label */}
        <div style={{
          width: 128, flexShrink: 0,
          color: labelColor,
          fontWeight: row.bold ? 500 : 400,
          fontSize: row.indent === 0 ? 11 : 10,
          letterSpacing: row.indent === 0 ? '0.02em' : 0,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {row.label}
        </div>

        {/* Year values */}
        {values.map((val, i) => {
          const isLatest = i === values.length - 1
          return (
            <div key={periods[i] ?? i} style={{
              width: colWidth, flexShrink: 0,
              textAlign: 'right', paddingRight: 4,
              color: isLatest ? valueColor : 'var(--text3)',
              fontWeight: isLatest && row.bold ? 500 : 400,
              fontSize: isLatest ? 11 : 10,
            }}>
              {fmtVal(val, row.key)}
            </div>
          )
        })}

        {/* Sparkline */}
        <div style={{ width: 56, flexShrink: 0, paddingLeft: 4 }}>
          <Sparkline values={values} inverted={row.inverted} />
        </div>

        {/* CAGR */}
        <div style={{
          width: 44, flexShrink: 0,
          textAlign: 'right', fontSize: 10, fontWeight: 500,
          color: cagrCol,
        }}>
          {cagrStr ?? ''}
        </div>
      </div>
    </>
  )
}

/* ── Main ────────────────────────────────────────────────── */
export default function FinancialsPanel({ ticker }: FinancialsPanelProps) {
  const [data,    setData]    = useState<FinancialsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()
    setData(null); setError(null); setLoading(false)
    if (!ticker) return

    const abort = new AbortController()
    abortRef.current = abort
    setLoading(true)

    fetch(`${API}/company/${ticker}/financials`, { signal: abort.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { if (!abort.signal.aborted) { setData(d); setLoading(false) } })
      .catch(e => { if (e.name !== 'AbortError') { setError(e.message); setLoading(false) } })

    return () => abort.abort()
  }, [ticker])

  /* ── Render states ─────────────────────────────────────── */
  if (!ticker) return (
    <div className="panel-empty">
      <span className="panel-empty-icon">○</span><span>enter ticker to load</span>
    </div>
  )
  if (loading) return (
    <div className="panel-empty">
      <span className="loading-dots">loading financials</span>
    </div>
  )
  if (error) return (
    <div className="panel-empty">
      <span style={{ color: 'var(--red)', fontSize: 11 }}>⚠ {error}</span>
    </div>
  )
  if (!data) return null

  const { periods, rows } = data
  const n        = periods.length
  // Column width shrinks as we add more years to fit in panel
  const colWidth = n >= 5 ? 62 : n >= 4 ? 72 : 88
  const totalW   = 128 + colWidth * n + 56 + 44
  const visible  = INCOME_ROWS.filter(row => rows[row.key] !== undefined)

  return (
    <div style={{ fontSize: 11, overflowX: 'auto' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        fontSize: 9, color: 'var(--text4)',
        padding: '3px 0 6px 0',
        borderBottom: '1px solid var(--border2)',
        letterSpacing: '0.1em', textTransform: 'uppercase',
        marginBottom: 3, minWidth: totalW,
      }}>
        <div style={{ width: 128, flexShrink: 0 }}>METRIC</div>
        {periods.map((p, i) => (
          <div key={p} style={{
            width: colWidth, flexShrink: 0,
            textAlign: 'right', paddingRight: 4,
            color: i === n - 1 ? 'var(--text2)' : 'var(--text4)',
          }}>
            {p}
          </div>
        ))}
        <div style={{ width: 56, flexShrink: 0 }} />
        <div style={{ width: 44, flexShrink: 0, textAlign: 'right' }}>CAGR</div>
      </div>

      {/* Rows */}
      <div style={{ minWidth: totalW }}>
        {visible.map(row => (
          <FinRow
            key={row.key}
            row={row}
            values={rows[row.key] ?? []}
            periods={periods}
            colWidth={colWidth}
          />
        ))}
      </div>

      {/* Legend */}
      <div style={{
        display: 'flex', gap: 14, marginTop: 12, paddingTop: 7,
        borderTop: '1px solid #1e1e1e',
        fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em',
        minWidth: totalW,
      }}>
        <span><span style={{ color: '#4499ff' }}>■</span> Revenue / Gross</span>
        <span><span style={{ color: '#44ff88' }}>■</span> Profit / Cash</span>
        <span style={{ marginLeft: 'auto' }}>{n}yr · CAGR oldest→latest</span>
      </div>
    </div>
  )
}

'use client'

import { useState, useEffect, useRef } from 'react'

const API = 'http://localhost:8000'

interface MetricDiff {
  metric:     string
  prior:      number | null
  current:    number | null
  change_pct: number | null
}

interface FinancialsPanelProps {
  ticker:      string | null
  metricsDiff?: MetricDiff[] | null
  periods?:    { prior: string; current: string } | null
}

/* ── Income statement structure ──────────────────────────── */
const INCOME_ROWS: Array<{
  key:      string
  label:    string
  indent:   number
  color?:   'fin-blue' | 'fin-green' | 'red' | 'default'
  bold?:    boolean
  divider?: boolean
}> = [
  { key: 'Revenue',             label: 'Revenue',              indent: 0, color: 'fin-blue',  bold: true },
  { key: 'Gross Margin %',      label: 'Gross Margin',         indent: 1, color: 'default' },
  { key: 'Operating Income',    label: 'Operating Income',     indent: 0, color: 'fin-green', bold: true, divider: true },
  { key: 'Net Income',          label: 'Net Income',           indent: 0, color: 'fin-green', bold: true },
  { key: 'Operating Cash Flow', label: 'Operating Cash Flow',  indent: 1, color: 'fin-green' },
  { key: 'Owner Earnings',      label: 'Owner Earnings',       indent: 1, color: 'fin-green' },
  { key: 'SBC',                 label: 'Stock-Based Comp',     indent: 1, color: 'default',   divider: true },
  { key: 'SBC / Revenue %',     label: 'SBC / Revenue',        indent: 2, color: 'default' },
  { key: 'D&A',                 label: 'Depreciation & Amort', indent: 1, color: 'default' },
  { key: 'CapEx',               label: 'Capital Expenditure',  indent: 1, color: 'default' },
  { key: 'Shares Outstanding',  label: 'Shares Outstanding',   indent: 0, color: 'default',   divider: true },
  { key: 'Receivables',         label: 'Receivables',          indent: 0, color: 'default',   divider: true },
  { key: 'Inventory',           label: 'Inventory',            indent: 1, color: 'default' },
  { key: 'Long-Term Debt',      label: 'Long-Term Debt',       indent: 0, color: 'default',   divider: true },
  { key: 'Goodwill',            label: 'Goodwill',             indent: 1, color: 'default' },
  { key: 'Goodwill Impairment', label: 'Goodwill Impairment',  indent: 2, color: 'red' },
  { key: 'Backlog',             label: 'Backlog',              indent: 0, color: 'fin-blue',  divider: true },
]

/* ── Helpers ─────────────────────────────────────────────── */
function fmtVal(val: number | null, metric: string): string {
  if (val === null || val === undefined || val === 0) return '—'
  const abs = Math.abs(val)
  if (metric.includes('%')) return `${val.toFixed(1)}%`
  if (abs >= 1e9) return `$${(val / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `$${(val / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `$${(val / 1e3).toFixed(1)}K`
  return val.toLocaleString()
}

function fmtDelta(pct: number | null, metric: string): { label: string; positive: boolean } | null {
  if (pct === null || pct === undefined) return null
  const invertedMetrics = ['SBC', 'SBC / Revenue %', 'Long-Term Debt', 'Goodwill Impairment', 'Shares Outstanding']
  const isInverted = invertedMetrics.some(m => metric.includes(m))
  const positive = isInverted ? pct <= 0 : pct >= 0
  return { label: `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`, positive }
}

function shortPeriod(s: string): string {
  if (!s) return '—'
  try { return new Date(s).toLocaleDateString('en-US', { month: 'short', year: '2-digit' }) }
  catch { return s }
}

/* ── Row component ───────────────────────────────────────── */
function IncomeRow({
  row, prior, current, change_pct,
}: {
  row: typeof INCOME_ROWS[0]
  prior: number | null
  current: number | null
  change_pct: number | null
  priorLabel: string
  currentLabel: string
}) {
  const delta = fmtDelta(change_pct, row.key)

  const labelColor =
    row.color === 'fin-blue'  ? '#4499ff' :
    row.color === 'fin-green' ? '#44ff88' :
    row.color === 'red'       ? '#ff6666' :
    'var(--text2)'

  const valueColor =
    row.color === 'fin-blue'  ? '#4499ff' :
    row.color === 'fin-green' ? '#44ff88' :
    row.color === 'red'       ? '#ff6666' :
    'var(--text)'

  return (
    <>
      {row.divider && (
        <div style={{ borderTop: '1px solid #1e1e1e', margin: '4px 0' }} />
      )}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 90px 90px 68px',
        fontSize: 12,
        padding: '4px 0',
        paddingLeft: row.indent * 14,
        alignItems: 'center',
        borderBottom: '1px solid #141414',
      }}>
        <span style={{
          color: labelColor,
          fontWeight: row.bold ? 500 : 400,
          letterSpacing: row.indent === 0 ? '0.02em' : 0,
        }}>
          {row.label}
        </span>
        <span style={{ textAlign: 'right', color: 'var(--text3)', fontSize: 11 }}>
          {fmtVal(prior, row.key)}
        </span>
        <span style={{ textAlign: 'right', color: valueColor, fontWeight: row.bold ? 500 : 400 }}>
          {fmtVal(current, row.key)}
        </span>
        <span style={{
          textAlign: 'right',
          fontSize: 11,
          fontWeight: 500,
          color: delta
            ? delta.positive ? '#44ff88' : '#ff5555'
            : '#333',
        }}>
          {delta?.label ?? ''}
        </span>
      </div>
    </>
  )
}

/* ── Main ────────────────────────────────────────────────── */
export default function FinancialsPanel({ ticker, metricsDiff, periods: periodsProp }: FinancialsPanelProps) {
  const [localMetrics, setLocalMetrics] = useState<MetricDiff[] | null>(null)
  const [localPeriods, setLocalPeriods] = useState<{ prior: string; current: string } | null>(null)
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // BUG FIX: separate the two concerns into two effects.
  //
  // Effect 1 — reset local state when ticker changes.
  useEffect(() => {
    abortRef.current?.abort()
    setLocalMetrics(null)
    setLocalPeriods(null)
    setError(null)
    setLoading(false)
  }, [ticker])

  // Effect 2 — self-fetch only when ticker is set AND props haven't arrived.
  // Re-runs whenever metricsDiff changes, so if props arrive after mount the
  // fetch is cancelled and loading is cleared immediately.
  useEffect(() => {
    if (!ticker) return

    // Props already populated — cancel any in-flight fetch and use them.
    if (metricsDiff && metricsDiff.length > 0) {
      abortRef.current?.abort()
      setLoading(false)
      setError(null)
      return
    }

    // No props yet — start self-fetch.
    abortRef.current?.abort()
    const abort = new AbortController()
    abortRef.current = abort
    setLoading(true)
    setLocalMetrics(null)
    setError(null)

    fetch(`${API}/company/${ticker}/signals?fast=true`, { signal: abort.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => {
        if (!abort.signal.aborted) {
          setLocalMetrics(d.metrics_diff ?? [])
          setLocalPeriods({ prior: d.prior_period, current: d.current_period })
          setLoading(false)
        }
      })
      .catch(e => {
        if (e.name !== 'AbortError') {
          setError(e.message)
          setLoading(false)
        }
      })

    return () => abort.abort()
  }, [ticker, metricsDiff])

  // Prefer props over local state
  const metrics = (metricsDiff && metricsDiff.length > 0) ? metricsDiff : localMetrics
  const periods = periodsProp ?? localPeriods

  /* ── Render states ─────────────────────────────────────── */
  if (!ticker) return (
    <div className="panel-empty">
      <span className="panel-empty-icon">○</span>
      <span>enter ticker to load</span>
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

  if (!metrics?.length) return (
    <div className="panel-empty">
      <span style={{ color: 'var(--text4)', fontSize: 11 }}>no financial data</span>
    </div>
  )

  const metricMap = new Map(metrics.map(m => [m.metric, m]))
  const priorLabel   = periods?.prior   ? shortPeriod(periods.prior)   : 'Prior'
  const currentLabel = periods?.current ? shortPeriod(periods.current) : 'Current'
  const visibleRows  = INCOME_ROWS.filter(row => metricMap.has(row.key))

  return (
    <div style={{ fontSize: 12 }}>
      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 90px 90px 68px',
        fontSize: 9,
        color: 'var(--text4)',
        padding: '3px 0 6px 0',
        borderBottom: '1px solid var(--border2)',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        marginBottom: 4,
      }}>
        <span>METRIC</span>
        <span style={{ textAlign: 'right' }}>{priorLabel}</span>
        <span style={{ textAlign: 'right' }}>{currentLabel}</span>
        <span style={{ textAlign: 'right' }}>ΔYOY</span>
      </div>

      {/* Rows */}
      {visibleRows.map(row => {
        const m = metricMap.get(row.key)!
        return (
          <IncomeRow
            key={row.key}
            row={row}
            prior={m.prior}
            current={m.current}
            change_pct={m.change_pct}
            priorLabel={priorLabel}
            currentLabel={currentLabel}
          />
        )
      })}

      {/* Legend */}
      <div style={{
        display: 'flex', gap: 16, marginTop: 14, paddingTop: 8,
        borderTop: '1px solid #1e1e1e',
        fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em',
      }}>
        <span><span style={{ color: '#4499ff' }}>■</span> Revenue / Gross</span>
        <span><span style={{ color: '#44ff88' }}>■</span> Profit / Cash</span>
        <span style={{ marginLeft: 'auto', color: '#333' }}>Prior shown in grey</span>
      </div>
    </div>
  )
}

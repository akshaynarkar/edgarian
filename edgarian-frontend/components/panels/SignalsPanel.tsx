'use client'

import { useState, useEffect, useRef } from 'react'
import type { FilingJump } from './FilingPanel'

const API = 'http://localhost:8000'

interface Flag {
  type: string; severity: 'high'|'medium'|'low'|'info'; color: 'red'|'amber'|'blue'; text: string; source: string
}
interface MetricDiff { metric: string; prior: number|null; current: number|null; change_pct: number|null }
interface SignalsData {
  company: string; ticker: string; filing_type: string
  current_period: string; prior_period: string; fast_mode: boolean
  metrics_diff: MetricDiff[]; red_flags: Flag[]; section_diffs?: any
}
interface SignalsPanelProps {
  ticker: string|null
  onSectionDiffs?: (d: any) => void
  onSignalsData?:  (d: any) => void
  onFlagClick?: (j: FilingJump) => void
}

const COLOR = {
  red:   { border: '#ff4444', bg: '#200a0a', text: '#ff6666' },
  amber: { border: '#ffaa00', bg: '#1a1200', text: '#ffcc44' },
  blue:  { border: '#4499ff', bg: '#080f20', text: '#66bbff' },
}
const SEV_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2, info: 3 }

// Map flag type → fallback section when source has no Item ref
const FLAG_SECTION_FALLBACK: Record<string, FilingJump> = {
  recv_growth:             { sectionId: '7', paragraphIndex: 0 },
  inventory_build:         { sectionId: '7', paragraphIndex: 0 },
  cash_conversion:         { sectionId: '7', paragraphIndex: 0 },
  sbc_creep:               { sectionId: '7', paragraphIndex: 0 },
  dilution:                { sectionId: '7', paragraphIndex: 0 },
  debt_load:               { sectionId: '7', paragraphIndex: 0 },
  gross_margin_compression:{ sectionId: '7', paragraphIndex: 0 },
  operating_deterioration: { sectionId: '7', paragraphIndex: 0 },
  earnings_collapse:       { sectionId: '7', paragraphIndex: 0 },
  operating_loss:          { sectionId: '7', paragraphIndex: 0 },
  goodwill_impairment:     { sectionId: '8', paragraphIndex: 0 },
  rev_rec_change:          { sectionId: '8', paragraphIndex: 0 },
  capex_decline:           { sectionId: '7', paragraphIndex: 0 },
  book_to_bill_low:        { sectionId: '7', paragraphIndex: 0 },
  book_to_bill_strong:     { sectionId: '7', paragraphIndex: 0 },
}

function sourceToJump(source: string, flagType: string): FilingJump | null {
  const secMatch  = source.match(/Item\s+(1A|7|8|1)\b/i)
  const paraMatch = source.match(/paragraph\s+(\d+)/i)
  if (secMatch) {
    return { sectionId: secMatch[1].toUpperCase(), paragraphIndex: paraMatch ? parseInt(paraMatch[1], 10) : 0 }
  }
  return FLAG_SECTION_FALLBACK[flagType] ?? null
}

function fmtNum(val: number|null, metric: string): string {
  if (val === null || val === undefined) return '—'
  const abs = Math.abs(val)
  if (metric.includes('%')) return `${val.toFixed(1)}%`
  if (abs >= 1e9) return `$${(val/1e9).toFixed(2)}B`
  if (abs >= 1e6) return `$${(val/1e6).toFixed(1)}M`
  if (abs >= 1e3) return `$${(val/1e3).toFixed(1)}K`
  return val.toFixed(2)
}

function fmtDelta(pct: number|null) {
  if (pct === null || pct === undefined) return null
  return { label: `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`, positive: pct >= 0 }
}

function shortPeriod(s: string): string {
  try { return new Date(s).toLocaleDateString('en-US', { month: 'short', year: '2-digit' }) }
  catch { return s }
}

function FlagCard({ flag, onJump }: { flag: Flag; onJump?: (j: FilingJump) => void }) {
  const [tip, setTip] = useState(false)
  const c    = COLOR[flag.color] ?? COLOR.blue
  const jump = sourceToJump(flag.source, flag.type)

  return (
    <div
      style={{
        borderLeft: `2px solid ${c.border}`, background: c.bg, color: c.text,
        fontSize: 12, fontWeight: 500, padding: '8px 10px', marginBottom: 7,
        cursor: jump ? 'pointer' : 'default', position: 'relative', overflow: 'visible',
      }}
      onMouseEnter={() => setTip(true)}
      onMouseLeave={() => setTip(false)}
      onClick={() => jump && onJump?.(jump)}
      title={jump ? `Click → jump to Item ${jump.sectionId}` : undefined}
    >
      <div style={{ lineHeight: 1.5 }}>{flag.text}</div>
      <div style={{ fontSize: 10, color: '#666', fontWeight: 400, marginTop: 3, display: 'flex', justifyContent: 'space-between' }}>
        <span>{flag.source}</span>
        {jump && <span style={{ color: '#2a3050' }}>→ Item {jump.sectionId}</span>}
      </div>
      {tip && (
        <div style={{
          position: 'absolute', left: '100%', top: 0, marginLeft: 6,
          background: '#1a1a1a', border: '1px solid #444',
          padding: '6px 10px', fontSize: 10, color: '#ccc',
          lineHeight: 1.7, zIndex: 300, minWidth: 200, maxWidth: 280,
          whiteSpace: 'normal', pointerEvents: 'none',
        }}>
          <div style={{ color: '#fff', fontWeight: 500, marginBottom: 3 }}>{flag.type.replace(/_/g, ' ').toUpperCase()}</div>
          {flag.text}
          {jump && <div style={{ color: '#4499ff', marginTop: 4, fontSize: 9 }}>Click to open Item {jump.sectionId} in Filing Reader</div>}
        </div>
      )}
    </div>
  )
}

function MetricsTable({ metrics, prior_period, current_period }: { metrics: MetricDiff[]; prior_period: string; current_period: string }) {
  if (!metrics?.length) return null
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 10, color: 'var(--text3)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 8 }}>Metrics</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 90px 90px 70px', fontSize: 10, color: 'var(--text3)', padding: '3px 0', borderBottom: '1px solid #222', letterSpacing: '0.05em' }}>
        <span>METRIC</span>
        <span style={{ textAlign: 'right' }}>{shortPeriod(prior_period)}</span>
        <span style={{ textAlign: 'right' }}>{shortPeriod(current_period)}</span>
        <span style={{ textAlign: 'right' }}>ΔYOY</span>
      </div>
      {metrics.map((m, i) => {
        const d = fmtDelta(m.change_pct)
        return (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 90px 90px 70px', fontSize: 12, padding: '5px 0', borderBottom: '1px solid #181818', alignItems: 'center' }}>
            <span style={{ color: 'var(--text2)' }}>{m.metric}</span>
            <span style={{ textAlign: 'right', color: 'var(--text)', fontWeight: 500 }}>{fmtNum(m.prior, m.metric)}</span>
            <span style={{ textAlign: 'right', color: 'var(--text)', fontWeight: 500 }}>{fmtNum(m.current, m.metric)}</span>
            <span style={{ textAlign: 'right', fontWeight: 500, color: d ? (d.positive ? 'var(--green)' : 'var(--red)') : 'var(--text3)' }}>{d?.label ?? '—'}</span>
          </div>
        )
      })}
    </div>
  )
}

type LoadState = 'idle'|'fast-loading'|'fast-done'|'full-loading'|'full-done'|'error'

export default function SignalsPanel({ ticker, onSectionDiffs, onSignalsData, onFlagClick }: SignalsPanelProps) {
  const [data, setData]           = useState<SignalsData|null>(null)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [error, setError]         = useState<string|null>(null)
  const abortRef = useRef<AbortController|null>(null)

  useEffect(() => {
    if (!ticker) { setData(null); setLoadState('idle'); setError(null); return }
    abortRef.current?.abort()
    const abort = new AbortController()
    abortRef.current = abort

    const run = async () => {
      setData(null); setError(null)
      setLoadState('fast-loading')
      try {
        const r = await fetch(`${API}/company/${ticker}/signals?fast=true`, { signal: abort.signal })
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        const fast: SignalsData = await r.json()
        if (!abort.signal.aborted) {
          setData(fast)
          setLoadState('fast-done')
          onSignalsData?.(fast)
        }
      } catch (e: any) {
        if (e.name === 'AbortError') return
        setError(e.message); setLoadState('error'); return
      }
      setLoadState('full-loading')
      try {
        const r = await fetch(`${API}/company/${ticker}/signals`, { signal: abort.signal })
        if (!r.ok) throw new Error(`${r.status}`)
        const full: SignalsData = await r.json()
        if (!abort.signal.aborted) {
          setData(full); setLoadState('full-done')
          if (full.section_diffs) onSectionDiffs?.(full.section_diffs)
        }
      } catch (e: any) {
        if (e.name === 'AbortError') return
        setLoadState('fast-done')
      }
    }
    run()
    return () => abort.abort()
  }, [ticker])

  if (!ticker) return <div className="panel-empty"><span className="panel-empty-icon">○</span><span>enter ticker to load</span></div>
  if (loadState === 'fast-loading') return <div className="panel-empty"><span className="loading-dots">loading signals</span></div>
  if (loadState === 'error') return (
    <div className="panel-empty">
      <span style={{ color: 'var(--red)', fontSize: 11 }}>⚠ {error}</span>
      <span style={{ fontSize: 10, color: 'var(--text4)', marginTop: 4 }}>is the backend running on localhost:8000?</span>
    </div>
  )
  if (!data) return null

  const sorted = [...(data.red_flags ?? [])].sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))

  return (
    <div style={{ fontSize: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 8, borderBottom: '1px solid var(--border2)' }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ color: 'var(--text2)', fontSize: 10, letterSpacing: '0.1em' }}>{data.filing_type}</span>
          <span style={{ color: 'var(--text3)', fontSize: 10 }}>{shortPeriod(data.current_period)}</span>
          <span style={{ fontSize: 10, color: '#666', borderLeft: '1px solid #333', paddingLeft: 8 }}>{sorted.length} flag{sorted.length !== 1 ? 's' : ''}</span>
        </div>
        <div style={{ fontSize: 10 }}>
          {loadState === 'full-loading' && <span className="loading-dots" style={{ color: 'var(--amber)' }}>loading diffs</span>}
          {loadState === 'full-done'    && <span style={{ color: 'var(--green)' }}>● full</span>}
          {loadState === 'fast-done'    && <span style={{ color: 'var(--amber)' }}>◐ fast</span>}
        </div>
      </div>

      {sorted.length > 0 ? (
        <div>
          <div style={{ fontSize: 10, color: 'var(--text3)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 8 }}>Flags</div>
          {sorted.map((f, i) => <FlagCard key={i} flag={f} onJump={onFlagClick} />)}
        </div>
      ) : (
        <div style={{ padding: '12px 0 12px 10px', color: 'var(--green)', fontSize: 11, borderLeft: '2px solid var(--green)', marginBottom: 12, background: 'var(--green-bg)' }}>
          No flags detected
        </div>
      )}

      <MetricsTable metrics={data.metrics_diff} prior_period={data.prior_period} current_period={data.current_period} />
    </div>
  )
}

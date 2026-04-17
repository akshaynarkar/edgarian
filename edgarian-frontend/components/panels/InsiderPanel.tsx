'use client'

import { useState, useEffect, useRef } from 'react'

const API = 'http://localhost:8000'

/* ── Types ───────────────────────────────────────────────── */
interface InsiderTransaction {
  name:               string
  title:              string
  transaction_type:   'P' | 'S'          // P = buy, S = sell
  shares:             number
  price_per_share:    number
  total_value:        number
  filing_date:        string
  period_of_report:   string
  '52_week_high':     number
  '52_week_low':      number
  price_vs_52wk:      'near high' | 'near low' | 'mid range'
  pct_of_holdings:    number | null
}

interface ClusterFlag {
  detected:    boolean
  buy_count:   number
  window_days: number
  message:     string
}

interface InsiderResponse {
  ticker:       string
  transactions: InsiderTransaction[]
  cluster_flag: ClusterFlag
}

interface InsiderPanelProps {
  ticker: string | null
}

/* ── Helpers ─────────────────────────────────────────────── */
function fmtShares(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return n.toLocaleString()
}

function fmtMoney(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

function fmtDate(s: string): string {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
  } catch { return s }
}

function shortTitle(title: string): string {
  // Abbreviate common titles to keep rows compact
  return title
    .replace(/Chief Executive Officer/i, 'CEO')
    .replace(/Chief Financial Officer/i, 'CFO')
    .replace(/Chief Operating Officer/i, 'COO')
    .replace(/Chief Technology Officer/i, 'CTO')
    .replace(/Chief Marketing Officer/i, 'CMO')
    .replace(/President and CEO/i, 'President & CEO')
    .replace(/Executive Vice President/i, 'EVP')
    .replace(/Senior Vice President/i, 'SVP')
    .replace(/Vice President/i, 'VP')
    .replace(/Director/i, 'Dir.')
    .trim()
}

/* ── 52-week range bar ───────────────────────────────────── */
function RangeBar({
  low, high, price, label,
}: {
  low: number
  high: number
  price: number
  label: 'near high' | 'near low' | 'mid range'
}) {
  const pct = high > low ? Math.max(0, Math.min(100, ((price - low) / (high - low)) * 100)) : 50

  const dotColor =
    label === 'near high' ? '#ff5555' :   // selling near high = red context
    label === 'near low'  ? '#44ff88' :   // buying near low  = green context
    'var(--text3)'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{ fontSize: 9, color: 'var(--text4)', whiteSpace: 'nowrap' }}>
        ${low.toFixed(0)}
      </span>
      <div style={{
        position: 'relative',
        flex: 1,
        height: 3,
        background: 'var(--border2)',
        minWidth: 40,
      }}>
        <div style={{
          position: 'absolute',
          left: `${pct}%`,
          top: -2,
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: dotColor,
          transform: 'translateX(-50%)',
        }} />
      </div>
      <span style={{ fontSize: 9, color: 'var(--text4)', whiteSpace: 'nowrap' }}>
        ${high.toFixed(0)}
      </span>
    </div>
  )
}

/* ── Single transaction row ──────────────────────────────── */
function TransactionRow({ tx }: { tx: InsiderTransaction }) {
  const isBuy = tx.transaction_type === 'P'

  return (
    <div style={{
      borderBottom: '1px solid #141414',
      padding: '9px 0',
    }}>
      {/* Row 1: name · title · BUY/SELL badge · total value */}
      <div style={{
        display: 'flex',
        alignItems: 'baseline',
        justifyContent: 'space-between',
        gap: 8,
        marginBottom: 4,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0 }}>
          <span style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {tx.name}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text3)', whiteSpace: 'nowrap' }}>
            {shortTitle(tx.title)}
          </span>
        </div>

        <span style={{
          fontSize: 11,
          fontWeight: 500,
          color: isBuy ? '#44ff88' : '#ff5555',
          whiteSpace: 'nowrap',
        }}>
          {isBuy ? '▲ BUY' : '▼ SELL'}
        </span>
      </div>

      {/* Row 2: shares · price · date · total */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr 1fr',
        fontSize: 11,
        color: 'var(--text2)',
        marginBottom: 6,
        gap: 4,
      }}>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em', marginBottom: 2 }}>SHARES</div>
          <div style={{ color: 'var(--text)', fontWeight: 500 }}>{fmtShares(tx.shares)}</div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em', marginBottom: 2 }}>PRICE</div>
          <div style={{ color: 'var(--text)', fontWeight: 500 }}>${tx.price_per_share.toFixed(2)}</div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em', marginBottom: 2 }}>DATE</div>
          <div style={{ color: 'var(--text)' }}>{fmtDate(tx.period_of_report)}</div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em', marginBottom: 2 }}>VALUE</div>
          <div style={{ color: isBuy ? '#44ff88' : '#ff5555', fontWeight: 500 }}>
            {fmtMoney(tx.total_value)}
          </div>
        </div>
      </div>

      {/* Row 3: 52-week bar + pct of holdings */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em', marginBottom: 3 }}>
            52-WEEK RANGE
          </div>
          <RangeBar
            low={tx['52_week_low']}
            high={tx['52_week_high']}
            price={tx.price_per_share}
            label={tx.price_vs_52wk}
          />
        </div>

        {tx.pct_of_holdings != null && (
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: 'var(--text4)', letterSpacing: '0.08em', marginBottom: 2 }}>
              % HOLDINGS
            </div>
            <div style={{
              fontSize: 11,
              fontWeight: 500,
              color: isBuy ? '#44ff88' : tx.pct_of_holdings > 20 ? '#ff5555' : 'var(--text2)',
            }}>
              {tx.pct_of_holdings.toFixed(1)}%
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Main ────────────────────────────────────────────────── */
export default function InsiderPanel({ ticker }: InsiderPanelProps) {
  const [data,    setData]    = useState<InsiderResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()
    setData(null)
    setError(null)
    setLoading(false)

    if (!ticker) return

    const abort = new AbortController()
    abortRef.current = abort
    setLoading(true)

    fetch(`${API}/company/${ticker}/insider`, { signal: abort.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => {
        if (!abort.signal.aborted) {
          setData(d)
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
  }, [ticker])

  /* ── Render states ─────────────────────────────────────── */
  if (!ticker) return (
    <div className="panel-empty">
      <span className="panel-empty-icon">○</span>
      <span>enter ticker to load</span>
    </div>
  )

  if (loading) return (
    <div className="panel-empty">
      <span className="loading-dots">loading insider activity</span>
    </div>
  )

  if (error) return (
    <div className="panel-empty">
      <span style={{ color: 'var(--red)', fontSize: 11 }}>⚠ {error}</span>
    </div>
  )

  if (!data || data.transactions.length === 0) return (
    <div className="panel-empty">
      <span style={{ color: 'var(--text4)', fontSize: 11 }}>no insider filings found</span>
    </div>
  )

  // Sort: buys first, then sells; most recent first within each group
  const sorted = [...data.transactions].sort((a, b) => {
    if (a.transaction_type !== b.transaction_type) {
      return a.transaction_type === 'P' ? -1 : 1
    }
    return new Date(b.period_of_report).getTime() - new Date(a.period_of_report).getTime()
  })

  const buyCount  = sorted.filter(t => t.transaction_type === 'P').length
  const sellCount = sorted.filter(t => t.transaction_type === 'S').length

  return (
    <div style={{ fontSize: 12 }}>

      {/* Cluster buy badge */}
      {data.cluster_flag?.detected && (
        <div style={{
          borderLeft: '2px solid var(--amber)',
          background: 'var(--amber-bg)',
          color: 'var(--amber-text)',
          fontSize: 12,
          fontWeight: 500,
          padding: '8px 10px',
          marginBottom: 10,
        }}>
          ◆ {data.cluster_flag.message}
          <div style={{ fontSize: 10, color: '#aa8800', marginTop: 2, fontWeight: 400 }}>
            cluster buy signal · {data.cluster_flag.window_days}-day window
          </div>
        </div>
      )}

      {/* Summary bar */}
      <div style={{
        display: 'flex',
        gap: 16,
        fontSize: 10,
        color: 'var(--text4)',
        letterSpacing: '0.08em',
        paddingBottom: 8,
        borderBottom: '1px solid var(--border2)',
        marginBottom: 2,
      }}>
        <span>
          <span style={{ color: '#44ff88', fontWeight: 500 }}>{buyCount}</span> BUY
        </span>
        <span>
          <span style={{ color: '#ff5555', fontWeight: 500 }}>{sellCount}</span> SELL
        </span>
        <span style={{ marginLeft: 'auto' }}>
          {sorted.length} TRANSACTIONS
        </span>
      </div>

      {/* Transaction rows */}
      {sorted.map((tx, i) => (
        <TransactionRow key={`${tx.name}-${tx.period_of_report}-${i}`} tx={tx} />
      ))}

    </div>
  )
}

'use client'

import { useState, useEffect, useRef, useCallback } from 'react'

const API = 'http://localhost:8000'

interface FilingSection {
  ticker: string; section: string; text: string
  truncated: boolean; chars_extracted: number
  filing_url: string; document_url: string; accession_number: string
}
interface DiffMarker {
  paragraph_index: number; type: 'added'|'removed'|'modified'
  current_text?: string; prior_text?: string
}
export interface FilingJump { sectionId: string; paragraphIndex: number }
interface FilingPanelProps {
  ticker: string|null; sectionDiffs?: any
  jumpTo?: FilingJump|null; onJumpConsumed?: () => void
}

const TABS = [
  { id: '1',  label: 'Item 1',  explanation: null },
  { id: '1A', label: 'Item 1A', explanation: 'What could go wrong — every material risk the company must legally disclose. New or expanded risks here are the most important signals in any 10-K.' },
  { id: '7',  label: 'Item 7',  explanation: "Management's own narrative: what drove revenue and margins, and what they expect ahead. Compare against the metrics to spot gaps between the story and the numbers." },
  { id: '8',  label: 'Item 8',  explanation: 'Formal financial statements and footnotes. Revenue recognition changes here can signal shifting business models or accounting risk — flagged automatically.' },
]
const DIFF_KEY: Record<string,string> = { '1A': 'risk_factors', '7': 'mda', '8': 'revenue_rec' }

function extractMarkers(diffs: any, sid: string): DiffMarker[] {
  const d = diffs?.[DIFF_KEY[sid]]
  if (!d) return []
  const out: DiffMarker[] = []
  ;(d.added    ?? []).forEach((i: any) => out.push({ paragraph_index: i.paragraph_index ?? -1, type: 'added',    current_text: i.text ?? i.current_text }))
  ;(d.modified ?? []).forEach((i: any) => out.push({ paragraph_index: i.paragraph_index ?? -1, type: 'modified', current_text: i.current_text, prior_text: i.prior_text }))
  ;(d.removed  ?? []).forEach((i: any) => out.push({ paragraph_index: i.paragraph_index ?? -1, type: 'removed',  prior_text: i.text ?? i.prior_text }))
  return out
}

function FilingText({ text, markers, jumpIndex, paraRefs }: {
  text: string; markers: DiffMarker[]
  jumpIndex: number|null; paraRefs: React.MutableRefObject<(HTMLDivElement|null)[]>
}) {
  const byIdx = new Map(markers.map(m => [m.paragraph_index, m]))
  const paras = text.split(/\n{2,}/).filter(p => p.trim())

  return (
    <div className="filing-text-body">
      {paras.map((para, i) => {
        const m = byIdx.get(i)
        const isJump = jumpIndex === i
        return (
          <div key={i} ref={el => { paraRefs.current[i] = el }} style={{
            marginBottom: 16,
            background: isJump ? 'rgba(68,153,255,0.1)' : m?.type === 'added' ? 'rgba(68,255,136,0.03)' : m?.type === 'modified' ? 'rgba(255,170,0,0.03)' : undefined,
            outline: isJump ? '1px solid #4499ff55' : undefined,
            padding: isJump ? '4px 6px' : undefined,
          }}>
            {m && (
              <span style={{
                display: 'inline-block', marginRight: 6,
                fontSize: 9, fontWeight: 500, padding: '1px 5px', letterSpacing: '0.1em',
                color:      m.type === 'added' ? '#44ff88' : m.type === 'modified' ? '#ffcc44' : '#ff6666',
                border:     `1px solid ${m.type === 'added' ? '#44ff88' : m.type === 'modified' ? '#ffaa00' : '#ff5555'}`,
                background: m.type === 'added' ? '#091409' : m.type === 'modified' ? '#1a1200' : '#200a0a',
                verticalAlign: 'middle',
              }}>
                {m.type === 'added' ? '▲ NEW' : m.type === 'modified' ? '⇄ CHG' : '▼ DEL'}
              </span>
            )}
            {para}
            {m?.type === 'modified' && m.prior_text && (
              <div style={{ marginTop: 6, fontSize: 11, color: '#ff6666', background: '#200a0a', padding: '4px 8px', borderLeft: '2px solid #ff4444', textDecoration: 'line-through', opacity: 0.7 }}>
                {m.prior_text.slice(0, 300)}{m.prior_text.length > 300 ? '…' : ''}
              </div>
            )}
          </div>
        )
      })}
      <span className="blink-cursor" />
    </div>
  )
}

export default function FilingPanel({ ticker, sectionDiffs, jumpTo, onJumpConsumed }: FilingPanelProps) {
  const [tab,     setTab]     = useState('1A')
  const [data,    setData]    = useState<FilingSection|null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string|null>(null)
  const [jumpIdx, setJumpIdx] = useState<number|null>(null)
  const [panelH,  setPanelH]  = useState(520)

  const abortRef = useRef<AbortController|null>(null)
  const bodyRef  = useRef<HTMLDivElement>(null)
  const paraRefs = useRef<(HTMLDivElement|null)[]>([])
  const resizing = useRef<{startY:number;startH:number}|null>(null)

  useEffect(() => {
    if (!ticker) { setData(null); setError(null); return }
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true); setData(null); setError(null)
    paraRefs.current = []
    fetch(`${API}/company/${ticker}/filing/${tab}`, { signal: ctrl.signal })
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then(j  => { if (!ctrl.signal.aborted) { setData(j); setLoading(false) } })
      .catch(e => { if (e.name !== 'AbortError') { setError(e.message); setLoading(false) } })
    return () => ctrl.abort()
  }, [ticker, tab])

  useEffect(() => {
    if (!jumpTo) return
    if (jumpTo.sectionId !== tab) setTab(jumpTo.sectionId)
    setJumpIdx(jumpTo.paragraphIndex)
    onJumpConsumed?.()
  }, [jumpTo])

  useEffect(() => {
    if (jumpIdx === null || loading) return
    setTimeout(() => {
      const el = paraRefs.current[jumpIdx]
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      else if (bodyRef.current) bodyRef.current.scrollTop = 0
    }, 80)
  }, [jumpIdx, loading, data])

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    resizing.current = { startY: e.clientY, startH: panelH }
    const move = (ev: MouseEvent) => {
      if (!resizing.current) return
      setPanelH(Math.max(200, Math.min(900, resizing.current.startH + ev.clientY - resizing.current.startY)))
    }
    const up = () => { resizing.current = null; window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
  }, [panelH])

  if (!ticker) return <div className="panel-empty"><span className="panel-empty-icon">○</span><span>enter ticker to load</span></div>

  const markers  = extractMarkers(sectionDiffs, tab)
  const diffKey  = DIFF_KEY[tab]
  const thisDiff = diffKey && sectionDiffs ? sectionDiffs[diffKey] : null
  const timedOut = thisDiff?.timed_out === true
  const tabDef   = TABS.find(t => t.id === tab)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: panelH }}>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border2)', flexShrink: 0 }}>
        {TABS.map(t => {
          const dd = DIFF_KEY[t.id] && sectionDiffs ? sectionDiffs[DIFF_KEY[t.id]] : null
          const dot = dd && ((dd.added?.length ?? 0) + (dd.modified?.length ?? 0) + (dd.removed?.length ?? 0)) > 0
          return (
            <button key={t.id} onClick={() => { setTab(t.id); setJumpIdx(null) }} style={{
              background: 'transparent', border: 'none',
              borderBottom: t.id === tab ? '2px solid var(--text)' : '2px solid transparent',
              color: t.id === tab ? 'var(--text)' : 'var(--text3)',
              fontFamily: 'var(--font-mono)', fontSize: 11,
              padding: '6px 12px', cursor: 'pointer',
              letterSpacing: '0.05em', position: 'relative', marginBottom: -1,
            }}>
              {t.label}
              {dot && <span style={{ position: 'absolute', top: 4, right: 4, width: 4, height: 4, borderRadius: '50%', background: '#ffaa00' }} />}
            </button>
          )
        })}
      </div>

      {/* Layman explanation */}
      {tabDef?.explanation && (
        <div style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.7, padding: '7px 0', borderBottom: '1px solid var(--border2)', flexShrink: 0, fontStyle: 'italic' }}>
          {tabDef.explanation}
        </div>
      )}

      {/* Banners */}
      {data?.truncated && !timedOut && (
        <div style={{ fontSize: 10, color: '#ffcc44', background: '#1a1200', border: '1px solid #ffaa00', padding: '5px 10px', display: 'flex', justifyContent: 'space-between', flexShrink: 0, marginTop: 4 }}>
          <span>Truncated at {(data.chars_extracted/1000).toFixed(0)}K chars</span>
          {data.filing_url && <a href={data.filing_url} target="_blank" rel="noopener noreferrer" style={{ color: '#4499ff', textDecoration: 'none' }}>View full on SEC EDGAR →</a>}
        </div>
      )}
      {timedOut && (
        <div style={{ fontSize: 10, color: '#ff6666', background: '#200a0a', border: '1px solid #ff4444', padding: '5px 10px', display: 'flex', justifyContent: 'space-between', flexShrink: 0, marginTop: 4 }}>
          <span>Diff timed out</span>
          {thisDiff?.filing_url && <a href={thisDiff.filing_url} target="_blank" rel="noopener noreferrer" style={{ color: '#4499ff', textDecoration: 'none' }}>View full on SEC EDGAR →</a>}
        </div>
      )}

      {/* Diff summary */}
      {markers.length > 0 && (
        <div style={{ display: 'flex', gap: 12, fontSize: 10, padding: '5px 0', borderBottom: '1px solid var(--border2)', flexShrink: 0 }}>
          {[['added','#44ff88'],['modified','#ffcc44'],['removed','#ff6666']].map(([type, color]) => {
            const n = markers.filter(m => m.type === type).length
            return n ? <span key={type} style={{ color }}>{n} {type}</span> : null
          })}
        </div>
      )}

      {/* Text body */}
      <div ref={bodyRef} style={{ flex: 1, overflow: 'auto', paddingRight: 6, marginTop: 8 }}>
        {loading ? (
          <div className="panel-empty" style={{ height: 100 }}><span className="loading-dots">loading section</span></div>
        ) : error ? (
          <div className="panel-empty" style={{ height: 100 }}><span style={{ color: 'var(--red)', fontSize: 11 }}>⚠ {error}</span></div>
        ) : data?.text ? (
          <FilingText text={data.text} markers={markers} jumpIndex={jumpIdx} paraRefs={paraRefs} />
        ) : (
          <div className="panel-empty" style={{ height: 100 }}><span style={{ color: 'var(--text4)', fontSize: 11 }}>no text for this section</span></div>
        )}
      </div>

      {/* Resize handle */}
      <div onMouseDown={onResizeStart} style={{ height: 8, cursor: 'ns-resize', flexShrink: 0, borderTop: '1px solid var(--border2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 8, color: 'var(--border3)', letterSpacing: 3, userSelect: 'none' }}>━━━</span>
      </div>
    </div>
  )
}

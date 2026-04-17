'use client'

import { useState, useEffect, useRef, KeyboardEvent } from 'react'

const API = 'http://localhost:8000'

const INDEX_DATA = [
  { name: 'S&P 500', value: '5,308.13', change: '+0.41%', pos: true  },
  { name: 'NASDAQ',  value: '16,742.39', change: '+0.55%', pos: true  },
  { name: 'DOW',     value: '39,069.59', change: '+0.20%', pos: true  },
  { name: 'VIX',     value: '13.42',     change: '-2.10%', pos: false },
  { name: '10Y',     value: '4.621%',    change: '+0.03%', pos: true  },
  { name: 'DXY',     value: '105.22',    change: '-0.12%', pos: false },
]
const TICKER_ITEMS = [...INDEX_DATA, ...INDEX_DATA]

interface Suggestion { ticker: string; name: string }

interface TopbarProps {
  company:    string | null
  loading:    boolean
  onLoad:     (ticker: string) => void
  font:       string
  fontSize:   number
  theme:      string
  onFont:     (f: string) => void
  onFontSize: (s: number) => void
  onTheme:    () => void
}

export default function Topbar({ company, loading, onLoad, font, fontSize, theme, onFont, onFontSize, onTheme }: TopbarProps) {
  const [input,       setInput]       = useState('')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [showDrop,    setShowDrop]    = useState(false)
  const [activeIdx,   setActiveIdx]   = useState(-1)
  const [datetime,    setDatetime]    = useState('')
  const inputRef  = useRef<HTMLInputElement>(null)
  const dropRef   = useRef<HTMLDivElement>(null)
  const fetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  /* Live clock */
  useEffect(() => {
    const tick = () => {
      const now = new Date()
      const d = now.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
      const t = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
      setDatetime(`${d} ${t}`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  /* Typeahead — debounced fetch to /company/{ticker} for name lookup */
  useEffect(() => {
    if (fetchTimer.current) clearTimeout(fetchTimer.current)
    const q = input.trim().toUpperCase()
    if (q.length < 1) { setSuggestions([]); setShowDrop(false); return }

    // Optimistic: show the raw input as first suggestion immediately
    setSuggestions([{ ticker: q, name: '' }])
    setShowDrop(true)
    setActiveIdx(-1)

    // After 300ms try to resolve the name
    fetchTimer.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/company/${q}`)
        if (r.ok) {
          const d = await r.json()
          setSuggestions([{ ticker: q, name: d.name ?? '' }])
        }
      } catch { /* backend down — keep raw suggestion */ }
    }, 300)
  }, [input])

  /* Close dropdown on outside click */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropRef.current && !dropRef.current.contains(e.target as Node) &&
          inputRef.current && !inputRef.current.contains(e.target as Node)) {
        setShowDrop(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const commit = (ticker: string) => {
    if (!ticker) return
    onLoad(ticker)
    setInput('')
    setSuggestions([])
    setShowDrop(false)
    setActiveIdx(-1)
  }

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIdx >= 0 && suggestions[activeIdx]) commit(suggestions[activeIdx].ticker)
      else commit(input.trim().toUpperCase())
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx(i => Math.min(i + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => Math.max(i - 1, -1))
    } else if (e.key === 'Escape') {
      setShowDrop(false)
    }
  }

  return (
    <header className="topbar">
      {/* Left: search with typeahead */}
      <div className="topbar-left" style={{ position: 'relative' }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <input
            ref={inputRef}
            className="ticker-input"
            type="text"
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={handleKey}
            onFocus={() => input && setShowDrop(true)}
            placeholder="search ticker…"
            maxLength={10}
            spellCheck={false}
            autoComplete="off"
            disabled={loading}
            style={{ paddingRight: 32 }}
          />
          {/* Magnifying glass inside input */}
          <button
            onClick={() => commit(input.trim().toUpperCase())}
            disabled={loading || !input.trim()}
            style={{
              position: 'absolute', right: 6,
              background: 'none', border: 'none',
              color: input ? 'var(--text2)' : 'var(--text4)',
              cursor: input ? 'pointer' : 'default',
              fontSize: 13, padding: 0, lineHeight: 1,
            }}
            aria-label="Search"
          >
            🔍
          </button>
        </div>

        {/* Dropdown */}
        {showDrop && suggestions.length > 0 && (
          <div ref={dropRef} style={{
            position: 'absolute', top: '100%', left: 0,
            minWidth: 220, background: '#1a1a1a',
            border: '1px solid #444', zIndex: 500,
            marginTop: 2,
          }}>
            {suggestions.map((s, i) => (
              <div
                key={s.ticker}
                onMouseDown={() => commit(s.ticker)}
                style={{
                  display: 'flex', justifyContent: 'space-between',
                  alignItems: 'center', padding: '6px 10px',
                  cursor: 'pointer', fontSize: 12,
                  background: i === activeIdx ? '#222' : 'transparent',
                }}
                onMouseEnter={() => setActiveIdx(i)}
              >
                <span style={{ color: '#fff', fontWeight: 500 }}>{s.ticker}</span>
                {s.name && <span style={{ color: '#555', fontSize: 10, maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</span>}
              </div>
            ))}
          </div>
        )}

        {company && !showDrop && (
          <span className="topbar-company">{company}</span>
        )}
      </div>

      {/* Center: index ticker */}
      <div className="index-ticker-wrap">
        <div className="index-ticker-track">
          {TICKER_ITEMS.map((item, i) => (
            <div key={i} className="index-item">
              <span className="index-name">{item.name}</span>
              <span className="index-value">{item.value}</span>
              <span className={`index-change ${item.pos ? 'pos' : 'neg'}`}>{item.change}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right: controls */}
      <div className="topbar-right">
        <select className="ctrl-select" value={font} onChange={e => onFont(e.target.value)} title="Font family">
          <option value="ibm">IBM Plex Mono</option>
          <option value="courier">Courier New</option>
          <option value="jetbrains">JetBrains Mono</option>
          <option value="fira">Fira Code</option>
        </select>
        <select className="ctrl-select" value={fontSize} onChange={e => onFontSize(Number(e.target.value))} title="Font size" style={{ width: 40 }}>
          {[12, 13, 14, 15, 16].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="theme-toggle" onClick={onTheme} title={theme === 'dark' ? 'Light mode' : 'Dark mode'} aria-label="Toggle theme">◐</button>
        <span className="topbar-datetime">{datetime}</span>
      </div>
    </header>
  )
}

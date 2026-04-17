'use client'

import { ReactNode, useState, useEffect } from 'react'

interface PanelProps {
  ptype:    string
  pticker:  string | null
  onClose?: () => void
  children: ReactNode
  span?:    number
}

export function Panel({ ptype, pticker, onClose, children, span = 1 }: PanelProps) {
  const [maximized, setMaximized] = useState(false)

  // ESC to restore
  useEffect(() => {
    if (!maximized) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setMaximized(false) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [maximized])

  const normalStyle: React.CSSProperties = span > 1 ? { gridColumn: `span ${span}` } : {}

  const maxStyle: React.CSSProperties = {
    position: 'fixed',
    top: 44,   // clears topbar
    left: 48,  // clears side menu
    right: 0, bottom: 0,
    zIndex: 1000,
    background: 'var(--bg2)',
    border: '1px solid var(--border2)',
    display: 'flex',
    flexDirection: 'column',
  }

  return (
    <div className="panel" style={maximized ? maxStyle : normalStyle}>
      {/* Header — always pinned at top, even in fullscreen */}
      <div className="panel-header" style={maximized ? {
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--bg2)',
        borderBottom: '1px solid var(--border2)',
      } : {}}>
        <div className="panel-header-left">
          <span className="panel-ptype">{ptype}</span>
          <span className="panel-pticker">{pticker ?? '—'}</span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            className="panel-close"
            onClick={() => setMaximized(m => !m)}
            title={maximized ? 'Restore (Esc)' : 'Maximize'}
            style={{ fontSize: 12, opacity: 0.7 }}
          >
            {maximized ? '⊡' : '⊞'}
          </button>
          {onClose && (
            <button
              className="panel-close"
              onClick={maximized ? () => setMaximized(false) : onClose}
              aria-label={maximized ? 'Exit fullscreen' : 'Close panel'}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div
        className="panel-body"
        style={maximized ? { flex: 1, overflow: 'auto', padding: 16 } : {}}
      >
        {children}
      </div>
    </div>
  )
}

export function PanelEmpty({ icon, label }: { icon?: string; label: string }) {
  return (
    <div className="panel-empty">
      {icon && <span className="panel-empty-icon">{icon}</span>}
      <span>{label}</span>
    </div>
  )
}

export function PanelLoading({ label }: { label?: string }) {
  return (
    <div className="panel-empty">
      <span className="loading-dots">{label ?? 'loading'}</span>
    </div>
  )
}

export function PanelGrid({ children }: { children: ReactNode }) {
  return <div className="panel-grid">{children}</div>
}



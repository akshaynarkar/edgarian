'use client'

interface PanelDef {
  id: string
  abbr: string
  label: string
  primary: boolean
}

const PANELS: PanelDef[] = [
  { id: 'signals',    abbr: 'SIG', label: 'Signals',        primary: true  },
  { id: 'filing',     abbr: 'FIL', label: 'Filing Reader',  primary: true  },
  { id: 'financials', abbr: 'FIN', label: 'Financials',     primary: true  },
  { id: 'insider',    abbr: 'INS', label: 'Insider · F4',   primary: true  },
  { id: 'peers',      abbr: 'PRR', label: 'Peer Compare',   primary: false },
  { id: 'diff',       abbr: 'DIF', label: 'Filing Diff',    primary: false },
]

interface SideMenuProps {
  activePanels: Set<string>
  onToggle: (id: string) => void
}

export default function SideMenu({ activePanels, onToggle }: SideMenuProps) {
  const primary   = PANELS.filter(p => p.primary)
  const secondary = PANELS.filter(p => !p.primary)

  return (
    <aside className="sidemenu">
      {/* Logo */}
      <div className="sidemenu-logo" title="Edgarian">
        <span className="logo-E">E</span>
        <span className="logo-D">D</span>
        <span className="logo-G">G</span>
        <span className="logo-R">R</span>
      </div>

      {/* Primary panel toggles */}
      {primary.map(p => (
        <button
          key={p.id}
          className={`panel-toggle${activePanels.has(p.id) ? ' active' : ''}`}
          onClick={() => onToggle(p.id)}
          aria-label={p.label}
          aria-pressed={activePanels.has(p.id)}
        >
          {p.abbr}
          <span className="panel-toggle-tooltip">{p.label}</span>
        </button>
      ))}

      <div className="sidemenu-divider" />

      {/* Secondary panel toggles */}
      {secondary.map(p => (
        <button
          key={p.id}
          className={`panel-toggle${activePanels.has(p.id) ? ' active' : ''}`}
          onClick={() => onToggle(p.id)}
          aria-label={p.label}
          aria-pressed={activePanels.has(p.id)}
        >
          {p.abbr}
          <span className="panel-toggle-tooltip">{p.label}</span>
        </button>
      ))}
    </aside>
  )
}

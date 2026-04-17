'use client'

import { useState, useEffect } from 'react'
import SideMenu from '@/components/SideMenu'
import Topbar from '@/components/Topbar'
import { Panel, PanelGrid, PanelEmpty, PanelLoading } from '@/components/PanelShell'
import SignalsPanel from '@/components/panels/SignalsPanel'
import FilingPanel, { type FilingJump } from '@/components/panels/FilingPanel'
import FinancialsPanel from '@/components/panels/FinancialsPanel'
import InsiderPanel from '@/components/panels/InsiderPanel'

const DEFAULT_PANELS = new Set(['signals', 'filing', 'financials', 'insider'])

const PANEL_META: Record<string, { ptype: string }> = {
  signals:    { ptype: 'SIGNALS' },
  filing:     { ptype: 'FILING READER' },
  financials: { ptype: 'FINANCIALS · INCOME' },
  insider:    { ptype: 'INSIDER · FORM 4' },
  peers:      { ptype: 'PEER COMPARISON' },
  diff:       { ptype: 'FILING DIFF' },
}

export default function Home() {
  const [activePanels, setActivePanels] = useState<Set<string>>(DEFAULT_PANELS)
  const [ticker,   setTicker]   = useState<string | null>(null)
  const [company,  setCompany]  = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)
  const [font,     setFont]     = useState('ibm')
  const [fontSize, setFontSize] = useState(13)
  const [theme,       setTheme]       = useState<'dark' | 'light'>('dark')
  const [sectionDiffs,  setSectionDiffs]  = useState<any>(null)
  const [jumpTo,        setJumpTo]        = useState<FilingJump | null>(null)
  const [signalsData,   setSignalsData]   = useState<any>(null)

  // Apply font/size/theme to document
  useEffect(() => {
    const el = document.documentElement
    el.dataset.theme = theme
    el.dataset.font  = font === 'ibm' ? '' : font
    el.style.setProperty('--font-size', `${fontSize}px`)
  }, [font, fontSize, theme])

  const togglePanel = (id: string) => {
    setActivePanels(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleLoad = async (t: string) => {
    setLoading(true)
    setTicker(t)
    setCompany(null)
    setSectionDiffs(null)
    setJumpTo(null)
    setSignalsData(null)
    try {
      const res = await fetch(`http://localhost:8000/company/${t}`)
      if (res.ok) {
        const data = await res.json()
        setCompany(data.name ?? t)
      } else {
        setCompany(t)
      }
    } catch {
      setCompany(t)
    } finally {
      setLoading(false)
    }
  }

  const orderedPanels = [
    'signals', 'filing', 'financials', 'insider', 'peers', 'diff'
  ].filter(id => activePanels.has(id))

  return (
    <div className="shell">
      <SideMenu
        activePanels={activePanels}
        onToggle={togglePanel}
      />

      <Topbar
        company={company}
        loading={loading}
        onLoad={handleLoad}
        font={font}
        fontSize={fontSize}
        theme={theme}
        onFont={setFont}
        onFontSize={setFontSize}
        onTheme={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
      />

      <main className="main">
        {orderedPanels.length === 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--text4)', fontSize: 11,
            letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>
            no panels open — toggle from side menu
          </div>
        ) : (
          <PanelGrid>
            {orderedPanels.map(id => (
              <Panel
                key={id}
                ptype={PANEL_META[id].ptype}
                pticker={ticker}
                onClose={() => togglePanel(id)}
              >
                {id === 'signals' ? (
                  <SignalsPanel
                    ticker={ticker}
                    onSectionDiffs={setSectionDiffs}
                    onSignalsData={setSignalsData}
                    onFlagClick={(jump) => {
                      setJumpTo(jump)
                      setActivePanels(prev => { const n = new Set(prev); n.add('filing'); return n })
                    }}
                  />
                ) : id === 'filing' ? (
                  <FilingPanel
                    ticker={ticker}
                    sectionDiffs={sectionDiffs}
                    jumpTo={jumpTo}
                    onJumpConsumed={() => setJumpTo(null)}
                  />
                ) : id === 'financials' ? (
                  <FinancialsPanel
                    ticker={ticker}
                    metricsDiff={signalsData?.metrics_diff ?? null}
                    periods={signalsData ? { prior: signalsData.prior_period, current: signalsData.current_period } : null}
                  />
                ) : id === 'insider' ? (
                  <InsiderPanel ticker={ticker} />
                ) : ticker ? (
                  <PanelEmpty label={`${id} panel — coming next`} />
                ) : (
                  <PanelEmpty icon="○" label="enter ticker to load" />
                )}
              </Panel>
            ))}
          </PanelGrid>
        )}
      </main>
    </div>
  )
}

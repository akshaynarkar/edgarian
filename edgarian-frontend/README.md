# Edgarian — Frontend

Next.js 14 · App Router · IBM Plex Mono · No external UI libs

## Setup

```bash
# 1. Bootstrap (run once in parent dir)
npx create-next-app@14 edgarian-frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"
cd edgarian-frontend

# 2. Replace generated files with these files (copy all files from this zip)
#    Overwrite: app/globals.css, app/layout.tsx, app/page.tsx
#    Add:       components/SideMenu.tsx, components/Topbar.tsx, components/PanelShell.tsx
#    Add:       public/manifest.json, next.config.js

# 3. Run
npm run dev
# → http://localhost:3000

# 4. Start backend (separate terminal)
cd ../edgarian-v4
$env:EDGAR_IDENTITY="you@email.com"   # Windows
# export EDGAR_IDENTITY="you@email.com"  # Mac/Linux
uvicorn main:app --reload
# → http://localhost:8000
```

## File Structure

```
app/
  globals.css       — all CSS tokens + base styles (no Tailwind used here)
  layout.tsx        — root layout, metadata
  page.tsx          — shell orchestration (state, panel toggling, ticker load)
components/
  SideMenu.tsx      — 48px side menu, logo, panel toggles with tooltips
  Topbar.tsx        — search input, LOAD button, index ticker, font/theme controls
  PanelShell.tsx    — Panel, PanelGrid, PanelEmpty, PanelLoading
public/
  manifest.json     — PWA manifest
```

## Build Order (remaining phases)

- [ ] Signals panel  → `components/panels/SignalsPanel.tsx`
- [ ] Filing Reader  → `components/panels/FilingPanel.tsx`
- [ ] Financials     → `components/panels/FinancialsPanel.tsx`
- [ ] Insider        → `components/panels/InsiderPanel.tsx`
- [ ] Peer Compare   → `components/panels/PeersPanel.tsx` (after Phase 2 SIC data)
- [ ] Light mode polish
- [ ] PWA icons

## API

Backend: `http://localhost:8000`  
Swagger: `http://localhost:8000/docs`

Key endpoints used by frontend:
- `GET /company/{ticker}` → name, CIK, SIC
- `GET /company/{ticker}/signals?fast=true` → fast metrics + flags (~2s)
- `GET /company/{ticker}/signals` → full with section diffs (~8-35s)
- `GET /company/{ticker}/filing/{section}` → section text + truncation
- `GET /company/{ticker}/financials` → income statement
- `GET /company/{ticker}/insider` → Form 4 activity

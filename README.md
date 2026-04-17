# Edgarian backend scaffold

Implemented in the requested backend-first order:

1. project scaffold
2. `core/filing_cleaner.py`
3. `core/diff.py`
4. `core/flags.py`
5. `core/owner_earnings.py`
6. `core/insider_cluster.py`
7. `core/peer_metrics.py`
8. FastAPI routers and `main.py`
9. placeholder `frontend/` directory
10. core tests

## Notes

- Call `set_identity()` before any edgartools call.
- `filing.financials` is not used; routers go through filing objects and XBRL accessors.
- XBRL access is guarded because older filings may not have it.
- Peer-universe discovery is scaffolded with a stable API surface, but same-SIC enumeration may need a small version-specific adapter once you test against your local edgartools install.
- `core/filing_cleaner.py` includes attribution comments for the requested logic port.

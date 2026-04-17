from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.company import router as company_router
from routers.signals import router as signals_router
from routers.insider import router as insider_router
from routers.peers import router as peers_router
from routers.financials import router as financials_router
from routers.filing import router as filing_router

app = FastAPI(title="Edgarian", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(company_router)
app.include_router(signals_router)
app.include_router(insider_router)
app.include_router(peers_router)
app.include_router(financials_router)
app.include_router(filing_router)


@app.get("/")
def root() -> dict:
    return {"app": "Edgarian", "status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)

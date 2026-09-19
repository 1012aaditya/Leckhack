"""HTTP surface for the citation auditor."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .audit import audit_text
from .config import get_settings, get_source
from .models import AuditReport
from .sources.courtlistener import MAX_TEXT_CHARS

app = FastAPI(
    title="Citation Auditor",
    description="Checks whether the cases in AI-generated legal text are real.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "live_database": settings.has_live_source,
        "source": get_source(settings).name,
    }


@app.post("/audit", response_model=AuditReport)
async def audit(request: AuditRequest) -> AuditReport:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="No text supplied.")
    return await audit_text(request.text, get_source())

"""HTTP surface for the citation auditor.

Serves both the JSON API and the single-page frontend, so `uvicorn app.main:app`
is the entire product. No build step, no second process, nothing to go wrong at
a venue.
"""

from __future__ import annotations

import io
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import describe_components, get_auditor, get_settings
from .models import AuditReport
from .sources.courtlistener import MAX_TEXT_CHARS

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(
    title="Citation Auditor",
    description="Checks whether the cases in AI-generated legal text are real.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
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
        "model_judge": settings.has_model_judge,
        "semantic_embeddings": settings.has_semantic_embeddings,
        "components": describe_components(settings),
    }


@app.post("/audit", response_model=AuditReport)
async def audit(request: AuditRequest) -> AuditReport:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="No text supplied.")
    return await get_auditor().run(request.text)


@app.post("/audit/pdf", response_model=AuditReport)
async def audit_pdf(file: UploadFile = File(...)) -> AuditReport:
    """Audit a PDF brief. Text extraction only - no OCR of scanned pages."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Please upload a PDF.")

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(await file.read()))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        raise HTTPException(
            status_code=503, detail="PDF support is not installed on this server."
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read that PDF: {exc}")

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text found. Scanned PDFs need OCR, which this does not do.",
        )
    return await get_auditor().run(text[:MAX_TEXT_CHARS])


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

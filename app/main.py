"""Flashpoint — FastAPI backend for incident extraction and PDF export."""

from __future__ import annotations

import logging
import time
import uuid
from io import BytesIO
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.extractor import extract_incident_data, OLLAMA_URL
from app.pdf_generator import generate_pdf
from app.schemas import IncidentReport

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("flashpoint")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # project root

app = FastAPI(title="Flashpoint", version="0.1.0")

# --- CORS (allow localhost dev servers) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------------------------------------------------------
# Request-logging middleware (console only, no external deps)
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    """Lightweight probe — reports Ollama reachability."""
    ollama_ok = False
    try:
        # Ollama exposes a simple GET on its root that returns "Ollama is running"
        resp = httpx.get(OLLAMA_URL.replace("/api/generate", ""), timeout=3.0)
        ollama_ok = resp.status_code == 200
    except Exception:  # noqa: BLE001
        pass
    return {"status": "ok", "ollama": ollama_ok}


@app.get("/")
async def index(request: Request):
    """Serve the single-page UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/extract")
async def extract(description: str = Form(...)):
    """Accept an incident description, run LLM extraction, return JSON.

    Response shape:
        {success: bool, data: dict | null, error: str | null}
    """
    if not description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty.")

    try:
        report: IncidentReport = extract_incident_data(description)
        return JSONResponse(
            {"success": True, "data": report.model_dump(), "error": None}
        )
    except ValueError as exc:
        return JSONResponse(
            {"success": False, "data": None, "error": str(exc)},
            status_code=422,
        )
    except Exception as exc:  # noqa: BLE001 — catch-all for unexpected LLM issues
        return JSONResponse(
            {"success": False, "data": None, "error": f"Unexpected error: {exc}"},
            status_code=500,
        )


@app.post("/download")
async def download(report: IncidentReport):
    """Generate a PDF from a validated IncidentReport and stream it back.

    Returns a StreamingResponse with Content-Disposition so the browser
    triggers a file download.
    """
    try:
        pdf_bytes = generate_pdf(report)
        short_id = uuid.uuid4().hex[:8]
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="incident_report_{short_id}.pdf"'
                )
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"PDF generation failed: {exc}"
        ) from exc

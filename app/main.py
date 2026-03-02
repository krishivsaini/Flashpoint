"""Flashpoint — FastAPI backend for incident extraction and PDF export."""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.extractor import extract_incident_data
from app.pdf_generator import generate_pdf
from app.schemas import IncidentReport

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # project root

app = FastAPI(title="Flashpoint", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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

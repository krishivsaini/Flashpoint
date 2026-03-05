"""Tests for the FastAPI endpoints — all LLM calls are mocked."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import IncidentReport


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

client = TestClient(app)

# A fully valid IncidentReport payload reused across tests.
VALID_REPORT: dict = {
    "location": "742 Evergreen Terrace, Springfield",
    "datetime": "2026-03-01T14:30:00",
    "incident_type": "structure fire",
    "units_involved": ["Engine 7", "Ladder 3"],
    "injuries": 2,
    "hazards": ["propane tanks", "downed power lines"],
    "summary": "Two-alarm structure fire with partial roof collapse.",
}


def _dummy_report() -> IncidentReport:
    """Build a valid IncidentReport from VALID_REPORT for mock returns."""
    return IncidentReport(**VALID_REPORT)


# ---------------------------------------------------------------------------
# GET /  — serves the single-page UI
# ---------------------------------------------------------------------------


class TestIndex:
    def test_returns_200(self) -> None:
        response = client.get("/")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /health  — Ollama reachability probe
# ---------------------------------------------------------------------------


class TestHealth:
    @patch("app.main.httpx.get")
    def test_health_ollama_ok(self, mock_get: MagicMock) -> None:
        """When Ollama is reachable, ollama should be True."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["ollama"] is True

    @patch("app.main.httpx.get", side_effect=Exception("connection refused"))
    def test_health_ollama_down(self, mock_get: MagicMock) -> None:
        """When Ollama is unreachable, ollama should be False."""
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["ollama"] is False


# ---------------------------------------------------------------------------
# POST /extract  — LLM extraction endpoint
# ---------------------------------------------------------------------------


class TestExtract:
    """Mock extract_incident_data so tests never touch Ollama."""

    @patch("app.main.extract_incident_data")
    def test_valid_description_returns_success(
        self, mock_extract: MagicMock
    ) -> None:
        """A well-formed description should return success:true with all fields."""
        mock_extract.return_value = _dummy_report()

        response = client.post(
            "/extract",
            data={"description": "Fire at 742 Evergreen Terrace."},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None

        # Ensure every IncidentReport field is present in the response data.
        data = body["data"]
        for field_name in IncidentReport.model_fields:
            assert field_name in data, f"Missing field: {field_name}"

        # Spot-check a few values
        assert data["location"] == VALID_REPORT["location"]
        assert data["injuries"] == VALID_REPORT["injuries"]
        assert data["units_involved"] == VALID_REPORT["units_involved"]

    @patch("app.main.extract_incident_data")
    def test_extractor_value_error_returns_failure(
        self, mock_extract: MagicMock
    ) -> None:
        """When extract_incident_data raises ValueError, the API should
        return success:false with the error message."""
        mock_extract.side_effect = ValueError("Cannot connect to Ollama")

        response = client.post(
            "/extract",
            data={"description": "Some incident happened."},
        )

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["data"] is None
        assert "Cannot connect to Ollama" in body["error"]

    def test_empty_description_returns_400(self) -> None:
        """An empty/whitespace description should be rejected."""
        response = client.post("/extract", data={"description": "   "})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /download  — PDF generation endpoint
# ---------------------------------------------------------------------------


class TestDownload:
    def test_returns_pdf_with_correct_headers(self) -> None:
        """Posting a valid IncidentReport JSON should return PDF bytes
        with the correct Content-Type and Content-Disposition."""
        response = client.post("/download", json=VALID_REPORT)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment")
        assert "incident_report_" in disposition
        assert disposition.endswith('.pdf"')

        # PDF bytes should start with the %PDF magic header.
        assert response.content[:5] == b"%PDF-"

    def test_invalid_report_returns_422(self) -> None:
        """Missing required fields should trigger Pydantic validation error."""
        response = client.post("/download", json={"location": "Somewhere"})
        assert response.status_code == 422

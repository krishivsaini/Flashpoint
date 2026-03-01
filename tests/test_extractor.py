"""Tests for app.extractor — all Ollama calls are mocked."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.extractor import extract_incident_data, _parse_json
from app.schemas import IncidentReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAYLOAD: dict = {
    "location": "742 Evergreen Terrace, Springfield",
    "datetime": "2026-03-01T14:30:00",
    "incident_type": "structure fire",
    "units_involved": ["Engine 7", "Ladder 3"],
    "injuries": 2,
    "hazards": ["propane tanks", "downed power lines"],
    "summary": "Two-alarm structure fire with partial roof collapse.",
}


def _mock_response(body: dict | str, status_code: int = 200) -> MagicMock:
    """Create a fake ``httpx.Response``-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    if isinstance(body, dict):
        resp.json.return_value = body
        resp.text = json.dumps(body)
    else:
        resp.json.return_value = json.loads(body) if isinstance(body, str) else body
        resp.text = body
    resp.raise_for_status.return_value = None
    return resp


def _ollama_body(content: str) -> dict:
    """Wrap *content* in the Ollama ``/api/generate`` response envelope."""
    return {"response": content}


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestValidExtraction:
    """LLM returns clean JSON that maps to IncidentReport."""

    @patch("app.extractor.httpx.post")
    def test_returns_correct_incident_report(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response(
            _ollama_body(json.dumps(VALID_PAYLOAD))
        )
        report = extract_incident_data("Some fire happened at 742 Evergreen.")
        assert isinstance(report, IncidentReport)
        assert report.location == VALID_PAYLOAD["location"]
        assert report.injuries == 2
        assert report.units_involved == ["Engine 7", "Ladder 3"]

    @patch("app.extractor.httpx.post")
    def test_string_injuries_coerced_to_int(self, mock_post: MagicMock) -> None:
        """Pydantic v2 coerces ``"3"`` → ``3`` in strict=False (default)."""
        payload = {**VALID_PAYLOAD, "injuries": "3"}
        mock_post.return_value = _mock_response(
            _ollama_body(json.dumps(payload))
        )
        report = extract_incident_data("Minor event.")
        assert report.injuries == 3
        assert isinstance(report.injuries, int)


# ---------------------------------------------------------------------------
# Network / server error tests
# ---------------------------------------------------------------------------


class TestNetworkErrors:
    @patch("app.extractor.httpx.post", side_effect=httpx.ConnectError("refused"))
    def test_ollama_down_raises_value_error(self, mock_post: MagicMock) -> None:
        with pytest.raises(ValueError, match="Cannot connect"):
            extract_incident_data("anything")

    @patch("app.extractor.httpx.post", side_effect=httpx.TimeoutException("slow"))
    def test_timeout_raises_value_error(self, mock_post: MagicMock) -> None:
        with pytest.raises(ValueError, match="timed out"):
            extract_incident_data("anything")


# ---------------------------------------------------------------------------
# Malformed output tests
# ---------------------------------------------------------------------------


class TestMalformedOutput:
    @patch("app.extractor.httpx.post")
    def test_malformed_json_raises_value_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response(
            _ollama_body("This is not JSON at all!!!")
        )
        with pytest.raises(ValueError, match="Failed to extract valid JSON"):
            extract_incident_data("anything")


# ---------------------------------------------------------------------------
# _parse_json edge-case tests
# ---------------------------------------------------------------------------


class TestParseJson:
    def test_handles_markdown_fences(self) -> None:
        raw = '```json\n' + json.dumps(VALID_PAYLOAD) + '\n```'
        result = _parse_json(raw)
        assert result == VALID_PAYLOAD

    def test_handles_preamble_text_before_json(self) -> None:
        raw = (
            "Sure! Here is the extracted data:\n\n"
            + json.dumps(VALID_PAYLOAD)
        )
        result = _parse_json(raw)
        assert result == VALID_PAYLOAD

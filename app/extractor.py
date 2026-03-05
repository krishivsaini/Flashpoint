"""LLM-powered incident data extraction via Ollama (Mistral)."""

from __future__ import annotations

import json
import os
import re

import httpx
from pydantic import ValidationError

from app.schemas import IncidentReport

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/generate"
MODEL = os.getenv("MODEL", "mistral")


def _build_prompt(description: str) -> str:
    """Build a single-shot extraction prompt that includes the JSON schema."""
    field_descriptions = "\n".join(
        f"  - {name} ({info.annotation.__name__ if hasattr(info.annotation, '__name__') else str(info.annotation)}): {info.description}"
        for name, info in IncidentReport.model_fields.items()
    )
    return (
        "You are a structured-data extraction assistant. "
        "Given the incident description below, extract the fields into JSON.\n\n"
        f"### Required JSON fields\n{field_descriptions}\n\n"
        f"### Incident description\n{description}\n\n"
        "Respond ONLY with valid JSON matching the schema above."
    )


def _parse_json(raw: str) -> dict:
    """Attempt to parse JSON from potentially messy LLM output.

    Strategy (in order):
      1. Direct ``json.loads`` on the full string.
      2. Strip markdown code fences and retry.
      3. Regex hunt for the first ``{…}`` block.
    """
    # --- attempt 1: direct parse ---
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # --- attempt 2: strip markdown fences ---
    stripped = re.sub(r"```(?:json)?\s*", "", raw)
    stripped = stripped.replace("```", "").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # --- attempt 3: regex hunt for first {…} block ---
    match = re.search(r"\{[\s\S]*\}", stripped)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Failed to extract valid JSON from the model response. "
        f"Raw output: {raw[:500]}"
    )


def extract_incident_data(description: str) -> IncidentReport:
    """Send *description* to Ollama and return a validated ``IncidentReport``.

    Raises:
        ValueError: On network errors, timeouts, bad HTTP status, malformed
            JSON, or Pydantic validation failures — always with a
            human-readable message.
    """
    prompt = _build_prompt(description)

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
        },
    }

    try:
        response = httpx.post(OLLAMA_URL, json=payload, timeout=120.0)
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise ValueError(
            f"Cannot connect to Ollama at {OLLAMA_URL}. "
            "Is the Ollama server running?"
        ) from exc
    except httpx.TimeoutException as exc:
        raise ValueError(
            f"Request to Ollama timed out after 120 s. "
            "Try a shorter description or increase the timeout."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ValueError(
            f"Ollama returned HTTP {exc.response.status_code}: "
            f"{exc.response.text[:300]}"
        ) from exc

    body = response.json()
    raw_text: str = body.get("response", "")

    try:
        data = _parse_json(raw_text)
    except ValueError:
        raise  # already has a readable message

    try:
        return IncidentReport.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"LLM output did not match the IncidentReport schema: {exc}"
        ) from exc

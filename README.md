# 🔥 Flashpoint

**AI-powered incident report extraction and PDF generation for fire departments — built as a modern replacement for FireForm.**

---

## Why Flashpoint?

- **GSoC 2026 Portfolio Piece** — Demonstrates end-to-end LLM integration, structured data extraction, and production-grade API design for the [Google Summer of Code](https://summerofcode.withgoogle.com/) programme.
- **Solves a Real Problem** — FireForm required manual copy-pasting from radio transcripts into web forms. Flashpoint replaces that with a single text box: paste the description, get a validated report.
- **Local-First AI** — Runs entirely on your machine using [Ollama](https://ollama.com/) + Mistral — no API keys, no cloud dependency, no data leaving the station.

---

## Architecture

```
┌──────────────┐       POST /extract        ┌───────────────┐
│              │ ─────────────────────────▶  │               │
│   Browser    │                             │   FastAPI     │
│  (index.html)│ ◀─────────────────────────  │   Server      │
│              │    JSON {success, data}     │               │
└──────────────┘                             └───────┬───────┘
       │                                             │
       │  POST /download                             │ httpx.post
       │  (IncidentReport JSON)                      ▼
       │                                     ┌───────────────┐
       │                                     │   Ollama       │
       │                                     │   (Mistral)    │
       │                                     └───────┬───────┘
       │                                             │
       ▼                                             ▼
┌──────────────┐                             ┌───────────────┐
│  PDF Download │ ◀── ReportLab ◀─────────── │   Pydantic    │
│  (report.pdf) │                            │   Validation  │
└──────────────┘                             └───────────────┘
```

**Flow:** Browser → FastAPI → Ollama/Mistral → Pydantic validation → JSON response (or PDF via ReportLab).

---

## Quickstart

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| [Ollama](https://ollama.com/) | Latest |

### 1. Clone & install

```bash
git clone https://github.com/krishivsaini/Flashpoint.git
cd Flashpoint
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Ollama with Mistral

```bash
ollama pull mistral
ollama serve          # keep running in a separate terminal
```

### 3. Launch Flashpoint

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### 4. Run tests

```bash
pytest -v
```

---

## Improvements over FireForm

| Feature | FireForm | Flashpoint |
|---|---|---|
| Data entry | Manual form fields | AI extracts from plain text |
| Validation | Client-side only | Pydantic v2 server-side schemas |
| PDF generation | None | Professional ReportLab PDF with one click |
| LLM provider | None (no AI) | Local Ollama/Mistral — zero cloud dependency |
| API design | Monolithic Django views | FastAPI with async endpoints & OpenAPI docs |
| Error handling | Generic 500 pages | Structured JSON errors with granular status codes |
| Testing | Minimal | Pytest suite with mocked LLM calls |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| LLM runtime | [Ollama](https://ollama.com/) (Mistral 7B) |
| HTTP client | [httpx](https://www.python-httpx.org/) |
| Data validation | [Pydantic v2](https://docs.pydantic.dev/) |
| PDF generation | [ReportLab](https://docs.reportlab.com/) (Platypus) |
| Templating | [Jinja2](https://jinja.palletsprojects.com/) |
| Testing | [pytest](https://docs.pytest.org/) + FastAPI TestClient |

---

## GSoC 2026 Context

Flashpoint is part of a portfolio targeting **Google Summer of Code 2026**. The project demonstrates competency in LLM application development, schema-driven design, and API engineering — skills directly applicable to GSoC organisations working on AI-assisted tools, data extraction pipelines, and public-safety software. It serves as a focused companion project alongside [ModelPulse](https://github.com/krishivsaini/ModelPulse), showing breadth across both reinforcement-learning simulation and NLP-powered data extraction.

---

## License

MIT

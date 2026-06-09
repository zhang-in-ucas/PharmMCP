# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

PharmMCP is a drug molecule intelligent query and screening agent built on the MCP (Model Context Protocol). It integrates PubChem, ChEMBL, and PubMed APIs and exposes 8 tools that an LLM (DeepSeek via OpenAI-compatible interface) can call. Multiple frontends exist: terminal (`client.py`, `client_http.py`) and a Gradio web UI (`web_ui.py`).

## Commands

```bash
# Install dependencies (conda env recommended)
conda create -n agent310 python=3.10 -y && conda activate agent310
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy and edit .env (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, MCP_SERVER_URL)
cp .env.example .env

# Run connectivity tests
python test_api.py

# Run tool integration tests
python test_tools.py

# Start MCP server (stdio mode — for MCP Inspector or client.py)
python server.py

# Start MCP server (HTTP mode — for web_ui.py or client_http.py)
python server.py --http

# Terminal client (stdio mode — launches server as subprocess)
python client.py

# Terminal client (HTTP mode — server.py --http must be running first)
python client_http.py

# Web UI (server.py --http must be running first)
python web_ui.py
# Opens at http://127.0.0.1:7860

# Docker
docker build -t pharmmcp .
docker run -p 8000:8000 --env-file .env pharmmcp
```

## Architecture

```
User → Web UI (Gradio) / Terminal Client
         → LLM (DeepSeek, OpenAI SDK)
              → MCP Client (stdio or streamable-http)
                   → FastMCP Server (server.py)
                        → PubChemClient / ChEMBLClient / PubMedClient (httpx)
                             → PubChem REST API / ChEMBL REST API / PubMed E-utilities
```

### Core layers

**Server (`server.py`)** — FastMCP application registering 8 tools as async functions via `@mcp.tool()`. Supports `stdio` (default) and `streamable-http` (`--http` flag, port 8000) transports. Tools are the public API; the LLM decides which to call.

**API clients** — Three standalone async clients using `httpx.AsyncClient` with lazy-init singleton pattern: each module exports a module-level instance (`pubchem`, `chembl`, `pubmed`) that reuses a single connection pool across all requests, avoiding repeated TCP/TLS handshakes. Each has retry logic (2 retries), timeout handling (30s), and no API key requirements. PubChem additionally has rate limiting with `asyncio.Lock`-guarded scheduling (≥0.4s between requests to stay under 3 req/s). All return `Optional[dict/list]` — `None` means "not found" or "request failed".

**Local computation (`druglikeness.py`)** — Lipinski Rule of Five check with no external dependencies (no rdkit). Pure math: MW ≤ 500, XLogP ≤ 5, HBD ≤ 5, HBA ≤ 10. Returns passes/violations/details. Handles `None` values gracefully (marked as "缺失"). Input comes from `PubChemClient.get_properties()`.

**Pipeline (`pipeline.py`)** — Orchestrates 6 steps using `asyncio.gather` for 2-phase concurrency: Phase 1 runs PubChem search ‖ ChEMBL search in parallel; Phase 2 runs properties ‖ similar ‖ drug_info ‖ activities in parallel. Each step has a 10s timeout via `asyncio.wait_for`; total pipeline has a 45s hard cap via `asyncio.wait_for`. Failed steps are skipped with a note rather than aborting. This is called by the `drug_screen` tool.

**Clients** — Both `client.py` (stdio) and `client_http.py` (HTTP) follow the same pattern: connect to MCP server, fetch tool list, convert MCP tools to OpenAI function-calling format, then enter a multi-round chat loop (max 10 rounds). The `web_ui.py` uses a threading + queue pattern to bridge async MCP calls with Gradio's synchronous streaming interface.

### Tool dependency chain

Several tools require data from prior tools — the LLM is instructed to chain them:

1. `search_molecule` → returns CID + SMILES (prerequisite for tools 2, 5, 6)
2. `get_molecule_properties(cid)` → returns MW, LogP, HBD, HBA, TPSA
3. `get_drug_targets(molecule_name)` → ChEMBL activities (IC50, Ki)
4. `get_clinical_info(molecule_name)` → clinical phase, indication, approval year
5. `get_similar_molecules(smiles)` → 2D similarity search
6. `filter_by_druglikeness(cid)` → Lipinski pass/fail
7. `search_literature(query)` → PubMed papers
8. `drug_screen(molecule_name)` → all-in-one 6-step pipeline

### Environment variables (`.env`)

| Variable | Purpose | Required |
|---|---|---|
| `LLM_API_KEY` | API key for DeepSeek/OpenAI-compatible LLM | Yes (for clients/web UI) |
| `LLM_BASE_URL` | LLM API base URL (default: `https://api.deepseek.com`) | Yes |
| `LLM_MODEL` | Model name (default: `deepseek-chat`) | Yes |
| `MCP_SERVER_URL` | HTTP mode server URL (default: `http://127.0.0.1:8000/mcp`) | For HTTP clients only |

### Key dependencies

- `fastmcp==2.14.0` — MCP server framework (the `FastMCP` class, `@mcp.tool()` decorator)
- `openai==2.14.0` — LLM client (used in OpenAI-compatible mode for DeepSeek)
- `httpx==0.28.1` — async HTTP for all three API clients
- `gradio>=5.0.0` — Web UI (`gr.ChatInterface`)
- `mcp==1.25.0` — MCP Python SDK (client-side `ClientSession`, transports)

### Testing strategy

There are no unit tests (no pytest, no mocks). Testing is integration-only:
- `test_api.py` — direct API connectivity to PubChem, ChEMBL, PubMed, plus end-to-end pipeline.
- `test_tools.py` — exercises each client method and the pipeline/orchestration functions with real API calls.

## Data source constraints

- **PubChem**: No API key, rate limit 3 req/s. 404 = molecule not found.
- **ChEMBL**: No API key, no rate limit documented. 404 = molecule not found.
- **PubMed**: No API key, rate limit 3 req/s (enforced manually with `asyncio.sleep(0.4)`).
- XLogP values from PubChem can be `None` for some molecules — Lipinski treats missing values as non-violations.

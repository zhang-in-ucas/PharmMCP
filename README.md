# 🧪 PharmMCP — Drug Molecule Intelligence Platform (MCP-Native)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/framework-FastMCP%202.14-purple)](https://github.com/jlowin/fastmcp)
[![MCP](https://img.shields.io/badge/protocol-MCP-black)](https://modelcontextprotocol.io/)
[![Gradio](https://img.shields.io/badge/UI-Gradio%205.x-orange)](https://gradio.app/)

> An **MCP-native** drug molecule intelligence platform. 8 standardized tools, 2-layer architecture, dual transport modes — built to demonstrate how MCP enables composable, extensible AI agent tool ecosystems.

[中文](#中文) | [English](#english)

---

## 🎯 Why This Project Matters

This is not a "wrapper around a few APIs." It's a **production-style demonstration of MCP engineering best practices**:

- ✅ **8 standardized MCP tools** covering the full drug discovery chain
- ✅ **2-layer tool architecture** (Tool → Pipeline) — the same pattern teams use to scale agent capabilities
- ✅ **Dual transport modes** (stdio for local dev, streamable-http for remote deployment) with transport/business layer decoupling
- ✅ **Async high-concurrency design** — httpx.AsyncClient for parallel multi-API calls with timeout management
- ✅ **Real-time streaming Web UI** — tool call progress visualization + streaming LLM output
- ✅ **Built with Claude Code** — architecture, debugging, and validation by the author; code generation AI-assisted

---

## 🏗 Tool Architecture

```
┌──────────────────────────────────────────────────┐
│              PharmMCP Tool System                 │
│                                                    │
│  ┌─────────────┐                                  │
│  │ Pipeline    │  drug_screen                     │
│  │ Layer       │  6-step automated workflow        │
│  │ (多步编排)   │                                  │
│  ├─────────────┤                                  │
│  │  Tool Layer │  search_molecule                 │
│  │  (单步查询)   │  get_molecule_properties         │
│  │             │  get_drug_targets                │
│  │             │  get_clinical_info               │
│  │             │  get_similar_molecules           │
│  │             │  filter_by_druglikeness          │
│  │             │  search_literature               │
│  └─────────────┘                                  │
│         │                                          │
│         ▼                                          │
│  ┌─────────────────────────────────────────────┐ │
│  │  Data Sources                                │ │
│  │  PubChem  │  ChEMBL  │  PubMed               │ │
│  │  (no key) │ (no key) │ (no key)               │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 8 MCP Tools

| # | Tool | Type | Data Source | Description |
|---|------|------|-------------|-------------|
| 1 | `search_molecule` | Query | PubChem | Search by name or SMILES; returns CID, SMILES, MW, formula |
| 2 | `get_molecule_properties` | Query | PubChem | Physicochemical properties: MW, LogP, HBD, HBA, TPSA |
| 3 | `get_drug_targets` | Query | ChEMBL | Target proteins and bioactivity data (IC₅₀, Kᵢ) |
| 4 | `get_clinical_info` | Query | ChEMBL | Clinical phase, indications, approval year |
| 5 | `get_similar_molecules` | Query | PubChem | 2D structural similarity search (Tanimoto) |
| 6 | `filter_by_druglikeness` | Analysis | Local | Lipinski's Rule of Five compliance check |
| 7 | `search_literature` | Query | PubMed | Literature search (title, author, abstract) |
| 8 | `drug_screen` | **Pipeline** | Multi | One-click molecular briefing: 6-step automated workflow |

### Dual Transport Modes

| Mode | Protocol | Use Case |
|------|----------|----------|
| **stdio** | MCP standard I/O | Local development, Claude Desktop integration |
| **streamable-http** | HTTP/SSE | Remote deployment, Web UI, multi-client access |

Transport layer is fully decoupled from business logic — switch modes with one CLI flag (`--http`).

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- LLM API Key (OpenAI-compatible endpoint)

### Setup

```bash
git clone https://github.com/zhang-in-ucas/PharmMCP.git
cd PharmMCP
pip install -r requirements.txt
cp .env.example .env
# Edit .env: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
```

### Test (no LLM needed)

```bash
python test_api.py      # API connectivity test
python test_tools.py    # Tool function tests
```

### Run

```bash
# Mode 1: Terminal chat (stdio)
python client.py

# Mode 2: Web UI (recommended for demos)
# Terminal 1:
python server.py --http
# Terminal 2:
python web_ui.py
# Open http://127.0.0.1:7860

# Mode 3: MCP Inspector (debugging)
npx @modelcontextprotocol/inspector python server.py
```

### Web UI Demo Flow

1. Type a drug name: `aspirin`
2. Watch real-time tool calls: `🔧 search_molecule → ✅ complete → 🔧 get_molecule_properties → ...`
3. Read the streaming AI-generated molecular briefing

---

## 📁 Project Structure

```
PharmMCP/
├── server.py              # MCP Server (8 tools, FastMCP)
├── client.py              # stdio mode client
├── client_http.py         # HTTP mode client
├── web_ui.py              # Gradio Web UI (streaming output)
├── pubchem_client.py      # PubChem API wrapper (async)
├── chembl_client.py       # ChEMBL API wrapper (async)
├── pubmed_client.py       # PubMed API wrapper (async)
├── druglikeness.py        # Lipinski's Rule of Five (local computation)
├── pipeline.py            # Drug screening pipeline (6-step orchestration)
├── test_api.py            # API connectivity tests
├── test_tools.py          # Tool function tests
├── Dockerfile             # Containerized deployment
└── requirements.txt
```

---

## 🔬 Druglikeness: Lipinski's Rule of Five

| Rule | Threshold | Meaning |
|------|-----------|---------|
| Molecular Weight (MW) | ≤ 500 Da | Oral absorption limit |
| LogP | ≤ 5 | Lipophilicity limit |
| H-Bond Donors (HBD) | ≤ 5 | -OH, -NH count |
| H-Bond Acceptors (HBA) | ≤ 10 | O, N heteroatom count |

**Verdict**: ≤ 1 violation → drug-like ✅ | ≥ 2 violations → poor oral bioavailability ⚠️

---

## 🔗 Integration Examples

### With Claude Desktop

```json
{
  "mcpServers": {
    "pharmmcp": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/PharmMCP"
    }
  }
}
```

### With LangGraph Agent

```python
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({"pharmmcp": {...}}) as client:
    tools = client.get_tools()
    agent = create_react_agent(llm, tools)
```

### With Any OpenAI-Compatible Client

The tools are exposed as standard MCP tools — any MCP-compatible client can consume them. See `client.py` / `client_http.py` for reference implementations.

---

## 🔗 Related Projects

- [**MediGuard**](https://github.com/zhang-in-ucas/MediGuard) — Multi-Agent medical safety-compliant consultation system with LangGraph + RAG + two-layer safety review

---

## 📄 License

MIT License.

---

## ✨ Author

Built by a pharmacy-background developer demonstrating how domain expertise + modern AI engineering converge. All tool architecture decisions and debugging done by the author; Claude Code assisted with code generation — exemplifying the "AI tool power user" workflow valued in modern AI engineering teams.

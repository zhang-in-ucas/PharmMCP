# 🧪 PharmMCP — 药物分子智能查询与筛选平台（MCP-Native）

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/framework-FastMCP%202.14-purple)](https://github.com/jlowin/fastmcp)
[![MCP](https://img.shields.io/badge/protocol-MCP-black)](https://modelcontextprotocol.io/)
[![Gradio](https://img.shields.io/badge/UI-Gradio%205.x-orange)](https://gradio.app/)

> 基于 MCP 协议的药物分子智能平台。8 个标准化工具，两层架构，双传输模式 — 展示 MCP 如何构建可组合、可扩展的 AI agent 工具生态。

---

## 🎯 项目亮点

这不是"给几个 API 套层壳"。这是 **MCP 工程最佳实践的完整演示**：

- ✅ **8 个标准化 MCP 工具**，覆盖药物发现全链路
- ✅ **两层工具架构**（单步工具 → 编排流水线）— 规模化 agent 能力的标准模式
- ✅ **双传输模式**（stdio 本地开发 / streamable-http 远程部署），传输层与业务层完全解耦
- ✅ **异步并发架构** — `asyncio.gather` 两阶段并行 API 调用；惰性初始化 `httpx.AsyncClient` 单例复用连接池；`asyncio.Lock` 保护速率限制；分层超时控制（单步 10s / 总超时 45s）
- ✅ **实时流式 Web UI** — 工具调用过程可视化 + LLM 流式输出
- ✅ **AI 协作构建** — 架构设计与调试由作者完成，代码生成由 AI 辅助

---

## 🏗 工具架构

```
┌──────────────────────────────────────────────────┐
│              PharmMCP 工具体系                     │
│                                                    │
│  ┌─────────────┐                                  │
│  │ 编排层       │  drug_screen                     │
│  │ Pipeline    │  6 步自动化流程                   │
│  ├─────────────┤                                  │
│  │ 工具层       │  search_molecule                 │
│  │ Tool        │  get_molecule_properties         │
│  │             │  get_drug_targets                │
│  │             │  get_clinical_info               │
│  │             │  get_similar_molecules           │
│  │             │  filter_by_druglikeness          │
│  │             │  search_literature               │
│  └─────────────┘                                  │
│         │                                          │
│         ▼                                          │
│  ┌─────────────────────────────────────────────┐ │
│  │  数据源                                       │ │
│  │  PubChem  │  ChEMBL  │  PubMed               │ │
│  │  (免费)   │  (免费)   │  (免费)                 │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 8 个 MCP 工具

| # | 工具 | 类型 | 数据源 | 说明 |
|---|------|------|--------|------|
| 1 | `search_molecule` | 查询 | PubChem | 按名称或 SMILES 搜索分子，返回 CID、结构、分子式 |
| 2 | `get_molecule_properties` | 查询 | PubChem | 物化性质：分子量、LogP、氢键供体/受体、TPSA |
| 3 | `get_drug_targets` | 查询 | ChEMBL | 靶点蛋白与生物活性数据（IC₅₀、Kᵢ） |
| 4 | `get_clinical_info` | 查询 | ChEMBL | 临床阶段、适应症、批准年份 |
| 5 | `get_similar_molecules` | 查询 | PubChem | 2D 结构相似性搜索（Tanimoto 系数） |
| 6 | `filter_by_druglikeness` | 分析 | 本地 | Lipinski 五规则类药性判断 |
| 7 | `search_literature` | 查询 | PubMed | 文献检索（标题、作者、摘要） |
| 8 | `drug_screen` | **编排** | 多源 | 一键分子简报：6 步自动化流水线 |

### 双传输模式

| 模式 | 协议 | 适用场景 |
|------|------|----------|
| **stdio** | MCP 标准 I/O | 本地开发、Claude Desktop 集成 |
| **streamable-http** | HTTP/SSE | 远程部署、Web UI、多客户端访问 |

传输层与业务逻辑完全解耦，一个 CLI 参数（`--http`）即可切换。

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- LLM API Key（兼容 OpenAI 接口）

### 安装

```bash
git clone https://github.com/zhang-in-ucas/PharmMCP.git
cd PharmMCP
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：LLM_API_KEY、LLM_BASE_URL、LLM_MODEL
```

### 测试（无需 LLM）

```bash
python test_api.py      # API 连通性测试
python test_tools.py    # 工具函数测试
```

### 运行

```bash
# 模式 1：终端对话（stdio）
python client.py

# 模式 2：Web UI（推荐用于演示）
# 终端 1：
python server.py --http
# 终端 2：
python web_ui.py
# 浏览器打开 http://127.0.0.1:7860

# 模式 3：MCP Inspector（调试）
npx @modelcontextprotocol/inspector python server.py
```

### Web UI 演示流程

1. 输入药物名称：`aspirin`
2. 实时查看工具调用：`🔧 search_molecule → ✅ 完成 → 🔧 get_molecule_properties → ...`
3. 阅读 AI 流式生成的分子简报

---

## 📁 项目结构

```
PharmMCP/
├── server.py              # MCP Server（8 个工具，FastMCP）
├── client.py              # stdio 模式客户端
├── client_http.py         # HTTP 模式客户端
├── web_ui.py              # Gradio Web UI（流式输出）
├── pubchem_client.py      # PubChem API 客户端（异步，连接池复用）
├── chembl_client.py       # ChEMBL API 客户端（异步，连接池复用）
├── pubmed_client.py       # PubMed API 客户端（异步，连接池复用）
├── druglikeness.py        # Lipinski 五规则（纯本地计算，无需 RDKit）
├── pipeline.py            # 药物筛选流水线（asyncio.gather 两阶段并发，10s 单步 / 45s 总超时）
├── test_api.py            # API 连通性测试
├── test_tools.py          # 工具函数测试
├── Dockerfile             # 容器化部署
└── requirements.txt
```

---

## 🔬 类药性：Lipinski 五规则

| 规则 | 阈值 | 含义 |
|------|------|------|
| 分子量（MW） | ≤ 500 Da | 口服吸收上限 |
| LogP（脂水分配系数） | ≤ 5 | 亲脂性上限 |
| 氢键供体（HBD） | ≤ 5 | -OH、-NH 数量 |
| 氢键受体（HBA） | ≤ 10 | O、N 杂原子数量 |

**判定**：违反 ≤ 1 条 → 类药性好 ✅ | 违反 ≥ 2 条 → 口服生物利用度差 ⚠️

---

## 🔗 集成示例

### 集成到 Claude Desktop

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

### 集成到 LangGraph Agent

```python
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({"pharmmcp": {...}}) as client:
    tools = client.get_tools()
    agent = create_react_agent(llm, tools)
```

### 集成到任意 OpenAI 兼容客户端

所有工具作为标准 MCP 工具暴露，任何兼容 MCP 协议的客户端均可调用。参考实现见 `client.py` / `client_http.py`。

---

## 🔗 相关项目

- [**MediGuard**](https://github.com/zhang-in-ucas/MediGuard) — 多 Agent 医疗安全合规咨询系统，基于 LangGraph + RAG + 双层安全审查

---

## 📄 许可证

MIT License.

---

## ✨ 作者

药学背景开发者，展示领域知识 + 现代 AI 工程如何融合。所有工具架构决策和调试由作者完成，代码生成由 Claude Code 辅助 — 体现现代 AI 工程团队看重的"AI 工具高级用户"工作流。

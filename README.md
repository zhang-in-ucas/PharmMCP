---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7638657128173060398-data_volume/files/所有对话/主对话/PharmMCP_README.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 2926213286594729#1780326332374
    ReservedCode2: ""
---
# 🧪 PharmMCP

基于 MCP 协议的药物分子智能查询与筛选 Agent，集成 PubChem、ChEMBL、PubMed 三大数据库，提供从分子搜索、物化性质分析、类药性判断到文献检索的完整链路。

## ✨ 亮点

- **9 个 MCP 工具**：7 个基础查询 + 1 个 Pipeline 编排 + 1 个 Skill 对比，覆盖药物研发全流程
- **三层工具架构**：Tool 层（单步查询）→ Pipeline 层（多步编排）→ Skill 层（组合分析），新增工具只需实现统一接口
- **双传输模式**：MCP stdio（本地开发）+ streamable-http（远程部署），传输层与业务层完全解耦
- **异步高并发**：基于 httpx.AsyncClient 实现 Pipeline 并行调用，单步超时 10s，总超时 45s
- **Web UI**：Gradio 流式输出界面，工具调用进度实时展示

## 🔧 工具总览

### 基础工具（Tool 层，7 个）

| 工具 | 数据源 | 说明 |
|------|--------|------|
| `search_molecule` | PubChem | 按名称/SMILES 搜索分子，返回 CID、分子式等 |
| `get_molecule_properties` | PubChem | 物化性质：MW、XLogP、HBD、HBA、TPSA、可旋转键数 |
| `get_drug_targets` | ChEMBL | 靶点与生物活性数据（IC50、Ki 等） |
| `get_clinical_info` | ChEMBL | 临床阶段、适应症、批准年份 |
| `get_similar_molecules` | PubChem | 2D 结构相似性搜索（Tanimoto 系数） |
| `filter_by_druglikeness` | 本地计算 | Lipinski 五规则类药性判断 |
| `search_literature` | PubMed | 文献检索，返回标题、作者、摘要、DOI |

### Pipeline 工具（Pipeline 层，1 个）

| 工具 | 说明 |
|------|------|
| `drug_screen` | 6 步串联：分子搜索 → 物化性质 → Lipinski → 临床信息 → 生物活性 → 相似化合物，一键生成分子简报 |

### Skill 工具（Skill 层，1 个）

| 工具 | 说明 |
|------|------|
| `drug_compare` | 药物对比分析：自动查询两个分子的物化性质和类药性，横向对比输出 |

## 🏗️ 架构

```
用户 → Gradio Web UI / 终端 Client
        ↓
   LLM (DeepSeek / OpenAI 兼容接口)
        ↓ MCP Function Calling
   MCP Server (FastMCP)
    ├── Tool 层：pubchem_client / chembl_client / pubmed_client / druglikeness
    ├── Pipeline 层：drug_screen_pipeline（6 步编排）
    └── Skill 层：drug_compare（多 Tool 组合）
        ↓
   PubChem REST API / ChEMBL REST API / PubMed E-utilities
```

**三层工具设计**：

```
Tool 层     → 7 个基础单步查询（search_molecule, get_properties, ...）
Pipeline 层 → 1 个多步串行流水线（drug_screen：6 步自动编排，失败跳过不阻塞）
Skill 层    → 1 个组合分析工具（drug_compare：多 Tool 组合横向对比）
```

## 🚀 快速开始

### 1. 环境准备

```bash
conda create -n pharmmcp python=3.10 -y
conda activate pharmmcp
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key
```

### 3. 连通性测试

```bash
python test_api.py      # 测试 PubChem / ChEMBL / PubMed API 连通性
python test_tools.py    # 测试 MCP 工具函数
```

### 4. 运行

**方式一：终端对话（stdio 模式）**

```bash
python client.py
```

**方式二：Web 界面（推荐）**

```bash
# 终端 1：启动 MCP Server（HTTP 模式）
python server.py --http

# 终端 2：启动 Web UI
python web_ui.py
# 浏览器打开 http://127.0.0.1:7860
```

**方式三：HTTP 客户端（远程 Server）**

```bash
# 终端 1：启动 MCP Server
python server.py --http

# 终端 2：启动 HTTP Client
python client_http.py
```

**方式四：MCP Inspector 调试**

```bash
npx @modelcontextprotocol/inspector python server.py
```

## 📁 项目结构

```
PharmMCP/
├── server.py              # MCP Server（9 个工具注册 + 双传输模式）
├── client.py              # stdio 模式 Client（终端对话）
├── client_http.py         # HTTP 模式 Client（远程连接）
├── web_ui.py              # Gradio Web UI（流式输出 + 工具调用进度）
├── pubchem_client.py      # PubChem API 封装（5 个异步方法 + 速率控制）
├── chembl_client.py       # ChEMBL API 封装（3 个异步方法 + 重试机制）
├── pubmed_client.py       # PubMed API 封装（1 个异步方法 + XML 解析）
├── druglikeness.py        # Lipinski 五规则（本地计算，无需 rdkit）
├── pipeline.py            # 药物筛选流水线（6 步编排 + 超时容错）
├── test_api.py            # API 连通性测试
├── test_tools.py          # MCP 工具函数测试
├── requirements.txt       # 依赖列表
├── .env.example           # 环境变量模板
├── Dockerfile             # 容器化部署
└── README.md
```

## 💊 Lipinski 五规则

| 规则 | 阈值 | 说明 |
|------|------|------|
| 分子量 (MW) | ≤ 500 | 口服吸收上限 |
| 脂水分配系数 (XLogP) | ≤ 5 | 亲脂性上限 |
| 氢键供体 (HBD) | ≤ 5 | -OH, -NH 数量 |
| 氢键受体 (HBA) | ≤ 10 | O, N 杂原子数量 |

违反 ≤ 1 条 → 类药性好

## 📊 数据源

| 数据源 | 地址 | 认证 | 速率限制 |
|--------|------|------|----------|
| PubChem | https://pubchem.ncbi.nlm.nih.gov/ | 无需 Key | 3 次/秒 |
| ChEMBL | https://www.ebi.ac.uk/chembl/ | 无需 Key | - |
| PubMed | https://www.ncbi.nlm.nih.gov/books/NBK25501/ | 无需 Key | 3 次/秒 |

## 🐳 Docker 部署

```bash
docker build -t pharmmcp .
docker run -d -p 8000:8000 -p 7860:7860 --env-file .env pharmmcp
```

## 🛠️ 技术栈

- **MCP 框架**：FastMCP 2.14 + MCP SDK 1.25
- **LLM**：DeepSeek（OpenAI 兼容接口）+ OpenAI Python SDK
- **异步 HTTP**：httpx 0.28 + asyncio
- **Web 框架**：Gradio 5.x（流式输出）
- **数据验证**：Pydantic（ChEMBL 数据类型校验）
- **协议**：MCP stdio / streamable-http

## 📄 License

MIT



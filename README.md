# PharmMCP - 药物分子智能查询与筛选Agent

基于 MCP 协议的药物分子智能查询与筛选系统，集成 PubChem 和 ChEMBL 数据库，提供从分子搜索到药物筛选的完整链路。

## 7个工具

| 工具 | 类型 | 说明 |
|:---:|:---:|:---|
| `search_molecule` | 查询 | 按名称/SMILES搜索分子（PubChem） |
| `get_molecule_properties` | 查询 | 物化性质：MW、LogP、HBD、HBA、TPSA |
| `get_drug_targets` | 查询 | 靶点与生物活性数据（ChEMBL） |
| `get_clinical_info` | 查询 | 临床阶段、适应症、批准年份 |
| `get_similar_molecules` | 查询 | 2D结构相似性搜索 |
| `filter_by_druglikeness` | 分析 | Lipinski五规则类药性判断 |
| `drug_screen` | 编排 | 多工具串联，一键生成分子简报 |

## 技术架构

```
浏览器 → Web UI (Gradio) → LLM (DeepSeek) → MCP Client → MCP Server → PubChem/ChEMBL API
                                                    ↑
                                          Tool调用结果返回LLM
```

- **传输协议**：MCP (stdio / streamable-http 双模式)
- **LLM**：DeepSeek (OpenAI兼容接口)
- **数据源**：PubChem REST API + ChEMBL REST API
- **框架**：FastMCP 2.14 + OpenAI Python SDK + Gradio
- **前端**：Gradio Web UI（流式输出）

## 快速开始

```bash
# 1. 创建环境
conda create -n agent310 python=3.10 -y
conda activate agent310

# 2. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 4. 测试
python test_api.py
python test_tools.py
```

## 运行方式

### 方式一：终端对话（stdio模式）

```bash
python client.py
```

### 方式二：Web界面（推荐）

```bash
# 终端1：启动MCP Server
python server.py --http

# 终端2：启动Web UI
python web_ui.py
# 浏览器打开 http://127.0.0.1:7860
```

### 方式三：MCP Inspector调试

```bash
npx @modelcontextprotocol/inspector python server.py
```

## 项目结构

```
PharmMCP/
├── server.py              # MCP Server（7个工具）
├── client.py              # stdio模式Client（终端对话）
├── client_http.py         # HTTP模式Client（终端对话）
├── web_ui.py              # Web UI（浏览器界面，流式输出）
├── pubchem_client.py      # PubChem API封装（5个异步方法）
├── chembl_client.py       # ChEMBL API封装（3个异步方法）
├── druglikeness.py        # Lipinski五规则（本地计算）
├── pipeline.py            # 药物筛选流水线（6步编排）
├── test_api.py            # API连通性测试
├── test_tools.py          # 工具函数测试
├── requirements.txt       # 依赖列表
├── .env.example           # 环境变量模板
├── Dockerfile             # 容器化部署
└── README.md
```

## Lipinski五规则

| 规则 | 阈值 | 说明 |
|:---:|:---:|:---|
| 分子量 (MW) | ≤ 500 | 口服吸收上限 |
| 脂水分配系数 (XLogP) | ≤ 5 | 亲脂性上限 |
| 氢键供体 (HBD) | ≤ 5 | -OH, -NH 数量 |
| 氢键受体 (HBA) | ≤ 10 | O, N 杂原子数量 |

违反 ≤ 1 条 → 类药性好

## 数据源

- **PubChem**: https://pubchem.ncbi.nlm.nih.gov/ (无需Key，速率3次/秒)
- **ChEMBL**: https://www.ebi.ac.uk/chembl/ (无需Key)

## License

MIT

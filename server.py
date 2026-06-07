"""
PharmMCP - 基于MCP协议的药物分子智能查询与筛选Agent

提供8个MCP工具，覆盖从分子搜索到药物筛选的完整链路：

基础工具（7个）：
1. search_molecule - 分子搜索（PubChem）
2. get_molecule_properties - 物化性质查询（PubChem）
3. get_drug_targets - 靶点与生物活性（ChEMBL）
4. get_clinical_info - 临床阶段与适应症（ChEMBL）
5. get_similar_molecules - 相似化合物搜索（PubChem）
6. filter_by_druglikeness - Lipinski五规则过滤（本地计算）
7. search_literature - 文献检索（PubMed）

高级工具（1个）：
8. drug_screen - 多工具串联生成分子简报（Pipeline）

运行方式：python server.py（stdio模式） / python server.py --http（HTTP模式）
"""

import asyncio
from typing import Optional

from fastmcp import FastMCP
from pubchem_client import PubChemClient
from pubmed_client import PubMedClient
from chembl_client import ChEMBLClient
from druglikeness import check_lipinski
from pipeline import drug_screen_pipeline

# 初始化FastMCP Server
mcp = FastMCP("PharmMCP")

# 初始化API客户端
pubchem = PubChemClient()
pubmed = PubMedClient()
chembl = ChEMBLClient()


# ============================================================
# Tool 1: 分子搜索
# ============================================================
@mcp.tool()
async def search_molecule(name: str) -> Optional[dict]:
    """搜索药物分子，返回CID、SMILES、分子式等基本信息。

    支持按英文名或SMILES字符串搜索，优先按名称搜索。
    返回结果包含CID，可用于后续查询物化性质等。

    Args:
        name: 分子名（如aspirin）或SMILES字符串
    """
    # 简单判断：如果包含常见SMILES字符，按SMILES搜索
    if any(c in name for c in "=#[]()") and len(name) > 5:
        result = await pubchem.search_by_smiles(name)
    else:
        result = await pubchem.search_by_name(name)
        # 名称搜不到时，尝试按SMILES搜
        if result is None:
            result = await pubchem.search_by_smiles(name)
    return result


# ============================================================
# Tool 2: 物化性质查询
# ============================================================
@mcp.tool()
async def get_molecule_properties(cid: int) -> Optional[dict]:
    """查询分子的物化性质，包括分子量、LogP、氢键供体/受体、TPSA等。

    这些性质是Lipinski五规则判断的基础数据。
    需要先通过search_molecule获取CID。

    Args:
        cid: PubChem化合物ID，如2244
    """
    return await pubchem.get_properties(cid)


# ============================================================
# Tool 3: 靶点与生物活性
# ============================================================
@mcp.tool()
async def get_drug_targets(molecule_name: str, limit: int = 10) -> Optional[dict]:
    """查询分子的靶点信息和生物活性数据（IC50、Ki等）。

    返回靶点名称、物种、实验类型和活性数值。
    数据来源于ChEMBL数据库。

    Args:
        molecule_name: 分子英文名或ChEMBL ID（如CHEMBL25）
        limit: 返回活性记录数量，默认10
    """
    # 如果传入的是CHEMBL ID，直接用
    if molecule_name.startswith("CHEMBL"):
        chembl_id = molecule_name
    else:
        # 先搜索获取chembl_id
        search = await chembl.search_molecule(molecule_name)
        if not search:
            return {"error": f"未在ChEMBL中找到分子: {molecule_name}"}
        chembl_id = search["chembl_id"]

    activities = await chembl.get_activities(chembl_id, limit=limit)
    return {
        "chembl_id": chembl_id,
        "activities": activities or [],
    }


# ============================================================
# Tool 4: 临床阶段与适应症
# ============================================================
@mcp.tool()
async def get_clinical_info(molecule_name: str) -> Optional[dict]:
    """查询药物的临床阶段、适应症和批准年份。

    临床阶段：临床前、Phase I/II/III、已上市。
    适应症来源于ChEMBL的drug_indication接口。
    已上市药物会额外查询批准年份。

    Args:
        molecule_name: 分子名或ChEMBL ID（如CHEMBL25）
    """
    if molecule_name.startswith("CHEMBL"):
        chembl_id = molecule_name
    else:
        search = await chembl.search_molecule(molecule_name)
        if not search:
            return {"error": f"未在ChEMBL中找到分子: {molecule_name}"}
        chembl_id = search["chembl_id"]

    return await chembl.get_drug_info(chembl_id)


# ============================================================
# Tool 5: 相似化合物搜索
# ============================================================
@mcp.tool()
async def get_similar_molecules(smiles: str, threshold: int = 90, max_results: int = 5) -> Optional[list]:
    """搜索结构相似的化合物，用于药物优化和先导化合物发现。

    基于PubChem的2D结构相似性搜索（Tanimoto系数）。
    threshold越高，返回的化合物越相似。

    Args:
        smiles: SMILES字符串（如CC(=O)Oc1ccccc1C(=O)O）
        threshold: 相似度阈值(0-100)，默认90，越高越相似
        max_results: 返回数量，默认5
    """
    return await pubchem.get_similar(smiles, threshold=threshold, max_results=max_results)


# ============================================================
# Tool 6: Lipinski五规则过滤
# ============================================================
@mcp.tool()
async def filter_by_druglikeness(cid: int) -> Optional[dict]:
    """基于Lipinski五规则判断分子的类药性。

    Lipinski规则：MW≤500, XLogP≤5, HBD≤5, HBA≤10。
    违反≤1条视为通过（类药性好）。
    需要先通过get_molecule_properties获取CID。

    Args:
        cid: PubChem化合物ID
    """
    props = await pubchem.get_properties(cid)
    if not props:
        return {"error": f"未获取到CID={cid}的物化性质，无法判断类药性"}

    lipinski = check_lipinski(props)
    return {
        "cid": cid,
        "molecule_name": f"CID:{cid}",
        "lipinski": lipinski,
        "properties_used": props,
    }


# ============================================================
# Tool 7: 药物筛选流水线
# ============================================================
@mcp.tool()
async def drug_screen(molecule_name: str) -> dict:
    """执行完整的药物筛选流水线，一键生成分子简报。

    自动串联6个步骤：分子搜索→物化性质→Lipinski过滤→临床信息→生物活性→相似化合物。
    失败步骤会跳过并标注，不影响整体流程。
    适合快速了解一个分子的全貌。

    Args:
        molecule_name: 分子英文名或中文名，如aspirin
    """
    return await drug_screen_pipeline(molecule_name)


# ============================================================
# Tool 8: 文献检索
# ============================================================
@mcp.tool()
async def search_literature(query: str, max_results: int = 5) -> Optional[list]:
    """检索PubMed文献，返回相关论文的标题、作者、摘要等信息。

    适用于查找某个靶点、分子或疾病的最新研究文献。
    数据来源于PubMed数据库。

    Args:
        query: 检索关键词，如 "LRPPRC inhibitor"、"aspirin COX-2"、"acylhydrazone anticancer"
        max_results: 返回数量，默认5
    """
    return await pubmed.search_literature(query, max_results=max_results)

# ============================================================
# 启动Server（stdio模式）
# ============================================================
if __name__ == "__main__":
    import sys
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
    else:
        mcp.run(transport="stdio")
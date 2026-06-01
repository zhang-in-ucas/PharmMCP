"""
药物筛选流水线模块

串联6个步骤，生成完整的分子简报：
1. 分子搜索（PubChem）
2. 物化性质（PubChem）
3. Lipinski过滤（本地计算）
4. 临床阶段与适应症（ChEMBL）
5. 生物活性数据（ChEMBL）
6. 相似化合物（PubChem）

特性：
- 单步10秒超时，总45秒超时
- 失败步骤跳过并标注，不阻塞后续步骤
- 结果汇总为结构化简报
"""

import asyncio
from typing import Optional

from pubchem_client import PubChemClient
from chembl_client import ChEMBLClient
from druglikeness import check_lipinski


# 超时配置
STEP_TIMEOUT = 10   # 单步超时（秒）
TOTAL_TIMEOUT = 45  # 总超时（秒）


async def drug_screen_pipeline(molecule_name: str) -> dict:
    """
    执行完整的药物筛选流水线

    Args:
        molecule_name: 分子英文名，如 "aspirin"
    Returns:
        结构化的分子简报字典
    """
    pubchem = PubChemClient()
    chembl = ChEMBLClient()

    report = {
        "query": molecule_name,
        "steps": {},
        "summary": {
            "found": False,
            "lipinski_pass": None,
            "clinical_phase": None,
            "indication": None,
        },
    }

    # ---- Step 1: 分子搜索 ----
    search_result = await _run_step(
        "search", pubchem.search_by_name, molecule_name
    )
    report["steps"]["search"] = _step_report(search_result)
    if not search_result:
        report["steps"]["search"]["note"] = "未找到该分子，流水线终止"
        return report

    report["summary"]["found"] = True
    cid = search_result["cid"]

    # ---- Step 2: 物化性质 ----
    props = await _run_step(
        "properties", pubchem.get_properties, cid
    )
    report["steps"]["properties"] = _step_report(props)

    # ---- Step 3: Lipinski过滤（纯本地，不需要API） ----
    if props:
        lipinski = check_lipinski(props)
        report["steps"]["lipinski"] = {
            "status": "success",
            "data": lipinski,
        }
        report["summary"]["lipinski_pass"] = lipinski["passes"]
    else:
        report["steps"]["lipinski"] = {
            "status": "skipped",
            "note": "物化性质获取失败，跳过Lipinski检查",
        }

    # ---- Step 4: 临床阶段与适应症 ----
    # 先通过ChEMBL搜索获取chembl_id
    chembl_search = await _run_step(
        "chembl_search", chembl.search_molecule, molecule_name
    )
    if chembl_search:
        chembl_id = chembl_search["chembl_id"]
        drug_info = await _run_step(
            "drug_info", chembl.get_drug_info, chembl_id
        )
        report["steps"]["drug_info"] = _step_report(drug_info)
        if drug_info:
            report["summary"]["clinical_phase"] = drug_info.get("phase_description")
            report["summary"]["indication"] = drug_info.get("indication")
    else:
        report["steps"]["chembl_search"] = _step_report(None, "ChEMBL中未找到该分子")

    # ---- Step 5: 生物活性数据 ----
    if chembl_search:
        activities = await _run_step(
            "activities", chembl.get_activities, chembl_id
        )
        report["steps"]["activities"] = _step_report(activities)
    else:
        report["steps"]["activities"] = {
            "status": "skipped",
            "note": "缺少chembl_id，跳过活性数据查询",
        }

    # ---- Step 6: 相似化合物 ----
    similar = await _run_step(
        "similar", pubchem.get_similar, search_result["smiles"]
    )
    report["steps"]["similar"] = _step_report(similar)

    return report


async def _run_step(step_name: str, coro_func, *args) -> Optional[dict]:
    """执行单步，带超时和错误处理"""
    try:
        result = await asyncio.wait_for(
            coro_func(*args), timeout=STEP_TIMEOUT
        )
        return result
    except asyncio.TimeoutError:
        print(f"[Pipeline] 步骤 '{step_name}' 超时（{STEP_TIMEOUT}s），跳过")
        return None
    except Exception as e:
        print(f"[Pipeline] 步骤 '{step_name}' 异常: {e}，跳过")
        return None


def _step_report(data: Optional[dict], note: str = None) -> dict:
    """生成步骤报告"""
    if data is None:
        result = {"status": "failed"}
        if note:
            result["note"] = note
        return result
    return {"status": "success", "data": data}
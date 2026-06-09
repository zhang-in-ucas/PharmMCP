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
- 单步10秒超时
- 失败步骤跳过并标注，不阻塞后续步骤
- 使用 asyncio.gather 并发执行独立步骤，减少总耗时
- 结果汇总为结构化简报

并发策略（两阶段 gather）：
                     molecule_name
                    /              \
         search (PubChem)      chembl_search (ChEMBL)
         → CID, SMILES         → chembl_id
        /          \            /           \
  properties    similar    drug_info    activities
      |
   lipinski
"""

import asyncio
from typing import Optional

from pubchem_client import pubchem
from chembl_client import chembl
from druglikeness import check_lipinski


# 超时配置
STEP_TIMEOUT = 10   # 单步超时（秒）
TOTAL_TIMEOUT = 45  # 流水线总超时（秒），防止多阶段全超时拖垮调用方


async def drug_screen_pipeline(molecule_name: str) -> dict:
    """
    执行完整的药物筛选流水线

    使用 asyncio.gather 并发执行无依赖的步骤：
    Phase 1: PubChem搜索 ‖ ChEMBL搜索
    Phase 2: 物化性质 ‖ 相似化合物 ‖ 临床信息 ‖ 生物活性

    总超时 TOTAL_TIMEOUT 作为硬上限，防止单步全超时导致总耗时失控。

    Args:
        molecule_name: 分子英文名，如 "aspirin"
    Returns:
        结构化的分子简报字典
    """
    try:
        return await asyncio.wait_for(
            _pipeline_impl(molecule_name),
            timeout=TOTAL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        print(f"[Pipeline] 流水线总超时（{TOTAL_TIMEOUT}s）")
        return {
            "query": molecule_name,
            "error": f"流水线执行超时（>{TOTAL_TIMEOUT}s）",
            "steps": {},
            "summary": {
                "found": False,
                "lipinski_pass": None,
                "clinical_phase": None,
                "indication": None,
            },
        }


async def _pipeline_impl(molecule_name: str) -> dict:
    """流水线实现体，由 drug_screen_pipeline 包装总超时"""

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

    # ═══════════════════════════════════════════════════
    # Phase 1: 并发 — PubChem搜索 + ChEMBL搜索
    # 两者只依赖 molecule_name，无互相依赖，可并行发出请求
    # ═══════════════════════════════════════════════════
    search_result, chembl_search = await asyncio.gather(
        _run_step("search", pubchem.search_by_name, molecule_name),
        _run_step("chembl_search", chembl.search_molecule, molecule_name),
    )

    report["steps"]["search"] = _step_report(search_result)
    if chembl_search is None:
        report["steps"]["chembl_search"] = _step_report(None, "ChEMBL中未找到该分子")

    # PubChem 搜索失败则流水线终止
    if not search_result:
        report["steps"]["search"]["note"] = "未找到该分子，流水线终止"
        return report

    report["summary"]["found"] = True
    cid = search_result["cid"]

    # ═══════════════════════════════════════════════════
    # Phase 2: 并发 — 四个独立子任务
    # - properties: 需要 CID（Phase 1 提供）
    # - similar: 需要 SMILES（Phase 1 提供）
    # - drug_info: 需要 chembl_id（Phase 1 提供，若 chembl 搜到）
    # - activities: 需要 chembl_id（Phase 1 提供，若 chembl 搜到）
    # ═══════════════════════════════════════════════════
    tasks = [
        _run_step("properties", pubchem.get_properties, cid),
        _run_step("similar", pubchem.get_similar, search_result["smiles"]),
    ]
    has_chembl = chembl_search is not None

    if has_chembl:
        chembl_id = chembl_search["chembl_id"]
        tasks.append(_run_step("drug_info", chembl.get_drug_info, chembl_id))
        tasks.append(_run_step("activities", chembl.get_activities, chembl_id))

    phase2_results = await asyncio.gather(*tasks)

    # 解析 Phase 2 结果
    props = phase2_results[0]
    similar = phase2_results[1]
    report["steps"]["properties"] = _step_report(props)
    report["steps"]["similar"] = _step_report(similar)

    if has_chembl:
        drug_info = phase2_results[2]
        activities = phase2_results[3]
        report["steps"]["drug_info"] = _step_report(drug_info)
        if drug_info:
            report["summary"]["clinical_phase"] = drug_info.get("phase_description")
            report["summary"]["indication"] = drug_info.get("indication")
        report["steps"]["activities"] = _step_report(activities)
    else:
        report["steps"]["activities"] = {
            "status": "skipped",
            "note": "缺少chembl_id，跳过活性数据查询",
        }

    # ═══════════════════════════════════════════════════
    # Phase 3: Lipinski 过滤（本地计算，几乎零耗时）
    # ═══════════════════════════════════════════════════
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

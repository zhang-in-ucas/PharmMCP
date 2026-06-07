"""
API 连通性测试

测试3个外部数据源 + 1个组合功能的连通性：
1. PubChem REST API
2. ChEMBL REST API
3. PubMed E-utilities API（新增）
4. drug_screen 流水线（端到端）

运行方式：python test_api.py
"""

import httpx
import asyncio

# ============================================================
# API端点配置
# ============================================================
PUBCHEM_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/aspirin"
    "/property/MolecularWeight,IsomericSMILES/JSON"
)
CHEMBL_URL = (
    "https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?q=aspirin"
)
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


# ============================================================
# 基础API连通测试
# ============================================================
async def test_pubchem():
    """测试PubChem REST API连通性"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(PUBCHEM_URL)
            resp.raise_for_status()
            data = resp.json()
            fields = list(
                data.get("PropertyTable", {}).get("Properties", [{}])[0].keys()
            )
            print(f"✅ PubChem 连通! 返回字段: {fields}")
        except Exception as e:
            print(f"❌ PubChem 连接失败: {e}")


async def test_chembl():
    """测试ChEMBL REST API连通性"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                CHEMBL_URL, headers={"Accept": "application/json"}
            )
            resp.raise_for_status()
            data = resp.json()
            molecules = data.get("molecules", [])
            print(f"✅ ChEMBL 连通! 返回 {len(molecules)} 条结果")
        except Exception as e:
            print(f"❌ ChEMBL 连接失败: {e}")


async def test_pubmed():
    """测试PubMed E-utilities API连通性（两步：esearch + efetch）"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Step 1: esearch 获取PMID列表
            search_params = {
                "db": "pubmed",
                "term": "aspirin",
                "retmax": 3,
                "retmode": "json",
            }
            resp = await client.get(PUBMED_SEARCH_URL, params=search_params)
            resp.raise_for_status()
            search_data = resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            print(f"✅ PubMed esearch 连通! 返回 {len(id_list)} 条PMID")

            # Step 2: efetch 获取文献详情
            if id_list:
                await asyncio.sleep(0.4)  # 速率控制
                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "rettype": "abstract",
                    "retmode": "xml",
                }
                resp2 = await client.get(PUBMED_FETCH_URL, params=fetch_params)
                resp2.raise_for_status()
                print(f"✅ PubMed efetch 连通! 返回 {len(resp2.text)} 字符")
        except Exception as e:
            print(f"❌ PubMed 连接失败: {e}")


# ============================================================
# 组合功能端到端测试
# ============================================================
async def test_pipeline():
    """测试drug_screen流水线（6步编排）"""
    from pipeline import drug_screen_pipeline

    try:
        result = await asyncio.wait_for(
            drug_screen_pipeline("aspirin"), timeout=60
        )
        steps = result.get("steps", {})
        success_count = sum(
            1 for s in steps.values() if s.get("status") == "success"
        )
        total_count = len(steps)
        print(
            f"✅ Pipeline 流水线完成! "
            f"{success_count}/{total_count} 步成功 | "
            f"类药性: {result['summary'].get('lipinski_pass')} | "
            f"临床阶段: {result['summary'].get('clinical_phase')}"
        )
    except asyncio.TimeoutError:
        print("❌ Pipeline 流水线超时（60s）")
    except Exception as e:
        print(f"❌ Pipeline 流水线异常: {e}")


# ============================================================
# 主入口
# ============================================================
async def main():
    print("=" * 50)
    print("PharmMCP API 连通性测试")
    print("=" * 50)

    print("\n--- 基础API连通测试 ---")
    await test_pubchem()
    await test_chembl()
    await test_pubmed()

    print("\n--- 组合功能端到端测试 ---")
    await test_pipeline()

    print("\n" + "=" * 50)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
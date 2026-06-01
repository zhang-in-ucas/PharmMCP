"""
工具函数测试

测试8个MCP工具 + 2个组合功能：
1. PubChem: search_by_name, search_by_smiles, get_properties, get_similar
2. ChEMBL: search_molecule, get_activities, get_drug_info
3. PubMed: search_literature
4. druglikeness: check_lipinski
5. Pipeline: drug_screen_pipeline
6. drug_compare: 对比两个分子

运行方式：python test_tools.py
"""

import asyncio
import json

from pubchem_client import PubChemClient
from chembl_client import ChEMBLClient
from pubmed_client import PubMedClient
from druglikeness import check_lipinski

pubchem = PubChemClient()
chembl = ChEMBLClient()
pubmed = PubMedClient()

# ========== PubChem 测试 ==========
async def test_search_by_name():
    print("\n--- 测试 search_by_name ---")
    result = await pubchem.search_by_name("aspirin")
    print(f"结果: {result}")

async def test_search_by_smiles():
    print("\n--- 测试 search_by_smiles ---")
    result = await pubchem.search_by_smiles("CC(=O)Oc1ccccc1C(=O)O")
    print(f"结果: {result}")

async def test_get_properties():
    print("\n--- 测试 get_properties ---")
    result = await pubchem.get_properties(2244)
    print(f"结果: {result}")

async def test_get_similar():
    print("\n--- 测试 get_similar ---")
    result = await pubchem.get_similar("CC(=O)Oc1ccccc1C(=O)O", threshold=90, max_results=3)
    print(f"结果: {result}")

async def test_not_found():
    print("\n--- 测试 不存在的分子 ---")
    result = await pubchem.search_by_name("xyznotarealdrug123")
    print(f"结果: {result}")

# ========== ChEMBL 测试 ==========
async def test_chembl_search():
    print("\n--- 测试 ChEMBL search_molecule ---")
    result = await chembl.search_molecule("aspirin")
    print(f"结果: {result}")

async def test_chembl_activities():
    print("\n--- 测试 ChEMBL get_activities ---")
    result = await chembl.get_activities("CHEMBL25", limit=5)
    print(f"结果: {result}")

async def test_chembl_drug_info():
    print("\n--- 测试 ChEMBL get_drug_info ---")
    result = await chembl.get_drug_info("CHEMBL25")
    print(f"结果: {result}")

# ========== PubMed 测试（新增） ==========
async def test_pubmed_search():
    print("\n--- 测试 PubMed search_literature ---")
    result = await pubmed.search_literature("aspirin COX-2", max_results=3)
    if result:
        for paper in result:
            print(f"  PMID: {paper.get('pmid')} | {paper.get('title')}")
            print(f"  作者: {paper.get('authors')} | 期刊: {paper.get('journal')} | 年份: {paper.get('year')}")
            print(f"  摘要: {paper.get('abstract', '')[:80]}...")
            print()
    else:
        print("结果: None")

async def test_pubmed_not_found():
    print("\n--- 测试 PubMed 无结果查询 ---")
    result = await pubmed.search_literature("xyznotarealdrug123456789", max_results=3)
    print(f"结果: {result}")

# ========== Lipinski 测试 ==========
async def test_lipinski():
    print("\n--- 测试 check_lipinski ---")
    props = await pubchem.get_properties(2244)
    if props:
        result = check_lipinski(props)
        print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print("未获取到性质数据，跳过")

# ========== Pipeline 测试 ==========
async def test_pipeline():
    print("\n--- 测试 drug_screen_pipeline ---")
    from pipeline import drug_screen_pipeline
    report = await drug_screen_pipeline("aspirin")
    print(json.dumps(report, indent=2, ensure_ascii=False))

# ========== drug_compare 测试（新增） ==========
async def test_drug_compare():
    print("\n--- 测试 drug_compare ---")
    names = ["aspirin", "ibuprofen"]
    results = []

    for name in names:
        # Step 1: 搜索分子
        search = await pubchem.search_by_name(name)
        if not search:
            print(f"未找到分子: {name}")
            return

        # Step 2: 获取物化性质
        props = await pubchem.get_properties(search["cid"])
        if not props:
            print(f"未获取到 {name} 的性质")
            return

        # Step 3: Lipinski判断
        lipinski = check_lipinski(props)

        results.append({
            "name": name,
            "cid": search["cid"],
            "smiles": search.get("smiles"),
            "molecular_weight": props.get("molecular_weight"),
            "xlogp": props.get("xlogp"),
            "hbd": props.get("hbd"),
            "hba": props.get("hba"),
            "tpsa": props.get("tpsa"),
            "lipinski_pass": lipinski["passes"],
            "lipinski_violations": lipinski["violation_count"],
        })

    # 对比输出
    print("=" * 60)
    print(f"{'属性':<20} {'Aspirin':<20} {'Ibuprofen':<20}")
    print("-" * 60)
    for key in ["molecular_weight", "xlogp", "hbd", "hba", "tpsa"]:
        v0 = results[0].get(key, "N/A")
        v1 = results[1].get(key, "N/A")
        print(f"{key:<20} {str(v0):<20} {str(v1):<20}")
    print("-" * 60)
    p0 = "通过" if results[0]["lipinski_pass"] else "不通过"
    p1 = "通过" if results[1]["lipinski_pass"] else "不通过"
    print(f"{'Lipinski':<20} {p0:<20} {p1:<20}")
    print(f"{'违反条数':<20} {results[0]['lipinski_violations']:<20} {results[1]['lipinski_violations']:<20}")
    print("=" * 60)

# ========== 主函数 ==========
async def main():
    # PubChem
    await test_search_by_name()
    await test_search_by_smiles()
    await test_get_properties()
    await test_get_similar()
    await test_not_found()

    # ChEMBL
    await test_chembl_search()
    await test_chembl_activities()
    await test_chembl_drug_info()

    # PubMed（新增）
    await test_pubmed_search()
    await test_pubmed_not_found()

    # Lipinski
    await test_lipinski()

    # Pipeline
    await test_pipeline()

    # drug_compare（新增）
    await test_drug_compare()

if __name__ == "__main__":
    asyncio.run(main())
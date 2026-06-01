"""
PubChem REST API 封装模块

提供5个异步方法：
- search_by_name: 按名称搜索分子
- search_by_smiles: 按SMILES搜索分子
- get_properties: 获取物化性质
- get_similar: 搜索相似化合物
- get_2d_image_url: 获取2D结构图URL

API文档: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
速率限制: 3次/秒（请求间隔 ≥ 0.4秒）
"""

import asyncio
import urllib.parse
from typing import Optional

import httpx

# PubChem PUG REST API 基础URL
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


class PubChemClient:
    """PubChem API 异步客户端"""

    def __init__(self, timeout: float = 30.0, max_retries: int = 2):
        """
        Args:
            timeout: 单次请求超时时间（秒）
            max_retries: 失败重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request_time = 0.0  # 上次请求时间，用于速率控制

    async def _rate_limit(self):
        """速率控制：确保请求间隔 ≥ 0.4秒（满足3次/秒限制）"""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < 0.4:
            await asyncio.sleep(0.4 - elapsed)
        self._last_request_time = time.time()

    async def _request(self, url: str) -> Optional[dict]:
        """
        通用请求方法：带速率控制、超时、重试、错误处理

        Args:
            url: 完整的API请求URL
        Returns:
            解析后的JSON字典，失败返回None
        """
        for attempt in range(self.max_retries + 1):
            try:
                await self._rate_limit()
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.json()
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    print(f"[PubChem] 请求超时，第{attempt + 1}次重试...")
                    continue
                print(f"[PubChem] 请求超时，已达最大重试次数")
                return None
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # 404 = 未找到，不需要重试
                    return None
                if attempt < self.max_retries:
                    print(f"[PubChem] HTTP {e.response.status_code}，第{attempt + 1}次重试...")
                    continue
                print(f"[PubChem] HTTP {e.response.status_code}，已达最大重试次数")
                return None
            except Exception as e:
                if attempt < self.max_retries:
                    print(f"[PubChem] 请求异常: {e}，第{attempt + 1}次重试...")
                    continue
                print(f"[PubChem] 请求异常: {e}，已达最大重试次数")
                return None
        return None

    async def search_by_name(self, name: str) -> Optional[dict]:
        """
        按名称搜索分子

        Args:
            name: 分子名称，如 "aspirin"、"布洛芬"
        Returns:
            {"cid": int, "name": str, "smiles": str, "molecular_formula": str, "image_url": str}
            未找到返回 None
        """
        url = (
            f"{PUBCHEM_BASE}/compound/name/{urllib.parse.quote(name)}"
            f"/property/MolecularWeight,IsomericSMILES,MolecularFormula/JSON"
        )
        data = await self._request(url)
        if not data:
            return None

        properties = data.get("PropertyTable", {}).get("Properties", [])
        if not properties:
            return None

        prop = properties[0]
        cid = prop.get("CID")
        return {
            "cid": cid,
            "name": name,
            "smiles": prop.get("IsomericSMILES") or prop.get("SMILES", "暂无数据"),
            "molecular_formula": prop.get("MolecularFormula", "暂无数据"),
            "molecular_weight": prop.get("MolecularWeight", "暂无数据"),
            "image_url": self.get_2d_image_url(cid) if cid else None,
        }

    async def search_by_smiles(self, smiles: str) -> Optional[dict]:
        """
        按SMILES搜索分子

        Args:
            smiles: SMILES字符串，如 "CC(=O)Oc1ccccc1C(=O)O"（阿司匹林）
        Returns:
            同 search_by_name 的返回格式
        """
        url = (
            f"{PUBCHEM_BASE}/compound/smiles/{urllib.parse.quote(smiles, safe='')}"
            f"/property/MolecularWeight,IsomericSMILES,MolecularFormula/JSON"
        )
        data = await self._request(url)
        if not data:
            return None

        properties = data.get("PropertyTable", {}).get("Properties", [])
        if not properties:
            return None

        prop = properties[0]
        cid = prop.get("CID")
        return {
            "cid": cid,
            "name": f"SMILES: {smiles}",
            "smiles": prop.get("IsomericSMILES") or prop.get("SMILES", "暂无数据"),
            "molecular_formula": prop.get("MolecularFormula", "暂无数据"),
            "molecular_weight": prop.get("MolecularWeight", "暂无数据"),
            "image_url": self.get_2d_image_url(cid) if cid else None,
        }

    async def get_properties(self, cid: int) -> Optional[dict]:
        """
        获取分子物化性质

        Args:
            cid: PubChem CID
        Returns:
            {"cid": int, "molecular_weight": float, "xlogp": float, "hbd": int,
             "hba": int, "tpsa": float, "rotatable_bonds": int, "exact_mass": float}
            XLogP可能为None（部分分子没有计算值）
        """
        url = (
            f"{PUBCHEM_BASE}/compound/cid/{cid}"
            f"/property/MolecularWeight,XLogP,HBondDonorCount,"
            f"HBondAcceptorCount,TPSA,RotatableBondCount,ExactMass/JSON"
        )
        data = await self._request(url)
        if not data:
            return None

        properties = data.get("PropertyTable", {}).get("Properties", [])
        if not properties:
            return None

        prop = properties[0]
        return {
            "cid": cid,
            "molecular_weight": prop.get("MolecularWeight"),
            "xlogp": prop.get("XLogP"),  # 可能为None
            "hbd": prop.get("HBondDonorCount"),
            "hba": prop.get("HBondAcceptorCount"),
            "tpsa": prop.get("TPSA"),
            "rotatable_bonds": prop.get("RotatableBondCount"),
            "exact_mass": prop.get("ExactMass"),
        }

    async def get_similar(
        self, smiles: str, threshold: int = 90, max_results: int = 5
    ) -> Optional[list[dict]]:
        """
        搜索结构相似的化合物

        两步请求：
        1. 用SMILES搜索相似化合物的CID列表
        2. 用CID列表批量获取属性

        Args:
            smiles: SMILES字符串
            threshold: 相似度阈值（0-100），默认90表示90%相似
            max_results: 返回数量，默认5
        Returns:
            [{"cid": int, "smiles": str, "molecular_formula": str, "similarity": int}]
        """
        # 第一步：搜索相似化合物的CID
        url = (
            f"{PUBCHEM_BASE}/compound/fastsimilarity_2d/smiles/"
            f"{urllib.parse.quote(smiles, safe='')}"
            f"/cids/JSON?MaxRecords={max_results}&Threshold={threshold}"
        )
        data = await self._request(url)
        if not data:
            return None

        cids = data.get("IdentifierList", {}).get("CID", [])
        if not cids:
            return []

        # 第二步：批量获取属性
        cid_str = ",".join(str(c) for c in cids[:max_results])
        url = (
            f"{PUBCHEM_BASE}/compound/cid/{cid_str}"
            f"/property/MolecularWeight,IsomericSMILES,MolecularFormula/JSON"
        )
        data = await self._request(url)
        if not data:
            return None

        properties = data.get("PropertyTable", {}).get("Properties", [])
        results = []
        for prop in properties:
            results.append({
                "cid": prop.get("CID"),
                "smiles": prop.get("IsomericSMILES") or prop.get("SMILES", "暂无数据"),
                "molecular_formula": prop.get("MolecularFormula", "暂无数据"),
                "molecular_weight": prop.get("MolecularWeight", "暂无数据"),
                "similarity": f"≥{threshold}%",
            })
        return results

    @staticmethod
    def get_2d_image_url(cid: int) -> str:
        """
        获取2D分子结构图URL（无需API请求，直接拼接）

        Args:
            cid: PubChem CID
        Returns:
            图片URL字符串
        """
        return f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG"
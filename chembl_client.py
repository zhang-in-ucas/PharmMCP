"""
ChEMBL REST API 封装模块

提供3个异步方法：
- search_molecule: 搜索分子，获取CHEMBL_ID
- get_activities: 获取靶点和生物活性数据（IC50/Ki等）
- get_drug_info: 获取临床阶段和适应症信息

API文档: https://www.ebi.ac.uk/chembl/api/data/docs
无需API Key，无需认证
"""

import asyncio
from typing import Optional

import httpx

# ChEMBL REST API 基础URL
CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"

# 临床阶段映射
PHASE_MAP = {
    0: "临床前",
    1: "Phase I",
    2: "Phase II",
    3: "Phase III",
    4: "已上市",
}


class ChEMBLClient:
    """ChEMBL API 异步客户端

    httpx.AsyncClient 在首次请求时惰性创建，后续请求复用同一个连接池。
    使用完毕后应调用 close() 释放连接。
    """

    def __init__(self, timeout: float = 30.0, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self._http_client = None  # httpx.AsyncClient 惰性初始化

    async def _get_client(self) -> httpx.AsyncClient:
        """惰性获取或创建 httpx.AsyncClient，复用连接池"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self):
        """关闭 httpx 连接池"""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _request(self, url: str) -> Optional[dict]:
        client = await self._get_client()
        for attempt in range(self.max_retries + 1):
            try:
                resp = await client.get(
                    url,
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    print(f"[ChEMBL] 请求超时，第{attempt + 1}次重试...")
                    continue
                print(f"[ChEMBL] 请求超时，已达最大重试次数")
                return None
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                if attempt < self.max_retries:
                    print(f"[ChEMBL] HTTP {e.response.status_code}，第{attempt + 1}次重试...")
                    continue
                print(f"[ChEMBL] HTTP {e.response.status_code}，已达最大重试次数")
                return None
            except Exception as e:
                if attempt < self.max_retries:
                    print(f"[ChEMBL] 请求异常: {e}，第{attempt + 1}次重试...")
                    continue
                print(f"[ChEMBL] 请求异常: {e}，已达最大重试次数")
                return None
        return None

    async def search_molecule(self, molecule_name: str) -> Optional[dict]:
        url = f"{CHEMBL_BASE}/molecule/search.json?q={molecule_name}"
        data = await self._request(url)
        if not data:
            return None

        molecules = data.get("molecules", [])
        if not molecules:
            return None

        mol = molecules[0]
        properties = mol.get("molecule_properties", {}) or {}
        structures = mol.get("molecule_structures", {}) or {}

        max_phase_raw = mol.get("max_phase", 0)
        try:
            max_phase = int(float(max_phase_raw))
        except (TypeError, ValueError):
            max_phase = 0

        return {
            "chembl_id": mol.get("molecule_chembl_id"),
            "molecule_name": mol.get("pref_name") or molecule_name,
            "max_phase": max_phase,
            "molecular_formula": properties.get("full_molformula", "暂无数据"),
            "smiles": structures.get("canonical_smiles", "暂无数据"),
        }

    async def get_activities(
        self, chembl_id: str, limit: int = 10
    ) -> Optional[list[dict]]:
        url = (
            f"{CHEMBL_BASE}/activity.json"
            f"?molecule_chembl_id={chembl_id}&limit={limit}"
        )
        data = await self._request(url)
        if not data:
            return None

        activities = data.get("activities", [])
        if not activities:
            return []

        results = []
        for act in activities:
            target_info = act.get("target", {}) or {}
            results.append({
                "target_name": target_info.get("pref_name") or act.get("target_pref_name", "未知靶点"),
                "organism": target_info.get("organism") or act.get("target_organism", "未知"),
                "assay_type": act.get("assay_type", "未知"),
                "activity_type": act.get("standard_type", "未知"),
                "standard_value": act.get("standard_value"),
                "standard_units": act.get("standard_units", ""),
            })
        return results

    async def get_drug_info(self, chembl_id: str) -> Optional[dict]:
        # 第一步：从molecule获取临床阶段
        url = f"{CHEMBL_BASE}/molecule/{chembl_id}.json"
        data = await self._request(url)
        if not data:
            return None

        max_phase_raw = data.get("max_phase", 0)
        try:
            max_phase = int(float(max_phase_raw))
        except (TypeError, ValueError):
            max_phase = 0

        molecule_name = data.get("pref_name", chembl_id)

        result = {
            "chembl_id": chembl_id,
            "molecule_name": molecule_name,
            "max_phase": max_phase,
            "phase_description": PHASE_MAP.get(max_phase, "未知"),
            "indication": "暂无数据",
            "approval_year": None,
        }

        # 第二步：如果已上市，查drug记录获取批准年份
        if max_phase == 4:
            drug_url = f"{CHEMBL_BASE}/drug/search.json?molecule_chembl_id={chembl_id}"
            drug_data = await self._request(drug_url)
            if drug_data:
                drugs = drug_data.get("drugs", [])
                if drugs:
                    first_approved = drugs[0].get("first_approval", None)
                    result["approval_year"] = first_approved

        # 第三步：查drug_indication专用接口获取适应症
        indication_url = (
            f"{CHEMBL_BASE}/drug_indication.json"
            f"?molecule_chembl_id={chembl_id}&limit=5"
        )
        indication_data = await self._request(indication_url)
        if indication_data:
            indications = indication_data.get("drug_indications", [])
            if indications:
                terms = []
                for ind in indications[:3]:
                    term = (
                        ind.get("efo_term")
                        or ind.get("mesh_heading")
                        or ind.get("indication_class", "")
                    )
                    if term and term not in terms:
                        terms.append(term)
                if terms:
                    result["indication"] = "; ".join(terms)

        return result


# 模块级单例，跨请求复用 httpx 连接池
chembl = ChEMBLClient()
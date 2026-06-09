"""
PubMed E-utilities API 封装模块

提供1个异步方法：
- search_literature: 按关键词检索文献，返回标题、作者、摘要等

API文档: https://www.ncbi.nlm.nih.gov/books/books/NBK25501/
无需API Key（速率限制3次/秒）
"""

import asyncio
import urllib.parse
from typing import Optional

import httpx

# PubMed E-utilities 基础URL
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedClient:
    """PubMed API 异步客户端

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

    async def _request(self, url: str, params: dict = None) -> Optional[str]:
        """通用请求方法，返回原始文本"""
        client = await self._get_client()
        for attempt in range(self.max_retries + 1):
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.text
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    print(f"[PubMed] 请求超时，第{attempt + 1}次重试...")
                    continue
                print(f"[PubMed] 请求超时，已达最大重试次数")
                return None
            except httpx.HTTPStatusError as e:
                if attempt < self.max_retries:
                    print(f"[PubMed] HTTP {e.response.status_code}，第{attempt + 1}次重试...")
                    continue
                print(f"[PubMed] HTTP {e.response.status_code}，已达最大重试次数")
                return None
            except Exception as e:
                if attempt < self.max_retries:
                    print(f"[PubMed] 请求异常: {e}，第{attempt + 1}次重试...")
                    continue
                print(f"[PubMed] 请求异常: {e}，已达最大重试次数")
                return None
        return None

    async def search_literature(
        self, query: str, max_results: int = 5
    ) -> Optional[list[dict]]:
        """
        检索PubMed文献

        Args:
            query: 检索关键词，如 "LRPPRC inhibitor"
            max_results: 返回数量，默认5
        Returns:
            [{"pmid": str, "title": str, "authors": str, "journal": str,
              "year": str, "abstract": str, "doi": str, "pubmed_url": str}]
        """
        # 第一步：搜索获取PMID列表
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        search_text = await self._request(ESEARCH_URL, search_params)
        if not search_text:
            return None

        # 解析JSON获取PMID列表
        import json
        try:
            search_data = json.loads(search_text)
        except json.JSONDecodeError:
            return None

        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # 第二步：获取文献详情
        await asyncio.sleep(0.4)  # 速率控制
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "rettype": "abstract",
            "retmode": "xml",
        }
        fetch_text = await self._request(EFETCH_URL, fetch_params)
        if not fetch_text:
            return None

        # 第三步：解析XML
        return self._parse_pubmed_xml(fetch_text)

    def _parse_pubmed_xml(self, xml_text: str) -> list[dict]:
        """解析PubMed XML返回文献列表"""
        import xml.etree.ElementTree as ET

        results = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return results

        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            if medline is None:
                continue

            art = medline.find(".//Article")
            if art is None:
                continue

            # PMID
            pmid_el = medline.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else "未知"

            # 标题
            title_el = art.find(".//ArticleTitle")
            title = title_el.text if title_el is not None else "无标题"

            # 作者（取前3位）
            authors = []
            for author in art.findall(".//Author")[:3]:
                last = author.find("LastName")
                fore = author.find("ForeName")
                if last is not None:
                    name = last.text
                    if fore is not None:
                        name = f"{last.text} {fore.text}"
                    authors.append(name)
            author_str = ", ".join(authors)
            if len(art.findall(".//Author")) > 3:
                author_str += " et al."

            # 期刊
            journal_el = art.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else "未知期刊"

            # 年份
            year_el = art.find(".//PubDate/Year")
            if year_el is None:
                year_el = art.find(".//PubDate/MedlineDate")
            year = year_el.text[:4] if year_el is not None else "未知"

            # 摘要（截取前300字）
            abstract_parts = []
            for abs_text in art.findall(".//Abstract/AbstractText"):
                label = abs_text.get("Label", "")
                text = "".join(abs_text.itertext())
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)
            if len(abstract) > 300:
                abstract = abstract[:300] + "..."

            # DOI
            doi_el = article.find(".//PubmedData/ArticleIdList/ArticleId[@IdType='doi']")
            doi = doi_el.text if doi_el is not None else "暂无"

            results.append({
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "journal": journal,
                "year": year,
                "abstract": abstract if abstract else "暂无摘要",
                "doi": doi,
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })

        return results


# 模块级单例，跨请求复用 httpx 连接池
pubmed = PubMedClient()
"""
研究现状上下文构建器 - 搜寻论文相关领域的研究现状作为评估前后文

核心功能：
1. 从论文中提取关键研究主题
2. 通过Semantic Scholar API搜索相关论文
3. 通过CrossRef API搜索相关论文
4. 构建研究现状文档，作为评估的前后文

使用方式：
    from src.evaluation.research_context_builder import ResearchContextBuilder

    builder = ResearchContextBuilder()
    context = builder.build_context(thesis_content)
"""

import json
import logging
import os
import re
import time
import hashlib
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResearchContextBuilder:

    SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
    CROSSREF_BASE = "https://api.crossref.org/works"

    def __init__(self, cache_dir: str = None, request_delay: float = 1.0):
        self.request_delay = request_delay
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "research_cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        self._cache = {}
        self._llm_client = None
        self._ai_config = None

    def _ensure_llm(self):
        if self._llm_client is None:
            from src.config import get_ai_config
            self._ai_config = get_ai_config()
            import openai
            self._llm_client = openai.OpenAI(
                api_key=self._ai_config["api_key"],
                base_url=self._ai_config["base_url"]
            )

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 4000) -> str:
        self._ensure_llm()
        response = self._llm_client.chat.completions.create(
            model=self._ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    def build_context(self, thesis_content: str, key_topics: List[str] = None) -> Dict:
        start_time = time.time()
        logger.info("开始构建研究现状上下文...")

        if not key_topics:
            key_topics = self._extract_research_topics(thesis_content)
        logger.info(f"提取到{len(key_topics)}个研究主题: {key_topics[:5]}")

        all_papers = []
        for topic in key_topics[:6]:
            papers = self._search_papers(topic, max_results=5)
            all_papers.extend(papers)
            time.sleep(self.request_delay)

        seen_titles = set()
        unique_papers = []
        for p in all_papers:
            title_key = p.get("title", "")[:50].lower().strip()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_papers.append(p)

        research_landscape = self._build_research_landscape(unique_papers, key_topics)

        context_document = self._generate_context_document(research_landscape, key_topics, thesis_content)

        elapsed = time.time() - start_time
        logger.info(f"研究现状上下文构建完成，耗时{elapsed:.1f}秒，找到{len(unique_papers)}篇相关论文")

        return {
            "key_topics": key_topics,
            "related_papers": unique_papers,
            "papers_count": len(unique_papers),
            "research_landscape": research_landscape,
            "context_document": context_document,
            "build_time_seconds": round(elapsed, 1),
        }

    def _extract_research_topics(self, content: str) -> List[str]:
        system_prompt = """你是一位学术研究分析专家。请从论文中提取核心研究主题，用于搜索相关研究现状。

要求：
1. 提取5-8个最能代表论文研究方向的关键主题
2. 每个主题应该是学术界常用的研究术语或关键词组合
3. 主题应该覆盖论文的研究问题、方法、应用领域
4. 用中英文双语形式提供，便于搜索中英文文献

请输出JSON格式。"""

        content_preview = content[:15000]

        user_prompt = f"""请从以下论文中提取核心研究主题：

{content_preview}

请输出如下JSON格式：
{{
    "topics": [
        {{
            "chinese": "中文主题描述",
            "english": "English topic description",
            "search_query": "最适合搜索的英文关键词组合",
            "importance": "高/中/低"
        }}
    ]
}}"""

        try:
            raw = self._call_llm(system_prompt, user_prompt, temperature=0.2, max_tokens=4000)
            result = json.loads(raw)
            topics = []
            for t in result.get("topics", []):
                if t.get("importance") == "高":
                    topics.insert(0, t.get("search_query", t.get("english", "")))
                else:
                    topics.append(t.get("search_query", t.get("english", "")))
            return topics[:8] if topics else self._fallback_extract_topics(content)
        except Exception as e:
            logger.warning(f"LLM提取研究主题失败: {str(e)}")
            return self._fallback_extract_topics(content)

    def _fallback_extract_topics(self, content: str) -> List[str]:
        topics = []
        patterns = [
            r'(?:基于|提出|设计|采用)[了]?\s*([^\s，,。；;]{3,40}(?:方法|模型|算法|网络|框架|系统))',
            r'(?:物理信息神经网络|PINN|深度学习|机器学习|神经网络|Transformer|注意力机制|LSTM|CNN|RNN|GAN)',
            r'(?:Navier-Stokes|N-S|波动方程|热传导方程|有限元|有限差分|CFD|DNS|LES)',
        ]
        for pat in patterns:
            for m in re.finditer(pat, content[:10000]):
                term = m.group(0) if m.lastindex is None else m.group(m.lastindex)
                if term not in topics:
                    topics.append(term)

        if not topics:
            first_500 = content[:500].replace('\n', ' ')
            words = re.findall(r'[a-zA-Z]{3,}', first_500)
            for w in words[:5]:
                if len(w) > 3 and w not in topics:
                    topics.append(w)

        return topics[:6] if topics else ["thesis evaluation"]

    def _search_papers(self, query: str, max_results: int = 5) -> List[Dict]:
        papers = []

        ss_papers = self._search_semantic_scholar(query, max_results)
        papers.extend(ss_papers)

        if len(papers) < max_results:
            cr_papers = self._search_crossref(query, max_results - len(papers))
            papers.extend(cr_papers)

        return papers[:max_results]

    def _search_semantic_scholar(self, query: str, max_results: int = 5) -> List[Dict]:
        cache_key = f"ss_search_{hashlib.md5(query.encode()).hexdigest()}"
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode({
            "query": query,
            "limit": max_results,
            "fields": "title,authors,year,abstract,citationCount,influentialCitationCount,venue,openAccessPdf"
        })
        url = f"{self.SEMANTIC_SCHOLAR_BASE}/paper/search?{params}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            papers = []
            for item in data.get("data", []):
                authors = ", ".join(
                    a.get("name", "") for a in (item.get("authors") or [])[:3]
                )
                paper = {
                    "title": item.get("title", ""),
                    "authors": authors,
                    "year": item.get("year"),
                    "abstract": item.get("abstract", "") or "",
                    "citation_count": item.get("citationCount", 0),
                    "influential_citations": item.get("influentialCitationCount", 0),
                    "venue": item.get("venue", ""),
                    "source": "semantic_scholar",
                }
                if paper["title"]:
                    papers.append(paper)

            self._save_cache(cache_key, papers)
            return papers
        except Exception as e:
            logger.warning(f"Semantic Scholar搜索失败 ({query}): {str(e)}")
            return []

    def _search_crossref(self, query: str, max_results: int = 3) -> List[Dict]:
        cache_key = f"cr_search_{hashlib.md5(query.encode()).hexdigest()}"
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode({
            "query": query,
            "rows": max_results,
            "sort": "relevance"
        })
        url = f"{self.CROSSREF_BASE}?{params}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ThesisEvaluator/1.0 (mailto:eval@example.com)"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            papers = []
            for item in data.get("message", {}).get("items", []):
                authors = ", ".join(
                    f"{a.get('given', '')} {a.get('family', '')}".strip()
                    for a in (item.get("author") or [])[:3]
                )
                year = None
                date_parts = (
                    item.get("published-print", {}).get("date-parts", [[None]])[0]
                    or item.get("published-online", {}).get("date-parts", [[None]])[0]
                )
                if date_parts:
                    year = date_parts[0]

                title_list = item.get("title", [])
                title = title_list[0] if title_list else ""

                paper = {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "abstract": item.get("abstract", "") or "",
                    "citation_count": item.get("is-referenced-by-count", 0),
                    "venue": item.get("container-title", [""])[0] if item.get("container-title") else "",
                    "source": "crossref",
                }
                if paper["title"]:
                    papers.append(paper)

            self._save_cache(cache_key, papers)
            return papers
        except Exception as e:
            logger.warning(f"CrossRef搜索失败 ({query}): {str(e)}")
            return []

    def _load_cache(self, key: str) -> Optional[List[Dict]]:
        if key in self._cache:
            return self._cache[key]
        path = os.path.join(self.cache_dir, f"{hashlib.md5(key.encode()).hexdigest()}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[key] = data
                return data
            except Exception:
                pass
        return None

    def _save_cache(self, key: str, data):
        self._cache[key] = data
        path = os.path.join(self.cache_dir, f"{hashlib.md5(key.encode()).hexdigest()}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存保存失败: {str(e)}")

    def _build_research_landscape(self, papers: List[Dict], key_topics: List[str]) -> Dict:
        if not papers:
            return {
                "total_papers": 0,
                "year_range": None,
                "top_cited": [],
                "topic_coverage": {},
                "research_trends": "未找到相关论文",
            }

        years = [p["year"] for p in papers if p.get("year")]
        year_range = f"{min(years)}-{max(years)}" if years else "未知"

        sorted_by_citations = sorted(papers, key=lambda x: x.get("citation_count", 0), reverse=True)
        top_cited = sorted_by_citations[:10]

        topic_coverage = {}
        for topic in key_topics:
            related = []
            topic_lower = topic.lower()
            for p in papers:
                title_lower = p.get("title", "").lower()
                abstract_lower = p.get("abstract", "").lower()
                if topic_lower in title_lower or topic_lower in abstract_lower:
                    related.append(p.get("title", "")[:80])
            topic_coverage[topic] = len(related)

        return {
            "total_papers": len(papers),
            "year_range": year_range,
            "top_cited": [
                {
                    "title": p.get("title", ""),
                    "authors": p.get("authors", ""),
                    "year": p.get("year"),
                    "citations": p.get("citation_count", 0),
                    "venue": p.get("venue", ""),
                    "abstract": p.get("abstract", ""),
                }
                for p in top_cited
            ],
            "all_papers_with_abstracts": [
                {
                    "title": p.get("title", ""),
                    "authors": p.get("authors", ""),
                    "year": p.get("year"),
                    "citations": p.get("citation_count", 0),
                    "venue": p.get("venue", ""),
                    "abstract": p.get("abstract", ""),
                    "source": p.get("source", ""),
                }
                for p in papers
            ],
            "topic_coverage": topic_coverage,
        }

    def _generate_context_document(self, landscape: Dict, key_topics: List[str], thesis_content: str) -> str:
        if not landscape.get("total_papers"):
            return "未找到相关研究论文，无法构建研究现状上下文。"

        all_papers = landscape.get("all_papers_with_abstracts", [])
        papers_detail = ""
        for i, p in enumerate(all_papers[:20]):
            papers_detail += f"\n---\n论文{i+1}: {p.get('title', '未知')} ({p.get('year', '未知')})\n"
            if p.get("authors"):
                papers_detail += f"作者: {p['authors']}\n"
            if p.get("venue"):
                papers_detail += f"期刊/会议: {p['venue']}\n"
            papers_detail += f"引用数: {p.get('citations', 0)}\n"
            abstract = p.get("abstract", "")
            if abstract:
                papers_detail += f"摘要: {abstract[:500]}\n"
            else:
                papers_detail += "摘要: 无\n"

        topic_coverage_str = ""
        for topic, count in landscape.get("topic_coverage", {}).items():
            topic_coverage_str += f"- {topic}: 找到{count}篇相关论文\n"

        system_prompt = """你是一位学术研究综述专家。请**严格基于下方从学术数据库（Semantic Scholar / CrossRef）搜索到的真实论文**，撰写该领域的研究现状综述。

【核心原则 - 绝对禁止编造】
1. 你必须且只能基于下方提供的搜索结果论文来撰写综述
2. 每个观点、方法、趋势都必须引用具体的论文标题和作者作为依据
3. 绝对不能凭空编造论文、方法或结论
4. 如果搜索结果中的论文摘要为空或信息不足，请如实说明"该论文摘要不可获取"，不要推测其内容
5. 不要将任何上传论文的内容混入综述，综述完全基于外部搜索到的研究文献

请用中文撰写，内容详细，至少1000字。每个论点必须引用具体的论文。"""

        user_prompt = f"""请基于以下从学术数据库搜索到的真实论文，撰写研究现状综述：

## 研究主题
{chr(10).join(['- ' + t for t in key_topics])}

## 主题覆盖情况
{topic_coverage_str}

## 搜索到的论文（共{landscape.get('total_papers', 0)}篇，以下是详细信息）
{papers_detail}

## 论文年份范围
{landscape.get('year_range', '未知')}

请**严格基于以上搜索到的论文**撰写详细的研究现状综述，包括：
1. 该领域的研究背景和意义
2. 主要研究方向和进展
3. 关键技术方法综述
4. 当前研究热点和前沿
5. 现有研究的不足和挑战
6. 未来发展趋势

每个论点必须引用具体论文的标题和作者。

请输出如下JSON格式：
{{
    "research_background": "研究背景和意义（300字以上，引用具体论文）",
    "main_directions": "主要研究方向和进展（400字以上，引用具体论文）",
    "key_methods": "关键技术方法综述（400字以上，引用具体论文的方法和结论）",
    "hot_topics": "当前研究热点和前沿（300字以上，引用具体论文）",
    "gaps": "现有研究的不足和挑战（300字以上）",
    "trends": "未来发展趋势（300字以上）",
    "sota_summary": "当前该领域最先进方法的简要总结（300字以上，引用具体论文）"
}}"""

        try:
            raw = self._call_llm(system_prompt, user_prompt, temperature=0.3, max_tokens=6000)
            result = json.loads(raw)

            doc_parts = ["# 研究现状综述\n"]
            for key, label in [
                ("research_background", "## 研究背景和意义"),
                ("main_directions", "## 主要研究方向和进展"),
                ("key_methods", "## 关键技术方法综述"),
                ("hot_topics", "## 当前研究热点和前沿"),
                ("gaps", "## 现有研究的不足和挑战"),
                ("trends", "## 未来发展趋势"),
                ("sota_summary", "## 当前最先进方法总结"),
            ]:
                content = result.get(key, "")
                if content:
                    doc_parts.append(f"{label}\n{content}\n")

            doc_parts.append(f"\n## 参考论文（共{landscape.get('total_papers', 0)}篇）\n")
            for i, p in enumerate(landscape.get("top_cited", [])[:15]):
                doc_parts.append(f"{i+1}. {p.get('title', '')} ({p.get('year', '')}) - 引用{p.get('citations', 0)}次, {p.get('venue', '')}")

            return "\n\n".join(doc_parts)
        except Exception as e:
            logger.warning(f"LLM生成研究综述失败: {str(e)}")
            return f"研究现状上下文（自动生成失败，使用原始数据）:\n\n{papers_summary}"

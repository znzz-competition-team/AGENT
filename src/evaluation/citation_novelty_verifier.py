"""
基于引用网络的新颖度验证系统

利用Semantic Scholar API和CrossRef API验证论文引用的真实性、新颖度和学术影响力。
核心功能：
1. 引用文献真实性验证 - 检查引用的文献是否真实存在，识别虚假引用
2. 引用新颖度评估 - 分析引用文献的年份分布和时效性
3. 引用网络分析 - 通过引用图谱评估论文创新性
4. 自引检测 - 识别过度自引
5. 创新性交叉验证 - 将论文声称的创新点与引用网络中的已有工作进行对比
6. 虚假引用检测 - 多维度交叉验证，识别AI编造或虚构的参考文献
7. 引用质量深度评价 - 评估引用的权威性、相关性和充分性
"""

from typing import Dict, List, Optional, Tuple
import json
import logging
import os
import re
import time
import hashlib

logger = logging.getLogger(__name__)


class ReferenceExtractor:
    """参考文献提取器"""

    REFERENCE_PATTERNS = [
        re.compile(
            r'\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)',
            re.DOTALL,
        ),
        re.compile(
            r'^(\d+)\.\s*(.+?)$',
            re.MULTILINE,
        ),
    ]

    AUTHOR_YEAR_PATTERN = re.compile(
        r'([A-Z][a-z]+(?:\s+(?:et\s+al\.?|and|&))?)\s*[\(\[](\d{4})[\)\]]',
    )

    CHINESE_AUTHOR_PATTERN = re.compile(
        r'([\u4e00-\u9fff]{2,4})\s*[\(\[（](\d{4})[\)\]）]',
    )

    DOI_PATTERN = re.compile(r'10\.\d{4,9}/[^\s,;]+')

    def extract_references(self, text: str) -> List[Dict]:
        references = self._extract_reference_section(text)
        if not references:
            return []

        all_refs = []
        for pattern in self.REFERENCE_PATTERNS:
            matches = pattern.findall(references)
            if matches and len(matches) >= 3:
                for match in matches:
                    if isinstance(match, tuple):
                        idx = match[0].strip()
                        raw = match[1].strip()
                    else:
                        idx = str(len(all_refs) + 1)
                        raw = match.strip()

                    ref = self._parse_single_reference(idx, raw)
                    all_refs.append(ref)
                break

        if not all_refs:
            all_refs = self._extract_by_line_splitting(references)

        return all_refs

    def _extract_reference_section(self, text: str) -> Optional[str]:
        section_headers = [
            r'参考文献',
            r'References',
            r'Bibliography',
            r'引用文献',
            r'REFERENCES',
        ]

        for header in section_headers:
            pattern = re.compile(
                rf'(?:^|\n)\s*{header}\s*\n(.*?)(?=(?:\n\s*(?:附录|致谢|Appendix|Acknowledgement|ACKNOWLEDGEMENTS)\s*\n)|$)',
                re.DOTALL,
            )
            match = pattern.search(text)
            if match:
                return match.group(1).strip()

        return None

    def _parse_single_reference(self, index: str, raw_text: str) -> Dict:
        year = None
        authors = None
        doi = None

        author_year = self.AUTHOR_YEAR_PATTERN.search(raw_text)
        if author_year:
            authors = author_year.group(1).strip()
            year = author_year.group(2)

        if not year:
            cn_author = self.CHINESE_AUTHOR_PATTERN.search(raw_text)
            if cn_author:
                authors = cn_author.group(1).strip()
                year = cn_author.group(2)

        if not year:
            year_match = re.search(r'(19|20)\d{2}', raw_text)
            if year_match:
                year = year_match.group(0)

        doi_match = self.DOI_PATTERN.search(raw_text)
        if doi_match:
            doi = doi_match.group(0).rstrip('.')

        return {
            "index": int(index) if index.isdigit() else len(raw_text),
            "raw_text": raw_text[:500],
            "authors": authors,
            "year": year,
            "doi": doi,
            "title": self._extract_title(raw_text),
        }

    def _extract_title(self, raw_text: str) -> Optional[str]:
        if '.' in raw_text:
            parts = raw_text.split('.')
            if len(parts) >= 2:
                title_candidate = parts[1].strip()
                if 10 <= len(title_candidate) <= 200:
                    return title_candidate[:200]
        return None

    def _extract_by_line_splitting(self, ref_section: str) -> List[Dict]:
        lines = [l.strip() for l in ref_section.split('\n') if l.strip()]
        references = []

        for i, line in enumerate(lines):
            if len(line) < 10:
                continue
            ref = self._parse_single_reference(str(i + 1), line)
            references.append(ref)

        return references


class CitationNetworkVerifier:
    """引用网络验证器 - 通过Semantic Scholar API和CrossRef API验证引用"""

    SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
    CROSSREF_BASE = "https://api.crossref.org/works"

    def __init__(
        self,
        semantic_scholar_api_key: str = None,
        cache_dir: str = None,
        request_delay: float = 1.0,
    ):
        self.api_key = semantic_scholar_api_key
        self.request_delay = request_delay
        self.cache_dir = cache_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "citation_cache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        self._cache = {}

    def _get_cache_path(self, key: str) -> str:
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{h}.json")

    def _load_cache(self, key: str) -> Optional[Dict]:
        if key in self._cache:
            return self._cache[key]
        path = self._get_cache_path(key)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[key] = data
                return data
            except Exception:
                pass
        return None

    def _save_cache(self, key: str, data: Dict):
        self._cache[key] = data
        path = self._get_cache_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存保存失败: {str(e)}")

    def _semantic_scholar_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        import urllib.request
        import urllib.parse

        url = f"{self.SEMANTIC_SCHOLAR_BASE}/{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            time.sleep(self.request_delay)
            return data
        except Exception as e:
            logger.warning(f"Semantic Scholar API请求失败 ({endpoint}): {str(e)}")
            return None

    def _crossref_request(self, query: str, rows: int = 3) -> Optional[Dict]:
        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode({"query": query, "rows": rows})
        url = f"{self.CROSSREF_BASE}?{params}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ThesisEvaluator/1.0 (mailto:eval@example.com)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            time.sleep(self.request_delay * 0.5)
            return data
        except Exception as e:
            logger.warning(f"CrossRef API请求失败: {str(e)}")
            return None

    def verify_reference(self, reference: Dict, thesis_keywords: set = None) -> Dict:
        cache_key = f"verify_{reference.get('raw_text', '')[:100]}"
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        result = {
            "reference_index": reference.get("index"),
            "raw_text": reference.get("raw_text", "")[:200],
            "verified": False,
            "confidence": 0.0,
            "source": "none",
            "paper_info": {},
            "suspicious_indicators": [],
            "verification_detail": "",
            "topic_mismatch": False,
        }

        suspicious = self._check_suspicious_indicators(reference)
        result["suspicious_indicators"] = suspicious

        if reference.get("doi"):
            paper_info = self._verify_by_doi(reference["doi"])
            if paper_info:
                title_match = self._title_similarity(
                    reference.get("title", ""), paper_info.get("title", "")
                )
                if title_match < 0.3:
                    result["topic_mismatch"] = True
                    result["suspicious_indicators"].append(
                        f"DOI查到的论文标题与引用标题不匹配（相似度{title_match:.0%}）"
                    )
                    result["verification_detail"] = (
                        f"通过DOI找到论文，但标题不匹配: 引用标题「{reference.get('title', '')[:60]}」"
                        f" vs 实际论文「{paper_info.get('title', '')[:60]}」"
                    )
                    result["confidence"] = 0.3
                    result["paper_info"] = paper_info
                    result["source"] = "semantic_scholar_doi_mismatch"
                    self._save_cache(cache_key, result)
                    return result

                result.update({
                    "verified": True,
                    "confidence": 0.95,
                    "source": "semantic_scholar_doi",
                    "paper_info": paper_info,
                    "verification_detail": f"通过DOI在Semantic Scholar找到匹配论文: {paper_info.get('title', '')[:80]}",
                })
                self._save_cache(cache_key, result)
                return result

        title = reference.get("title")
        if title and len(title) > 10:
            paper_info = self._verify_by_title(title)
            if paper_info:
                title_match = self._title_similarity(title, paper_info.get("title", ""))
                if title_match < 0.4:
                    result["topic_mismatch"] = True
                    result["suspicious_indicators"].append(
                        f"标题搜索结果与引用标题不匹配（相似度{title_match:.0%}）"
                    )
                    result["verification_detail"] = (
                        f"通过标题搜索找到论文，但标题不匹配: 引用「{title[:60]}」"
                        f" vs 实际「{paper_info.get('title', '')[:60]}」"
                    )
                    result["confidence"] = 0.3
                    result["paper_info"] = paper_info
                    result["source"] = "semantic_scholar_title_mismatch"
                    self._save_cache(cache_key, result)
                    return result

                result.update({
                    "verified": True,
                    "confidence": 0.8,
                    "source": "semantic_scholar_title",
                    "paper_info": paper_info,
                    "verification_detail": f"通过标题在Semantic Scholar找到匹配论文: {paper_info.get('title', '')[:80]}",
                })
                self._save_cache(cache_key, result)
                return result

        authors = reference.get("authors", "")
        year = reference.get("year", "")
        if authors or year:
            paper_info = self._verify_by_crossref(authors, year, title)
            if paper_info:
                ref_title = reference.get("title", "") or ""
                found_title = paper_info.get("title", "")
                if ref_title and found_title:
                    title_match = self._title_similarity(ref_title, found_title)
                    if title_match < 0.3:
                        result["topic_mismatch"] = True
                        result["suspicious_indicators"].append(
                            f"CrossRef结果与引用标题不匹配（相似度{title_match:.0%}）"
                        )
                        result["verification_detail"] = (
                            f"通过CrossRef找到论文，但标题不匹配: 引用「{ref_title[:60]}」"
                            f" vs 实际「{found_title[:60]}」"
                        )
                        result["confidence"] = 0.2
                        result["paper_info"] = paper_info
                        result["source"] = "crossref_mismatch"
                        self._save_cache(cache_key, result)
                        return result

                if thesis_keywords and found_title:
                    found_keywords = self._extract_keywords_from_text(found_title)
                    topic_overlap = thesis_keywords & found_keywords
                    if not topic_overlap and len(thesis_keywords) > 3:
                        result["topic_mismatch"] = True
                        result["suspicious_indicators"].append(
                            f"CrossRef查到的论文与论文主题无关（标题: {found_title[:60]}）"
                        )
                        result["verification_detail"] = (
                            f"通过CrossRef找到论文，但与论文主题无关: 「{found_title[:60]}」"
                        )
                        result["confidence"] = 0.25
                        result["paper_info"] = paper_info
                        result["source"] = "crossref_topic_mismatch"
                        self._save_cache(cache_key, result)
                        return result

                result.update({
                    "verified": True,
                    "confidence": 0.6,
                    "source": "crossref",
                    "paper_info": paper_info,
                    "verification_detail": f"通过CrossRef找到匹配论文: {paper_info.get('title', '')[:80]}",
                })
                self._save_cache(cache_key, result)
                return result

        if suspicious:
            result["confidence"] = 0.1
            result["verification_detail"] = f"未在任何学术数据库中找到该文献，且存在可疑特征: {'; '.join(suspicious)}"
        else:
            result["confidence"] = 0.3
            result["verification_detail"] = "未在任何学术数据库中找到该文献，可能为较冷门文献或引用信息不完整"

        self._save_cache(cache_key, result)
        return result

    def _extract_keywords_from_text(self, text: str) -> set:
        if not text:
            return set()
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'shall', 'can', 'this', 'that',
            'these', 'those', 'it', 'its', 'not', 'no', 'as', 'if', 'than',
        }
        words = re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,4}', text.lower())
        return set(w for w in words if w not in stopwords)

    def _check_suspicious_indicators(self, reference: Dict) -> List[str]:
        """检测虚假引用的可疑指标"""
        suspicious = []
        raw = reference.get("raw_text", "")

        if not reference.get("authors") and not reference.get("year"):
            suspicious.append("缺少作者和年份信息")

        if reference.get("year"):
            try:
                y = int(reference["year"])
                import datetime
                if y > datetime.datetime.now().year + 1:
                    suspicious.append(f"年份异常（{y}年，超过当前年份）")
                if y < 1900:
                    suspicious.append(f"年份异常（{y}年，过早）")
            except (ValueError, TypeError):
                suspicious.append("年份格式异常")

        if reference.get("doi"):
            if not re.match(r'^10\.\d{4,9}/', reference["doi"]):
                suspicious.append("DOI格式异常")

        title = reference.get("title", "")
        if title:
            if len(title) < 5:
                suspicious.append("标题过短")
            if re.match(r'^[A-Z\s]+$', title) and len(title) > 30:
                suspicious.append("标题全大写（非正常学术格式）")

        if len(raw) < 20:
            suspicious.append("引用信息过短，可能不完整")

        if not reference.get("doi") and not reference.get("title"):
            suspicious.append("既无DOI也无标题，难以验证")

        return suspicious

    def _verify_by_doi(self, doi: str) -> Optional[Dict]:
        data = self._semantic_scholar_request(
            f"paper/DOI:{doi}",
            {"fields": "title,year,citationCount,authors,venue,externalIds,abstract"},
        )
        if data and data.get("title"):
            return self._format_paper_info(data)
        return None

    def _verify_by_title(self, title: str) -> Optional[Dict]:
        data = self._semantic_scholar_request(
            f"paper/search",
            {"query": title[:200], "limit": 1, "fields": "title,year,citationCount,authors,venue,externalIds,abstract"},
        )
        if data and data.get("data") and len(data["data"]) > 0:
            paper = data["data"][0]
            if paper.get("title"):
                title_sim = self._title_similarity(title, paper["title"])
                if title_sim > 0.5:
                    return self._format_paper_info(paper)
        return None

    def _verify_by_crossref(
        self, authors: str, year: str, title: str = None
    ) -> Optional[Dict]:
        query_parts = []
        if title:
            query_parts.append(title[:100])
        elif authors:
            query_parts.append(authors)
        if year:
            query_parts.append(year)

        query = " ".join(query_parts)
        if not query.strip():
            return None

        data = self._crossref_request(query)
        if data and data.get("message", {}).get("items"):
            item = data["message"]["items"][0]
            return {
                "title": item.get("title", [""])[0] if item.get("title") else "",
                "year": item.get("published-print", {}).get("date-parts", [[None]])[0][0]
                or item.get("published-online", {}).get("date-parts", [[None]])[0][0],
                "citation_count": item.get("is-referenced-by-count", 0),
                "authors": [
                    a.get("given", "") + " " + a.get("family", "")
                    for a in item.get("author", [])
                ],
                "venue": item.get("container-title", [""])[0] if item.get("container-title") else "",
                "doi": item.get("DOI", ""),
            }
        return None

    def _format_paper_info(self, data: Dict) -> Dict:
        authors = []
        for a in data.get("authors", []):
            authors.append(a.get("name", ""))

        return {
            "title": data.get("title", ""),
            "year": data.get("year"),
            "citation_count": data.get("citationCount", 0),
            "authors": authors[:5],
            "venue": data.get("venue", ""),
            "doi": data.get("externalIds", {}).get("DOI", ""),
            "abstract": data.get("abstract", "")[:300] if data.get("abstract") else "",
        }

    def _title_similarity(self, title1: str, title2: str) -> float:
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)


class NoveltyVerifier:
    """新颖度验证器 - 综合评估论文创新性"""

    def __init__(
        self,
        semantic_scholar_api_key: str = None,
        cache_dir: str = None,
    ):
        self.extractor = ReferenceExtractor()
        self.verifier = CitationNetworkVerifier(
            semantic_scholar_api_key=semantic_scholar_api_key,
            cache_dir=cache_dir,
        )

    def verify_thesis_novelty(
        self,
        thesis_content: str,
        claimed_innovations: List[str] = None,
        max_references_to_verify: int = 20,
    ) -> Dict:
        logger.info("开始新颖度验证...")

        references = self.extractor.extract_references(thesis_content)
        logger.info(f"提取到{len(references)}条参考文献")

        if not claimed_innovations:
            claimed_innovations = self._extract_claimed_innovations(thesis_content)
        logger.info(f"识别到{len(claimed_innovations)}个创新点声称")

        refs_to_verify = references[:max_references_to_verify]
        thesis_keywords = self._extract_keywords(thesis_content[:8000])
        verification_results = []
        verified_count = 0
        unverified_refs = []
        suspicious_refs = []
        topic_mismatch_refs = []

        for ref in refs_to_verify:
            result = self.verifier.verify_reference(ref, thesis_keywords=thesis_keywords)
            verification_results.append(result)
            if result.get("topic_mismatch"):
                topic_mismatch_refs.append({
                    "index": ref.get("index"),
                    "raw_text": ref.get("raw_text", "")[:150],
                    "found_title": result.get("paper_info", {}).get("title", ""),
                    "reason": result.get("verification_detail", ""),
                    "source": result.get("source", ""),
                })
                suspicious_refs.append({
                    "index": ref.get("index"),
                    "raw_text": ref.get("raw_text", "")[:150],
                    "indicators": result.get("suspicious_indicators", []),
                    "detail": result.get("verification_detail", ""),
                })
            elif result.get("verified"):
                verified_count += 1
            else:
                unverified_refs.append({
                    "index": ref.get("index"),
                    "raw_text": ref.get("raw_text", "")[:150],
                    "reason": result.get("verification_detail", "未找到"),
                    "suspicious_indicators": result.get("suspicious_indicators", []),
                })
                if result.get("suspicious_indicators"):
                    suspicious_refs.append({
                        "index": ref.get("index"),
                        "raw_text": ref.get("raw_text", "")[:150],
                        "indicators": result.get("suspicious_indicators", []),
                        "detail": result.get("verification_detail", ""),
                    })

        verification_rate = verified_count / max(len(refs_to_verify), 1)

        fake_ref_analysis = self._analyze_fake_references(
            references, verification_results, suspicious_refs, topic_mismatch_refs
        )

        recency_analysis = self._analyze_recency(references)

        self_citation_analysis = self._detect_self_citations(references, thesis_content)

        citation_quality = self._assess_citation_quality(verification_results, references)

        reference_relevance = self._assess_reference_relevance(references, thesis_content)

        novelty_score = self._compute_novelty_score(
            verification_rate=verification_rate,
            recency_analysis=recency_analysis,
            self_citation_analysis=self_citation_analysis,
            citation_quality=citation_quality,
            n_claimed_innovations=len(claimed_innovations),
            fake_ref_analysis=fake_ref_analysis,
            reference_relevance=reference_relevance,
        )

        innovation_verification = self._verify_innovations_against_citations(
            claimed_innovations, verification_results
        )

        verified_details = []
        for r in verification_results:
            if r.get("verified") and r.get("paper_info"):
                info = r["paper_info"]
                verified_details.append({
                    "index": r.get("reference_index"),
                    "title": info.get("title", ""),
                    "year": info.get("year"),
                    "citation_count": info.get("citation_count", 0),
                    "venue": info.get("venue", ""),
                    "authors": info.get("authors", [])[:3],
                    "source": r.get("source", ""),
                })

        result = {
            "novelty_score": novelty_score["overall"],
            "novelty_grade": novelty_score["grade"],
            "novelty_breakdown": novelty_score["breakdown"],
            "reference_statistics": {
                "total_references": len(references),
                "verified_references": verified_count,
                "verification_rate": round(verification_rate, 3),
                "references_checked": len(refs_to_verify),
                "unverified_count": len(unverified_refs),
                "suspicious_count": len(suspicious_refs),
            },
            "fake_reference_analysis": fake_ref_analysis,
            "unverified_references": unverified_refs[:15],
            "suspicious_references": suspicious_refs[:10],
            "topic_mismatch_references": topic_mismatch_refs[:10],
            "verified_reference_details": verified_details[:15],
            "recency_analysis": recency_analysis,
            "self_citation_analysis": self_citation_analysis,
            "citation_quality": citation_quality,
            "reference_relevance": reference_relevance,
            "claimed_innovations": claimed_innovations,
            "innovation_verification": innovation_verification,
            "verification_details": verification_results[:10],
        }

        logger.info(
            f"新颖度验证完成: 评分{result['novelty_score']}, "
            f"验证率{verification_rate:.1%}, "
            f"可疑引用{len(suspicious_refs)}条, "
            f"新颖度等级{result['novelty_grade']}"
        )

        return result

    def _analyze_fake_references(
        self,
        references: List[Dict],
        verification_results: List[Dict],
        suspicious_refs: List[Dict],
        topic_mismatch_refs: List[Dict] = None,
    ) -> Dict:
        """深度分析虚假引用"""
        total = len(verification_results)
        if total == 0:
            return {
                "risk_level": "unknown",
                "fake_probability": 0,
                "assessment": "无参考文献可供分析",
                "recommendations": [],
            }

        if topic_mismatch_refs is None:
            topic_mismatch_refs = []

        unverified = [r for r in verification_results if not r.get("verified") and not r.get("topic_mismatch")]
        topic_mismatched = [r for r in verification_results if r.get("topic_mismatch")]
        unverified_rate = len(unverified) / total
        topic_mismatch_rate = len(topic_mismatched) / total

        high_suspicious = []
        for sr in suspicious_refs:
            if len(sr.get("indicators", [])) >= 2:
                high_suspicious.append(sr)

        no_author_no_year = sum(
            1 for r in references
            if not r.get("authors") and not r.get("year")
        )

        fake_probability = 0
        risk_factors = []

        if topic_mismatched:
            fake_probability += min(len(topic_mismatched) * 20, 50)
            if len(topic_mismatched) == 1:
                risk_factors.append(f"1条引用与论文主题严重不匹配，可能是虚假引用或错误引用")
            else:
                risk_factors.append(f"{len(topic_mismatched)}条引用与论文主题严重不匹配，极可能包含虚假引用")

        if unverified_rate > 0.5:
            fake_probability += 40
            risk_factors.append(f"超过半数引用({unverified_rate:.0%})无法验证")
        elif unverified_rate > 0.3:
            fake_probability += 20
            risk_factors.append(f"较多引用({unverified_rate:.0%})无法验证")

        if high_suspicious:
            fake_probability += min(len(high_suspicious) * 10, 30)
            risk_factors.append(f"{len(high_suspicious)}条引用存在多个可疑特征")

        if no_author_no_year > 0:
            fake_probability += min(no_author_no_year * 5, 15)
            risk_factors.append(f"{no_author_no_year}条引用缺少作者和年份")

        all_raw_texts = [r.get("raw_text", "") for r in references]
        similar_pairs = []
        for i in range(len(all_raw_texts)):
            for j in range(i + 1, len(all_raw_texts)):
                if all_raw_texts[i] and all_raw_texts[j]:
                    sim = self._text_similarity(all_raw_texts[i], all_raw_texts[j])
                    if sim > 0.7:
                        similar_pairs.append((i + 1, j + 1, round(sim, 2)))

        if similar_pairs:
            fake_probability += min(len(similar_pairs) * 5, 15)
            risk_factors.append(f"发现{len(similar_pairs)}对高度相似的引用")

        fake_probability = min(100, fake_probability)

        if fake_probability >= 50:
            risk_level = "high"
            assessment = "⚠️ 引用真实性风险高：存在大量无法验证或可疑的参考文献，可能包含虚假引用"
        elif fake_probability >= 25:
            risk_level = "medium"
            assessment = "⚡ 引用真实性风险中等：部分参考文献无法验证或与主题不匹配，建议人工核查"
        elif fake_probability >= 10:
            risk_level = "low"
            assessment = "✅ 引用真实性风险较低：少量参考文献无法验证，属正常情况"
        else:
            risk_level = "minimal"
            assessment = "✅ 引用真实性风险极低：参考文献均可验证"

        if topic_mismatched:
            assessment = f"🚨 发现{len(topic_mismatched)}条引用与论文主题严重不匹配，极可能为虚假引用或AI编造引用！"

        recommendations = []
        if topic_mismatched:
            mismatch_indices = [str(r.get("reference_index", r.get("index", "?"))) for r in topic_mismatched]
            recommendations.append(f"⚠️ 第{', '.join(mismatch_indices)}条引用与论文主题严重不匹配，强烈建议人工核查，可能是虚假引用或AI编造的引用")
            for tm in topic_mismatch_refs[:3]:
                found_title = tm.get("found_title", "")
                if found_title:
                    recommendations.append(f"引用[{tm.get('index')}]实际对应的论文为「{found_title[:80]}」，与论文主题无关")
        if unverified_rate > 0.3:
            recommendations.append("建议人工核查所有未验证的参考文献，确认其真实性")
        if high_suspicious:
            recommendations.append(f"重点关注第{', '.join([str(s['index']) for s in high_suspicious])}条引用，这些引用存在多个可疑特征")
        if similar_pairs:
            recommendations.append("发现高度相似的引用对，可能存在重复引用或复制错误")
        if no_author_no_year > 0:
            recommendations.append("部分引用缺少基本信息（作者/年份），建议补充完整引用信息")

        return {
            "risk_level": risk_level,
            "fake_probability": round(fake_probability, 1),
            "assessment": assessment,
            "risk_factors": risk_factors,
            "high_suspicious_count": len(high_suspicious),
            "topic_mismatch_count": len(topic_mismatched),
            "similar_pairs": similar_pairs[:5],
            "recommendations": recommendations,
        }

    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        if not text1 or not text2:
            return 0.0
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _assess_reference_relevance(self, references: List[Dict], thesis_content: str) -> Dict:
        """评估参考文献与论文内容的相关性"""
        if not references or not thesis_content:
            return {"relevance_score": 50, "assessment": "无法评估"}

        thesis_keywords = self._extract_keywords(thesis_content[:5000])

        relevant_count = 0
        relevance_scores = []

        for ref in references:
            ref_text = ref.get("raw_text", "").lower()
            ref_keywords = self._extract_keywords(ref_text)

            if not ref_keywords:
                continue

            overlap = thesis_keywords & ref_keywords
            if overlap:
                score = len(overlap) / max(len(ref_keywords), 1)
                relevance_scores.append(score)
                if score > 0.1:
                    relevant_count += 1
            else:
                relevance_scores.append(0)

        if not relevance_scores:
            return {"relevance_score": 50, "assessment": "无法评估相关性"}

        avg_relevance = sum(relevance_scores) / len(relevance_scores)
        relevant_ratio = relevant_count / max(len(references), 1)

        relevance_score = min(100, (avg_relevance * 60 + relevant_ratio * 40) * 100)

        if relevance_score >= 70:
            assessment = "参考文献与论文主题高度相关"
        elif relevance_score >= 50:
            assessment = "参考文献与论文主题基本相关"
        elif relevance_score >= 30:
            assessment = "部分参考文献与论文主题相关性较弱"
        else:
            assessment = "参考文献与论文主题相关性差，可能存在无关引用"

        return {
            "relevance_score": round(relevance_score, 1),
            "avg_relevance": round(avg_relevance, 3),
            "relevant_ratio": round(relevant_ratio, 3),
            "assessment": assessment,
        }

    def _extract_keywords(self, text: str) -> set:
        """从文本中提取关键词"""
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'shall', 'can', 'this', 'that',
            'these', 'those', 'it', 'its', 'not', 'no', 'as', 'if', 'than',
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
            '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
            '看', '好', '自己', '这', '他', '她', '它', '们', '那', '些', '什么',
            '如何', '怎么', '为什么', '因为', '所以', '但是', '然而', '虽然', '如果',
        }

        words = re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,4}', text.lower())
        return set(w for w in words if w not in stopwords)

    def _extract_claimed_innovations(self, content: str) -> List[str]:
        innovations = []

        innovation_keywords = [
            r'本文的主要创新点',
            r'本文的创新之处',
            r'主要贡献',
            r'创新性贡献',
            r'本文提出了',
            r'首次提出',
            r'首次将',
            r'创新性地',
            r'本研究的创新',
            r'novel',
            r'innovative',
            r'contribution',
            r'for the first time',
        ]

        for keyword in innovation_keywords:
            pattern = re.compile(
                rf'{keyword}[^。？！\n]{{10,200}}[。？！]',
                re.IGNORECASE,
            )
            matches = pattern.findall(content)
            innovations.extend(matches[:3])

        if not innovations:
            abstract_match = re.search(
                r'(?:摘要|Abstract|ABSTRACT)\s*[:：]?\s*(.*?)(?=(?:关键词|Keywords|KEYWORDS|第1章|1\s+引言|1\s+绪论))',
                content,
                re.DOTALL,
            )
            if abstract_match:
                abstract = abstract_match.group(1)
                contribution_pattern = re.compile(
                    r'(?:提出|设计|实现|构建|开发)[^。？！]{{10,150}}[。？！]',
                )
                innovations.extend(contribution_pattern.findall(abstract)[:3])

        return innovations[:5]

    def _analyze_recency(self, references: List[Dict]) -> Dict:
        years = []
        for ref in references:
            year = ref.get("year")
            if year:
                try:
                    y = int(year)
                    if 1950 <= y <= 2030:
                        years.append(y)
                except (ValueError, TypeError):
                    continue

        if not years:
            return {
                "has_year_info": False,
                "avg_year": None,
                "recency_score": 50,
                "year_distribution": {},
                "assessment": "无法获取引用年份信息",
            }

        import datetime
        current_year = datetime.datetime.now().year

        avg_year = sum(years) / len(years)
        recent_5y = sum(1 for y in years if y >= current_year - 5)
        recent_3y = sum(1 for y in years if y >= current_year - 3)
        recent_5y_ratio = recent_5y / len(years)
        recent_3y_ratio = recent_3y / len(years)

        recency_score = min(100, recent_5y_ratio * 80 + recent_3y_ratio * 40)

        decade_counts = {}
        for y in years:
            decade = (y // 10) * 10
            decade_counts[f"{decade}s"] = decade_counts.get(f"{decade}s", 0) + 1

        if recency_score >= 80:
            assessment = "引用文献非常新颖，紧跟学术前沿"
        elif recency_score >= 60:
            assessment = "引用文献较为新颖，包含较多近期研究"
        elif recency_score >= 40:
            assessment = "引用文献时效性一般，建议增加近期文献"
        else:
            assessment = "引用文献偏旧，缺乏近期研究，建议更新参考文献"

        return {
            "has_year_info": True,
            "total_with_year": len(years),
            "avg_year": round(avg_year, 1),
            "median_year": sorted(years)[len(years) // 2],
            "recent_5y_count": recent_5y,
            "recent_5y_ratio": round(recent_5y_ratio, 3),
            "recent_3y_count": recent_3y,
            "recent_3y_ratio": round(recent_3y_ratio, 3),
            "recency_score": round(recency_score, 1),
            "year_distribution": decade_counts,
            "assessment": assessment,
        }

    def _detect_self_citations(self, references: List[Dict], thesis_content: str) -> Dict:
        author_patterns = [
            re.search(r'(?:作者|Author)\s*[:：]\s*(.*?)(?=\n)', thesis_content[:3000]),
            re.search(r'(?:指导教师|导师)\s*[:：]\s*(.*?)(?=\n)', thesis_content[:3000]),
            re.search(r'(?:学生姓名|姓名)\s*[:：]\s*(.*?)(?=\n)', thesis_content[:3000]),
        ]

        thesis_authors = []
        for match in author_patterns:
            if match:
                author_text = match.group(1).strip()
                for name in re.split(r'[，、,\s]', author_text):
                    name = name.strip()
                    if len(name) >= 2:
                        thesis_authors.append(name)

        if not thesis_authors:
            return {
                "self_citation_detected": False,
                "self_citation_count": 0,
                "self_citation_ratio": 0.0,
                "assessment": "无法检测（未找到作者信息）",
                "detail": "论文中未提取到作者信息，无法进行自引检测",
            }

        self_cite_count = 0
        self_cite_details = []
        for ref in references:
            raw = ref.get("raw_text", "")
            for author in thesis_authors:
                if author in raw:
                    self_cite_count += 1
                    self_cite_details.append({
                        "index": ref.get("index"),
                        "author": author,
                        "raw_text": raw[:100],
                    })
                    break

        self_cite_ratio = self_cite_count / max(len(references), 1)

        if self_cite_ratio > 0.3:
            assessment = "自引比例过高（>30%），可能存在引用操纵"
        elif self_cite_ratio > 0.15:
            assessment = "自引比例偏高（15-30%），需关注"
        elif self_cite_count > 0:
            assessment = "存在少量自引，属正常范围"
        else:
            assessment = "未检测到自引"

        return {
            "self_citation_detected": self_cite_count > 0,
            "thesis_authors": thesis_authors,
            "self_citation_count": self_cite_count,
            "self_citation_ratio": round(self_cite_ratio, 3),
            "assessment": assessment,
            "self_cite_details": self_cite_details[:5],
        }

    def _assess_citation_quality(self, verification_results: List[Dict], references: List[Dict]) -> Dict:
        if not verification_results:
            return {"quality_score": 50, "assessment": "无验证数据", "detail": "未进行引用验证"}

        verified = [r for r in verification_results if r.get("verified")]
        citation_counts = [
            r.get("paper_info", {}).get("citation_count", 0)
            for r in verified
            if r.get("paper_info", {}).get("citation_count") is not None
        ]

        venues = [
            r.get("paper_info", {}).get("venue", "")
            for r in verified
            if r.get("paper_info", {}).get("venue")
        ]

        avg_citations = sum(citation_counts) / max(len(citation_counts), 1) if citation_counts else 0
        venue_coverage = len(venues) / max(len(verified), 1) if verified else 0

        high_cite_ratio = sum(1 for c in citation_counts if c >= 50) / max(len(citation_counts), 1) if citation_counts else 0
        zero_cite_ratio = sum(1 for c in citation_counts if c == 0) / max(len(citation_counts), 1) if citation_counts else 0

        quality_score = min(100, high_cite_ratio * 60 + venue_coverage * 40)

        has_journal = any(v for v in venues if any(kw in v.lower() for kw in ['journal', 'ieee', 'acm', 'springer', 'elsevier', '学报', '期刊']))
        has_conference = any(v for v in venues if any(kw in v.lower() for kw in ['conference', 'proceedings', 'symposium', '会议']))

        source_diversity = []
        if has_journal:
            source_diversity.append("期刊论文")
        if has_conference:
            source_diversity.append("会议论文")
        if len(verified) > len(venues):
            source_diversity.append("其他来源")

        if avg_citations >= 100:
            authority = "引用文献权威性高，多为高影响力论文"
        elif avg_citations >= 30:
            authority = "引用文献权威性中等，包含一定数量的高影响力论文"
        elif avg_citations >= 5:
            authority = "引用文献权威性偏低，高影响力论文较少"
        else:
            authority = "引用文献权威性低，多为低被引或零被引论文"

        cn_refs = sum(1 for r in references if r.get("raw_text") and re.search(r'[\u4e00-\u9fff]{5,}', r.get("raw_text", "")))
        en_refs = len(references) - cn_refs
        lang_balance = ""
        if cn_refs > 0 and en_refs > 0:
            lang_balance = f"中英文文献比例: 中文{cn_refs}篇, 英文{en_refs}篇"
        elif cn_refs > 0:
            lang_balance = f"仅引用中文文献({cn_refs}篇)，建议增加英文文献"
        elif en_refs > 0:
            lang_balance = f"仅引用英文文献({en_refs}篇)，建议适当增加中文文献"

        detail_parts = []
        detail_parts.append(authority)
        if source_diversity:
            detail_parts.append(f"文献类型: {', '.join(source_diversity)}")
        if lang_balance:
            detail_parts.append(lang_balance)
        if zero_cite_ratio > 0.3:
            detail_parts.append(f"注意: {zero_cite_ratio:.0%}的已验证文献零被引，可能引用了过新或质量较低的论文")

        return {
            "quality_score": round(quality_score, 1),
            "avg_citation_count": round(avg_citations, 1),
            "high_citation_ratio": round(high_cite_ratio, 3),
            "zero_citation_ratio": round(zero_cite_ratio, 3),
            "venue_coverage": round(venue_coverage, 3),
            "authority_assessment": authority,
            "source_diversity": source_diversity,
            "language_balance": lang_balance,
            "detail": "; ".join(detail_parts),
        }

    def _compute_novelty_score(
        self,
        verification_rate: float,
        recency_analysis: Dict,
        self_citation_analysis: Dict,
        citation_quality: Dict,
        n_claimed_innovations: int,
        fake_ref_analysis: Dict = None,
        reference_relevance: Dict = None,
    ) -> Dict:
        verification_component = verification_rate * 100

        recency_component = recency_analysis.get("recency_score", 50)

        self_cite_penalty = min(self_citation_analysis.get("self_citation_ratio", 0) * 200, 30)

        quality_component = citation_quality.get("quality_score", 50)

        innovation_bonus = min(n_claimed_innovations * 5, 15)

        fake_penalty = 0
        if fake_ref_analysis:
            fake_prob = fake_ref_analysis.get("fake_probability", 0)
            topic_mismatch_count = fake_ref_analysis.get("topic_mismatch_count", 0)
            if topic_mismatch_count > 0:
                fake_penalty += topic_mismatch_count * 15
            if fake_prob >= 50:
                fake_penalty += fake_prob * 0.3
            elif fake_prob >= 25:
                fake_penalty += fake_prob * 0.15
            else:
                fake_penalty += fake_prob * 0.05

        relevance_bonus = 0
        if reference_relevance:
            rel_score = reference_relevance.get("relevance_score", 50)
            if rel_score >= 70:
                relevance_bonus = 5
            elif rel_score >= 50:
                relevance_bonus = 2

        overall = (
            verification_component * 0.2
            + recency_component * 0.25
            + quality_component * 0.25
            + innovation_bonus
            + relevance_bonus
            - self_cite_penalty
            - fake_penalty
        )
        overall = max(0, min(100, overall))

        if overall >= 85:
            grade = "优秀"
        elif overall >= 75:
            grade = "良好"
        elif overall >= 65:
            grade = "中等"
        elif overall >= 55:
            grade = "及格"
        else:
            grade = "不及格"

        return {
            "overall": round(overall, 1),
            "grade": grade,
            "breakdown": {
                "reference_verifiability": round(verification_component, 1),
                "recency": round(recency_component, 1),
                "citation_quality": round(quality_component, 1),
                "innovation_bonus": round(innovation_bonus, 1),
                "self_citation_penalty": round(self_cite_penalty, 1),
                "fake_reference_penalty": round(fake_penalty, 1),
                "relevance_bonus": round(relevance_bonus, 1),
            },
        }

    def _verify_innovations_against_citations(
        self,
        claimed_innovations: List[str],
        verification_results: List[Dict],
    ) -> List[Dict]:
        if not claimed_innovations:
            return []

        verified_papers = [
            r.get("paper_info", {})
            for r in verification_results
            if r.get("verified") and r.get("paper_info")
        ]

        innovation_verifications = []
        for innovation in claimed_innovations:
            innovation_keywords = set(innovation.lower().split())

            related_papers = []
            for paper in verified_papers[:10]:
                title = paper.get("title", "").lower()
                abstract = paper.get("abstract", "").lower()
                search_text = title + " " + abstract

                title_words = set(title.split())
                overlap = innovation_keywords & title_words
                if len(overlap) >= 2:
                    related_papers.append({
                        "title": paper.get("title", ""),
                        "year": paper.get("year"),
                        "citation_count": paper.get("citation_count", 0),
                        "overlap_keywords": list(overlap),
                    })

            if related_papers:
                is_novel = all(
                    p.get("citation_count", 0) < 500 for p in related_papers
                )
                verification = "likely_novel" if is_novel else "possibly_incremental"
            else:
                verification = "no_prior_art_found"

            innovation_verifications.append({
                "claimed_innovation": innovation[:200],
                "verification_status": verification,
                "related_prior_works": related_papers[:3],
                "n_related_works": len(related_papers),
            })

        return innovation_verifications

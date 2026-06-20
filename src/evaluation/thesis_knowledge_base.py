"""
论文本地知识库 - 结构化+语义双索引

解决三大核心问题：
1. 表格/公式/图片无法识别 → 通过pdfplumber/python-docx表格提取 + 视觉LLM分析，构建完整知识图谱
2. 评价集中于文字笔误 → 结构化理解论文研究思路，评估时聚焦学术实质
3. 内容截断导致识别错误 → 按需检索相关段落，避免截断丢失

架构：
- 结构化索引：按章节/段落组织，保留上下文关系
- 语义索引：向量检索，支持模糊/概念性查询
- 视觉索引：表格/公式/图片的结构化描述

支持文件格式：PDF (.pdf)、Word (.docx/.doc)

使用方式：
    from src.evaluation.thesis_knowledge_base import ThesisKnowledgeBase

    kb = ThesisKnowledgeBase()
    kb.build_from_file(file_path)
    context = kb.get_context_for_query("论文使用了什么方法求解波动方程？")
"""

import hashlib
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ThesisKnowledgeBase:

    def __init__(self):
        self.structured_index = {}
        self.semantic_index = None
        self.visual_index = {}
        self.chunks = []
        self._embedding_client = None
        self._ai_config = None
        self._chroma_collection = None
        self._file_type = None

    def build_from_file(self, file_path: str, content: str = "", skip_visual: bool = False, use_cache: bool = True) -> Dict:
        start_time = time.time()
        file_ext = os.path.splitext(file_path)[1].lower() if file_path else ''
        self._file_type = file_ext

        if use_cache and self.load_from_local(file_path):
            elapsed = time.time() - start_time
            stats = self.get_stats()
            stats["build_time_seconds"] = round(elapsed, 1)
            stats["from_cache"] = True
            logger.info(f"知识库从本地缓存加载完成，耗时{elapsed:.1f}秒")
            return stats

        logger.info(f"开始构建知识库: {file_path} (类型: {file_ext}, skip_visual={skip_visual})")

        self.structured_index = self._build_structured_index(file_path, content)
        logger.info("结构化索引构建完成")

        if skip_visual:
            self.visual_index = {"tables": [], "figures": [], "formulas": [], "total_pages_analyzed": 0}
            logger.info("视觉索引已跳过（skip_visual=True）")
        else:
            self.visual_index = self._build_visual_index(file_path)
            logger.info("视觉索引构建完成")

        self.chunks = self._create_chunks()
        logger.info(f"分块完成，共{len(self.chunks)}个块")

        if skip_visual:
            logger.info("语义索引已跳过（skip_visual=True）")
            self.semantic_index = None
        else:
            try:
                self._build_semantic_index()
                logger.info("语义索引构建完成")
            except Exception as e:
                logger.warning(f"语义索引构建失败（不影响主流程）: {str(e)}")
                self.semantic_index = None

        try:
            self.save_to_local(file_path)
            logger.info("知识库已自动保存到本地")
        except Exception as e:
            logger.warning(f"知识库本地保存失败（不影响主流程）: {str(e)}")

        elapsed = time.time() - start_time
        stats = self.get_stats()
        stats["build_time_seconds"] = round(elapsed, 1)
        stats["from_cache"] = False
        logger.info(f"知识库构建完成，耗时{elapsed:.1f}秒")
        return stats

    def build_from_pdf(self, file_path: str, content: str = "", skip_visual: bool = False, use_cache: bool = True) -> Dict:
        return self.build_from_file(file_path, content, skip_visual=skip_visual, use_cache=use_cache)

    def _is_word_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower() if file_path else ''
        return ext in ['.docx', '.doc']

    def _is_pdf_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower() if file_path else ''
        return ext == '.pdf'

    def _build_structured_index(self, file_path: str, content: str) -> Dict:
        tables_data = []
        is_word = self._is_word_file(file_path)

        if is_word:
            try:
                from src.utils.word_extractor import WordExtractor
                extractor = WordExtractor()
                extracted_text, tables_data = extractor.extract(file_path)
                if not content:
                    content = extracted_text
                logger.info(f"Word表格提取完成: {len(tables_data)}个表格")
            except Exception as e:
                logger.warning(f"Word表格提取失败: {str(e)}")
        else:
            try:
                from src.utils.pdf_extractor import PDFExtractor
                extractor = PDFExtractor()
                _, tables_data = extractor.extract(file_path)
            except Exception as e:
                logger.warning(f"PDF表格提取失败: {str(e)}")

        if not content:
            if is_word:
                try:
                    from src.utils.word_extractor import extract_word_content
                    content = extract_word_content(file_path)
                except Exception as e:
                    logger.warning(f"Word文本提取失败: {str(e)}")
                    content = ""
            else:
                try:
                    from src.utils.pdf_extractor import extract_pdf_content
                    content = extract_pdf_content(file_path)
                except Exception as e:
                    logger.warning(f"PDF文本提取失败: {str(e)}")
                    content = ""

        sections = self._parse_sections(content)
        paragraphs = self._parse_paragraphs(content, sections)

        index = {
            "file_path": file_path,
            "file_type": "word" if is_word else "pdf",
            "content_length": len(content),
            "sections": sections,
            "paragraphs": paragraphs,
            "tables_structured": self._process_tables(tables_data, content),
            "figures": self._extract_figure_references(content),
            "formulas": self._extract_formula_references(content),
            "algorithms": self._extract_algorithm_references(content),
            "key_terms": self._extract_key_terms(content),
            "research_chain": self._extract_research_chain(content, sections),
        }
        return index

    def _parse_sections(self, content: str) -> List[Dict]:
        sections = []

        chapter_pattern = re.compile(r'(第[一二三四五六七八九十\d]+\s*章[^\n]*)')
        abstract_pattern = re.compile(r'(?:^|\n)\s*(摘\s*要)\s*(?:\n|：:|$)')
        abstract_en_pattern = re.compile(r'(?:^|\n)\s*(ABSTRACT)\s*(?:\n|：:|$)')
        non_chapter_patterns = [
            (re.compile(r'(?:^|\n)\s*(参\s*考\s*文\s*献)\s*(?:\n|$)'), "references"),
            (re.compile(r'(?:^|\n)\s*(致\s*谢)\s*(?:\n|$)'), "acknowledgment"),
            (re.compile(r'(?:^|\n)\s*(附\s*录)\s*(?:\n|$)'), "appendix"),
        ]

        all_raw = []
        for m in chapter_pattern.finditer(content):
            title = m.group(1).strip()
            title = re.sub(r'[\*#]+', '', title).strip()
            if not self._is_valid_chapter_title(title):
                continue
            all_raw.append({"title": title, "offset": m.start(), "raw_type": "chapter"})

        for m in abstract_pattern.finditer(content):
            all_raw.append({"title": "摘要", "offset": m.start(), "raw_type": "abstract"})

        for m in abstract_en_pattern.finditer(content):
            all_raw.append({"title": "ABSTRACT", "offset": m.start(), "raw_type": "abstract_en"})

        for pat, stype in non_chapter_patterns:
            for m in pat.finditer(content):
                all_raw.append({"title": m.group(1).strip(), "offset": m.start(), "raw_type": stype})

        all_raw.sort(key=lambda x: x["offset"])

        if not all_raw:
            chunk_size = max(len(content) // 5, 5000)
            for i in range(0, len(content), chunk_size):
                sections.append({
                    "title": f"段落{i // chunk_size + 1}",
                    "type": "auto_chunk",
                    "start_offset": i,
                    "end_offset": min(i + chunk_size, len(content)),
                    "content": content[i:min(i + chunk_size, len(content))],
                })
            return sections

        chapter_only = [m for m in all_raw if m["raw_type"] == "chapter"]
        toc_end = 0
        for i in range(len(chapter_only) - 1):
            gap = chapter_only[i + 1]["offset"] - chapter_only[i]["offset"]
            if gap < 300:
                toc_end = max(toc_end, chapter_only[i + 1]["offset"] + 200)

        def get_chapter_num(title):
            m = re.search(r'第([一二三四五六七八九十\d]+)\s*章', title)
            if m:
                num = m.group(1)
                cn_nums = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
                           '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
                           '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15'}
                return cn_nums.get(num, num)
            return None

        chapter_groups = {}
        non_chapter = []
        seen_special = set()

        for match in all_raw:
            ch_num = get_chapter_num(match["title"])
            if ch_num:
                if match["offset"] < toc_end:
                    continue
                if ch_num not in chapter_groups:
                    chapter_groups[ch_num] = []
                chapter_groups[ch_num].append(match)
            else:
                stype = match["raw_type"]
                if stype in seen_special:
                    continue
                seen_special.add(stype)
                non_chapter.append(match)

        deduped = list(non_chapter)
        for ch_num, matches in chapter_groups.items():
            matches.sort(key=lambda x: x["offset"])
            deduped.append(matches[0])

        deduped.sort(key=lambda x: x["offset"])

        if deduped and deduped[0]["offset"] > 200:
            sections.append({
                "title": "前言",
                "type": "preamble",
                "start_offset": 0,
                "end_offset": deduped[0]["offset"],
                "content": content[:deduped[0]["offset"]],
            })

        for i, match in enumerate(deduped):
            end_offset = deduped[i + 1]["offset"] if i + 1 < len(deduped) else len(content)
            sec_content = content[match["offset"]:end_offset]
            section_type = self._classify_section(match["title"], match["raw_type"])
            sections.append({
                "title": match["title"],
                "type": section_type,
                "start_offset": match["offset"],
                "end_offset": end_offset,
                "content": sec_content,
            })

        return sections

    def _is_valid_chapter_title(self, title: str) -> bool:
        m = re.match(r'第[一二三四五六七八九十\d]+\s*章\s*(.*)', title)
        if not m:
            return False
        rest = m.group(1).strip()
        rest = re.sub(r'[\*#]+', '', rest).strip()
        if not rest:
            return True
        if re.search(r'[，。；！？]', rest[:30]):
            return False
        if len(rest) > 60:
            return False
        return True

    def _classify_section(self, title: str, match_type: str) -> str:
        if match_type == "abstract" or match_type == "abstract_en":
            return "abstract"
        title_lower = title.lower()
        if any(kw in title_lower for kw in ["引言", "绪论", "introduction", "背景"]):
            return "introduction"
        if any(kw in title_lower for kw in ["文献", "综述", "related work", "literature"]):
            return "literature_review"
        if any(kw in title_lower for kw in ["方法", "method", "模型", "model", "算法", "algorithm", "设计", "design"]):
            return "methodology"
        if any(kw in title_lower for kw in ["实现", "implement", "系统", "system"]):
            return "implementation"
        if any(kw in title_lower for kw in ["实验", "experiment", "仿真", "simulation", "结果", "result"]):
            return "experiment"
        if any(kw in title_lower for kw in ["结论", "conclusion", "总结", "summary", "展望"]):
            return "conclusion"
        if any(kw in title_lower for kw in ["参考", "reference"]):
            return "references"
        if any(kw in title_lower for kw in ["致谢", "acknowledgment"]):
            return "acknowledgment"
        if any(kw in title_lower for kw in ["附录", "appendix"]):
            return "appendix"
        return "other"

    def _parse_paragraphs(self, content: str, sections: List[Dict]) -> List[Dict]:
        paragraphs = []
        para_pattern = re.compile(r'\n\s*\n')
        splits = para_pattern.split(content)

        offset = 0
        for i, para_text in enumerate(splits):
            para_text = para_text.strip()
            if not para_text:
                offset += 2
                continue

            actual_offset = content.find(para_text, offset)
            if actual_offset == -1:
                actual_offset = offset

            containing_section = "unknown"
            for sec in sections:
                if sec.get("start_offset", -1) <= actual_offset < sec.get("end_offset", len(content) + 1):
                    containing_section = sec["title"]
                    break

            paragraphs.append({
                "index": i,
                "text": para_text,
                "length": len(para_text),
                "offset": actual_offset,
                "section": containing_section,
            })
            offset = actual_offset + len(para_text)

        return paragraphs

    def _process_tables(self, tables_data: List[Dict], content: str) -> List[Dict]:
        processed = []
        for i, table in enumerate(tables_data):
            data = table.get("data", [])
            page = table.get("page", 0)

            headers = []
            rows = []
            if data:
                headers = [str(cell).strip() for cell in data[0]] if data[0] else []
                for row in data[1:]:
                    rows.append([str(cell).strip() for cell in row])

            caption = ""
            table_number = ""
            for m in re.finditer(r'表\s*(\d+[\.\-]\d+|\d+)\s*([^\n]*)', content):
                tbl_num = m.group(1)
                tbl_caption = m.group(2).strip()
                if not table_number:
                    table_number = f"表{tbl_num}"
                    caption = tbl_caption

            text_repr = ""
            if headers:
                text_repr += " | ".join(headers) + "\n"
                text_repr += "-" * (len(text_repr) + 10) + "\n"
            for row in rows[:10]:
                text_repr += " | ".join(row) + "\n"
            if len(rows) > 10:
                text_repr += f"...（共{len(rows)}行，仅展示前10行）\n"

            processed.append({
                "index": i,
                "table_number": table_number or f"表(第{page}页)",
                "caption": caption,
                "page": page,
                "headers": headers,
                "row_count": len(rows),
                "text_representation": text_repr,
                "summary": f"{table_number or '表'}: {caption or '无标题'}，{len(rows)}行数据，列头为{headers[:5] if headers else '未知'}"
            })

        return processed

    def _extract_figure_references(self, content: str) -> List[Dict]:
        figures = []
        seen = set()
        for m in re.finditer(r'图\s*(\d+[\.\-]\d+|\d+)\s*([^\n]{0,80})', content):
            fig_num = m.group(1)
            fig_caption = m.group(2).strip()
            key = fig_num
            if key not in seen:
                seen.add(key)
                figures.append({
                    "number": fig_num,
                    "label": f"图{fig_num}",
                    "caption": fig_caption,
                    "offset": m.start(),
                })
        return figures

    def _extract_formula_references(self, content: str) -> List[Dict]:
        formulas = []
        formula_patterns = [
            r'(?:公式|式)\s*(\d+[\.\-]\d+|\d+)',
            r'\(([一二三四五六七八九十\d]+)\)\s*[\u4e00-\u9fff]',  # (1) 后跟中文，可能是公式编号
        ]
        seen = set()
        for pat in formula_patterns:
            for m in re.finditer(pat, content):
                fnum = m.group(1)
                if fnum not in seen:
                    seen.add(fnum)
                    context_start = max(0, m.start() - 50)
                    context_end = min(len(content), m.end() + 100)
                    context = content[context_start:context_end].replace('\n', ' ')
                    formulas.append({
                        "number": fnum,
                        "label": f"公式{fnum}",
                        "context": context,
                        "offset": m.start(),
                    })
        return formulas

    def _extract_algorithm_references(self, content: str) -> List[Dict]:
        algorithms = []
        seen = set()
        for m in re.finditer(r'算法\s*(\d+[\.\-]\d+|\d+)', content):
            algo_num = m.group(1)
            if algo_num not in seen:
                seen.add(algo_num)
                context_start = max(0, m.start() - 20)
                context_end = min(len(content), m.end() + 200)
                context = content[context_start:context_end].replace('\n', ' ')
                algorithms.append({
                    "number": algo_num,
                    "label": f"算法{algo_num}",
                    "context": context,
                    "offset": m.start(),
                })
        return algorithms

    def _extract_key_terms(self, content: str) -> List[Dict]:
        patterns = [
            r'(?:应用|采用|使用|基于|利用|提出|设计|实现|构建|开发|研究|分析|求解|预测|仿真|模拟)[，,]?\s*([^\s，,。；;]{2,30}(?:方程|模型|方法|算法|网络|框架|系统|技术|理论|策略|方案|体系|平台|装置|设备|结构|机理|机制|原理|准则|标准|规范))',
            r'(?:物理信息神经网络|PINN|深度学习|机器学习|神经网络|卷积网络|循环网络|Transformer|注意力机制|随机森林|支持向量机|贝叶斯|遗传算法|强化学习|迁移学习|联邦学习|知识蒸馏|图神经网络|生成对抗|自编码器|LSTM|GRU|CNN|RNN|GAN|VAE|扩散模型)',
            r'(?:Navier-Stokes|N-S|波动方程|热传导方程|拉普拉斯方程|泊松方程|欧拉方程|麦克斯韦方程|薛定谔方程|扩散方程|对流方程|输运方程)',
            r'(?:有限元|有限差分|有限体积|谱方法|边界元|无网格|格子Boltzmann|SPH|DEM|CFD|DNS|LES|RANS)',
        ]

        terms = {}
        for pat in patterns:
            for m in re.finditer(pat, content):
                term = m.group(0) if m.lastindex is None else m.group(m.lastindex)
                if len(term) >= 2:
                    if term not in terms:
                        terms[term] = {"count": 0, "first_offset": m.start()}
                    terms[term]["count"] += 1

        sorted_terms = sorted(terms.items(), key=lambda x: x[1]["count"], reverse=True)
        return [
            {"term": t, "count": info["count"], "first_offset": info["first_offset"]}
            for t, info in sorted_terms[:50]
        ]

    def _extract_research_chain(self, content: str, sections: List[Dict]) -> Dict:
        chain = {
            "problem": "",
            "method": "",
            "experiment": "",
            "conclusion": "",
            "logic_flow": [],
        }

        def _first_sentence(text, max_len=120):
            text = text.strip()
            for end_char in ['。', '！', '？', '.', '!', '?']:
                idx = text.find(end_char)
                if 10 < idx < max_len:
                    return text[:idx + 1]
            return text[:max_len] + "..." if len(text) > max_len else text

        intro_sections = [s for s in sections if s.get("type") == "introduction"]
        if intro_sections:
            intro_content = intro_sections[0].get("content", "")
            problem_patterns = [
                r'(?:研究|解决|探讨|分析|针对)[了]?\s*([^\n，。；;]{5,80}(?:问题|挑战|难点|需求|目标))',
                r'(?:本文|本论文|本研究)[^\n]{0,20}(?:研究|探讨|分析|针对)[了]?\s*([^\n，。；;]{5,80})',
                r'(?:研究背景|研究意义)[：:]\s*([^\n]{10,100})',
            ]
            for pat in problem_patterns:
                matches = re.findall(pat, intro_content[:5000])
                if matches:
                    chain["problem"] = matches[0]
                    break
            if not chain["problem"]:
                body = intro_content.lstrip()
                body = re.sub(r'^[^\n]*\n', '', body).strip()
                if body:
                    chain["problem"] = _first_sentence(body)

        method_sections = [s for s in sections if s.get("type") == "methodology"]
        if method_sections:
            all_method_content = " ".join(s.get("content", "")[:2000] for s in method_sections)
            method_patterns = [
                r'(?:提出|设计|采用|基于|利用|构建|应用)[了]?\s*([^\n，。；;]{5,80}(?:方法|模型|算法|框架|策略|方案|网络))',
                r'(?:本文|本论文)[^\n]{0,20}(?:提出|设计|采用|基于|构建)[了]?\s*([^\n，。；;]{5,80})',
            ]
            for pat in method_patterns:
                matches = re.findall(pat, all_method_content)
                if matches:
                    chain["method"] = matches[0]
                    break
            if not chain["method"]:
                body = method_sections[0].get("content", "").lstrip()
                body = re.sub(r'^[^\n]*\n', '', body).strip()
                if body:
                    chain["method"] = _first_sentence(body)

        exp_sections = [s for s in sections if s.get("type") == "experiment"]
        if not exp_sections:
            exp_sections = [s for s in sections if s.get("type") == "methodology"]
        if exp_sections:
            exp_content = exp_sections[0].get("content", "")[:5000]
            exp_patterns = [
                r'(?:验证|测试|评估|对比|实验)[了]?\s*([^\n，。；;]{5,80})',
                r'(?:实验|测试|验证)[结果分析]*[：:]\s*([^\n]{10,100})',
            ]
            for pat in exp_patterns:
                matches = re.findall(pat, exp_content)
                if matches:
                    chain["experiment"] = matches[0]
                    break
            if not chain["experiment"]:
                body = exp_sections[0].get("content", "").lstrip()
                body = re.sub(r'^[^\n]*\n', '', body).strip()
                if body:
                    chain["experiment"] = _first_sentence(body)

        conc_sections = [s for s in sections if s.get("type") == "conclusion"]
        if conc_sections:
            conc_content = conc_sections[0].get("content", "")[:5000]
            conc_patterns = [
                r'(?:表明|证明|显示|得出|发现)[了]?\s*([^\n，。；;]{5,80})',
                r'(?:主要结论|结论)[：:]\s*([^\n]{10,100})',
            ]
            for pat in conc_patterns:
                matches = re.findall(pat, conc_content)
                if matches:
                    chain["conclusion"] = matches[0]
                    break
            if not chain["conclusion"]:
                body = conc_sections[0].get("content", "").lstrip()
                body = re.sub(r'^[^\n]*\n', '', body).strip()
                if body:
                    chain["conclusion"] = _first_sentence(body)

        for sec in sections:
            sec_type = sec.get("type", "")
            if sec_type in ("introduction", "methodology", "experiment", "conclusion"):
                content_text = sec.get("content", "")
                summary = content_text[:200].replace('\n', ' ').strip()
                summary = re.sub(r'\s+', ' ', summary)
                chain["logic_flow"].append({
                    "section": sec["title"],
                    "type": sec_type,
                    "summary": summary,
                })

        return chain

    def _build_visual_index(self, file_path: str) -> Dict:
        if self._is_word_file(file_path):
            return self._build_visual_index_word(file_path)
        else:
            return self._build_visual_index_pdf(file_path)

    def _build_visual_index_word(self, file_path: str) -> Dict:
        visual_tables = []
        visual_figures = []
        visual_formulas = []

        try:
            from src.utils.word_extractor import WordExtractor
            extractor = WordExtractor()
            structured = extractor.extract_with_structure(file_path)

            for table_data in structured.get("tables", []):
                data = table_data.get("data", [])
                headers = [str(cell).strip() for cell in data[0]] if data else []
                rows = [[str(cell).strip() for cell in row] for row in data[1:]] if len(data) > 1 else []

                text_repr = ""
                if headers:
                    text_repr += " | ".join(headers) + "\n"
                    text_repr += "-" * (len(text_repr) + 10) + "\n"
                for row in rows[:10]:
                    text_repr += " | ".join(row) + "\n"
                if len(rows) > 10:
                    text_repr += f"...（共{len(rows)}行，仅展示前10行）\n"

                visual_tables.append({
                    "table_number": f"表{table_data.get('index', 0) + 1}",
                    "caption": "",
                    "page": 0,
                    "description": f"Word文档中的第{table_data.get('index', 0) + 1}个表格，{len(rows)}行{len(headers)}列",
                    "text_representation": text_repr,
                })

            headings = structured.get("headings", [])
            for h in headings:
                text = h.get("text", "")
                level = h.get("level", 1)
                if any(kw in text for kw in ["图", "图例", "Fig", "Figure"]):
                    visual_figures.append({
                        "figure_number": text[:20],
                        "caption": text,
                        "type": "word_heading_reference",
                        "page": 0,
                        "description": f"Word文档中层级{level}标题引用的图",
                        "key_findings": "",
                    })

        except Exception as e:
            logger.warning(f"Word视觉索引构建失败: {str(e)}")

        try:
            from docx import Document
            doc = Document(file_path)
            img_count = 0
            for rel in doc.part.rels.values():
                if "image" in rel.reltype:
                    img_count += 1
            if img_count > 0:
                visual_figures.append({
                    "figure_number": f"共{img_count}张图片",
                    "caption": f"Word文档中嵌入的{img_count}张图片",
                    "type": "embedded_image",
                    "page": 0,
                    "description": f"Word文档中包含{img_count}张嵌入图片（python-docx无法直接提取图片内容，建议转为PDF后使用视觉分析）",
                    "key_findings": "",
                })
        except Exception as e:
            logger.warning(f"Word图片统计失败: {str(e)}")

        return {
            "tables": visual_tables,
            "figures": visual_figures,
            "formulas": visual_formulas,
            "total_pages_analyzed": 0,
        }

    def _build_visual_index_pdf(self, file_path: str) -> Dict:
        try:
            from src.evaluation.thesis_vision_analyzer import ThesisVisionAnalyzer
            analyzer = ThesisVisionAnalyzer()
            analysis = analyzer.analyze_key_pages(file_path)

            visual_tables = []
            for t in analysis.get("tables_found", []):
                headers = t.get("headers", [])
                rows = t.get("rows", [])
                text_repr = ""
                if headers:
                    text_repr += " | ".join(str(h) for h in headers) + "\n"
                for row in rows[:8]:
                    text_repr += " | ".join(str(v) for v in row) + "\n"
                if len(rows) > 8:
                    text_repr += f"...（共{len(rows)}行）\n"

                visual_tables.append({
                    "table_number": t.get("table_number", "未知"),
                    "caption": t.get("caption", ""),
                    "page": t.get("page_number", 0),
                    "description": t.get("description", ""),
                    "text_representation": text_repr,
                })

            visual_figures = []
            for fig in analysis.get("figures_found", []):
                visual_figures.append({
                    "figure_number": fig.get("figure_number", "未知"),
                    "caption": fig.get("caption", ""),
                    "type": fig.get("type", ""),
                    "page": fig.get("page_number", 0),
                    "description": fig.get("description", ""),
                    "key_findings": fig.get("key_findings", ""),
                })

            visual_formulas = []
            for f in analysis.get("formulas_found", []):
                visual_formulas.append({
                    "latex": f.get("latex", ""),
                    "description": f.get("description", ""),
                    "context": f.get("context", ""),
                    "page": f.get("page_number", 0),
                })

            return {
                "tables": visual_tables,
                "figures": visual_figures,
                "formulas": visual_formulas,
                "total_pages_analyzed": len(analysis.get("page_analyses", [])),
            }
        except Exception as e:
            logger.warning(f"视觉索引构建失败: {str(e)}")
            return {"tables": [], "figures": [], "formulas": [], "total_pages_analyzed": 0}

    def _create_chunks(self) -> List[Dict]:
        chunks = []

        for sec in self.structured_index.get("sections", []):
            sec_content = sec.get("content", "")
            if not sec_content:
                continue

            chunk_size = 2000
            overlap = 200

            if len(sec_content) <= chunk_size:
                chunks.append({
                    "text": sec_content,
                    "section_title": sec["title"],
                    "section_type": sec.get("type", "other"),
                    "chunk_type": "section",
                    "offset": sec.get("start_offset", 0),
                })
            else:
                start = 0
                while start < len(sec_content):
                    end = start + chunk_size
                    chunk_text = sec_content[start:end]
                    if start > 0:
                        chunk_text = "..." + chunk_text
                    if end < len(sec_content):
                        chunk_text = chunk_text + "..."

                    chunks.append({
                        "text": chunk_text,
                        "section_title": sec["title"],
                        "section_type": sec.get("type", "other"),
                        "chunk_type": "section_chunk",
                        "offset": sec.get("start_offset", 0) + start,
                    })
                    start += chunk_size - overlap

        for table in self.structured_index.get("tables_structured", []):
            text_repr = table.get("text_representation", "")
            if text_repr:
                chunks.append({
                    "text": f"[表格] {table.get('table_number', '')} {table.get('caption', '')}\n{text_repr}",
                    "section_title": "表格",
                    "section_type": "table",
                    "chunk_type": "table",
                    "offset": 0,
                })

        for fig in self.structured_index.get("figures", []):
            chunks.append({
                "text": f"[图] {fig.get('label', '')} {fig.get('caption', '')}",
                "section_title": "图片",
                "section_type": "figure",
                "chunk_type": "figure_reference",
                "offset": fig.get("offset", 0),
            })

        for formula in self.structured_index.get("formulas", []):
            chunks.append({
                "text": f"[公式] {formula.get('label', '')} 上下文: {formula.get('context', '')}",
                "section_title": "公式",
                "section_type": "formula",
                "chunk_type": "formula_reference",
                "offset": formula.get("offset", 0),
            })

        for vt in self.visual_index.get("tables", []):
            text_repr = vt.get("text_representation", "")
            if text_repr:
                chunks.append({
                    "text": f"[视觉识别表格] {vt.get('table_number', '')} {vt.get('caption', '')}（第{vt.get('page', 0)}页）\n{text_repr}\n描述: {vt.get('description', '')}",
                    "section_title": "视觉表格",
                    "section_type": "visual_table",
                    "chunk_type": "visual_table",
                    "offset": 0,
                })

        for vf in self.visual_index.get("figures", []):
            desc = vf.get("description", "")
            findings = vf.get("key_findings", "")
            chunks.append({
                "text": f"[视觉识别图] {vf.get('figure_number', '')} {vf.get('caption', '')}（第{vf.get('page', 0)}页）\n类型: {vf.get('type', '')}\n描述: {desc}\n关键发现: {findings}",
                "section_title": "视觉图片",
                "section_type": "visual_figure",
                "chunk_type": "visual_figure",
                "offset": 0,
            })

        for vfm in self.visual_index.get("formulas", []):
            chunks.append({
                "text": f"[视觉识别公式] 第{vfm.get('page', 0)}页\nLaTeX: {vfm.get('latex', '')}\n含义: {vfm.get('description', '')}\n作用: {vfm.get('context', '')}",
                "section_title": "视觉公式",
                "section_type": "visual_formula",
                "chunk_type": "visual_formula",
                "offset": 0,
            })

        return chunks

    def _build_semantic_index(self):
        if not self.chunks:
            return

        try:
            import chromadb
        except ImportError:
            logger.warning("chromadb未安装，跳过语义索引构建。可通过 pip install chromadb 安装")
            self.semantic_index = None
            return

        try:
            from src.config import get_ai_config
            self._ai_config = get_ai_config()
        except Exception:
            self.semantic_index = None
            return

        texts = [c["text"] for c in self.chunks]
        embeddings = self._compute_embeddings(texts)

        if embeddings is None:
            self.semantic_index = None
            return

        client = chromadb.Client()
        collection_name = f"thesis_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        self._chroma_collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        ids = [f"chunk_{i}" for i in range(len(self.chunks))]
        metas = [
            {
                "section_title": c.get("section_title", ""),
                "section_type": c.get("section_type", ""),
                "chunk_type": c.get("chunk_type", ""),
            }
            for c in self.chunks
        ]

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self._chroma_collection.add(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=texts[i:end],
                metadatas=metas[i:end],
            )

        self.semantic_index = {"total_chunks": len(self.chunks)}

    def _compute_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self._ai_config["api_key"],
                base_url=self._ai_config["base_url"]
            )

            all_embeddings = []
            batch_size = 50
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                try:
                    response = client.embeddings.create(
                        model="text-embedding-v3",
                        input=batch
                    )
                    for item in response.data:
                        all_embeddings.append(item.embedding)
                except Exception as e:
                    logger.warning(f"Embedding批次{i // batch_size}失败: {str(e)}")
                    for _ in batch:
                        all_embeddings.append([0.0] * 1024)

            return all_embeddings if len(all_embeddings) == len(texts) else None
        except Exception as e:
            logger.warning(f"Embedding计算失败: {str(e)}")
            return None

    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self._chroma_collection:
            return self._keyword_search(query, top_k)

        try:
            query_embedding = self._compute_embeddings([query])
            if not query_embedding:
                return self._keyword_search(query, top_k)

            results = self._chroma_collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            search_results = []
            for i, doc in enumerate(results["documents"][0]):
                search_results.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "relevance": 1 - results["distances"][0][i],
                })
            return search_results
        except Exception as e:
            logger.warning(f"语义搜索失败，回退到关键词搜索: {str(e)}")
            return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int = 5) -> List[Dict]:
        query_terms = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+|\d+', query.lower())
        if not query_terms:
            return []

        scored = []
        for i, chunk in enumerate(self.chunks):
            text_lower = chunk["text"].lower()
            score = 0
            for term in query_terms:
                count = text_lower.count(term)
                if count > 0:
                    score += count * (3 if len(term) >= 3 else 1)
            if score > 0:
                scored.append({
                    "text": chunk["text"],
                    "metadata": {
                        "section_title": chunk.get("section_title", ""),
                        "section_type": chunk.get("section_type", ""),
                        "chunk_type": chunk.get("chunk_type", ""),
                    },
                    "distance": 1 - min(score / 20, 0.99),
                    "relevance": min(score / 20, 0.99),
                    "score": score,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get_context_for_query(self, query: str, top_k: int = 8) -> str:
        results = self.semantic_search(query, top_k)
        if not results:
            return ""

        sections = []
        for r in results:
            meta = r.get("metadata", {})
            sec_title = meta.get("section_title", "未知")
            sec_type = meta.get("section_type", "")
            relevance = r.get("relevance", 0)
            sections.append(f"[{sec_title}({sec_type}) 相关度:{relevance:.2f}]\n{r['text']}\n")

        return "\n---\n".join(sections)

    def get_section_content(self, section_type: str) -> str:
        for sec in self.structured_index.get("sections", []):
            if sec.get("type") == section_type:
                return sec.get("content", "")
        return ""

    def get_all_tables_context(self) -> str:
        parts = []

        for table in self.structured_index.get("tables_structured", []):
            text_repr = table.get("text_representation", "")
            if text_repr:
                parts.append(f"### {table.get('table_number', '')} {table.get('caption', '')}\n{text_repr}")

        for vt in self.visual_index.get("tables", []):
            text_repr = vt.get("text_representation", "")
            if text_repr:
                parts.append(f"### [视觉识别] {vt.get('table_number', '')} {vt.get('caption', '')}（第{vt.get('page', 0)}页）\n{text_repr}\n描述: {vt.get('description', '')}")

        return "\n\n".join(parts) if parts else ""

    def get_all_figures_context(self) -> str:
        parts = []

        for fig in self.structured_index.get("figures", []):
            parts.append(f"- {fig.get('label', '')} {fig.get('caption', '')}")

        for vf in self.visual_index.get("figures", []):
            desc = vf.get("description", "")
            findings = vf.get("key_findings", "")
            parts.append(f"- [视觉识别] {vf.get('figure_number', '')} {vf.get('caption', '')}（第{vf.get('page', 0)}页）: {desc}" + (f" 关键发现: {findings}" if findings else ""))

        return "\n".join(parts) if parts else ""

    def get_all_formulas_context(self) -> str:
        parts = []

        for f in self.structured_index.get("formulas", []):
            parts.append(f"- {f.get('label', '')} 上下文: {f.get('context', '')}")

        for vf in self.visual_index.get("formulas", []):
            parts.append(f"- [视觉识别] 第{vf.get('page', 0)}页: {vf.get('latex', '')} ({vf.get('description', '')})")

        return "\n".join(parts) if parts else ""

    def get_research_chain_context(self) -> str:
        chain = self.structured_index.get("research_chain", {})
        if not chain:
            return ""

        parts = ["## 论文研究链条"]
        if chain.get("problem"):
            parts.append(f"**研究问题**: {chain['problem']}")
        if chain.get("method"):
            parts.append(f"**研究方法**: {chain['method']}")
        if chain.get("experiment"):
            parts.append(f"**实验验证**: {chain['experiment']}")
        if chain.get("conclusion"):
            parts.append(f"**主要结论**: {chain['conclusion']}")

        logic_flow = chain.get("logic_flow", [])
        if logic_flow:
            parts.append("\n**逻辑流程**:")
            for step in logic_flow:
                parts.append(f"  → {step.get('section', '')}({step.get('type', '')}): {step.get('summary', '')[:100]}")

        return "\n".join(parts)

    def get_full_evaluation_context(self, query: str = "") -> str:
        parts = []

        research_chain = self.get_research_chain_context()
        if research_chain:
            parts.append(research_chain)

        tables_ctx = self.get_all_tables_context()
        if tables_ctx:
            parts.append(f"\n## 论文中的表格\n{tables_ctx}")

        figures_ctx = self.get_all_figures_context()
        if figures_ctx:
            parts.append(f"\n## 论文中的图表\n{figures_ctx}")

        formulas_ctx = self.get_all_formulas_context()
        if formulas_ctx:
            parts.append(f"\n## 论文中的公式\n{formulas_ctx}")

        key_terms = self.structured_index.get("key_terms", [])
        if key_terms:
            terms_str = ", ".join([f"{t['term']}({t['count']}次)" for t in key_terms[:20]])
            parts.append(f"\n## 关键技术术语\n{terms_str}")

        if query:
            relevant = self.get_context_for_query(query, top_k=5)
            if relevant:
                parts.append(f"\n## 与查询相关的上下文\n{relevant}")

        return "\n\n".join(parts)

    def get_stats(self) -> Dict:
        return {
            "sections_count": len(self.structured_index.get("sections", [])),
            "paragraphs_count": len(self.structured_index.get("paragraphs", [])),
            "tables_count": len(self.structured_index.get("tables_structured", [])) + len(self.visual_index.get("tables", [])),
            "figures_count": len(self.structured_index.get("figures", [])) + len(self.visual_index.get("figures", [])),
            "formulas_count": len(self.structured_index.get("formulas", [])) + len(self.visual_index.get("formulas", [])),
            "key_terms_count": len(self.structured_index.get("key_terms", [])),
            "chunks_count": len(self.chunks),
            "has_semantic_index": self.semantic_index is not None,
            "visual_pages_analyzed": self.visual_index.get("total_pages_analyzed", 0),
        }

    def _get_cache_key(self, file_path: str) -> str:
        file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest() if file_path and os.path.exists(file_path) else "unknown"
        return f"kb_v3_{os.path.basename(file_path)}_{file_hash}"

    def _get_cache_dir(self) -> str:
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'knowledge_bases')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def save_to_local(self, file_path: str = None) -> str:
        fp = file_path or self.structured_index.get("file_path", "")
        if not fp:
            raise ValueError("无法确定文件路径，无法保存知识库")

        cache_key = self._get_cache_key(fp)
        cache_dir = self._get_cache_dir()
        save_path = os.path.join(cache_dir, f"{cache_key}.json")

        save_data = {
            "file_path": fp,
            "file_type": self._file_type,
            "structured_index": self.structured_index,
            "visual_index": self.visual_index,
            "chunks": self.chunks,
            "stats": self.get_stats(),
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"知识库已保存到: {save_path}")
        return save_path

    def load_from_local(self, file_path: str) -> bool:
        cache_key = self._get_cache_key(file_path)
        cache_dir = self._get_cache_dir()
        save_path = os.path.join(cache_dir, f"{cache_key}.json")

        if not os.path.exists(save_path):
            return False

        try:
            with open(save_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)

            self.structured_index = save_data.get("structured_index", {})
            self.visual_index = save_data.get("visual_index", {})
            self.chunks = save_data.get("chunks", [])
            self._file_type = save_data.get("file_type", None)
            self.semantic_index = None

            logger.info(f"知识库已从本地加载: {save_path}")
            return True
        except Exception as e:
            logger.warning(f"本地知识库加载失败: {str(e)}")
            return False

    @staticmethod
    def get_local_knowledge_bases() -> List[Dict]:
        kb_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'knowledge_bases')
        if not os.path.exists(kb_dir):
            return []

        results = []
        for fname in os.listdir(kb_dir):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(kb_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats = data.get("stats", {})
                results.append({
                    "filename": fname,
                    "filepath": fpath,
                    "file_path": data.get("file_path", ""),
                    "file_type": data.get("file_type", ""),
                    "stats": stats,
                    "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                })
            except Exception:
                pass

        return results

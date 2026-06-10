from typing import Dict, List
import base64
import json
import logging
import re

import openai

from src.config import get_ai_config

logger = logging.getLogger(__name__)


class ThesisVisionAnalyzer:

    def __init__(self):
        self.client = None
        self.ai_config = None

    def _ensure_client(self):
        if self.client is None:
            self.ai_config = get_ai_config()
            self.client = openai.OpenAI(
                api_key=self.ai_config["api_key"],
                base_url=self.ai_config["base_url"]
            )

    def _pdf_page_to_base64(self, file_path: str, page_num: int) -> str:
        try:
            import fitz
        except ImportError:
            logger.error("PyMuPDF(fitz)未安装，无法将PDF页面转为图片")
            return ""

        try:
            doc = fitz.open(file_path)
            if page_num < 1 or page_num > len(doc):
                logger.error(f"页码{page_num}超出范围，PDF共{len(doc)}页")
                doc.close()
                return ""

            page = doc[page_num - 1]
            mat = fitz.Matrix(200 / 72, 200 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            doc.close()

            b64_str = base64.b64encode(img_bytes).decode("utf-8")
            return b64_str
        except Exception as e:
            logger.error(f"PDF页面转base64失败: {str(e)}")
            return ""

    def analyze_key_pages(self, file_path: str, page_numbers: List[int] = None) -> Dict:
        if page_numbers is None:
            page_numbers = self.auto_detect_key_pages(file_path)

        if not page_numbers:
            return {
                "page_analyses": [],
                "tables_found": [],
                "figures_found": [],
                "formulas_found": []
            }

        page_analyses = []
        tables_found = []
        figures_found = []
        formulas_found = []

        for page_num in page_numbers:
            image_base64 = self._pdf_page_to_base64(file_path, page_num)
            if not image_base64:
                logger.warning(f"第{page_num}页转换失败，跳过")
                continue

            analysis = self._analyze_single_page(image_base64, page_num)
            if analysis:
                page_analyses.append(analysis)

                for table in analysis.get("tables", []):
                    tables_found.append({
                        "page_number": page_num,
                        **table
                    })
                for figure in analysis.get("figures", []):
                    figures_found.append({
                        "page_number": page_num,
                        **figure
                    })
                for formula in analysis.get("formulas", []):
                    formulas_found.append({
                        "page_number": page_num,
                        **formula
                    })

        return {
            "page_analyses": page_analyses,
            "tables_found": tables_found,
            "figures_found": figures_found,
            "formulas_found": formulas_found
        }

    def _analyze_single_page(self, image_base64: str, page_num: int) -> Dict:
        self._ensure_client()

        system_prompt = """你是一位学术论文视觉分析专家。请仔细分析这张论文页面图片，提取以下内容：

1. **表格**：如果页面包含表格，提取完整的表格数据（包括表头和所有单元格内容），并记录表格编号和标题
2. **数学公式**：如果页面包含数学公式，将其转换为LaTeX格式，并说明公式的物理/数学含义
3. **图片/图例**：如果页面包含图片、图表或图例，描述其内容（什么类型的图、展示了什么数据/趋势、关键结论）
4. **算法伪代码**：如果页面包含算法伪代码，提取算法步骤

请严格按照JSON格式输出。"""

        user_prompt = f"""请分析这张论文第{page_num}页的图片，提取其中的表格、公式、图片和算法信息。

请严格按照以下JSON格式输出：
{{
    "page_number": {page_num},
    "has_table": true或false,
    "has_figure": true或false,
    "has_formula": true或false,
    "tables": [
        {{
            "table_number": "表格编号",
            "caption": "表格标题",
            "headers": ["列1", "列2"],
            "rows": [["值1", "值2"]],
            "description": "表格内容概述"
        }}
    ],
    "figures": [
        {{
            "figure_number": "图编号",
            "caption": "图标题",
            "type": "折线图/柱状图/散点图/流程图/示意图/照片",
            "description": "图片内容详细描述（展示的数据、趋势、关键结论）",
            "key_findings": "从图中可以得出的关键发现"
        }}
    ],
    "formulas": [
        {{
            "latex": "LaTeX格式的公式",
            "description": "公式的物理/数学含义",
            "context": "公式在论文中的作用"
        }}
    ],
    "algorithms": [
        {{
            "name": "算法名称",
            "steps": ["步骤1", "步骤2"],
            "description": "算法功能描述"
        }}
    ],
    "page_summary": "该页面的核心内容摘要"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.ai_config["model"],
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=self.ai_config.get("max_tokens", 4000),
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content
            result = self._safe_json_parse(raw_content)
            result["page_number"] = page_num
            return result
        except Exception as e:
            logger.error(f"视觉分析第{page_num}页失败: {str(e)}")
            return {
                "page_number": page_num,
                "has_table": False,
                "has_figure": False,
                "has_formula": False,
                "tables": [],
                "figures": [],
                "formulas": [],
                "algorithms": [],
                "page_summary": "",
                "error": str(e)
            }

    def auto_detect_key_pages(self, file_path: str) -> List[int]:
        try:
            import fitz
        except ImportError:
            logger.warning("PyMuPDF(fitz)未安装，无法自动检测关键页面")
            return []

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            logger.error(f"无法打开PDF文件: {str(e)}")
            return []

        key_pages = set()
        pattern = re.compile(r'图\d|表\d|公式|equation|figure|table|Figure|Table|Equation', re.IGNORECASE)

        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text()

                if pattern.search(text):
                    key_pages.add(page_idx + 1)

                images = page.get_images()
                if images:
                    key_pages.add(page_idx + 1)

            doc.close()
        except Exception as e:
            logger.error(f"检测关键页面时出错: {str(e)}")
            doc.close()
            return []

        sorted_pages = sorted(key_pages)
        if len(sorted_pages) > 15:
            scored = []
            for p in sorted_pages:
                try:
                    doc2 = fitz.open(file_path)
                    page = doc2[p - 1]
                    text = page.get_text()
                    doc2.close()
                except Exception:
                    text = ""

                score = 0
                score += len(re.findall(r'表\d', text)) * 3
                score += len(re.findall(r'图\d', text)) * 2
                score += len(re.findall(r'公式|equation', text, re.IGNORECASE)) * 2
                scored.append((p, score))

            scored.sort(key=lambda x: x[1], reverse=True)
            sorted_pages = sorted([p for p, s in scored[:15]])

        return sorted_pages

    def get_visual_context_for_evaluation(self, file_path: str) -> str:
        analysis = self.analyze_key_pages(file_path)

        if not analysis["page_analyses"]:
            return ""

        sections = []
        sections.append("## 视觉分析结果（基于论文页面图像识别）")

        tables = analysis.get("tables_found", [])
        if tables:
            table_lines = ["### 表格数据"]
            for t in tables:
                table_number = t.get("table_number", "未知")
                caption = t.get("caption", "")
                headers = t.get("headers", [])
                rows = t.get("rows", [])
                description = t.get("description", "")

                header_str = ", ".join(headers) if headers else ""
                row_strs = []
                for row in rows[:5]:
                    row_strs.append(", ".join(str(v) for v in row))
                rows_str = "; ".join(row_strs) if row_strs else ""

                line = f'- {table_number} "{caption}"'
                if header_str:
                    line += f"：列头为[{header_str}]"
                if rows_str:
                    line += f"，数据为[{rows_str}]"
                if len(rows) > 5:
                    line += f"（共{len(rows)}行数据，仅展示前5行）"
                if description:
                    line += f"。{description}"
                table_lines.append(line)
            sections.append("\n".join(table_lines))

        formulas = analysis.get("formulas_found", [])
        if formulas:
            formula_lines = ["### 数学公式"]
            for f in formulas:
                latex = f.get("latex", "")
                description = f.get("description", "")
                page = f.get("page_number", "")
                line = f"- 第{page}页：{latex}"
                if description:
                    line += f"（{description}）"
                formula_lines.append(line)
            sections.append("\n".join(formula_lines))

        figures = analysis.get("figures_found", [])
        if figures:
            figure_lines = ["### 图表内容"]
            for fig in figures:
                figure_number = fig.get("figure_number", "未知")
                caption = fig.get("caption", "")
                fig_type = fig.get("type", "")
                description = fig.get("description", "")
                key_findings = fig.get("key_findings", "")

                line = f'- {figure_number} "{caption}"'
                if fig_type:
                    line += f"：{fig_type}"
                if description:
                    line += f"，{description}"
                if key_findings:
                    line += f"。关键发现：{key_findings}"
                figure_lines.append(line)
            sections.append("\n".join(figure_lines))

        return "\n\n".join(sections)

    def _safe_json_parse(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        cleaned = re.sub(r',\s*}', '}', raw)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw_content": raw}

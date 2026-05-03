"""
分段评估模块 - 智能论文分段评估系统
支持：
1. 大模型识别论文结构
2. 章节内容提取
3. 带上下文的章节评估
4. 章节衔接检测
5. 汇总评估
"""

from typing import Dict, List, Tuple, Optional
import json
import logging
import re

logger = logging.getLogger(__name__)


def repair_json(json_str: str) -> str:
    """
    修复常见的JSON格式错误
    
    Args:
        json_str: 可能包含错误的JSON字符串
        
    Returns:
        修复后的JSON字符串
    """
    import re
    
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
    
    json_str = re.sub(r'(?<!\\)"(?![,:}\]])', '\\"', json_str)
    
    json_str = re.sub(r'\n(?=[^"]*"[^"]*$)', '\\n', json_str)
    
    return json_str


def safe_json_parse(raw_content: str) -> dict:
    """
    安全地解析JSON，包含多层修复尝试
    
    Args:
        raw_content: 原始内容
        
    Returns:
        解析后的字典
        
    Raises:
        Exception: 如果所有解析尝试都失败
    """
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        logger.warning(f"首次JSON解析失败: {str(e)}")
    
    start_idx = raw_content.find('{')
    end_idx = raw_content.rfind('}') + 1
    if start_idx != -1 and end_idx != -1:
        json_str = raw_content[start_idx:end_idx]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"提取JSON后解析失败: {str(e)}")
            json_str = repair_json(json_str)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e2:
                logger.error(f"修复后仍然解析失败: {str(e2)}")
    
    try:
        import re
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, raw_content, re.DOTALL)
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except:
                    continue
    except Exception as e:
        logger.error(f"正则匹配JSON失败: {str(e)}")
    
    raise Exception(f"无法解析JSON内容: {raw_content[:200]}...")


class SectionedEvaluator:
    """分段评估器"""
    
    SECTION_TYPES = {
        "abstract": "摘要",
        "introduction": "绪论/引言",
        "literature_review": "文献综述/相关技术",
        "methodology": "方法/设计",
        "implementation": "实现/系统开发",
        "experiment": "实验/测试",
        "results": "结果分析",
        "conclusion": "结论/总结",
        "references": "参考文献",
        "appendix": "附录",
        "acknowledgement": "致谢",
        "other": "其他"
    }
    
    def __init__(self, llm_evaluator):
        """
        初始化分段评估器
        
        Args:
            llm_evaluator: LLM评估器实例
        """
        self.llm_evaluator = llm_evaluator
        self.ai_config = None
        self.client = None
    
    def _ensure_client(self):
        """确保大模型客户端已初始化"""
        if self.client is None:
            from src.config import get_ai_config
            self.ai_config = get_ai_config()
            self.client = self.llm_evaluator._initialize_client(self.ai_config)
    
    def identify_thesis_structure(self, content: str) -> Dict:
        """
        识别论文结构
        
        Args:
            content: 论文全文内容
            
        Returns:
            论文结构字典，包含各章节信息
        """
        self._ensure_client()
        
        content_preview = self._get_content_preview(content)
        
        system_prompt = """你是一位专业的学术论文结构分析专家。你的任务是分析论文的结构，识别出各个章节。

请仔细分析论文内容，识别出：
1. 论文的整体结构（各章节）
2. 每个章节的类型（摘要、绪论、方法、实现、实验、结论等）
3. 每个章节的起始和结束标记（用于后续提取）
4. 论文的主要工作内容（从摘要和绪论中提取）

注意：
- 不同论文的章节命名可能不同（如"绪论"可能是"引言"、"研究背景"等）
- 需要识别章节的实际类型，而不是仅仅看标题
- 起始标记和结束标记应该是文本中实际存在的、可以用于定位的字符串
- 对于最后一个章节（如结论、总结与展望），end_marker 应设置为空字符串 ""，表示提取到文档末尾
- 如果检测到"参考文献"、"致谢"等章节，结论章节的 end_marker 应设置为"参考文献"或"致谢"
- 请参考"检测到的章节标题"部分来设置准确的 start_marker 和 end_marker"""

        user_prompt = f"""请分析以下论文的结构：

## 论文内容预览

{content_preview}

## 请返回JSON格式结果

```json
{{
    "thesis_type": "论文类型（如：工程设计类、算法研究类、仿真分析类等）",
    "total_sections": 章节总数,
    "main_works": [
        "主要工作1",
        "主要工作2",
        "主要工作3"
    ],
    "sections": [
        {{
            "section_index": 0,
            "section_type": "abstract",
            "section_type_name": "摘要",
            "title": "摘要",
            "start_marker": "摘要",
            "end_marker": "关键词",
            "estimated_content": "摘要的大致内容描述"
        }},
        {{
            "section_index": 1,
            "section_type": "introduction",
            "section_type_name": "绪论",
            "title": "第一章 绪论",
            "start_marker": "第一章",
            "end_marker": "第二章",
            "estimated_content": "绪论的大致内容描述",
            "key_promises": ["绪论中承诺要做的工作1", "承诺的工作2"]
        }},
        {{
            "section_index": 2,
            "section_type": "methodology",
            "section_type_name": "方法/设计",
            "title": "第三章 系统设计",
            "start_marker": "第三章",
            "end_marker": "第四章",
            "estimated_content": "方法/设计的大致内容描述"
        }},
        {{
            "section_index": 3,
            "section_type": "implementation",
            "section_type_name": "实现",
            "title": "第四章 系统实现",
            "start_marker": "第四章",
            "end_marker": "第五章",
            "estimated_content": "实现的大致内容描述"
        }},
        {{
            "section_index": 4,
            "section_type": "experiment",
            "section_type_name": "实验/测试",
            "title": "第五章 系统测试",
            "start_marker": "第五章",
            "end_marker": "第六章",
            "estimated_content": "实验的大致内容描述"
        }},
        {{
            "section_index": 5,
            "section_type": "conclusion",
            "section_type_name": "结论",
            "title": "第六章 总结与展望",
            "start_marker": "第六章",
            "end_marker": "",
            "estimated_content": "结论的大致内容描述"
        }}
    ],
    "structure_analysis": "论文结构分析说明"
}}
```

请确保：
1. 准确识别所有章节
2. start_marker 和 end_marker 是文本中实际存在的字符串
3. section_type 使用标准类型：abstract, introduction, literature_review, methodology, implementation, experiment, results, conclusion, references, appendix, acknowledgement, other
4. 从绪论中提取 key_promises（承诺要做的工作）
5. 最后一个章节的 end_marker 设置为空字符串 ""，除非后面有参考文献或致谢
6. 如果有参考文献章节，结论章节的 end_marker 应设置为"参考文献"或"参考 文献" """

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        result = safe_json_parse(raw_content)
        
        logger.info(f"论文结构识别完成: 共{result.get('total_sections', 0)}个章节")
        return result
    
    def _get_content_preview(self, content: str) -> str:
        """
        获取内容预览（用于结构识别）
        包含开头、中间抽样、结尾部分
        同时提取所有可能的章节标题
        """
        max_length = 15000
        
        chapter_patterns = [
            r'【章节】([^\n]+)',
            r'【标题】([^\n]+)',
            r'第[一二三四五六七八九十\d]+\s*章[^\n]*',
            r'摘\s*要',
            r'ABSTRACT',
            r'Abstract',
            r'关键词',
            r'Key\s*words',
            r'参考\s*文献',
            r'致\s*谢',
            r'附录',
            r'结论[^\n]*',
            r'总结[^\n]*',
            r'展望[^\n]*',
        ]
        
        chapter_headers = []
        for pattern in chapter_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    chapter_headers.extend([m for m in matches[0] if m])
                else:
                    chapter_headers.extend(matches)
        
        chapter_headers_text = "\n".join(f"- {h.strip()}" for h in set(chapter_headers) if h.strip())
        
        if len(content) <= max_length:
            return f"## 检测到的章节标题\n{chapter_headers_text}\n\n## 论文内容\n{content}"
        
        head_length = 5000
        tail_length = 4000
        middle_length = max_length - head_length - tail_length - len(chapter_headers_text) - 200
        
        head = content[:head_length]
        tail = content[-tail_length:]
        
        total_middle = len(content) - head_length - tail_length
        if total_middle > 0:
            sample_points = 3
            middle_samples = []
            for i in range(sample_points):
                start = head_length + (total_middle // sample_points) * i
                end = start + (middle_length // sample_points)
                middle_samples.append(content[start:end])
            middle = "\n\n... (中间内容抽样) ...\n\n".join(middle_samples)
        else:
            middle = ""
        
        preview = f"""## 检测到的章节标题
{chapter_headers_text}

## 论文内容预览

### 开头部分
{head}

... (省略部分内容) ...

### 中间抽样
{middle}

... (省略部分内容) ...

### 结尾部分
{tail}"""
        
        return preview
    
    def extract_sections(self, content: str, structure: Dict) -> List[Dict]:
        """
        根据识别的结构提取各章节内容
        
        Args:
            content: 论文全文内容
            structure: 论文结构信息
            
        Returns:
            各章节内容列表
        """
        sections = structure.get("sections", [])
        extracted_sections = []
        
        for i, section_info in enumerate(sections):
            section_content = self._extract_single_section(
                content, 
                section_info, 
                sections[i+1] if i+1 < len(sections) else None
            )
            
            if len(section_content) < 100:
                section_content = self._fallback_extract_section(
                    content, 
                    section_info, 
                    sections[i+1] if i+1 < len(sections) else None
                )
            
            extracted_sections.append({
                **section_info,
                "content": section_content,
                "content_length": len(section_content)
            })
            
            logger.info(f"章节提取: {section_info.get('title', '')} - {len(section_content)}字符")
        
        logger.info(f"章节内容提取完成: 共{len(extracted_sections)}个章节")
        return extracted_sections
    
    def _fallback_extract_section(
        self,
        content: str,
        section_info: Dict,
        next_section: Optional[Dict] = None
    ) -> str:
        """
        备用章节提取方法
        
        当主方法提取的内容太短时使用
        """
        section_type = section_info.get("section_type", "")
        section_title = section_info.get("title", "")
        
        if section_type == "conclusion":
            conclusion_patterns = [
                r'(第[一二三四五六七八九十\d]+\s*章\s*(?:结论|总结|总结与展望)[^\n]*\n)(.*?)(?=\n\s*(?:参考\s*文献|致\s*谢|附录|$))',
                r'((?:结论|总结|总结与展望)[^\n]*\n)(.*?)(?=\n\s*(?:参考\s*文献|致\s*谢|附录|$))',
                r'(第[一二三四五六七八九十\d]+\s*章[^\n]*\n)(.*?)(?=\n\s*(?:参考\s*文献|致\s*谢|附录|$))',
            ]
            
            for pattern in conclusion_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    if len(match.groups()) > 1:
                        return match.group(2).strip()
                    else:
                        return match.group(1).strip()
            
            chapter_num_match = re.search(r'第([一二三四五六七八九十\d]+)\s*章', section_title)
            if chapter_num_match:
                chapter_num = chapter_num_match.group(1)
                pattern = rf'(第{chapter_num}\s*章[^\n]*\n)(.*?)(?=\n\s*(?:参考\s*文献|致\s*谢|附录|$))'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(2).strip()
            
            last_chapter_start = -1
            for pattern in [r'第[一二三四五六七八九十\d]+\s*章', r'结论', r'总结']:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                if matches:
                    last_chapter_start = max(last_chapter_start, matches[-1].start())
            
            if last_chapter_start != -1:
                ref_match = re.search(r'参考\s*文献|致\s*谢|附录', content[last_chapter_start:])
                if ref_match:
                    return content[last_chapter_start:last_chapter_start + ref_match.start()].strip()
                else:
                    return content[last_chapter_start:].strip()
        
        if section_type == "abstract":
            abstract_patterns = [
                r'摘\s*要\s*[：:]*\s*\n?(.*?)(?=\s*(?:关键词|Key\s*words|ABSTRACT|Abstract))',
                r'摘\s*要\s*\n?(.*?)(?=\n\s*(?:关键词|第[一二三四五六七八九十\d]+\s*章))',
            ]
            
            for pattern in abstract_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        if section_type == "introduction":
            intro_patterns = [
                r'(第[一二三四五六七八九十\d]+\s*章\s*绪?论[^\n]*\n)(.*?)(?=\n\s*第[一二三四五六七八九十\d]+\s*章)',
                r'(第[一二三四五六七八九十\d]+\s*章\s*引言[^\n]*\n)(.*?)(?=\n\s*第[一二三四五六七八九十\d]+\s*章)',
                r'(绪论[^\n]*\n)(.*?)(?=\n\s*第[一二三四五六七八九十\d]+\s*章)',
                r'(引言[^\n]*\n)(.*?)(?=\n\s*第[一二三四五六七八九十\d]+\s*章)',
            ]
            
            for pattern in intro_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match and len(match.groups()) > 1:
                    result = match.group(2).strip()
                    if len(result) > 100:
                        return result
            
            chapter_num_match = re.search(r'第([一二三四五六七八九十\d]+)\s*章', section_title)
            if chapter_num_match:
                chapter_num = chapter_num_match.group(1)
                
                pattern = rf'(第{chapter_num}\s*章[^\n]*\n)(.*?)(?=\n\s*第[一二三四五六七八九十\d]+\s*章)'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(2).strip()
            
            intro_start = -1
            for pattern in [r'第[一1]\s*章\s*绪?论', r'第[一1]\s*章\s*引言', r'绪论', r'引言']:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    intro_start = match.start()
                    break
            
            if intro_start != -1:
                next_chapter = re.search(r'\n\s*第[二三四五六七八九十\d]+\s*章', content[intro_start:], re.IGNORECASE)
                if next_chapter:
                    return content[intro_start:intro_start + next_chapter.start()].strip()
                else:
                    return content[intro_start:intro_start + 10000].strip()
        
        return ""
    
    def _extract_single_section(
        self, 
        content: str, 
        section_info: Dict, 
        next_section: Optional[Dict] = None
    ) -> str:
        """
        提取单个章节内容
        
        改进策略：
        1. 优先使用【章节】标记定位
        2. 使用下一个章节的 start_marker 作为结束标记
        3. 如果没有下一个章节，使用 end_marker 或文档末尾
        4. 支持多种章节标题格式的匹配
        """
        start_marker = section_info.get("start_marker", "")
        end_marker = section_info.get("end_marker", "")
        section_title = section_info.get("title", "")
        
        start_idx = -1
        
        if section_title:
            chapter_marker_pattern = rf'【章节】\s*{re.escape(section_title)}'
            match = re.search(chapter_marker_pattern, content, re.IGNORECASE)
            if match:
                start_idx = match.start()
        
        if start_idx == -1 and start_marker:
            chapter_marker_pattern = rf'【章节】\s*{re.escape(start_marker)}'
            match = re.search(chapter_marker_pattern, content, re.IGNORECASE)
            if match:
                start_idx = match.start()
        
        if start_idx == -1 and start_marker:
            start_idx = content.find(start_marker)
        
        if start_idx == -1 and section_title:
            title_patterns = [
                section_title,
                section_title.replace("第", "第 "),
                section_title.replace("章", "章 "),
                re.sub(r'第\s*(\d+)\s*章', r'第\1章', section_title),
                rf'【章节】\s*{re.escape(section_title)}',
                rf'【标题】\s*{re.escape(section_title)}',
            ]
            for pattern in title_patterns:
                try:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        start_idx = match.start()
                        break
                except:
                    start_idx = content.find(pattern)
                    if start_idx != -1:
                        break
        
        if start_idx == -1:
            start_idx = 0
        
        end_idx = -1
        
        if next_section:
            next_start_marker = next_section.get("start_marker", "")
            next_title = next_section.get("title", "")
            
            if next_title:
                chapter_marker_pattern = rf'【章节】\s*{re.escape(next_title)}'
                match = re.search(chapter_marker_pattern, content[start_idx:], re.IGNORECASE)
                if match:
                    end_idx = start_idx + match.start()
            
            if end_idx == -1 and next_start_marker:
                chapter_marker_pattern = rf'【章节】\s*{re.escape(next_start_marker)}'
                match = re.search(chapter_marker_pattern, content[start_idx:], re.IGNORECASE)
                if match:
                    end_idx = start_idx + match.start()
            
            if end_idx == -1 and next_start_marker:
                end_idx = content.find(next_start_marker, start_idx + len(start_marker) if start_marker else start_idx)
            
            if end_idx == -1 and next_title:
                title_patterns = [
                    next_title,
                    next_title.replace("第", "第 "),
                    next_title.replace("章", "章 "),
                ]
                for pattern in title_patterns:
                    found_idx = content.find(pattern, start_idx)
                    if found_idx != -1 and (end_idx == -1 or found_idx < end_idx):
                        end_idx = found_idx
                        break
        
        if end_idx == -1 and end_marker:
            end_idx = content.find(end_marker, start_idx + len(start_marker) if start_marker else start_idx)
        
        if end_idx == -1:
            end_idx = len(content)
        
        section_content = content[start_idx:end_idx].strip()
        
        section_content = re.sub(r'^【章节】\s*', '', section_content)
        section_content = re.sub(r'\n【章节】[^\n]*', '\n', section_content)
        
        section_content = self._clean_section_content(section_content, section_info.get("section_type", ""))
        
        return section_content
    
    def _clean_section_content(self, content: str, section_type: str) -> str:
        """
        清理章节内容
        
        移除：
        1. 章节末尾的参考文献
        2. 重复的封面和摘要
        3. 多余的空白
        """
        if not content:
            return content
        
        ref_patterns = [
            r'\n\s*参考\s*文献[^\n]*\n.*$',
            r'\n\s*References[^\n]*\n.*$',
            r'\n\s*\[\d+\].*$',  # 以[1]开头的参考文献格式
        ]
        
        if section_type not in ["references", "other"]:
            for pattern in ref_patterns:
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    potential_refs = content[match.start():]
                    if re.search(r'\[\d+\]', potential_refs) or re.search(r'参考\s*文献', potential_refs, re.IGNORECASE):
                        if len(potential_refs) < len(content) * 0.5:
                            content = content[:match.start()].strip()
                            break
        
        cover_patterns = [
            r'硕士学位论文',
            r'本科毕业设计',
            r'毕业设计',
            r'学位论文',
            r'分类号[：:]\s*\S+',
            r'UDC[：:]\s*\S+',
        ]
        
        if section_type not in ["abstract", "other"]:
            for pattern in cover_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    abstract_match = re.search(r'摘\s*要', content[match.start():], re.IGNORECASE)
                    if abstract_match:
                        content = content[:match.start()].strip()
                        break
        
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content
    
    def build_promise_tracking_table(
        self,
        sections: List[Dict],
        section_evaluations: List[Dict]
    ) -> Dict:
        """
        构建全局承诺-兑现追踪表
        
        从所有章节中提取承诺/目标，然后检查后续章节是否实现
        
        Args:
            sections: 各章节信息
            section_evaluations: 各章节评估结果
            
        Returns:
            追踪表结果
        """
        self._ensure_client()
        
        all_promises = []
        seen_promises = set()
        
        for i, evaluation in enumerate(section_evaluations):
            promises = evaluation.get("promises_made", [])
            section_title = sections[i].get("title", f"章节{i+1}")
            section_type = sections[i].get("section_type", "other")
            
            for promise in promises:
                promise_key = promise.strip().lower()
                
                if promise_key not in seen_promises and len(promise.strip()) > 5:
                    seen_promises.add(promise_key)
                    all_promises.append({
                        "promise": promise,
                        "source_section": section_title,
                        "source_section_type": section_type,
                        "source_index": i
                    })
        
        if not all_promises:
            return {
                "promises": [],
                "fulfillment_status": [],
                "overall_fulfillment_rate": 1.0,
                "unfulfilled_promises": []
            }
        
        all_content = ""
        for section in sections:
            all_content += section.get("content", "")[:3000] + "\n\n"
        
        system_prompt = """你是一位严谨的学术论文评审专家。你需要深度检查论文中的承诺是否被兑现。

任务：
1. 检查每个承诺在后续章节中是否被实现
2. 如果实现了，指出在哪个章节、如何实现的，引用原文证据
3. 如果未实现，标记为未兑现，分析可能的原因
4. 对于部分兑现的承诺，说明哪些部分兑现了，哪些没有

深度要求：
- 承诺可能以不同的表述方式实现，需要语义理解
- 部分承诺可能只是部分实现，需要仔细区分
- 要检查整篇论文，而不仅仅是相邻章节
- 每个承诺的兑现评价需要引用论文中的具体内容作为证据
- 分析承诺未兑现对论文整体质量的影响"""

        user_prompt = f"""请深度检查以下论文承诺的兑现情况：

## 论文中的承诺列表

{json.dumps(all_promises, ensure_ascii=False, indent=2)}

## 论文内容（各章节摘要）

{all_content[:10000]}

## 请返回JSON格式结果

```json
{{
    "fulfillment_status": [
        {{
            "promise": "承诺内容",
            "source_section": "来源章节",
            "is_fulfilled": true/false,
            "fulfillment_section": "兑现的章节（如果已兑现）",
            "fulfillment_evidence": "兑现的证据（必须引用原文具体内容）",
            "fulfillment_degree": "兑现程度（完全兑现/部分兑现/未兑现）",
            "comment": "评价说明（50-100字，详细说明兑现或未兑现的具体情况）",
            "impact_analysis": "该承诺兑现情况对论文整体质量的影响分析（30-50字）",
            "improvement_suggestion": "如未完全兑现，给出具体的改进建议"
        }}
    ],
    "overall_fulfillment_rate": 兑现率（0.0-1.0）,
    "unfulfilled_promises": ["未兑现的承诺列表"],
    "partially_fulfilled_promises": ["部分兑现的承诺列表"],
    "summary": "承诺兑现情况总结（100-200字，分析整体兑现情况、对论文质量的影响、改进方向）"
}}
```"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        result = safe_json_parse(raw_content)
        
        result["promises"] = all_promises
        logger.info(f"承诺追踪完成: 兑现率{result.get('overall_fulfillment_rate', 0):.1%}")
        return result
    
    def evaluate_section(
        self,
        section: Dict,
        prev_section_summary: Optional[str] = None,
        next_section_summary: Optional[str] = None,
        indicators: Dict = None,
        main_works: List[str] = None
    ) -> Dict:
        """
        评估单个章节（带上下文）
        
        Args:
            section: 章节信息（包含内容和元数据）
            prev_section_summary: 前一章节的摘要
            next_section_summary: 后一章节的摘要
            indicators: 评价指标
            main_works: 论文主要工作列表
            
        Returns:
            章节评估结果
        """
        self._ensure_client()
        
        section_type = section.get("section_type", "other")
        section_title = section.get("title", "未知章节")
        section_content = section.get("content", "")
        
        if len(section_content) > 10000:
            section_content = section_content[:5000] + "\n\n... (内容过长，已截断) ...\n\n" + section_content[-3000:]
        
        context_info = ""
        if prev_section_summary:
            context_info += f"\n### 前一章节摘要\n{prev_section_summary}\n"
        if next_section_summary:
            context_info += f"\n### 后一章节摘要\n{next_section_summary}\n"
        
        main_works_str = ""
        if main_works:
            main_works_str = f"\n### 论文主要工作（从摘要/绪论提取）\n" + "\n".join([f"- {work}" for work in main_works])
        
        system_prompt = """你是一位严谨的学术论文评审专家。你需要对论文的各个章节进行深度评估，并检测章节之间的逻辑连贯性。

评估原则：
1. 评分必须有充分依据，每个评分项都需引用论文中的具体内容作为证据
2. 改进建议必须具体、可操作，不能泛泛而谈
3. 问题诊断要精准，指出具体段落或句子的问题
4. 对比学术标准给出评价，而非仅做表面描述

评估维度与深度要求：
1. 内容质量（40%权重）：论述深度、数据充分性、论证严谨性、学术规范性
2. 逻辑连贯性（30%权重）：章节内部逻辑、与前后章节衔接、论证链条完整性
3. 创新与贡献（20%权重）：方法创新性、结果价值、与现有工作对比
4. 表达规范性（10%权重）：语言准确性、图表规范性、格式合规性

请严格按维度评分，每个维度都必须给出详细的评分理由和改进建议。"""

        user_prompt = f"""请深度评估以下论文章节：

## 章节信息
- 章节类型：{self.SECTION_TYPES.get(section_type, section_type)}
- 章节标题：{section_title}
{main_works_str}
{context_info}

## 章节内容

{section_content}

## 评价指标参考

{json.dumps(indicators, ensure_ascii=False, indent=2) if indicators else "无特定指标"}

## 评估要求

请严格按照以下维度进行深度评估，每个维度都需要：
- 给出具体分数和等级
- 引用章节中的具体内容作为评分依据（必须引用原文或概述原文内容）
- 列出发现的具体问题（指出具体位置）
- 给出可操作的改进建议

## 请返回JSON格式结果

```json
{{
    "section_score": 分数（0-100）,
    "grade_level": "等级（优秀/良好/中等/及格/不及格）",
    "content_quality": {{
        "score": 分数,
        "comment": "内容质量总体评价（80-150字）",
        "strengths": ["优点1（附具体证据）", "优点2（附具体证据）"],
        "weaknesses": ["不足1（附具体证据）", "不足2（附具体证据）"],
        "depth_analysis": "论述深度分析：是否仅停留在描述层面，还是有深入分析和推理",
        "data_sufficiency": "数据充分性评价：实验数据/文献数据是否充足支撑结论"
    }},
    "logic_coherence": {{
        "score": 分数,
        "comment": "逻辑连贯性总体评价（50-100字）",
        "internal_logic": "章节内部逻辑评价：论证链条是否完整",
        "cross_chapter_logic": "与前后章节的逻辑衔接评价",
        "issues": ["问题1（指出具体位置和原因）", "问题2（指出具体位置和原因）"]
    }},
    "innovation_contribution": {{
        "score": 分数,
        "comment": "创新与贡献评价（50-100字）",
        "novelty_type": "创新类型（原创/应用创新/改进/无创新）",
        "concrete_contribution": "具体贡献描述",
        "comparison_with_existing": "与现有工作的对比分析"
    }},
    "writing_quality": {{
        "score": 分数,
        "comment": "表达规范性评价（50字以内）",
        "language_issues": ["语言问题1", "语言问题2"],
        "format_issues": ["格式问题1", "格式问题2"]
    }},
    "key_points": [
        "该章节的关键点1（具体内容概述）",
        "该章节的关键点2（具体内容概述）",
        "该章节的关键点3（具体内容概述）"
    ],
    "summary": "该章节的摘要（100字以内，用于后续章节评估参考）",
    "promises_made": ["该章节承诺要做的工作（如果是绪论）"],
    "promises_fulfilled": ["该章节兑现的工作（如果不是绪论）"],
    "improvement_suggestions": [
        {{"aspect": "改进方面", "current_issue": "当前问题（附具体位置）", "suggestion": "具体建议", "priority": "高/中/低"}},
        {{"aspect": "改进方面", "current_issue": "当前问题（附具体位置）", "suggestion": "具体建议", "priority": "高/中/低"}}
    ],
    "evidence": "总体评分依据（100-200字，必须引用章节中的具体内容）",
    "detailed_score_reason": "各维度评分的详细推理过程（200-300字）：为什么给出这个分数，哪些内容加分，哪些内容扣分，与学术标准的差距在哪里"
}}
```"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        result = safe_json_parse(raw_content)
        
        result["section_type"] = section_type
        result["section_title"] = section_title
        
        logger.info(f"章节评估完成: {section_title} - {result.get('section_score', 0)}分")
        return result
    
    def check_section_coherence(
        self,
        prev_section: Dict,
        prev_evaluation: Dict,
        next_section: Dict,
        next_evaluation: Dict,
        main_works: List[str] = None
    ) -> Dict:
        """
        检测两个相邻章节之间的逻辑衔接
        
        注意：此方法只关注逻辑衔接，不检测承诺-兑现
        承诺-兑现检测由 build_promise_tracking_table 方法处理
        
        Args:
            prev_section: 前一章节信息
            prev_evaluation: 前一章节评估结果
            next_section: 后一章节信息
            next_evaluation: 后一章节评估结果
            main_works: 论文主要工作
            
        Returns:
            衔接检测结果
        """
        self._ensure_client()
        
        prev_content = prev_section.get("content", "")
        next_content = next_section.get("content", "")
        
        if len(prev_content) > 3000:
            prev_content = prev_content[-2000:]
        if len(next_content) > 3000:
            next_content = next_content[:2000]
        
        system_prompt = """你是一位严谨的学术论文评审专家。你需要深度检测论文相邻章节之间的逻辑衔接是否合理。

检测维度与深度要求（只关注逻辑衔接，不检测承诺-兑现）：
1. 逻辑连贯性：前后章节的论述是否连贯，是否有逻辑跳跃，论证链条是否完整
2. 内容一致性：前后章节的内容是否矛盾，术语使用是否统一
3. 过渡自然性：章节之间的过渡是否自然，是否有承上启下的段落
4. 论证完整性：前一章节提出的问题/方法是否在后一章节得到延续

每个维度都需要：
- 给出具体分数
- 引用前后章节中的具体内容作为证据
- 指出问题的具体位置
- 给出可操作的改进建议

注意：不要检测承诺-兑现，那是单独的检测任务。"""

        user_prompt = f"""请深度检测以下两个相邻章节之间的逻辑衔接：

## 前一章节信息
- 类型：{self.SECTION_TYPES.get(prev_section.get('section_type'), '未知')}
- 标题：{prev_section.get('title', '未知')}
- 评估摘要：{prev_evaluation.get('summary', '')}

### 前一章节末尾内容
{prev_content}

---

## 后一章节信息
- 类型：{self.SECTION_TYPES.get(next_section.get('section_type'), '未知')}
- 标题：{next_section.get('title', '未知')}
- 评估摘要：{next_evaluation.get('summary', '')}

### 后一章节开头内容
{next_content}

---

## 论文主要工作
{json.dumps(main_works, ensure_ascii=False) if main_works else "无"}

## 请返回JSON格式结果

```json
{{
    "coherence_score": 分数（0-100）,
    "grade_level": "等级（优秀/良好/中等/及格/不及格）",
    "logic_flow": {{
        "is_smooth": true/false,
        "issues": ["逻辑问题1（指出具体位置和原因）", "逻辑问题2（指出具体位置和原因）"],
        "score": 逻辑流畅分数,
        "comment": "逻辑连贯性评价（50-100字，引用具体内容）",
        "improvement_suggestions": ["改进建议1", "改进建议2"]
    }},
    "content_consistency": {{
        "is_consistent": true/false,
        "inconsistencies": ["不一致的地方（引用具体内容）"],
        "score": 内容一致性分数,
        "comment": "内容一致性评价（50-100字，引用具体内容）",
        "improvement_suggestions": ["改进建议1", "改进建议2"]
    }},
    "transition_quality": {{
        "is_natural": true/false,
        "score": 过渡质量分数,
        "comment": "过渡质量评价（50-100字，引用具体内容）",
        "missing_transition": "缺失的过渡内容描述（如有）",
        "improvement_suggestions": ["改进建议1", "改进建议2"]
    }},
    "argument_continuity": {{
        "is_continuous": true/false,
        "issues": ["论证不连续的地方（引用具体内容）"],
        "score": 论证连续性分数,
        "comment": "论证连续性评价（50-100字，引用具体内容）",
        "improvement_suggestions": ["改进建议1", "改进建议2"]
    }},
    "improvement_suggestions": [
        {{"aspect": "改进方面", "current_issue": "当前问题（附具体位置）", "suggestion": "具体建议", "priority": "高/中/低"}}
    ],
    "overall_comment": "整体衔接评价（100-150字，只关注逻辑衔接，需引用具体内容说明衔接好坏）"
}}
```"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=3000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        result = safe_json_parse(raw_content)
        
        result["prev_section"] = prev_section.get("title", "")
        result["next_section"] = next_section.get("title", "")
        
        return result
    
    def generate_final_evaluation(
        self,
        structure: Dict,
        section_evaluations: List[Dict],
        coherence_checks: List[Dict],
        promise_tracking: Dict = None,
        institutional_result: Dict = None,
        indicators: Dict = None
    ) -> Dict:
        """
        生成最终汇总评价
        
        Args:
            structure: 论文结构信息
            section_evaluations: 各章节评估结果
            coherence_checks: 章节衔接检测结果
            promise_tracking: 承诺追踪表结果
            institutional_result: 固有评价体系结果
            indicators: 评价指标
            
        Returns:
            最终评价结果
        """
        self._ensure_client()
        
        section_scores = [e.get("section_score", 0) for e in section_evaluations]
        avg_section_score = sum(section_scores) / len(section_scores) if section_scores else 0
        
        coherence_scores = [c.get("coherence_score", 0) for c in coherence_checks]
        avg_coherence_score = sum(coherence_scores) / len(coherence_scores) if coherence_scores else 100
        
        section_summary = []
        for e in section_evaluations:
            section_summary.append({
                "title": e.get("section_title", ""),
                "type": e.get("section_type", ""),
                "score": e.get("section_score", 0),
                "grade": e.get("grade_level", ""),
                "key_points": e.get("key_points", [])[:3]
            })
        
        coherence_summary = []
        for c in coherence_checks:
            coherence_summary.append({
                "from": c.get("prev_section", ""),
                "to": c.get("next_section", ""),
                "score": c.get("coherence_score", 0),
                "issues": c.get("logic_flow", {}).get("issues", [])[:2]
            })
        
        unfulfilled_promises = []
        fulfillment_rate = 1.0
        if promise_tracking:
            unfulfilled_promises = promise_tracking.get("unfulfilled_promises", [])
            fulfillment_rate = promise_tracking.get("overall_fulfillment_rate", 1.0)
        
        system_prompt = """你是一位拥有15年经验的学术论文评审专家，专注于毕业设计质量评估。

【你的专业背景】
- 曾担任多所高校毕业设计评审专家
- 熟悉各学科领域的创新评价标准
- 擅长识别"搭积木式创新"与"原创性创新"
- 对文献综述质量有敏锐判断

【评审思维链 - 必须严格按此步骤思考】

### 创新度评估（4步分析法）
**第1步：论文提出了什么新东西？**
- 识别创新点：新方法/新模型/新应用/新发现/新设计
- 定位证据：在论文中找到具体描述创新的原文

**第2步：这个"新"是真正的创新还是简单的组合？**
- 判断创新类型：原创性创新/改进型创新/集成创新/应用创新/简单组合
- 分析创新深度：是否触及核心技术原理

**第3步：创新是否有价值？解决了什么实际问题？**
- 评估实用价值：是否解决实际工程/学术问题
- 评估学术价值：是否有理论贡献

**第4步：与现有工作相比，改进有多大？**
- 对比现有方案：与最先进方法相比有何优势
- 量化改进程度：性能提升多少、效率提高多少

### 研究深度评估（4步分析法）
**第1步：文献综述是否覆盖了主要相关工作？**
**第2步：是否真正理解并分析了文献，而非简单罗列？**
**第3步：现状分析是否有深度，能否归纳出关键问题？**
**第4步：引用的文献是否新颖、权威？**

### 文章结构评估（4步分析法）
**第1步：章节安排是否符合学术规范？**
**第2步：各章节之间是否有逻辑关联？**
**第3步：论证是否连贯，有无跳跃或矛盾？**
**第4步：语言表达是否规范、清晰？**

### 方法与实验评估（4步分析法）
**第1步：研究方法是否适合研究问题？**
**第2步：方法描述是否详细、可复现？**
**第3步：实验设计是否科学、完整？**
**第4步：数据分析是否严谨、有说服力？**

【评分等级标准】
- 优秀(90-100分): 超出预期，有原创性贡献或深度见解，内容完整且高质量
- 良好(80-89分): 符合预期，有针对性改进，内容完整，有一定深度
- 中等(70-79分): 基本符合要求，有一定工作量但创新不足，深度一般
- 及格(60-69分): 勉强符合要求，工作量不足或深度不够
- 不及格(0-59分): 不符合要求，存在严重问题

【输出要求】
必须严格按照思维链4步分析法进行评估，每个维度的评分理由必须包含：
1. 具体的分析过程（按4步展开）
2. 论文中的具体证据（引用原文）
3. 与优秀标准的对比
4. 明确的评分依据"""

        user_prompt = f"""请根据以下信息生成最终评价：

## 论文结构信息
- 论文类型：{structure.get('thesis_type', '未知')}
- 章节总数：{structure.get('total_sections', 0)}
- 主要工作：{structure.get('main_works', [])}

## 各章节评估摘要
{json.dumps(section_summary, ensure_ascii=False, indent=2)}

## 章节衔接检测摘要（逻辑衔接）
{json.dumps(coherence_summary, ensure_ascii=False, indent=2)}

## 承诺-兑现追踪表
{json.dumps(promise_tracking, ensure_ascii=False, indent=2) if promise_tracking else "无"}

## 固有评价体系结果
{json.dumps(institutional_result, ensure_ascii=False, indent=2) if institutional_result else "无"}

## 评价指标
{json.dumps(indicators, ensure_ascii=False, indent=2) if indicators else "无"}

## 统计数据
- 章节平均分：{avg_section_score:.1f}
- 衔接平均分：{avg_coherence_score:.1f}
- 承诺兑现率：{fulfillment_rate:.1%}

## 评分要求

### 必须按照以下格式输出：

**第一步：输出量化评估表**
使用表格形式展示各维度评分，包含权重、得分、加权得分、核心评判依据。

**第二步：输出详细评审推导过程**
对每个维度，严格按照4步分析法进行详细分析：
1. 第1步分析 + 证据引用
2. 第2步分析 + 证据引用  
3. 第3步分析 + 证据引用
4. 第4步分析 + 证据引用
然后给出综合评分和理由。

**第三步：输出评审结论**
包含总体评价和改进建议。

## 请返回JSON格式结果

```json
{{
    "quantitative_table": {{
        "innovation": {{
            "weight": "权重（根据固有评价体系结果）",
            "score": 分数,
            "weighted_score": 加权得分,
            "core_evidence": "核心评判依据（一句话）"
        }},
        "research_depth": {{
            "weight": "权重",
            "score": 分数,
            "weighted_score": 加权得分,
            "core_evidence": "核心评判依据（一句话）"
        }},
        "structure": {{
            "weight": "权重",
            "score": 分数,
            "weighted_score": 加权得分,
            "core_evidence": "核心评判依据（一句话）"
        }},
        "method_experiment": {{
            "weight": "权重",
            "score": 分数,
            "weighted_score": 加权得分,
            "core_evidence": "核心评判依据（一句话）"
        }},
        "total_score": 总分
    }},
    "detailed_analysis": {{
        "innovation_analysis": {{
            "step1": {{
                "question": "论文提出了什么新东西？",
                "answer": "分析回答",
                "evidence": "论文中的具体证据（引用原文）"
            }},
            "step2": {{
                "question": "这个'新'是真正的创新还是简单的组合？",
                "answer": "分析回答",
                "innovation_type": "创新类型（原创性创新/改进型创新/集成创新/应用创新/简单组合）",
                "evidence": "论文中的具体证据"
            }},
            "step3": {{
                "question": "创新是否有价值？解决了什么实际问题？",
                "answer": "分析回答",
                "practical_value": "实用价值评估",
                "academic_value": "学术价值评估",
                "evidence": "论文中的具体证据"
            }},
            "step4": {{
                "question": "与现有工作相比，改进有多大？",
                "answer": "分析回答",
                "comparison": "与现有工作的对比分析",
                "improvement_degree": "改进程度评估",
                "evidence": "论文中的具体证据"
            }},
            "final_score": 分数,
            "score_reason": "综合评分理由（必须引用具体证据）"
        }},
        "research_depth_analysis": {{
            "step1": {{
                "question": "文献综述是否覆盖了主要相关工作？",
                "answer": "分析回答",
                "coverage": "覆盖范围评估",
                "evidence": "论文中的具体证据"
            }},
            "step2": {{
                "question": "是否真正理解并分析了文献，而非简单罗列？",
                "answer": "分析回答",
                "analysis_type": "综述方式类型（深度分析/中等分析/简单罗列）",
                "evidence": "论文中的具体证据"
            }},
            "step3": {{
                "question": "现状分析是否有深度，能否归纳出关键问题？",
                "answer": "分析回答",
                "problem_induction": "问题归纳能力评估",
                "evidence": "论文中的具体证据"
            }},
            "step4": {{
                "question": "引用的文献是否新颖、权威？",
                "answer": "分析回答",
                "literature_quality": "文献质量评估",
                "evidence": "论文中的具体证据"
            }},
            "final_score": 分数,
            "score_reason": "综合评分理由（必须引用具体证据）"
        }},
        "structure_analysis": {{
            "step1": {{
                "question": "章节安排是否符合学术规范？",
                "answer": "分析回答",
                "structure_completeness": "结构完整性评估",
                "evidence": "论文中的具体证据"
            }},
            "step2": {{
                "question": "各章节之间是否有逻辑关联？",
                "answer": "分析回答",
                "logic_chain": "逻辑链条评估",
                "evidence": "论文中的具体证据"
            }},
            "step3": {{
                "question": "论证是否连贯，有无跳跃或矛盾？",
                "answer": "分析回答",
                "argument_coherence": "论证连贯性评估",
                "evidence": "论文中的具体证据"
            }},
            "step4": {{
                "question": "语言表达是否规范、清晰？",
                "answer": "分析回答",
                "expression_quality": "表达质量评估",
                "evidence": "论文中的具体证据"
            }},
            "final_score": 分数,
            "score_reason": "综合评分理由（必须引用具体证据）"
        }},
        "method_experiment_analysis": {{
            "step1": {{
                "question": "研究方法是否适合研究问题？",
                "answer": "分析回答",
                "method_suitability": "方法适用性评估",
                "evidence": "论文中的具体证据"
            }},
            "step2": {{
                "question": "方法描述是否详细、可复现？",
                "answer": "分析回答",
                "reproducibility": "可复现性评估",
                "evidence": "论文中的具体证据"
            }},
            "step3": {{
                "question": "实验设计是否科学、完整？",
                "answer": "分析回答",
                "experiment_design": "实验设计评估",
                "evidence": "论文中的具体证据"
            }},
            "step4": {{
                "question": "数据分析是否严谨、有说服力？",
                "answer": "分析回答",
                "data_analysis": "数据分析评估",
                "evidence": "论文中的具体证据"
            }},
            "final_score": 分数,
            "score_reason": "综合评分理由（必须引用具体证据）"
        }}
    }},
    "overall_score": 总分（0-100）,
    "grade_level": "总体等级（优秀/良好/中等/及格/不及格）",
    "dimension_scores": [
        {{
            "indicator_id": "指标编号",
            "indicator_name": "指标名称",
            "score": 分数,
            "grade_level": "等级",
            "score_reason": "评分理由",
            "evidence": "证据"
        }}
    ],
    "strengths": ["优点1（附证据）", "优点2（附证据）", "优点3（附证据）"],
    "weaknesses": ["不足1（附证据）", "不足2（附证据）"],
    "coherence_analysis": {{
        "overall_coherence_score": 整体连贯性分数,
        "major_issues": ["主要问题1", "主要问题2"]
    }},
    "promise_fulfillment_analysis": {{
        "fulfillment_rate": 承诺兑现率,
        "unfulfilled_promises": ["未兑现的承诺"],
        "partially_fulfilled": ["部分兑现的承诺"],
        "comment": "承诺兑现情况分析"
    }},
    "detailed_evaluation": {{
        "abstract_evaluation": "摘要部分评价（100-150字，评价摘要的完整性、准确性、精炼度，引用具体问题）",
        "introduction_evaluation": "绪论部分评价（150-200字，评价研究背景阐述、文献综述质量、研究目标明确性、创新点表述，引用具体问题）",
        "methodology_evaluation": "方法/设计部分评价（150-200字，评价方法选择的合理性、技术路线的可行性、方法描述的完整性，引用具体问题）",
        "implementation_evaluation": "实现部分评价（150-200字，评价实现方案的完整性、技术细节的充分性、与设计的一致性，引用具体问题）",
        "experiment_evaluation": "实验部分评价（150-200字，评价实验设计的科学性、数据的充分性、结果分析的深度、对比实验的公平性，引用具体问题）",
        "conclusion_evaluation": "结论部分评价（100-150字，评价结论的准确性、展望的合理性、与正文的一致性，引用具体问题）"
    }},
    "section_level_details": [
        {{
            "section_title": "章节标题",
            "content_assessment": "内容评估（80-120字，详细评价该章节的内容质量、深度、与主题的相关性）",
            "key_findings": ["该章节的主要发现或贡献1", "主要发现或贡献2"],
            "specific_issues": ["具体问题1（指出位置和原因）", "具体问题2（指出位置和原因）"],
            "improvement_advice": "针对该章节的具体改进建议（50-80字）"
        }}
    ],
    "improvement_suggestions": [
        {{
            "aspect": "改进方面",
            "current_issue": "当前问题",
            "suggestion": "具体建议",
            "priority": "优先级（高/中/低）"
        }}
    ],
    "overall_comment": "总体评价（200-300字，需引用论文内容）",
    "conclusion": {{
        "overall_comment": "总体评价（200-300字，需引用论文内容）",
        "strengths": ["优势1（附证据）", "优势2（附证据）", "优势3（附证据）"],
        "weaknesses": ["不足1（附证据）", "不足2（附证据）"],
        "improvement_suggestions": [
            {{
                "aspect": "改进方面",
                "current_issue": "当前问题",
                "suggestion": "具体建议",
                "priority": "优先级（高/中/低）"
            }}
        ]
    }}
}}
```"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=10000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        result = safe_json_parse(raw_content)
        
        if "overall_score" in result:
            try:
                result["overall_score"] = float(result["overall_score"])
            except (ValueError, TypeError):
                logger.warning(f"overall_score无法转换为数字: {result.get('overall_score')}")
                result["overall_score"] = 0
        
        result["section_evaluations"] = section_evaluations
        result["coherence_checks"] = coherence_checks
        result["avg_section_score"] = round(avg_section_score, 1)
        result["avg_coherence_score"] = round(avg_coherence_score, 1)
        result["evaluation_method"] = "sectioned_evaluation"
        
        logger.info(f"最终评价生成完成: {result.get('overall_score', 0)}分")
        return result
    
    def evaluate_thesis_sectioned(
        self,
        content: str,
        indicators: Dict = None,
        student_info: Dict = None,
        dimension_weights: Dict = None
    ) -> Dict:
        """
        分段评估论文（完整流程）
        
        Args:
            content: 论文全文内容
            indicators: 评价指标
            student_info: 学生信息
            dimension_weights: 维度权重
            
        Returns:
            完整评估结果
        """
        logger.info("=" * 50)
        logger.info("开始分段评估论文")
        logger.info("=" * 50)
        
        logger.info("Step 1: 识别论文结构...")
        structure = self.identify_thesis_structure(content)
        
        logger.info("Step 2: 提取各章节内容...")
        sections = self.extract_sections(content, structure)
        
        main_works = structure.get("main_works", [])
        
        logger.info("Step 3: 评估各章节...")
        section_evaluations = []
        for i, section in enumerate(sections):
            prev_summary = None
            next_summary = None
            
            if i > 0 and section_evaluations:
                prev_summary = section_evaluations[-1].get("summary", "")
            
            logger.info(f"  评估章节 {i+1}/{len(sections)}: {section.get('title', '')}")
            evaluation = self.evaluate_section(
                section=section,
                prev_section_summary=prev_summary,
                next_section_summary=next_summary,
                indicators=indicators,
                main_works=main_works
            )
            section_evaluations.append(evaluation)
        
        logger.info("Step 4: 检测章节衔接（逻辑衔接）...")
        coherence_checks = []
        for i in range(len(sections) - 1):
            logger.info(f"  检测衔接 {i+1}/{len(sections)-1}: {sections[i].get('title', '')} -> {sections[i+1].get('title', '')}")
            coherence = self.check_section_coherence(
                prev_section=sections[i],
                prev_evaluation=section_evaluations[i],
                next_section=sections[i+1],
                next_evaluation=section_evaluations[i+1],
                main_works=main_works
            )
            coherence_checks.append(coherence)
        
        logger.info("Step 5: 构建承诺-兑现追踪表...")
        promise_tracking = self.build_promise_tracking_table(
            sections=sections,
            section_evaluations=section_evaluations
        )
        
        logger.info("Step 6: 固有评价体系评分...")
        institutional_result = None
        if dimension_weights:
            try:
                institutional_result = self.llm_evaluator.evaluate_institutional_dimensions(
                    submission_content=content,
                    dimension_weights=dimension_weights
                )
            except Exception as e:
                logger.error(f"固有评价体系评分失败: {str(e)}")
        
        logger.info("Step 7: 生成最终评价...")
        final_result = self.generate_final_evaluation(
            structure=structure,
            section_evaluations=section_evaluations,
            coherence_checks=coherence_checks,
            promise_tracking=promise_tracking,
            institutional_result=institutional_result,
            indicators=indicators
        )
        
        if not final_result.get("overall_score") or final_result.get("overall_score", 0) <= 0:
            logger.warning("最终评价overall_score为0，尝试从章节评分恢复...")
            if section_evaluations:
                scores = [e.get("section_score", 0) for e in section_evaluations if e.get("section_score")]
                if scores:
                    recovered = round(sum(scores) / len(scores), 1)
                    logger.info(f"从章节评分恢复: {recovered}分 (基于{len(scores)}个章节)")
                    final_result["overall_score"] = recovered
                    if recovered >= 90:
                        final_result["grade_level"] = "优秀"
                    elif recovered >= 80:
                        final_result["grade_level"] = "良好"
                    elif recovered >= 70:
                        final_result["grade_level"] = "中等"
                    elif recovered >= 60:
                        final_result["grade_level"] = "及格"
                    else:
                        final_result["grade_level"] = "不及格"
                    final_result["score_recovery_note"] = f"LLM最终评分异常(返回0)，已从{len(scores)}个章节评分恢复"
        
        final_result["student_info"] = student_info
        final_result["thesis_structure"] = structure
        final_result["promise_tracking"] = promise_tracking
        
        logger.info("=" * 50)
        logger.info(f"分段评估完成: {final_result.get('overall_score', 0)}分")
        logger.info("=" * 50)
        
        return final_result

"""
增强版PDF提取器 - 借鉴ChatGPT/Claude等大模型的PDF处理方法

特点：
1. 多策略提取：PyMuPDF + pdfplumber + OCR
2. 保留结构信息：标题、段落、列表
3. 智能章节识别：使用正则表达式识别章节
4. 页面级验证：检查每页提取质量
5. 详细日志：记录提取过程
"""

import re
import logging
from typing import Tuple, List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class EnhancedPDFExtractor:
    """增强版PDF提取器"""
    
    CHAPTER_PATTERNS = [
        r'第[一二三四五六七八九十百]+\s*章[^\n]*',
        r'第\d+\s*章[^\n]*',
        r'Chapter\s*\d+[^\n]*',
        r'[一二三四五六七八九十]+[、.．]\s*[^\n]{2,30}',
        r'\d+[、.．]\s*[^\n]{2,30}',
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
    
    def __init__(self, min_text_length: int = 100, enable_ocr: bool = False):
        """
        初始化增强版PDF提取器
        
        Args:
            min_text_length: 最小文本长度阈值
            enable_ocr: 是否启用OCR（需要安装pytesseract和tesseract）
        """
        self.min_text_length = min_text_length
        self.enable_ocr = enable_ocr
        self.extraction_log = []
    
    def extract(self, file_path: str) -> Tuple[str, List[Dict]]:
        """
        提取PDF内容，返回(文本内容, 表格列表)
        
        使用增强的多策略方法：
        1. 优先使用PyMuPDF提取文本（保留结构）
        2. 使用pdfplumber提取表格和补充文本
        3. 如果启用OCR，对图片页面使用OCR
        4. 验证提取质量
        """
        self.extraction_log = []
        text = ""
        tables = []
        
        text, page_texts = self._extract_with_pymupdf_enhanced(file_path)
        
        tables = self._extract_tables_with_pdfplumber(file_path)
        
        if len(text.strip()) < self.min_text_length:
            self._log("warning", f"PyMuPDF提取文本过短({len(text)}字符)，尝试pdfplumber")
            text2 = self._extract_with_pdfplumber_enhanced(file_path)
            if len(text2) > len(text):
                text = text2
        
        if self.enable_ocr and len(text.strip()) < self.min_text_length:
            self._log("info", "文本过短，尝试OCR提取")
            text = self._extract_with_ocr(file_path)
        
        text = self._clean_text_enhanced(text)
        
        text = self._identify_and_mark_chapters(text)
        
        self._validate_extraction(text, page_texts)
        
        return text, tables
    
    def _extract_with_pymupdf_enhanced(self, file_path: str) -> Tuple[str, List[str]]:
        """
        使用PyMuPDF增强提取（保留结构）
        
        Returns:
            (完整文本, 各页文本列表)
        """
        try:
            import fitz
            doc = fitz.open(file_path)
            all_text_parts = []
            page_texts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text_parts = []
                
                try:
                    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                    
                    for block in blocks:
                        if block.get("type") == 0:
                            for line in block.get("lines", []):
                                line_text = ""
                                for span in line.get("spans", []):
                                    text = span.get("text", "")
                                    font_size = span.get("size", 12)
                                    font_flags = span.get("flags", 0)
                                    
                                    is_bold = font_flags & 16
                                    if is_bold and len(text.strip()) > 0:
                                        if self._is_likely_title(text, font_size):
                                            line_text += f"\n【标题】{text}\n"
                                        else:
                                            line_text += text
                                    else:
                                        line_text += text
                                
                                if line_text.strip():
                                    page_text_parts.append(line_text)
                        
                        elif block.get("type") == 1:
                            self._log("info", f"第{page_num+1}页包含图片")
                
                except Exception as e:
                    self._log("warning", f"PyMuPDF增强提取第{page_num+1}页失败: {str(e)}")
                    page_text_parts.append(page.get_text())
                
                page_text = "\n".join(page_text_parts)
                page_texts.append(page_text)
                all_text_parts.append(page_text)
                
                if page_num % 10 == 0:
                    self._log("info", f"已提取{page_num+1}页...")
            
            doc.close()
            full_text = "\n\n".join(all_text_parts)
            self._log("success", f"PyMuPDF增强提取完成: {len(full_text)}字符, {len(page_texts)}页")
            return full_text, page_texts
            
        except ImportError:
            self._log("error", "PyMuPDF未安装")
            return "", []
        except Exception as e:
            self._log("error", f"PyMuPDF增强提取失败: {str(e)}")
            return "", []
    
    def _is_likely_title(self, text: str, font_size: float) -> bool:
        """判断文本是否可能是标题"""
        text = text.strip()
        if not text:
            return False
        
        for pattern in self.CHAPTER_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        if font_size >= 14:
            return True
        
        if len(text) < 50 and not re.search(r'[，。；：！？、]', text):
            return True
        
        return False
    
    def _extract_with_pdfplumber_enhanced(self, file_path: str) -> str:
        """使用pdfplumber增强提取"""
        try:
            import pdfplumber
            text_parts = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text(
                            layout=True,
                            x_tolerance=3,
                            y_tolerance=3
                        )
                        if page_text:
                            text_parts.append(page_text)
                    except Exception as e:
                        self._log("warning", f"pdfplumber提取第{page_num+1}页失败: {str(e)}")
            
            result = "\n\n".join(text_parts)
            self._log("success", f"pdfplumber增强提取完成: {len(result)}字符")
            return result
            
        except ImportError:
            self._log("error", "pdfplumber未安装")
            return ""
        except Exception as e:
            self._log("error", f"pdfplumber增强提取失败: {str(e)}")
            return ""
    
    def _extract_with_ocr(self, file_path: str) -> str:
        """使用OCR提取（需要pytesseract和tesseract）"""
        try:
            import fitz
            from PIL import Image
            import pytesseract
            import io
            
            doc = fitz.open(file_path)
            text_parts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                text_parts.append(text)
                
                if page_num % 5 == 0:
                    self._log("info", f"OCR已处理{page_num+1}页...")
            
            doc.close()
            result = "\n\n".join(text_parts)
            self._log("success", f"OCR提取完成: {len(result)}字符")
            return result
            
        except ImportError as e:
            self._log("error", f"OCR依赖未安装: {str(e)}")
            return ""
        except Exception as e:
            self._log("error", f"OCR提取失败: {str(e)}")
            return ""
    
    def _extract_tables_with_pdfplumber(self, file_path: str) -> List[Dict]:
        """使用pdfplumber提取表格"""
        tables = []
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_tables = page.extract_tables()
                        for table in page_tables:
                            if table and len(table) > 0:
                                cleaned_table = [
                                    [str(cell) if cell else "" for cell in row]
                                    for row in table
                                ]
                                tables.append({
                                    "page": page_num + 1,
                                    "data": cleaned_table
                                })
                    except Exception as e:
                        self._log("warning", f"表格提取第{page_num+1}页失败: {str(e)}")
            
            self._log("info", f"提取到{len(tables)}个表格")
        except ImportError:
            self._log("warning", "pdfplumber未安装，无法提取表格")
        except Exception as e:
            self._log("error", f"表格提取失败: {str(e)}")
        
        return tables
    
    def _clean_text_enhanced(self, text: str) -> str:
        """
        增强版文本清理
        
        改进：
        1. 保留章节标题标记
        2. 智能处理换行
        3. 保留段落结构
        4. 移除重复的封面和摘要
        5. 处理章节间的参考文献
        """
        if not text:
            return ""
        
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        text = re.sub(r'【标题】([^\n]+)\n', r'\n\n【标题】\1\n\n', text)
        
        text = self._remove_duplicate_covers(text)
        
        text = self._clean_references_between_chapters(text)
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('【标题】'):
                cleaned_lines.append(line)
            else:
                line = re.sub(r'[ \t]+', ' ', line)
                cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        return text
    
    def _remove_duplicate_covers(self, text: str) -> str:
        """
        移除重复的封面和摘要
        
        检测模式：
        1. 在参考文献后出现的封面信息
        2. 重复出现的摘要
        """
        cover_patterns = [
            r'硕士学位论文',
            r'本科毕业设计',
            r'毕业设计',
            r'学位论文',
            r'分类号[：:]\s*\S+',
            r'UDC[：:]\s*\S+',
            r'学校代码[：:]\s*\S+',
            r'学号[：:]\s*\S+',
        ]
        
        ref_pattern = r'参考\s*文献'
        ref_matches = list(re.finditer(ref_pattern, text, re.IGNORECASE))
        
        if len(ref_matches) > 1:
            for i, match in enumerate(ref_matches[1:], 1):
                ref_end = match.end()
                
                next_chapter = re.search(r'第[一二三四五六七八九十\d]+\s*章', text[ref_end:], re.IGNORECASE)
                if next_chapter:
                    section_text = text[ref_end:ref_end + next_chapter.start()]
                else:
                    section_text = text[ref_end:ref_end + 2000]
                
                has_cover = False
                for pattern in cover_patterns:
                    if re.search(pattern, section_text, re.IGNORECASE):
                        has_cover = True
                        break
                
                if has_cover:
                    abstract_match = re.search(r'摘\s*要', section_text, re.IGNORECASE)
                    if abstract_match:
                        remove_end = ref_end + abstract_match.start()
                        text = text[:ref_matches[i-1].end()] + "\n\n" + text[remove_end:]
                        break
        
        return text
    
    def _clean_references_between_chapters(self, text: str) -> str:
        """
        清理章节之间的参考文献
        
        如果参考文献后紧跟下一章，则移除参考文献部分
        """
        pattern = r'(参考\s*文献[^\n]*\n(?:.*?\n)*?)(?=\n*第[一二三四五六七八九十\d]+\s*章)'
        
        def replace_func(match):
            return ""
        
        text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)
        
        return text
    
    def _identify_and_mark_chapters(self, text: str) -> str:
        """
        识别并标记章节
        
        在章节标题前添加标记，便于后续处理
        """
        for pattern in self.CHAPTER_PATTERNS:
            text = re.sub(
                f'({pattern})',
                r'\n\n【章节】\1\n',
                text,
                flags=re.IGNORECASE
            )
        
        return text
    
    def _validate_extraction(self, text: str, page_texts: List[str]):
        """验证提取质量"""
        total_chars = len(text)
        
        if total_chars < 1000:
            self._log("warning", f"提取文本过短: {total_chars}字符，可能存在问题")
        
        empty_pages = sum(1 for pt in page_texts if len(pt.strip()) < 50)
        if empty_pages > 0:
            self._log("warning", f"有{empty_pages}页内容过短或为空")
        
        chapter_count = len(re.findall(r'【章节】', text))
        title_count = len(re.findall(r'【标题】', text))
        
        self._log("info", f"提取统计: {total_chars}字符, {chapter_count}个章节标记, {title_count}个标题标记")
    
    def _log(self, level: str, message: str):
        """记录日志"""
        log_entry = f"[{level.upper()}] {message}"
        self.extraction_log.append(log_entry)
        
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
    
    def get_extraction_log(self) -> List[str]:
        """获取提取日志"""
        return self.extraction_log
    
    def extract_with_metadata(self, file_path: str) -> Dict:
        """
        提取PDF内容，包含元数据和日志
        
        Returns:
            {
                "text": "文本内容",
                "tables": [...],
                "metadata": {...},
                "log": [...]
            }
        """
        text, tables = self.extract(file_path)
        
        metadata = {
            "char_count": len(text),
            "table_count": len(tables),
            "chapter_count": len(re.findall(r'【章节】', text)),
            "title_count": len(re.findall(r'【标题】', text)),
        }
        
        try:
            import fitz
            doc = fitz.open(file_path)
            metadata["page_count"] = len(doc)
            doc.close()
        except:
            metadata["page_count"] = 0
        
        return {
            "text": text,
            "tables": tables,
            "metadata": metadata,
            "log": self.extraction_log
        }


def extract_pdf_enhanced(file_path: str, enable_ocr: bool = False) -> str:
    """
    便捷函数：使用增强方法提取PDF文本内容
    
    Args:
        file_path: PDF文件路径
        enable_ocr: 是否启用OCR
        
    Returns:
        提取的文本内容
    """
    extractor = EnhancedPDFExtractor(enable_ocr=enable_ocr)
    text, _ = extractor.extract(file_path)
    return text

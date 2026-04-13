"""
PDF提取器模块 - 多库组合策略提取PDF内容

支持：
1. PyMuPDF (fitz) - 对中文支持最好
2. pdfplumber - 支持表格提取
3. pypdf/PyPDF2 - 备用方案
"""

import re
import logging
from typing import Tuple, List, Dict, Optional

logger = logging.getLogger(__name__)


class PDFExtractor:
    """增强版PDF提取器，使用多库组合策略"""
    
    def __init__(self, min_text_length: int = 50):
        self.min_text_length = min_text_length
    
    def extract(self, file_path: str) -> Tuple[str, List[Dict]]:
        """
        提取PDF内容，返回(文本内容, 表格列表)
        
        使用多库组合策略：
        1. 优先使用PyMuPDF提取文本（对中文支持最好）
        2. 使用pdfplumber提取表格
        3. 如果文本太短，尝试其他方法
        """
        text = ""
        tables = []
        
        text = self._extract_with_pymupdf(file_path)
        
        tables = self._extract_tables_with_pdfplumber(file_path)
        
        if len(text.strip()) < self.min_text_length:
            text = self._extract_with_pdfplumber(file_path)
        
        if len(text.strip()) < self.min_text_length:
            text = self._extract_with_pypdf(file_path)
        
        text = self._clean_text(text)
        
        return text, tables
    
    def _extract_with_pymupdf(self, file_path: str) -> str:
        """使用PyMuPDF提取文本（对中文支持最好）"""
        try:
            import fitz
            doc = fitz.open(file_path)
            text_parts = []
            
            for page_num, page in enumerate(doc):
                try:
                    blocks = page.get_text("blocks")
                    for block in blocks:
                        if len(block) >= 5 and block[6] == 0:
                            text_parts.append(block[4])
                except Exception as e:
                    logger.warning(f"PyMuPDF提取第{page_num+1}页失败: {str(e)}")
                    text_parts.append(page.get_text())
            
            doc.close()
            result = "\n".join(text_parts)
            logger.info(f"PyMuPDF提取成功，共{len(result)}字符")
            return result
        except ImportError:
            logger.warning("PyMuPDF未安装，跳过此方法")
            return ""
        except Exception as e:
            logger.error(f"PyMuPDF提取失败: {str(e)}")
            return ""
    
    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """使用pdfplumber提取文本"""
        try:
            import pdfplumber
            text_parts = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception as e:
                        logger.warning(f"pdfplumber提取第{page_num+1}页失败: {str(e)}")
            
            result = "\n".join(text_parts)
            logger.info(f"pdfplumber提取成功，共{len(result)}字符")
            return result
        except ImportError:
            logger.warning("pdfplumber未安装，跳过此方法")
            return ""
        except Exception as e:
            logger.error(f"pdfplumber提取失败: {str(e)}")
            return ""
    
    def _extract_with_pypdf(self, file_path: str) -> str:
        """使用pypdf/PyPDF2提取文本（备用方案）"""
        text_parts = []
        
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            logger.info(f"pypdf提取成功，共{len(''.join(text_parts))}字符")
        except ImportError:
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                logger.info(f"PyPDF2提取成功，共{len(''.join(text_parts))}字符")
            except ImportError:
                logger.warning("pypdf和PyPDF2都未安装")
            except Exception as e:
                logger.error(f"PyPDF2提取失败: {str(e)}")
        except Exception as e:
            logger.error(f"pypdf提取失败: {str(e)}")
        
        return "\n".join(text_parts)
    
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
                                    [cell if cell else "" for cell in row]
                                    for row in table
                                ]
                                tables.append({
                                    "page": page_num + 1,
                                    "data": cleaned_table
                                })
                    except Exception as e:
                        logger.warning(f"pdfplumber提取第{page_num+1}页表格失败: {str(e)}")
            
            logger.info(f"pdfplumber提取到{len(tables)}个表格")
        except ImportError:
            logger.warning("pdfplumber未安装，无法提取表格")
        except Exception as e:
            logger.error(f"表格提取失败: {str(e)}")
        
        return tables
    
    def _clean_text(self, text: str) -> str:
        """
        智能清理文本，保留可读性
        
        改进点：
        1. 移除不可打印字符
        2. 统一换行符
        3. 保留段落结构（双换行）
        4. 智能处理行内多余空白
        """
        if not text:
            return ""
        
        text = ''.join(c if c.isprintable() or c in '\n\t' else '' for c in text)
        
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            line = re.sub(r'[ \t]+', ' ', line)
            cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    def extract_with_metadata(self, file_path: str) -> Dict:
        """
        提取PDF内容，包含元数据
        
        Returns:
            {
                "text": "文本内容",
                "tables": [...],
                "metadata": {
                    "page_count": 页数,
                    "char_count": 字符数,
                    "extraction_method": "使用的方法"
                }
            }
        """
        text, tables = self.extract(file_path)
        
        metadata = {
            "char_count": len(text),
            "table_count": len(tables),
            "extraction_methods": []
        }
        
        try:
            import fitz
            doc = fitz.open(file_path)
            metadata["page_count"] = len(doc)
            metadata["extraction_methods"].append("pymupdf")
            doc.close()
        except:
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    metadata["page_count"] = len(pdf.pages)
                    metadata["extraction_methods"].append("pdfplumber")
            except:
                metadata["page_count"] = 0
        
        return {
            "text": text,
            "tables": tables,
            "metadata": metadata
        }


def extract_pdf_content(file_path: str) -> str:
    """
    便捷函数：提取PDF文本内容
    
    Args:
        file_path: PDF文件路径
        
    Returns:
        提取的文本内容
    """
    extractor = PDFExtractor()
    text, _ = extractor.extract(file_path)
    return text


def extract_pdf_with_tables(file_path: str) -> Tuple[str, List[Dict]]:
    """
    便捷函数：提取PDF文本和表格
    
    Args:
        file_path: PDF文件路径
        
    Returns:
        (文本内容, 表格列表)
    """
    extractor = PDFExtractor()
    return extractor.extract(file_path)

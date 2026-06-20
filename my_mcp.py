from mcp.server.fastmcp import FastMCP
import os

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, Cm
except ImportError:
    print("请先安装依赖: pip install python-docx")
    exit(1)

# 1. 初始化一个名为 TongjiFormatValidator 的 MCP 服务器
mcp = FastMCP("TongjiFormatValidator")

# ==========================================
# 核心安全机制：防止 Style 继承导致的误判辅助函数
# ==========================================

def get_effective_alignment(para):
    """回溯获取段落的实际对齐方式（支持样式继承）"""
    if para.alignment is not None:
        return para.alignment
    style = para.style
    while style is not None:
        if hasattr(style, 'paragraph_format') and style.paragraph_format.alignment is not None:
            return style.paragraph_format.alignment
        style = getattr(style, 'base_style', None)
    return None

def check_has_indent(para):
    """
    深度检测是否有首行缩进。
    兼容绝对长度(Pt/Cm)与 Word 特有的相对字符缩进(firstLineChars)，彻底解决误报。
    """
    # 1. 检查段落直接设置的绝对缩进
    if para.paragraph_format.first_line_indent is not None:
        return para.paragraph_format.first_line_indent > 0
        
    # 2. 沿样式树向上追溯绝对缩进
    style = para.style
    while style is not None:
        if hasattr(style, 'paragraph_format') and style.paragraph_format.first_line_indent is not None:
            return style.paragraph_format.first_line_indent > 0
        style = getattr(style, 'base_style', None)
        
    # 3. 终极回溯：解析底层 XML，检查是否使用了 Word 的 "2 字符" 智能缩进
    try:
        if para._p.pPr is not None and para._p.pPr.ind is not None:
            if para._p.pPr.ind.firstLine is not None or para._p.pPr.ind.firstLineChars is not None:
                return True
    except AttributeError:
        pass
        
    try:
        style = para.style
        while style is not None:
            if hasattr(style, '_element') and hasattr(style._element, 'pPr') and style._element.pPr is not None:
                if style._element.pPr.ind is not None:
                    if style._element.pPr.ind.firstLine is not None or style._element.pPr.ind.firstLineChars is not None:
                        return True
            style = getattr(style, 'base_style', None)
    except AttributeError:
        pass
        
    return False

def get_effective_line_spacing(para):
    """回溯获取实际行距"""
    if para.paragraph_format.line_spacing is not None:
        return para.paragraph_format.line_spacing
    style = para.style
    while style is not None:
        if hasattr(style, 'paragraph_format') and style.paragraph_format.line_spacing is not None:
            return style.paragraph_format.line_spacing
        style = getattr(style, 'base_style', None)
    return None

def get_effective_font_size(run, para):
    """回溯获取 Run 的实际字号"""
    if run.font.size is not None:
        return run.font.size
    style = para.style
    while style is not None:
        if hasattr(style, 'font') and style.font.size is not None:
            return style.font.size
        style = getattr(style, 'base_style', None)
    return None

def get_effective_font_bold(run, para):
    """回溯获取是否加粗"""
    if run.font.bold is not None:
        return run.font.bold
    style = para.style
    while style is not None:
        if hasattr(style, 'font') and style.font.bold is not None:
            return style.font.bold
        style = getattr(style, 'base_style', None)
    return False


# 2. 注册为 MCP 工具
@mcp.tool()
def check_thesis_format(file_path: str) -> str:
    """
    读取并校验指定 Word 文档的格式是否符合同济大学毕业论文规范。
    已修正因样式继承、字符缩进引发的误报 Bug。
    """
    if not os.path.exists(file_path):
        return f"❌ 错误：未找到文件 {file_path}，请检查路径是否正确。"
    
    if not file_path.endswith('.docx'):
        return "❌ 错误：工具目前仅支持 .docx 格式的 Word 文档，请先转换格式。"
    
    try:
        doc = Document(file_path)
    except Exception as e:
        return f"❌ 加载文档失败。错误信息: {str(e)}"

    report = ["# 🎓 同济大学毕业设计(论文)格式校验报告 (精准版)\n"]
    report.append(f"**校验文件:** `{file_path}`\n")
    report.append("---")
    
    errors = []
    
    # 模块一：页边距与页面设置校验
    for s_idx, section in enumerate(doc.sections):
        top = round(section.top_margin.cm, 2) if section.top_margin else None
        bottom = round(section.bottom_margin.cm, 2) if section.bottom_margin else None
        left = round(section.left_margin.cm, 2) if section.left_margin else None
        right = round(section.right_margin.cm, 2) if section.right_margin else None
        
        margin_errors = []
        if top and abs(top - 2.5) > 0.1: margin_errors.append(f"上边距当前 {top}cm (标准: 2.5cm)")
        if bottom and abs(bottom - 2.5) > 0.1: margin_errors.append(f"下边距当前 {bottom}cm (标准: 2.5cm)")
        if left and left < 2.5: margin_errors.append(f"左边距当前 {left}cm (标准: 建议不小于 2.5cm)")
        if right and abs(right - 2.5) > 0.1: margin_errors.append(f"右边距当前 {right}cm (标准: 2.5cm)")
        
        if margin_errors:
            errors.append(f"- **第 {s_idx+1} 节页面设置**: {', '.join(margin_errors)}")

    # 模块二：段落核心逻辑遍历
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue  
            
        style_name = para.style.name
        
        # --- 1. 一级标题校验 ---
        if style_name.startswith('Heading 1') or style_name == '标题 1':
            align = get_effective_alignment(para)
            if align != WD_ALIGN_PARAGRAPH.CENTER and align is not None:
                errors.append(f"- **段落 {i+1}** (一级标题 '{text[:12]}...'): **未居中对齐**。")
            
            h1_size_err, h1_bold_err = False, False
            for run in para.runs:
                if run.text.strip():
                    size = get_effective_font_size(run, para)
                    bold = get_effective_font_bold(run, para)
                    if size and size != Pt(14): 
                        h1_size_err = True
                    if not bold:
                        h1_bold_err = True
            if h1_size_err: errors.append(f"- **段落 {i+1}** (一级标题): 字号错误，应为**四号(14磅)**。")
            if h1_bold_err: errors.append(f"- **段落 {i+1}** (一级标题): 未加粗。")
                         
        # --- 2. 二级标题校验 ---
        elif style_name.startswith('Heading 2') or style_name == '标题 2':
            align = get_effective_alignment(para)
            if align == WD_ALIGN_PARAGRAPH.CENTER:
                errors.append(f"- **段落 {i+1}** (二级标题 '{text[:12]}...'): 应为**左对齐**，不应居中。")
            
            h2_size_err, h2_bold_err = False, False
            for run in para.runs:
                if run.text.strip():
                    size = get_effective_font_size(run, para)
                    bold = get_effective_font_bold(run, para)
                    if size and size != Pt(12): 
                        h2_size_err = True
                    if not bold:
                        h2_bold_err = True
            if h2_size_err: errors.append(f"- **段落 {i+1}** (二级标题): 字号错误，应为**小四(12磅)**。")
            if h2_bold_err: errors.append(f"- **段落 {i+1}** (二级标题): 未加粗。")

        # --- 3. 正文校验 ---
        elif style_name == 'Normal' or style_name == '正文':
            # 使用新升级的复合缩进检测算法
            if not check_has_indent(para):
                if text.startswith("    ") or text.startswith("  "):
                    errors.append(f"- **段落 {i+1}** (正文): 使用了空格敲出的假缩进，请在 Word 中右键段落设置真正的**首行缩进 2 字符**。")
                else:
                    errors.append(f"- **段落 {i+1}** (正文 '{text[:12]}...'): 疑似**无首行缩进**。")
            
            # 行距检测（安全容错模式）
            ls = get_effective_line_spacing(para)
            if ls is not None:
                if isinstance(ls, Pt) and abs(ls - Pt(18)) > 0.1:
                    errors.append(f"- **段落 {i+1}** (正文): 行距错误，当前为固定值 {ls.pt} 磅 (规范要求: **固定值18磅**)。")
                elif not isinstance(ls, Pt):
                    errors.append(f"- **段落 {i+1}** (正文): 行距非固定值，当前为多倍行距 (规范要求: **固定值18磅**)。")

            # 字号检测（安全容错模式：若完全未显式定义则默认遵循全局，不报错）
            body_size_err = False
            for run in para.runs:
                size = get_effective_font_size(run, para)
                if run.text.strip() and size and size != Pt(10.5):
                    body_size_err = True
            if body_size_err: 
                errors.append(f"- **段落 {i+1}** (正文): 内部文本字号错误，应统一为**五号(10.5磅)**。")

        # --- 4. 图表题辅助校验 ---
        if text.startswith("图") or text.startswith("表"):
            if "1." in text or "2." in text or "-" in text or " " in text: 
                align = get_effective_alignment(para)
                if align != WD_ALIGN_PARAGRAPH.CENTER and align is not None:
                    errors.append(f"- **段落 {i+1}** (疑似图表题 '{text[:12]}...'): 强特征图表标题**未居中对齐**。")

    # 3. 生成报告结果
    if errors:
        report.append("## 🚨 发现的格式问题：")
        report.extend(errors)
        report.append("\n*请根据上述提示返回 Word 文档中进行修改。*")
    else:
        report.append("## ✅ 基础格式检查通过！")
        report.append("未发现明显的页边距、多级标题对齐、字号、正文缩进及行距错误。")
        
    return "\n".join(report)

if __name__ == "__main__":
    mcp.run()
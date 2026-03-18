#!/usr/bin/env python3
"""
修复项目中的相对导入问题
"""

import os
import re

def fix_relative_imports_in_file(file_path):
    """修复单个文件中的相对导入路径"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 替换 from .xxx import 为 from xxx import（同级目录）
    content = re.sub(r'from \.([a-zA-Z_][a-zA-Z0-9_]*) import', r'from \1 import', content)
    
    # 替换 from ..xxx import 为 from xxx import（上级目录）
    content = re.sub(r'from \.\.([a-zA-Z_][a-zA-Z0-9_]*) import', r'from \1 import', content)
    
    # 替换 from ...xxx import 为 from xxx import（上上级目录）
    content = re.sub(r'from \.\.\.([a-zA-Z_][a-zA-Z0-9_]*) import', r'from \1 import', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed relative imports: {file_path}")
        return True
    return False

def main():
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    
    fixed_files = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_relative_imports_in_file(file_path):
                    fixed_files.append(file_path)
    
    print(f"\nTotal fixed files: {len(fixed_files)}")
    for f in fixed_files:
        print(f"  - {f}")

if __name__ == "__main__":
    main()

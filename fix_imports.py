#!/usr/bin/env python3
"""
修复项目中的导入路径问题
"""

import os
import re

def fix_imports_in_file(file_path):
    """修复单个文件中的导入路径"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换 from src.xxx import 为 from xxx import
    original_content = content
    content = re.sub(r'from src\.', 'from ', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
        return True
    return False

def main():
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    
    fixed_files = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_imports_in_file(file_path):
                    fixed_files.append(file_path)
    
    print(f"\nTotal fixed files: {len(fixed_files)}")
    for f in fixed_files:
        print(f"  - {f}")

if __name__ == "__main__":
    main()

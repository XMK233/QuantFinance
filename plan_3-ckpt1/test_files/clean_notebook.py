#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
清理 Jupyter Notebook 文件中的 cell output
使用方法: python clean_notebook.py <notebook_path.ipynb>
"""

import json
import sys
import os

def clean_notebook(notebook_path):
    """清理 notebook 文件中的输出内容"""
    
    # 备份原文件
    backup_path = notebook_path + '.backup'
    if not os.path.exists(backup_path):
        import shutil
        shutil.copy2(notebook_path, backup_path)
        print(f"📁 已创建备份: {backup_path}")
    
    # 读取 notebook 文件
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    # 清理每个 cell
    cells_cleaned = 0
    for cell in notebook['cells']:
        # 清理代码 cell 的输出
        if cell['cell_type'] == 'code':
            if 'outputs' in cell and cell['outputs']:
                cell['outputs'] = []
                cells_cleaned += 1
            if 'execution_count' in cell:
                cell['execution_count'] = None
    
    # 保存清理后的文件
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 已清理 {cells_cleaned} 个代码 cell 的输出")
    print(f"💾 已保存清理后的文件: {notebook_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        notebook_path = sys.argv[1]
        if os.path.exists(notebook_path):
            clean_notebook(notebook_path)
        else:
            print(f"❌ 文件不存在: {notebook_path}")
    else:
        print("使用方法: python clean_notebook.py <notebook_path.ipynb>")
        print("示例: python clean_notebook.py 3.0-runner.ipynb")
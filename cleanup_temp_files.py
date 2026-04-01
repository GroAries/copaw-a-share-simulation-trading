#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理临时文件
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent

# 要删除的临时文件
temp_files = [
    "check_dependencies.py",
    "rename_strategy_files.py",
    "multi_strategy_test.py",  # 根目录的这个是临时的
    "strategies/trading_skill_002_v2_2.py"
]

for filename in temp_files:
    file_path = BASE_DIR / filename
    if file_path.exists():
        print(f"删除 {file_path}")
        file_path.unlink()
    else:
        print(f"{file_path} 不存在，跳过")

print("完成")

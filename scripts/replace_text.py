#!/usr/bin/env python3
 -*- coding: utf-8 -*-
"""
批量替换文本工具
"""
import sys

def replace_in_file(input_path, output_path):
    """批量替换文本"""
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 批量替换
    replacements = [
        ("Compact-Check", "兼容性测试（Compatibility Check）"),
        ("compact-check", "compatibility-check"),
        ("紧凑检查", "兼容性测试"),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ 已创建: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python3 replace_text.py <输入文件> <输出文件>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    replace_in_file(input_path, output_path)

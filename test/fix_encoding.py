# -*- coding: utf-8 -*-
import sys

# 修复 sync.py 文件
with open('app/api/v1/endpoints/sync.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查三引号数量
if content.count('"""') % 2 != 0:
    print('Warning: Unmatched triple quotes')

# 尝试编译
try:
    compile(content, 'sync.py', 'exec')
    print('Syntax OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.text}')
    print('Trying to fix...')
    # 如果无法编译，尝试恢复备份

print('File length:', len(content))
print('Done')

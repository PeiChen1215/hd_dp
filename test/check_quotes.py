# -*- coding: utf-8 -*-
with open('app/api/v1/endpoints/sync.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if '"""' in line:
        print(f'{i}: {line.rstrip()}')

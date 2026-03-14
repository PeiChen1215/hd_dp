#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from app.agents.wanji_agent import WanjiAgent
from unittest.mock import MagicMock

mock_db = MagicMock()
agent = WanjiAgent(mock_db, 'test-user')

test_cases = [
    '明天下午3点',
    '明天下午3:00',
    '明天15:00',
    '明天3点',
    '今天下午2点',
    '明天上午9点',
    '明天晚上8点',
]

print('时间解析修复测试:')
print('='*60)
for case in test_cases:
    try:
        result = agent._parse_time(case)
        print(f'{case:20s} -> {result.strftime("%Y-%m-%d %H:%M")}')
    except Exception as e:
        print(f'{case:20s} -> 错误: {e}')

print('='*60)
print('验证: "明天下午3点" 应该显示 15:00，不是 16:00')

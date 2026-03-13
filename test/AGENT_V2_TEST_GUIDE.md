# 万机 Agent V2 本地测试指南

## 🚀 快速开始

### 1. 启动后端服务

确保后端服务已启动：

```bash
cd D:\Gitproject\ChronoSync

# 激活虚拟环境
.venv\Scripts\activate

# 执行数据库迁移（如果是首次运行）
alembic upgrade head

# 启动后端服务
uvicorn app.main:app --reload
```

### 2. 运行快速测试（推荐先跑这个）

打开新的终端窗口：

```bash
cd D:\Gitproject\ChronoSync
.venv\Scripts\activate

# 运行快速测试（约 30 秒）
python test/test_agent_v2_quick.py
```

### 3. 运行完整测试

如果快速测试通过，运行完整测试：

```bash
# 运行完整测试（约 2-3 分钟）
python test/test_agent_v2_local.py
```

---

## 📋 测试内容说明

### 快速测试 (`test_agent_v2_quick.py`)

| 测试项 | 说明 | 预计时间 |
|-------|------|---------|
| 健康检查 | 检查后端服务是否正常 | < 1s |
| 用户注册/登录 | 创建测试用户并获取 Token | < 2s |
| Agent 创建日程 | "帮我安排明天下午3点的会议" | 5-10s |
| Agent 查询日程 | "明天有什么安排" | 5-10s |
| **多日查询** ⭐ | "最近3天有什么安排" (V2新功能) | 5-10s |
| **对话历史 API** ⭐ | 获取对话记录 (V2新功能) | < 1s |
| 清空对话历史 | 清空测试数据 | < 1s |

### 完整测试 (`test_agent_v2_local.py`)

包含快速测试的所有内容，外加：

| 测试项 | 说明 |
|-------|------|
| 增强时间解析 | 测试大后天、N天后、本周/下周等 |
| 建议时段确认 | 测试冲突检测和建议确认流程 |
| Agent 备忘录 | 创建和查询备忘录 |
| Agent 统计 | 统计日程和备忘录数量 |

---

## 🔧 常见问题

### 1. "无法连接到本地服务器"

**原因**: 后端服务未启动

**解决**:
```bash
# 检查 8000 端口是否被占用
netstat -ano | findstr :8000

# 启动后端
uvicorn app.main:app --reload --port 8000
```

### 2. "Agent 创建失败" 或超时

**原因**: DASHSCOPE_API_KEY 未配置或无效

**解决**:
1. 检查 `.env` 文件：
```bash
DASHSCOPE_API_KEY=sk-49141e05df7f4584966fac0f8cddbb7d
DASHSCOPE_MODEL=deepseek-v3
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
```

2. 检查环境变量是否加载：
```bash
python -c "from app.core.config import settings; print(settings.DASHSCOPE_API_KEY[:10])"
```

### 3. "对话历史 API 失败"

**原因**: 数据库迁移未执行

**解决**:
```bash
alembic upgrade head
```

### 4. 测试卡住不动

**原因**: Agent 调用 LLM 需要较长时间

**解决**: 这是正常的，LLM 调用通常需要 5-30 秒，请耐心等待。

---

## 📊 测试结果解读

### 快速测试通过标准

```
✅ 健康检查
✅ 用户注册
✅ 用户登录
✅ Agent 创建日程
✅ Agent 查询日程
✅ 多日查询          <-- V2 新功能
✅ 对话历史 API      <-- V2 新功能
✅ 清空对话历史

🎉 快速测试完成！
```

如果全部显示 ✅，说明核心功能正常，可以部署！

### 完整测试通过标准

```
总计: 12/12 通过 (100.0%)
🎉 所有测试通过！Agent V2 功能正常

可以部署到云端了！
```

---

## 🚀 部署到云端

测试通过后，按以下步骤部署：

### 1. 提交代码

```bash
git add .
git commit -m "feat: 集成万机 Agent V2，支持多日查询和建议确认"
git push origin main
```

### 2. 服务器部署

SSH 到服务器执行：

```bash
cd /path/to/ChronoSync

# 拉取代码
git pull origin main

# 执行数据库迁移
alembic upgrade head

# 安装依赖（如果有新依赖）
pip install -r requirements.txt

# 重启服务
sudo systemctl restart chronosync
# 或者
pkill -f uvicorn
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### 3. 验证部署

```bash
# 在服务器本地测试
curl http://localhost:8000/health

# 测试 Agent 接口
curl -X POST http://localhost:8000/api/v1/agent/process \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "帮我安排明天下午3点的会议"}'
```

---

## 📝 测试脚本说明

| 脚本 | 用途 | 运行时间 |
|------|------|---------|
| `test_agent_v2_quick.py` | 快速验证核心功能 | ~30秒 |
| `test_agent_v2_local.py` | 完整功能测试 | ~2-3分钟 |

---

## 🎯 测试覆盖的功能

### V1 已有功能（回归测试）
- ✅ 基础 Agent 对话
- ✅ 创建/查询/修改/删除日程
- ✅ 创建/查询备忘录
- ✅ 统计信息

### V2 新增功能（重点测试）
- ✅ **多日/范围查询**: "这两天"、"最近3天"、"本周"
- ✅ **建议时段确认**: 冲突时返回建议，用户确认后自动应用
- ✅ **增强时间解析**: 大后天、N天后/前、本周/下周
- ✅ **对话历史持久化**: API 获取和清空对话记录

---

## 💡 调试技巧

### 查看详细日志

修改 `app/agents/wanji_agent.py` 中的日志级别：

```python
# 在 process 方法中添加打印
print(f"[DEBUG] 用户输入: {text}")
print(f"[DEBUG] Agent 回复: {reply}")
```

### 手动测试 API

使用 curl 或 Postman：

```bash
# 1. 登录获取 Token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test123"}' | jq -r .access_token)

# 2. 调用 Agent
curl -X POST http://localhost:8000/api/v1/agent/process \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "明天有什么安排"}'

# 3. 获取对话历史
curl http://localhost:8000/api/v1/agent/conversations \
  -H "Authorization: Bearer $TOKEN"
```

---

**最后更新**: 2026-03-13  
**测试脚本版本**: v1.0.0

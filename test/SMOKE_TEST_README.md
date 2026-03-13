# ChronoSync 烟雾测试指南

## 📋 测试文件说明

| 文件 | 用途 | 测试内容 |
|------|------|---------|
| `smoke_test.py` | 基础 API 测试 | 注册、登录、日程 CRUD、备忘录 CRUD |
| `smoke_test_sync_ws.py` | 同步 + WebSocket 测试 | WebSocket 连接、实时推送、增量同步、冲突检测 |
| `run_smoke_test.bat` | Windows 一键运行脚本 | 自动检查依赖、检查服务、运行测试 |

---

## 🚀 快速开始

### 方式一：Windows 一键运行（推荐）

1. **启动后端服务**
   ```bash
   uvicorn app.main:app --reload
   ```

2. **双击运行测试脚本**
   ```
   run_smoke_test.bat
   ```

3. **选择测试类型**
   - 选项 1: 基础 API 测试
   - 选项 2: WebSocket + 同步测试
   - 选项 3: 运行全部测试

### 方式二：命令行运行

#### 1. 安装依赖

```bash
pip install httpx websockets
```

#### 2. 确保后端服务运行

```bash
# 在另一个终端窗口运行
uvicorn app.main:app --reload
```

#### 3. 运行测试

```bash
# 基础 API 测试
python smoke_test.py

# WebSocket + 同步测试
python smoke_test_sync_ws.py

# 两个都运行
python smoke_test.py && python smoke_test_sync_ws.py
```

---

## 🧪 测试内容详解

### smoke_test.py - 基础 API 测试

```
[1/7] 健康检查
[2/7] 用户注册
[3/7] 用户登录
[4/7] 创建日程
[5/7] 查询日程列表
[6/7] 创建备忘录
[7/7] 查询备忘录列表
```

**预期结果**: 所有测试通过，最后自动清理测试数据

---

### smoke_test_sync_ws.py - WebSocket + 同步测试

```
[1/9] 健康检查（含 WebSocket 状态）
[2/9] 注册登录
[3/9] WebSocket 连接与心跳
       - 连接 WebSocket
       - 等待并响应服务器 ping
[4/9] WebSocket 实时推送
       - 建立监听连接
       - 通过 HTTP 创建日程
       - 验证收到 WebSocket 推送
       - 发送消息确认 (ack)
[5/9] 同步推送-创建
       - 推送本地新建的日程
       - 验证返回 server_id
[6/9] 同步拉取
       - 拉取自指定时间的变更
       - 验证返回数据格式
[7/9] 同步推送-更新
       - 更新已存在的日程
       - 验证更新成功
[8/9] 冲突检测
       - 模拟多设备同时修改
       - 验证冲突检测
       - 测试冲突解决
[9/9] 全量同步
       - 获取服务器全量数据
```

**预期结果**: 所有测试通过，WebSocket 连接正常，同步功能工作正常

---

## 📊 测试结果示例

### 成功示例

```
============================================================
 ChronoSync WebSocket + 同步功能 烟雾测试
============================================================
测试地址: http://localhost:8000
WebSocket: ws://localhost:8000
测试用户: smoke_ws_a1b2c3d4

[1/9] 健康检查
--------------------------------------------------
ℹ️  WebSocket 在线用户: 0
ℹ️  WebSocket 连接数: 0
✅ 健康检查通过

[2/9] 注册登录
--------------------------------------------------
ℹ️  注册用户: smoke_ws_a1b2c3d4
✅ 用户注册成功, ID: 550e8400-e29b-41d4-a716-446655440000
✅ 登录成功, Token: eyJhbGciOiJIUzI1NiIsInR5cCI6...

[3/9] WebSocket 连接与心跳
--------------------------------------------------
ℹ️  连接 WebSocket: ws://localhost:8000/api/v1/ws?token=...
✅ WebSocket 连接成功
ℹ️  服务器时间: 2026-03-08T20:30:00Z
✅ 收到服务器心跳 (ping)
✅ 回复心跳 (pong)

[4/9] WebSocket 实时推送
--------------------------------------------------
✅ 监听端连接成功
ℹ️  通过 HTTP 创建日程...
✅ 日程创建成功: 550e8400-e29b-41d4-a716-446655440001
✅ 收到 WebSocket 推送: event_created
✅ 发送消息确认 (ack)

...

============================================================
 测试结果汇总
============================================================
✅ 通过: 9/9
❌ 失败: 0/9

🎉 所有测试通过！WebSocket + 同步功能工作正常
============================================================
```

### 失败示例

```
[3/9] WebSocket 连接与心跳
--------------------------------------------------
ℹ️  连接 WebSocket: ws://localhost:8000/api/v1/ws?token=...
❌ 测试失败: 连接失败: Connection refused

测试结果汇总
============================================================
✅ 通过: 2/9
❌ 失败: 1/9

⚠️  1 个测试失败，请检查日志
============================================================
```

---

## 🔧 故障排除

### 问题 1: 后端服务未运行

**现象**:
```
❌ 后端服务未运行，请先启动后端：
   uvicorn app.main:app --reload
```

**解决**:
```bash
# 在另一个终端启动后端
uvicorn app.main:app --reload
```

---

### 问题 2: 缺少依赖

**现象**:
```
ModuleNotFoundError: No module named 'websockets'
```

**解决**:
```bash
pip install httpx websockets
```

---

### 问题 3: WebSocket 连接失败

**现象**:
```
❌ WebSocket 连接失败: Connection refused
```

**排查步骤**:
1. 确认后端服务已启动
2. 确认 URL 正确（`ws://` 不是 `http://`）
3. 检查后端日志是否有 WebSocket 相关错误
4. 确认端口 8000 未被占用

---

### 问题 4: 测试超时

**现象**:
```
❌ 等待 WebSocket 推送超时 (5秒)
```

**可能原因**:
1. WebSocket 连接未正确建立
2. 后端未正确发送推送消息
3. 网络延迟

**解决**:
- 检查后端日志
- 增加超时时间（修改代码中的 `timeout=5.0`）
- 确保数据库和 WebSocket 管理器正常初始化

---

### 问题 5: 冲突检测未触发

**现象**:
```
❌ 期望冲突但未触发，状态: success
```

**可能原因**:
- `last_synced_at` 时间设置不正确
- 时间精度问题

**调试**:
查看后端日志中的冲突检测逻辑输出

---

## 📝 手动测试 WebSocket

如果你想手动测试 WebSocket 连接：

```bash
# 1. 获取 token（先运行 smoke_test.py 或手动注册登录）
# 假设 token 是: eyJhbGciOiJIUzI1NiIsInR5cCI6...

# 2. 使用 wscat 连接
npx wscat -c "ws://localhost:8000/api/v1/ws?token=eyJhbGciOiJIUzI1NiIsInR5cCI6...&device_id=manual_test"

# 3. 连接成功后，你会收到:
Connected (press CTRL+C to quit)
< {"type": "connected", "data": {"server_time": "...", "device_id": "manual_test"}}

# 4. 等待 ping，回复 pong:
< {"type": "ping", "data": {"timestamp": "..."}}
> {"type": "pong", "data": {"timestamp": "2026-03-08T12:00:00Z"}}

# 5. 在另一个窗口创建日程，观察推送:
< {"type": "event_created", "msg_id": "...", "data": {"title": "..."}, ...}

# 6. 发送确认:
> {"type": "ack", "data": {"msg_id": "..."}}
```

---

## 🎯 测试覆盖清单

| 功能 | smoke_test.py | smoke_test_sync_ws.py |
|------|---------------|----------------------|
| 健康检查 | ✅ | ✅ |
| 用户注册/登录 | ✅ | ✅ |
| 日程 CRUD | ✅ | ✅ |
| 备忘录 CRUD | ✅ | ⚪ |
| WebSocket 连接 | ⚪ | ✅ |
| WebSocket 心跳 | ⚪ | ✅ |
| 实时推送 | ⚪ | ✅ |
| 增量推送 (push) | ⚪ | ✅ |
| 增量拉取 (pull) | ⚪ | ✅ |
| 冲突检测 | ⚪ | ✅ |
| 全量同步 | ⚪ | ✅ |

---

## 🔄 持续集成建议

在 CI/CD 流程中添加烟雾测试：

```yaml
# .github/workflows/smoke-test.yml
name: Smoke Test

on: [push, pull_request]

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start Backend
        run: |
          pip install -r requirements.txt
          uvicorn app.main:app &
          sleep 5
      
      - name: Run Smoke Tests
        run: |
          pip install httpx websockets
          python smoke_test.py
          python smoke_test_sync_ws.py
```

---

**祝测试顺利！🚀**

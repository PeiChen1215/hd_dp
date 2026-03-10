# ChronoSync API 快速参考卡

## 🔑 认证
```http
POST /api/v1/auth/login
{ "username": "xxx", "password": "xxx" }

# 响应
{ "access_token": "JWT_TOKEN", "token_type": "bearer", "expires_in": 1800 }

# 后续请求 Header
Authorization: Bearer JWT_TOKEN
```

---

## 📅 日程/备忘录 CRUD（不变）

```http
GET    /api/v1/events              # 列表
POST   /api/v1/events              # 创建
GET    /api/v1/events/{id}         # 详情
PUT    /api/v1/events/{id}         # 更新
DELETE /api/v1/events/{id}         # 删除
PATCH  /api/v1/events/{id}/status  # 改状态

# 备忘录接口相同 /api/v1/memos/xxx
```

---

## 🔄 同步接口（新增）

### 1. 拉取服务器变更
```http
GET /api/v1/sync/pull?since=2026-03-08T00:00:00Z

# 响应
{
  "items": [{
    "server_id": "uuid",
    "client_id": "123",
    "entity_type": "event",      // event | memo
    "action": "created",         // created | updated | deleted
    "payload": { /* 完整数据 */ },
    "server_modified_at": "2026-03-08T12:00:00Z"
  }],
  "has_more": false,
  "server_time": "2026-03-08T12:10:00Z"  // 保存用于下次 since
}
```

### 2. 推送本地变更
```http
POST /api/v1/sync/push
{
  "items": [{
    "client_id": "123",          // 本地自增ID
    "server_id": null,           // 新建为null
    "entity_type": "event",
    "action": "create",          // create | update | delete
    "payload": { /* 数据 */ },
    "modified_at": "2026-03-08T12:00:00Z"
  }],
  "last_synced_at": "2026-03-08T11:00:00Z"
}

# 响应
{
  "results": [{
    "client_id": "123",
    "server_id": "uuid",
    "status": "success",         // success | conflict | error
    "message": "...",
    "server_modified_at": "..."
  }],
  "conflicts": [],               // 冲突列表
  "server_time": "..."
}
```

### 3. 解决冲突
```http
POST /api/v1/sync/resolve-conflict
{
  "client_id": "123",
  "server_id": "uuid",
  "entity_type": "event",
  "resolution": "client"         // client | server | merge
}
```

### 4. 全量同步（首次/恢复）
```http
POST /api/v1/sync/full-sync
{ "items": [ /* 本地所有数据 */ ] }

# 响应
{
  "server_data": {
    "events": [ /* 服务器所有日程 */ ],
    "memos": [ /* 服务器所有备忘录 */ ]
  },
  "server_time": "..."
}
```

---

## ⚡ WebSocket 实时推送（新增）

### 连接
```
wss://api.example.com/api/v1/ws?token=JWT_TOKEN&device_id=android_xxx
```

### 消息类型

**服务端 -> 客户端**:
```json
// 连接成功
{ "type": "connected", "data": { "server_time": "...", "device_id": "..." } }

// 心跳（30秒一次）
{ "type": "ping", "data": { "timestamp": "..." } }

// 数据变更推送
{
  "type": "event_created",      // event_updated | event_deleted | memo_xxx
  "msg_id": "msg-uuid",
  "timestamp": "...",
  "require_ack": true,
  "data": { "id": "...", "title": "...", ... }
}

// 被踢下线
{ "type": "kickout", "data": { "reason": "new_device_login" } }
```

**客户端 -> 服务端**:
```json
// 心跳响应
{ "type": "pong", "data": { "timestamp": "..." } }

// 消息确认
{ "type": "ack", "data": { "msg_id": "msg-uuid" } }
```

---

## 🗄️ 本地数据库字段建议

```kotlin
@Entity(tableName = "events")
data class EventEntity(
    @PrimaryKey(autoGenerate = true)
    val localId: Long = 0,
    
    val serverId: String?,           // UUID，同步后填充
    val title: String,
    val description: String?,
    val startTime: String?,          // ISO8601
    val endTime: String?,
    val location: String?,
    val status: String,
    
    // 同步字段
    val syncStatus: SyncStatus = SyncStatus.SYNCED,
    val modifiedAt: Long = System.currentTimeMillis()
)

enum class SyncStatus {
    SYNCED, PENDING_CREATE, PENDING_UPDATE, PENDING_DELETE, CONFLICT
}
```

---

## 📝 字段映射表

| 本地 (Kotlin) | API 请求 | API 响应 | 说明 |
|--------------|---------|---------|------|
| `localId` | `client_id` | - | 本地自增 ID |
| `serverId` | `server_id` | `id` | 服务器 UUID |
| `title` | `title` | `title` | 标题 |
| `startTime` | `start_time` | `start_time` | ISO8601 格式 |
| `syncStatus` | - | - | 仅本地使用 |
| `modifiedAt` | `modified_at` | `server_modified_at` | 时间戳转 ISO8601 |

---

## 🐛 调试命令

```bash
# WebSocket 测试
wscat -c "ws://localhost:8000/api/v1/ws?token=TOKEN&device_id=test"

# 发送心跳
> {"type": "pong", "data": {"timestamp": "2026-03-08T12:00:00Z"}}

# 发送确认
> {"type": "ack", "data": {"msg_id": "xxx"}}
```

---

## 📞 联系
- 后端: [你的名字]
- API 文档: `app/openapi.yaml`
- 本地地址: `http://localhost:8000`

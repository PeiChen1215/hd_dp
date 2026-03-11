# ChronoSync API 更新文档 v1.0

> **更新日期**: 2026-03-08  
> **文档版本**: v1.0.0  
> **后端负责人**: [李鸿佑]  
> **关联文档**: [openapi.yaml](./app/openapi.yaml)

---

## 📋 更新概览

本次更新主要新增 **离线同步** 和 **实时推送** 两大功能模块，支持多端数据一致性。

| 类别 | 变更内容 | 影响程度 |
|------|---------|---------|
| 🆕 **新增接口** | 4 个同步相关 API | 高（需对接） |
| 🆕 **新增功能** | WebSocket 实时推送 | 高（需对接） |
| ✅ **保持不变** | 认证、日程 CRUD、备忘录 CRUD、AI Agent | 无影响 |
| ⚠️ **字段调整** | Event/Memo 新增 `serverId` 字段 | 中（需适配） |

---

## 🆕 一、新增接口详解

### 1. 增量拉取 - 获取服务器变更

```http
GET /api/v1/sync/pull?since={timestamp}&cursor={cursor}&limit=100
```

**使用场景**: 客户端启动时、从后台切回前台、网络恢复时

**参数说明**:
| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| `since` | string | 否 | 上次同步时间（ISO8601），首次不传拉取全量 |
| `cursor` | string | 否 | 分页游标，首次不传 |
| `limit` | int | 否 | 单次返回条数，默认 100，最大 500 |

**响应示例**:
```json
{
  "items": [
    {
      "server_id": "550e8400-e29b-41d4-a716-446655440000",
      "client_id": "123",
      "entity_type": "event",
      "action": "created",
      "payload": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "新项目会议",
        "start_time": "2026-03-09T09:00:00Z",
        "end_time": "2026-03-09T10:00:00Z",
        "status": "pending"
      },
      "client_modified_at": "2026-03-08T12:00:00Z",
      "server_modified_at": "2026-03-08T12:05:00Z"
    }
  ],
  "next_cursor": "2026-03-08T12:05:00Z",
  "has_more": false,
  "server_time": "2026-03-08T12:10:00Z"
}
```

**前端处理逻辑**:
1. 保存 `server_time` 到本地，作为下次 `since` 参数
2. 如果 `has_more` 为 true，继续用 `next_cursor` 拉取
3. 将 `items` 应用到本地数据库

---

### 2. 增量推送 - 上传本地变更

```http
POST /api/v1/sync/push
```

**使用场景**: 用户创建/修改/删除数据后，将本地变更同步到服务器

**请求体**:
```json
{
  "items": [
    {
      "client_id": "123",
      "server_id": null,
      "entity_type": "event",
      "action": "create",
      "payload": {
        "title": "新项目会议",
        "start_time": "2026-03-09T09:00:00Z",
        "end_time": "2026-03-09T10:00:00Z",
        "status": "pending"
      },
      "modified_at": "2026-03-08T12:00:00Z"
    },
    {
      "client_id": "456",
      "server_id": "550e8400-e29b-41d4-a716-446655440000",
      "entity_type": "event",
      "action": "update",
      "payload": {
        "title": "修改后的标题",
        "start_time": "2026-03-09T10:00:00Z"
      },
      "modified_at": "2026-03-08T12:05:00Z"
    }
  ],
  "last_synced_at": "2026-03-08T11:00:00Z"
}
```

**关键字段说明**:
- `client_id`: 本地数据库的自增 ID（如 Room 的 `localId`）
- `server_id`: 服务器返回的 UUID，**新建时为 null**
- `action`: `create` / `update` / `delete`
- `modified_at`: 客户端修改时间（用于冲突检测）
- `last_synced_at`: 上次成功同步的时间

**响应示例**:
```json
{
  "results": [
    {
      "client_id": "123",
      "server_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "success",
      "message": "create event succeeded",
      "server_modified_at": "2026-03-08T12:10:00Z"
    },
    {
      "client_id": "456",
      "server_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "conflict",
      "message": "Server has newer version",
      "server_data": { /* 服务器上的数据 */ },
      "server_modified_at": "2026-03-08T12:08:00Z"
    }
  ],
  "conflicts": [
    /* 冲突列表，需要用户处理 */
  ],
  "server_time": "2026-03-08T12:10:00Z"
}
```

**前端处理逻辑**:
1. **success**: 更新本地记录的 `server_id` 和 `sync_status = SYNCED`
2. **conflict**: 标记冲突状态，弹出对话框让用户选择
3. **error**: 保留 `PENDING` 状态，下次重试

---

### 3. 解决冲突

```http
POST /api/v1/sync/resolve-conflict
```

**使用场景**: 推送返回冲突时，用户选择解决策略后调用

**请求体**:
```json
{
  "client_id": "456",
  "server_id": "550e8400-e29b-41d4-a716-446655440000",
  "entity_type": "event",
  "resolution": "client"
}
```

**resolution 选项**:
| 值 | 说明 | 后续操作 |
|---|------|---------|
| `client` | 使用客户端版本（覆盖服务器） | 重新推送 |
| `server` | 使用服务器版本（放弃本地） | 应用到本地数据库 |
| `merge` | 合并数据（预留） | 手动合并后推送 |

---

### 4. 全量同步（首次安装/数据恢复）

```http
POST /api/v1/sync/full-sync
```

**使用场景**: 首次安装、用户主动刷新、数据异常恢复

**请求体**:
```json
{
  "items": [
    /* 客户端所有本地数据 */
  ]
}
```

**响应示例**:
```json
{
  "server_data": {
    "events": [ /* 服务器所有日程 */ ],
    "memos": [ /* 服务器所有备忘录 */ ]
  },
  "push_results": [ /* 本地数据推送结果 */ ],
  "server_time": "2026-03-08T12:10:00Z"
}
```

**前端处理逻辑**:
1. 上传本地所有数据
2. 清空本地数据库
3. 写入服务器返回的全量数据
4. 标记所有数据为 `SYNCED`

---

## 🔄 二、WebSocket 实时推送（新增）

### 连接方式

```
wss://api.example.com/api/v1/ws?token={JWT_TOKEN}&device_id={DEVICE_ID}
```

**参数说明**:
- `token`: JWT Token（登录时获取）
- `device_id`: 设备唯一标识（建议格式：`android_{uuid前8位}`）

### 消息协议

#### 1. 连接成功
```json
{
  "type": "connected",
  "data": {
    "server_time": "2026-03-08T12:00:00Z",
    "device_id": "android_abc123"
  }
}
```

#### 2. 心跳机制（重要）
- **服务端发送**: `{"type": "ping", "data": {"timestamp": "..."}}`
- **客户端回复**: `{"type": "pong", "data": {"timestamp": "..."}}`
- **频率**: 每 30 秒一次

#### 3. 数据变更推送（核心）
```json
{
  "type": "event_created",
  "msg_id": "msg-uuid-123",
  "timestamp": "2026-03-08T12:05:00Z",
  "require_ack": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "新项目会议",
    "start_time": "2026-03-09T09:00:00Z",
    ...
  }
}
```

**消息类型列表**:
| type | 说明 | 前端操作 |
|------|------|---------|
| `event_created` | 新日程创建 | 插入本地数据库 |
| `event_updated` | 日程更新 | 更新本地数据库 |
| `event_deleted` | 日程删除 | 删除本地记录 |
| `memo_created` | 新备忘录创建 | 插入本地数据库 |
| `memo_updated` | 备忘录更新 | 更新本地数据库 |
| `memo_deleted` | 备忘录删除 | 删除本地记录 |

**确认机制**:
```json
{"type": "ack", "data": {"msg_id": "msg-uuid-123"}}
```

#### 4. 被踢下线
```json
{
  "type": "kickout",
  "data": {
    "reason": "new_device_login",
    "device_id": "android_abc123"
  }
}
```

**处理方式**: 显示提示"账号在其他设备登录"，不自动重连

### 前端实现建议

```kotlin
class WebSocketManager {
    fun connect()
    fun disconnect()
    
    // 收到消息后的处理流程
    fun handleMessage(msg: SyncMessage) {
        when (msg.type) {
            "event_created" -> eventDao.insert(msg.data.toEntity())
            "event_updated" -> eventDao.update(msg.data.toEntity())
            "event_deleted" -> eventDao.deleteByServerId(msg.data.id)
            // 类似处理 memo_xxx
        }
        
        // 发送确认
        if (msg.require_ack) {
            sendAck(msg.msg_id)
        }
    }
}
```

---

## ⚠️ 三、字段变更说明

### Event 实体

| 字段 | 类型 | 说明 | 变更 |
|-----|------|------|------|
| `id` | UUID | 服务器唯一标识 | 🆕 新增（即之前的 `serverId`） |
| `clientId` | Long | 本地自增 ID | ➡️ 仅用于同步协议，API 返回中没有 |
| `title` | String | 标题 | ✅ 不变 |
| `description` | String | 描述 | ✅ 不变 |
| `start_time` | ISO8601 | 开始时间 | ✅ 格式统一为 ISO8601 |
| `end_time` | ISO8601 | 结束时间 | ✅ 格式统一为 ISO8601 |
| `location` | String | 地点 | ✅ 不变 |
| `status` | Enum | 状态 | ✅ 不变 |

### Memo 实体

| 字段 | 类型 | 说明 | 变更 |
|-----|------|------|------|
| `id` | UUID | 服务器唯一标识 | 🆕 新增 |
| `content` | String | 内容 | ✅ 不变 |
| `tags` | [String] | 标签 | ✅ 不变 |
| `created_at` | ISO8601 | 创建时间 | ✅ 不变 |
| `updated_at` | ISO8601 | 更新时间 | ✅ 不变 |

### 本地数据库建议字段

```kotlin
@Entity(tableName = "events")
data class EventEntity(
    @PrimaryKey(autoGenerate = true)
    val localId: Long = 0,           // 本地自增 ID
    
    val serverId: String?,            // 服务器 UUID（同步后填充）
    val title: String,
    val description: String?,
    val startTime: String?,           // ISO8601
    val endTime: String?,
    val location: String?,
    val status: String,
    
    // 同步相关字段
    val syncStatus: SyncStatus,       // SYNCED / PENDING_CREATE / PENDING_UPDATE / PENDING_DELETE / CONFLICT
    val modifiedAt: Long,             // 毫秒时间戳
    val createdAt: Long
)

enum class SyncStatus {
    SYNCED,         // 已同步
    PENDING_CREATE, // 待创建（本地新增）
    PENDING_UPDATE, // 待更新（本地修改）
    PENDING_DELETE, // 待删除（本地删除）
    CONFLICT        // 冲突待解决
}
```

---

## 📱 四、前端对接建议

### 推荐架构

```
┌─────────────────────────────────────────────────────────┐
│                     UI Layer (Compose)                   │
│  - 观察 Room LiveData/Flow 自动更新                      │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│                  Repository 层                           │
│  - 封装业务逻辑                                          │
│  - 决定何时调用 API / WebSocket                          │
└────────────────┬────────────────────────────────────────┘
                 │
       ┌─────────┴──────────┐
       │                    │
┌──────▼──────┐    ┌────────▼────────┐
│  Room DB    │    │  SyncManager    │
│  (本地数据源) │    │  (同步控制)      │
└─────────────┘    └────────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼────┐  ┌────▼────┐  ┌─────▼──────┐
        │ REST API │  │WebSocket│  │ WorkManager│
        │ (Sync)   │  │ (Real-time)│ │ (后台同步) │
        └──────────┘  └─────────┘  └────────────┘
```

### 同步策略建议

| 场景 | 策略 |
|------|------|
| **应用启动** | 检查 WebSocket 连接，同时执行一次 `/sync/pull` 兜底 |
| **用户操作** | 立即写本地数据库，后台异步推送 |
| **网络恢复** | 立即执行全量同步 `/sync/full-sync` |
| **后台保活** | WorkManager 每 15 分钟执行一次同步 |
| **实时更新** | WebSocket 收到消息直接应用到数据库 |

### 冲突处理 UI 建议

```kotlin
// 检测到冲突时显示对话框
@Composable
fun ConflictDialog(
    localEvent: EventEntity,
    serverEvent: EventData,
    onResolve: (ConflictResolution) -> Unit
) {
    AlertDialog(
        title = { Text("数据冲突") },
        text = {
            Column {
                Text("该日程在另一台设备上被修改")
                Spacer(Modifier.height(8.dp))
                Text("本地版本:", fontWeight = FontWeight.Bold)
                Text("标题: ${localEvent.title}")
                Text("时间: ${localEvent.startTime}")
                Spacer(Modifier.height(8.dp))
                Text("服务器版本:", fontWeight = FontWeight.Bold)
                Text("标题: ${serverEvent.title}")
                Text("时间: ${serverEvent.startTime}")
            }
        },
        confirmButton = {
            TextButton(onClick = { onResolve(ConflictResolution.SERVER) }) {
                Text("使用服务器版本")
            }
        },
        dismissButton = {
            TextButton(onClick = { onResolve(ConflictResolution.CLIENT) }) {
                Text("使用本地版本")
            }
        }
    )
}
```

---

## 🔧 五、调试工具

### 1. 使用 Swagger UI 测试 API

```bash
# 启动后端后访问
http://localhost:8000/docs
```

### 2. WebSocket 测试

```bash
# 安装 wscat
npm install -g wscat

# 连接（先通过登录接口获取 token）
wscat -c "ws://localhost:8000/api/v1/ws?token=YOUR_JWT_TOKEN&device_id=test_device"

# 发送心跳
> {"type": "pong", "data": {"timestamp": "2026-03-08T12:00:00Z"}}

# 发送确认
> {"type": "ack", "data": {"msg_id": "xxx"}}
```

### 3. 日志查看

后端日志会输出同步和 WebSocket 相关信息：
```
[WebSocket] Connected: user-uuid/android_abc123
[Sync] Push success: 3 items, 1 conflict
[WebSocket] Broadcast to user-uuid: event_created
```

---

## 📞 六、问题反馈

对接过程中遇到问题请联系：
- **后端负责人**: [你的名字/联系方式]
- **API 文档**: [openapi.yaml](./app/openapi.yaml)
- **后端地址**: http://localhost:8000 (本地开发)

### 常见问题

**Q1: 首次安装如何同步数据？**  
A: 调用 `POST /api/v1/sync/full-sync`，上传本地空数据，返回服务器全量数据。

**Q2: WebSocket 断开后如何恢复？**  
A: 自动重连（指数退避），重连成功后立即执行一次 `/sync/pull` 补齐离线期间的数据。

**Q3: 如何处理时间格式？**  
A: 服务器使用 ISO8601 格式（如 `2026-03-08T12:00:00Z`），客户端需要转换为本地时间显示。

**Q4: 多设备同时修改会冲突吗？**  
A: 会。后端通过 `last_synced_at` 检测冲突，返回 `status: conflict`，前端需要引导用户解决。

---

## ✅ 七、对接检查清单

前端完成以下功能后即可上线：

- [ ] 本地数据库添加 `serverId`, `syncStatus`, `modifiedAt` 字段
- [ ] 实现 CRUD 操作时自动标记 `syncStatus`
- [ ] 实现增量同步逻辑（pull + push）
- [ ] 实现 WebSocket 连接和消息处理
- [ ] 实现冲突解决对话框
- [ ] 实现后台同步（WorkManager）
- [ ] 处理网络断开/恢复场景
- [ ] 测试多设备同时修改场景

---

**祝对接顺利！有问题随时联系 🚀**

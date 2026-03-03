# ChronoSync 接口文档（精简版）

说明：此文档基于 OpenAPI 草案，包含前端常用接口、请求示例与响应示例，便于快速联调与实现同步逻辑。

认证
- POST /api/v1/auth/register
  - 请求：
  ```json
  {"username":"alice","password":"secret"}
  ```
  - 响应 201：
  ```json
  {"user_id":"uuid","username":"alice","created_at":"2026-03-03T10:00:00Z"}
  ```

- POST /api/v1/auth/login
  - 请求：同上
  - 响应 200：
  ```json
  {"access_token":"ey...","token_type":"bearer","expires_in":1800}
  ```

通用说明
- 认证：除登录/注册外，其他接口需要在 Header 中包含 `Authorization: Bearer <token>`。
- 时间：后端以 `start_time` / `end_time`（ISO8601，UTC）为存储标准。前端可继续使用 `date`/`startTime` 显示字段，但请求推荐带 ISO 时间以避免时区问题。

日程（Events）
- GET /api/v1/events?start_date=&end_date=&page=&size=
  - 用途：分页查询日程（前端用于日历日视图或范围查询）。
  - 响应示例：
  ```json
  {
    "items":[{"serverId":"uuid","clientId":123,"title":"周会","start_time":"2026-03-03T02:00:00Z","end_time":"2026-03-03T03:00:00Z","type":"WORK","priority":2}],
    "total":1,"page":1,"size":20
  }
  ```

- POST /api/v1/events
  - 创建单条日程（后端返回 `serverId` 用于跨端同步）
  - 请求示例：
  ```json
  {"clientId":123,"title":"周会","start_time":"2026-03-03T02:00:00Z","end_time":"2026-03-03T03:00:00Z","type":"WORK","priority":2}
  ```
  - 响应 201：返回完整对象（含 `serverId`、`created_at`、`updated_at`）。

- GET /api/v1/events/{serverId}
- PUT /api/v1/events/{serverId}
- DELETE /api/v1/events/{serverId}
- PATCH /api/v1/events/{serverId}/status
  - 用途：按 serverId 操作（更新/删除/更改状态）。
  - 状态 PATCH 请求体示例：`{"status":"completed"}`。

备忘录（Memos）
- GET /api/v1/memos?page=&size=
- POST /api/v1/memos
- GET/PUT/DELETE /api/v1/memos/{serverId}
  - 请求/响应样式与 Events 类似，前端仍可保留 `updatedAt`（epoch ms）字段用于本地排序。

自然语言指令（Agent）
- POST /api/v1/agent/process
  - 请求：
  ```json
  {"text":"把下周二的会推迟一小时","conversation_id":null}
  ```
  - 响应示例：
  ```json
  {"action":"update","entity":"event","data":{"serverId":"...","start_time":"2026-03-10T10:00:00Z"},"reply":"已将会议推迟一小时，新的开始时间为10:00。"}
  ```

RAG 聊天（基于历史数据问答）
- POST /api/v1/chat
  - 请求：`{"query":"我上周跑了几次步？"}`
  - 响应示例：
  ```json
  {"answer":"您上周共跑步3次，分别是3月1日、3月3日和3月5日。","sources":[{"type":"event","id":"uuid","title":"跑步","start_time":"2026-03-01T19:00:00Z"}]}
  ```

AI 提供商
- GET /api/v1/providers
  - 返回可用 AI 提供商列表（前端可用于显示选择或调试信息）。

增量同步接口（推荐供移动端使用）
- GET /api/v1/sync/events?since={ISO8601或epoch_ms}
  - 用途：拉取自 `since` 时间点之后的新增/更新/删除变更。
  - 响应示例：
  ```json
  {"items":[{"clientId":123,"serverId":"uuid","status":"ok","updated_at":"2026-03-02T12:00:00Z"}],"cursor":"2026-03-02T12:00:00Z"}
  ```

- POST /api/v1/sync/events
  - 用途：批量上推客户端变更（创建/更新/删除），后端返回每条的 `serverId` 和最终 `updated_at`。
  - 请求示例：
  ```json
  {"items":[{"clientId":123,"title":"周会","start_time":"2026-03-03T02:00:00Z"}]}
  ```
  - 响应示例：
  ```json
  {"items":[{"clientId":123,"serverId":"uuid","status":"created","updated_at":"2026-03-03T02:00:05Z"}]}
  ```

实时同步（WebSocket）
- 连接示例：`ws://host/api/v1/ws?token=<JWT>`
- 消息示例：
  ```json
  {"type":"event_created","data":{"serverId":"uuid","title":"周会",...}}
  ```

字段对齐与注意事项（摘要）
- `clientId`：前端本地自增 id，后端应返回 `serverId`（UUID）用于全局唯一标识。前端应保存 `clientId`↔`serverId` 映射。
- 时间：推荐前端发送 `start_time`/`end_time`（ISO8601），后端以 UTC 存储并返回 ISO 字段；为兼容显示，可在响应中一并返回 `date`/`startTime` 字段。
- 枚举与校验：`type` 和 `priority` 由后端校验，超出值返回 400。
- 冲突解决：建议采用 `updated_at`（服务端时间）为准的 LWW 策略，复杂冲突可返回冲突详情让前端决策。

联调建议
- 提供方（后端）应把 `app/openapi.yaml` 发给前端并在接口实现就绪后发布 Swagger UI（`/docs`）。
- 若前端需要离线开发，可要求我生成 Postman 集合或 Mock Server。

文件位置：`app/openapi.yaml`（机器可读 OpenAPI）和当前 `API_DOCUMENTATION.md`（人类可读）。

如需，我现在可以把 `app/openapi.yaml` 导出为 Postman 集合或基于该 OpenAPI 启动 mock server（用 `prism` 或 `mockoon`）。

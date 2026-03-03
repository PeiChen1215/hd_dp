# ChronoSyncApp 数据模型对齐文档（本地 Room）

本文档用于与后端同学对齐当前 App 侧的数据模型（以本地 Room 数据库为准），便于后续接口/同步协议设计。

## 1. 数据库概览

- 数据库文件名：`chronosync.db`
- Room 定义：`app/src/main/java/com/example/chronosyncapp/data/AppDatabase.java`
- version：`1`
- `exportSchema = false`
- 迁移策略：`fallbackToDestructiveMigration()`（版本变更时会丢弃并重建本地库）

当前包含 2 张表：

- `schedule_events`：日程事件
- `memos`：备忘录

> 说明：实体类均为 Java POJO，字段未显式声明 `@NonNull`，Room 层面不强制 NOT NULL；但业务侧通常应视为“必填字段”。

---

## 2. 表：`schedule_events`（日程事件）

对应实体：`app/src/main/java/com/example/chronosyncapp/data/ScheduleEventEntity.java`

### 2.1 字段定义

| 字段名 | SQL 类型（Room 推导） | 业务含义 | 约束/取值 | 示例 |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | 本地自增主键 | `@PrimaryKey(autoGenerate = true)`；新增时可不传或传 `0` | `123` |
| `date` | TEXT | 事件所属日期 | **ISO-8601 日期字符串**：`yyyy-MM-dd` | `2026-03-03` |
| `title` | TEXT | 标题/摘要 | 建议必填 | `"周会"` |
| `startTime` | TEXT | 开始时间 | **24 小时制**：`HH:mm` | `"10:00"` |
| `endTime` | TEXT | 结束时间 | **24 小时制**：`HH:mm` | `"11:00"` |
| `type` | TEXT | 事件类型 | 当前约定：`WORK` / `LIFE` / `STUDY`（字符串枚举） | `"WORK"` |
| `priority` | INTEGER | 优先级 | 当前约定：`1`(低) / `2`(中) / `3`(高) | `2` |

### 2.2 查询与排序（DAO）

DAO：`app/src/main/java/com/example/chronosyncapp/data/ScheduleEventDao.java`

- 查询某天事件：`SELECT * FROM schedule_events WHERE date = :date ORDER BY startTime ASC`
  - 说明：同一天内按 `startTime` 字符串升序排序（`HH:mm` 格式下字典序与时间序一致）
- 事件数量：`SELECT COUNT(*) FROM schedule_events`
- 日历标记数据：`SELECT date, type, priority FROM schedule_events`（投影为 `EventMarker`）

### 2.3 日历标记投影：`EventMarker`

类：`app/src/main/java/com/example/chronosyncapp/data/EventMarker.java`

用于“日历底部条绘制”的轻量投影，只包含：

- `date`：同上
- `type`：同上
- `priority`：同上

---

## 3. 表：`memos`（备忘录）

对应实体：`app/src/main/java/com/example/chronosyncapp/data/MemoEntity.java`

### 3.1 字段定义

| 字段名 | SQL 类型（Room 推导） | 业务含义 | 约束/取值 | 示例 |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | 本地自增主键 | `@PrimaryKey(autoGenerate = true)`；新增时可不传或传 `0` | `45` |
| `title` | TEXT | 备忘录标题 | 建议必填（可与 `content` 二选一） | `"买菜"` |
| `content` | TEXT | 备忘录内容 | 建议必填（可与 `title` 二选一） | `"鸡蛋、牛奶"` |
| `updatedAt` | INTEGER | 最近更新时间 | **Unix epoch 毫秒**（`System.currentTimeMillis()` 语义） | `1709455200000` |

### 3.2 查询与排序（DAO）

DAO：`app/src/main/java/com/example/chronosyncapp/data/MemoDao.java`

- 查询全部：`SELECT * FROM memos ORDER BY updatedAt DESC`
- 备忘录数量：`SELECT COUNT(*) FROM memos`

---

## 4. 建议后端对齐的 JSON 模型（参考）

> 说明：以下为便于对齐的“推荐 JSON 表达”，字段名与本地表字段保持一致，便于直连映射。是否采用由后端接口设计决定。

### 4.1 ScheduleEvent

```json
{
  "id": 123,
  "date": "2026-03-03",
  "title": "周会",
  "startTime": "10:00",
  "endTime": "11:00",
  "type": "WORK",
  "priority": 2
}
```

### 4.2 Memo

```json
{
  "id": 45,
  "title": "买菜",
  "content": "鸡蛋、牛奶",
  "updatedAt": 1709455200000
}
```

---

## 5. 同步/接口设计注意点（对齐用）

- `id` 当前为本地自增主键：若需要“多端同步/服务端主键”，建议后端另给 `serverId`（或统一改为全局唯一 ID），否则本地自增值无法跨设备稳定对齐。
- 时间字段当前为字符串：`date` + `startTime/endTime` 组合表达；若后端用时间戳，需定义双向转换规则与时区（当前模型未包含时区信息）。
- `type`、`priority` 均为约定枚举：建议后端做枚举校验，防止出现未知值导致 UI 渲染异常。


# Release Notes

Version: initial-sync-setup

Summary:
- 初始化项目骨架并对接 FastAPI、async SQLAlchemy、Alembic、pgvector 支持
- 添加了 OpenAPI 描述与接口占位实现
- 在仓库中添加 `.env`（后已移除并从历史中清理）

Important:
- `.env` 包含敏感信息（SECRET_KEY 与 DATABASE_URL），已从最新提交中删除并从历史中清理。所有协作者需重新克隆仓库或重置本地分支：

```bash
git fetch origin
git reset --hard origin/main
```

Changelog:
- 迁移（Alembic）已生成并应用（初始迁移文件在 `alembic/versions/`）
- 增加 `README.md`、`RELEASE_NOTES.md`、以及基础服务模块

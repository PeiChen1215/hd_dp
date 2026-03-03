# ChronoSync

轻量级同步与 RAG 后端示例项目（FastAPI + async SQLAlchemy + pgvector）。

## 功能概览
- 用户、事件、备忘录与会话模型
- 使用 PostgreSQL + pgvector 存储向量
- RAG / agent 概要模块（占位）
- OpenAPI 自动生成（`/docs`）

## 快速启动（开发）
1. 克隆仓库并进入目录

```bash
git clone https://github.com/PeiChen1215/hd_dp.git
cd hd_dp
```

2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

3. 在项目根创建 `.env`，示例内容：

```
SECRET_KEY=你的随机密钥
DATABASE_URL=postgresql+asyncpg://user:pass@DB_HOST:5432/chronosync
```

4. 生成并应用 Alembic 迁移：

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

（在本项目我已自动生成并应用初始迁移，若你需要重新生成请先备份数据库）

5. 启动开发服务器：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档： http://localhost:8000/docs

## 部署建议
- 数据库建议部署在私有网络或使用云托管数据库；开发时可用 SSH 隧道安全连接。 
- 生产环境建议使用 Docker 或 systemd + Supervisor 部署，并在前端放置反向代理与 HTTPS。

## 贡献
欢迎提交 PR 或 issue。请务必在提交前运行测试并更新迁移。 

## 联系
作者: PeiChen1215
# ChronoSync — 后端项目骨架

快速开始：

1. 复制示例环境变量并修改：

```bash
cp .env.example .env
# 编辑 .env
```

2. 使用 Docker Compose 启动（本地开发）

```bash
docker-compose up --build
```

3. 启动后访问： http://localhost:8000/docs

说明：本仓库包含 FastAPI 项目骨架、基础模块和示例路由。后续会补充完整的模型、迁移脚本与 Agent 实现。

# 后端登录接口修改说明

## 问题描述

后端登录接口的实现与 `openapi2.yaml` 文档不一致。

## 现象

**openapi2.yaml 定义**（JSON 格式）：
```yaml
/api/v1/auth/login:
  post:
    requestBody:
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/UserCreate'
```

**实际后端实现**（form-urlencoded）：
- 使用 FastAPI 的 `OAuth2PasswordRequestForm`
- 只接受 `application/x-www-form-urlencoded`

**测试结果**：
```bash
curl -X POST http://115.190.155.26:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# 返回 422
{"detail":[{"type":"missing","loc":["body","username"],"msg":"Field required"...}]}
```

## 建议修改方案

将登录接口从 form-urlencoded 改为 JSON 格式，与注册接口保持一致：

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

# 修改前（form-urlencoded）
@app.post("/api/v1/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    ...

# 修改后（JSON）
@app.post("/api/v1/auth/login")
async def login(user: UserCreate):
    # 原有的验证逻辑保持不变
    ...
```

## 修改原因

1. **文档一致性**：openapi2.yaml 明确定义为 JSON 格式
2. **接口统一**：注册接口已经是 JSON，登录也应该是 JSON
3. **现代规范**：REST API 通常使用 JSON 而非 form-urlencoded
4. **前端已适配**：前端已按 openapi2.yaml 改为 JSON 格式，需要后端配合

## 验证方法

修改后测试：
```bash
curl -X POST http://115.190.155.26:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# 期望返回 200
{"access_token":"xxx","token_type":"bearer","expires_in":1800}
```

## 注意事项

- 修改后 Swagger UI (/docs) 会自动更新
- 其他接口（events、memos 等）不受影响
- 建议更新后更新 `API_PROGRESS.md` 中的登录接口状态

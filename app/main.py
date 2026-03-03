from fastapi import FastAPI
from app.api.v1 import api_router

app = FastAPI(title="ChronoSync API")


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")

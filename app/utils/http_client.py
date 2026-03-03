import httpx

client = httpx.AsyncClient(timeout=30.0)

async def aget(url: str, **kwargs):
    return await client.get(url, **kwargs)

async def apost(url: str, **kwargs):
    return await client.post(url, **kwargs)

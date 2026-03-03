from .base import BaseAgent


class WenxinAgent(BaseAgent):
    async def process(self, text: str, context: dict) -> dict:
        # TODO: call Wenxin function-calling API
        return {"action": "noop", "entity": "none", "data": {}, "reply": "未实现"}

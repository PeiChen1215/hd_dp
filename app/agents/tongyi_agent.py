from .base import BaseAgent


class TongyiAgent(BaseAgent):
    async def process(self, text: str, context: dict) -> dict:
        # TODO: call Tongyi function-calling API
        return {"action": "noop", "entity": "none", "data": {}, "reply": "未实现"}

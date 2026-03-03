class VectorStore:
    def __init__(self, db):
        self.db = db

    async def add(self, user_id: str, item_id: str, vector: list, metadata: dict):
        # TODO: persist vector to pgvector column
        pass

    async def search(self, user_id: str, vector: list, limit: int = 5):
        # TODO: perform vector similarity search
        return []

"""記憶體版對話儲存：不需任何設定即可用，但重啟服務會清空"""
from collections import defaultdict, deque
from app.config import settings

_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=settings.MAX_HISTORY_TURNS * 2))


async def get_history(user_id: str) -> list[dict]:
    return list(_store[user_id])


async def append(user_id: str, role: str, content: str):
    _store[user_id].append({"role": role, "content": content})


async def clear(user_id: str):
    _store[user_id].clear()

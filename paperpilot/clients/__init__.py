from .zotero import ZoteroClient
from .notion import NotionClient
from .ai import AIClient, AISettings

try:
    from .deepxiv import DeepXivClient
except ImportError:
    DeepXivClient = None  # type: ignore[misc,assignment]

__all__ = ["ZoteroClient", "NotionClient", "AIClient", "AISettings", "DeepXivClient"]

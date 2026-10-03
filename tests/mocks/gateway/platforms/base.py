"""Stub gateway.platforms.base for plugin tests."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SendResult:
    """Result of a send operation."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter:
    """Base platform adapter stub for plugin tests."""

    def __init__(self, config, platform):
        self.config = config
        self.platform = platform
        self.connected = False

    async def connect(self) -> bool:
        return False

    async def disconnect(self) -> None:
        pass

    async def send(self, chat_id: str, content: str, reply_to: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> SendResult:
        return SendResult(success=False)

    async def get_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        return None

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        return None

    @property
    def platform_name(self) -> str:
        return self.platform.value if hasattr(self.platform, 'value') else str(self.platform)

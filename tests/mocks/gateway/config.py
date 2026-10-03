"""Stub gateway.config for plugin tests."""

from dataclasses import dataclass, field
from typing import Any, Dict


class Platform:
    """Platform identifier enum stub."""

    def __init__(self, value: str):
        self.value = value

    def __eq__(self, other):
        if isinstance(other, Platform):
            return self.value == other.value
        return self.value == other

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f"Platform('{self.value}')"


@dataclass
class PlatformConfig:
    """Stub PlatformConfig matching Hermes gateway interface."""

    enabled: bool = False
    api_key: str = ""
    token: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

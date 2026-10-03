"""Stub gateway.platform_registry for plugin tests."""

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class PlatformEntry:
    """Platform registry entry stub."""

    name: str
    label: str
    adapter_factory: Callable
    check_fn: Callable


class PlatformRegistry:
    """Minimal platform registry for tests."""

    def __init__(self):
        self._registered: Dict[str, PlatformEntry] = {}

    def is_registered(self, name: str) -> bool:
        return name in self._registered

    def register(self, entry: PlatformEntry) -> None:
        self._registered[entry.name] = entry

    def get(self, name: str) -> Optional[PlatformEntry]:
        return self._registered.get(name)


platform_registry = PlatformRegistry()

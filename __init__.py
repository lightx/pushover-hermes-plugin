"""Pushover platform adapter — outbound push notifications."""
try:
    from .pushover_hermes_plugin.adapter import register
except ImportError:  # imported without a parent package (e.g. pytest rootdir)
    from pushover_hermes_plugin.adapter import register

__all__ = ["register"]

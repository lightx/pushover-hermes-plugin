"""Pushover platform adapter — outbound notifications only.

Plugin-based gateway adapter that sends push notifications via the
Pushover API (https://pushover.net). Outbound-only — no inbound
message handling.

Configuration in config.yaml::

    gateway:
      platforms:
        pushover:
          enabled: true
          api_key: <PUSHOVER_APP_TOKEN>   # app token — PlatformConfig.api_key
          token: <PUSHOVER_USER_KEY>      # user key  — PlatformConfig.token
          extra:
            device: ""   # optional device filter

NOTE: the field naming follows hermes PlatformConfig convention, not Pushover's
own terminology. api_key = app token, token = user key. Env vars are the simpler
approach and always take precedence:
    PUSHOVER_APP_TOKEN, PUSHOVER_USER_KEY
"""

import logging
import os
from typing import Any, Dict, Optional

import aiohttp

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, SendResult

logger = logging.getLogger(__name__)

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
MAX_MESSAGE_LENGTH = 1024


def check_requirements() -> bool:
    """Check that aiohttp is available.

    This is a package dependency check only — NOT a credential check.
    check_fn() is called by platform_registry.create_adapter(); returning
    False prevents adapter creation and shows install_hint. Credential
    validation belongs in is_connected() so the platform stays registered
    even when env vars aren't set yet.
    """
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False




def validate_config(config) -> bool:
    """Check whether Pushover is configured via env vars or config.yaml."""
    # Env vars take precedence — always check them first.
    if os.getenv("PUSHOVER_APP_TOKEN", "").strip() and os.getenv("PUSHOVER_USER_KEY", "").strip():
        return True
    # Fall back to config.yaml values.
    token = getattr(config, "token", "") or ""
    api_key = getattr(config, "api_key", "") or ""
    return bool(token and api_key)


def is_connected(config) -> bool:
    """True if credentials are available from env or config.yaml."""
    if os.getenv("PUSHOVER_APP_TOKEN", "").strip() and os.getenv("PUSHOVER_USER_KEY", "").strip():
        return True
    return validate_config(config)


def interactive_setup() -> None:
    """Prompt for Pushover credentials and write them to ~/.hermes/.env.

    Called by ``hermes gateway setup`` when the user picks Pushover.
    Inlines prompts rather than importing _prompt_env_var from
    hermes_cli.gateway (private helper, fragile across upstream updates).
    Writes to ~/.hermes/.env — standard hermes env file location.
    """
    print()
    print("  \u2500\u2500\u2500 \U0001f514 Pushover Setup \u2500\u2500\u2500")
    print("  1. Log in at https://pushover.net")
    print("  2. Your User Key is on the front page \u2014 copy it")
    print("  3. Create an app at https://pushover.net/apps \u2192 Create New Application")
    print("  4. Copy the API Token for your new app")
    print()

    env_path = os.path.expanduser("~/.hermes/.env")
    updates: Dict[str, str] = {}

    for var, prompt in [
        ("PUSHOVER_APP_TOKEN", "Pushover App Token (from pushover.net/apps)"),
        ("PUSHOVER_USER_KEY",  "Pushover User Key (from pushover.net front page)"),
        ("PUSHOVER_ALLOWED_USERS", "Allowed user keys, comma-separated (leave empty = allow all)"),
    ]:
        current = os.getenv(var, "")
        display = f" [{current}]" if current else ""
        value = input(f"  {prompt}{display}: ").strip()
        if value:
            updates[var] = value

    if not updates:
        print("  No changes.")
        return

    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    for var, value in updates.items():
        key_prefix = f"{var}="
        replaced = False
        for i, line in enumerate(lines):
            if line.startswith(key_prefix):
                lines[i] = f"{var}={value}\n"
                replaced = True
                break
        if not replaced:
            lines.append(f"{var}={value}\n")

    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    with open(env_path, "w") as f:
        f.writelines(lines)
    print(f"  Saved to {env_path}")


class PushoverAdapter(BasePlatformAdapter):
    """Outbound-only Pushover adapter.

    Sends push notifications to the Pushover API.
    No persistent connection — each send() opens a short-lived aiohttp session.
    """

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("pushover"))
        # Field mapping: PlatformConfig.api_key = PUSHOVER_APP_TOKEN (app token)
        #                PlatformConfig.token    = PUSHOVER_USER_KEY  (user key)
        # Confirmed from _apply_env_overrides(): api_key=pushover_app, token=pushover_user
        # and send_message_tool.py: _send_pushover(pconfig.api_key, pconfig.token, chunk)
        self._app_token: str = os.getenv("PUSHOVER_APP_TOKEN", "") or getattr(config, "api_key", "") or ""
        self._user_key: str = os.getenv("PUSHOVER_USER_KEY", "") or getattr(config, "token", "") or ""
        extra = getattr(config, "extra", {}) or {}
        self._device: str = extra.get("device", "") if isinstance(extra, dict) else ""

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        """Accept the ``is_reconnect`` kwarg required by the gateway's
        reconnect watcher (see BasePlatformAdapter.connect contract).

        Pushover is stateless (outbound HTTP only), so this is a no-op.
        """
        return True

    async def disconnect(self) -> None:
        pass

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        # Pushover sends to a user key. For home-channel cron delivery,
        # chat_id may be empty — fall back to the configured user key.
        effective_user = chat_id or self._user_key

        if not self._app_token or not effective_user:
            return SendResult(
                success=False,
                error="Pushover credentials not configured (PUSHOVER_APP_TOKEN / PUSHOVER_USER_KEY)",
            )

        # Truncation is handled by send_message_tool before this is called,
        # but apply a hard cap as a safety net.
        if len(content) > MAX_MESSAGE_LENGTH:
            content = content[: MAX_MESSAGE_LENGTH - 3] + "..."

        payload: Dict[str, str] = {
            "token": self._app_token,
            "user": effective_user,
            "message": content,
        }
        if self._device:
            payload["device"] = self._device
        if metadata and "title" in metadata:
            payload["title"] = metadata["title"]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(PUSHOVER_API_URL, data=payload) as resp:
                    result = await resp.json()
                    if resp.status == 200 and result.get("status") == 1:
                        return SendResult(success=True, message_id=result.get("request"))
                    errors = result.get("errors", [result.get("message", "Unknown error")])
                    logger.error("Pushover send failed: %s", errors[0])
                    return SendResult(success=False, error=str(errors[0]))
        except aiohttp.ClientError as e:
            logger.error("Pushover HTTP error: %s", e)
            return SendResult(success=False, error=str(e))

    async def send_image(self, chat_id: str, image_url: str, caption: str = "") -> SendResult:
        content = f"{caption}\n\n{image_url}" if caption else image_url
        return await self.send(chat_id, content)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        # BasePlatformAdapter.get_chat_info is abstract AND async — must match signature.
        return {"name": "Pushover", "type": "user", "chat_id": self._user_key}


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin loader."""
    ctx.register_platform(
        name="pushover",
        label="Pushover",
        adapter_factory=PushoverAdapter,
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY"],
        install_hint="pip install aiohttp",  # shown only if aiohttp is missing
        setup_fn=interactive_setup,
        allowed_users_env="PUSHOVER_ALLOWED_USERS",
        allow_all_env="PUSHOVER_ALLOW_ALL_USERS",
        max_message_length=MAX_MESSAGE_LENGTH,
        emoji="\U0001f514",
        pii_safe=True,
        allow_update_command=False,
        cron_deliver_env_var="PUSHOVER_HOME_CHANNEL",
        platform_hint=(
            "You are sending a Pushover push notification. Keep messages very short \u2014 "
            "Pushover notifications are brief alerts, max 1024 characters. No markdown "
            "rendering. Use plain text. Pushover is fire-and-forget; do not expect a reply."
        ),
    )

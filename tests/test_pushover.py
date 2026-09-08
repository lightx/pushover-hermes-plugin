"""Tests for the Pushover platform plugin adapter.

Ported from hermes-agent tests/gateway/test_pushover.py with these changes:
- Import path: gateway.platforms.pushover → pushover_hermes_plugin.adapter
- check_pushover_requirements() → check_requirements() (aiohttp-only check)
- is_connected() tests added (env-var credential check moved here)
- Platform.PUSHOVER → adapter.platform.value == "pushover" (stable across enum changes)
- get_chat_info() is now async — tests use @pytest.mark.asyncio
- test_send_http_error: fixed to raise aiohttp.ClientError (adapter catches ClientError,
  not bare Exception — original test was using the wrong exception type)
- aiohttp.ClientSession patch target scoped to adapter module
"""

import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.config import PlatformConfig
from pushover_hermes_plugin.adapter import (
    PushoverAdapter,
    check_requirements,
    is_connected,
    validate_config,
    MAX_MESSAGE_LENGTH,
)


# ---------------------------------------------------------------------------
# check_requirements() — aiohttp availability only, NOT credentials
# ---------------------------------------------------------------------------

class TestCheckRequirements:
    """check_requirements() only verifies aiohttp is importable."""

    def test_returns_true_when_aiohttp_available(self):
        # aiohttp is a declared dependency — always present when plugin is installed.
        assert check_requirements() is True

    def test_returns_false_when_aiohttp_missing(self):
        import sys
        with patch.dict(sys.modules, {"aiohttp": None}):
            assert check_requirements() is False


# ---------------------------------------------------------------------------
# is_connected() — credential check (was check_pushover_requirements in core)
# ---------------------------------------------------------------------------

class TestIsConnected:
    """is_connected() checks env vars and config for credentials."""

    def test_false_when_both_env_vars_missing(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {}, clear=True):
            assert is_connected(config) is False

    def test_false_when_only_app_token(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok"}, clear=True):
            assert is_connected(config) is False

    def test_false_when_only_user_key(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_USER_KEY": "key"}, clear=True):
            assert is_connected(config) is False

    def test_true_when_both_env_vars_set(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "key"}, clear=True):
            assert is_connected(config) is True

    def test_true_when_config_has_both_fields(self):
        # api_key = PUSHOVER_APP_TOKEN, token = PUSHOVER_USER_KEY (hermes field convention)
        config = PlatformConfig(enabled=True, api_key="tok", token="key")
        with patch.dict("os.environ", {}, clear=True):
            assert is_connected(config) is True


# ---------------------------------------------------------------------------
# validate_config()
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_false_when_empty(self):
        assert validate_config(PlatformConfig(enabled=True)) is False

    def test_false_when_only_api_key(self):
        assert validate_config(PlatformConfig(enabled=True, api_key="tok")) is False

    def test_false_when_only_token(self):
        assert validate_config(PlatformConfig(enabled=True, token="key")) is False

    def test_true_when_both_set(self):
        assert validate_config(PlatformConfig(enabled=True, api_key="tok", token="key")) is True


# ---------------------------------------------------------------------------
# PushoverAdapter init
# ---------------------------------------------------------------------------

class TestPushoverAdapterInit:
    """Test PushoverAdapter initialization."""

    def test_platform_value_is_pushover(self):
        # Use .value == "pushover" — stable whether PUSHOVER enum member exists or not.
        config = PlatformConfig(enabled=True)
        adapter = PushoverAdapter(config)
        assert adapter.platform.value == "pushover"

    def test_reads_tokens_from_env(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "my-app-token", "PUSHOVER_USER_KEY": "my-user-key"}, clear=True):
            adapter = PushoverAdapter(config)
        assert adapter._app_token == "my-app-token"
        assert adapter._user_key == "my-user-key"

    def test_env_takes_precedence_over_config(self):
        # api_key in config = app token; token in config = user key
        config = PlatformConfig(enabled=True, api_key="config-app", token="config-user")
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "env-app", "PUSHOVER_USER_KEY": "env-user"}, clear=True):
            adapter = PushoverAdapter(config)
        assert adapter._app_token == "env-app"
        assert adapter._user_key == "env-user"

    def test_falls_back_to_config_when_no_env(self):
        # api_key = app token, token = user key (hermes PlatformConfig convention)
        config = PlatformConfig(enabled=True, api_key="config-app", token="config-user")
        with patch.dict("os.environ", {}, clear=True):
            adapter = PushoverAdapter(config)
        assert adapter._app_token == "config-app"
        assert adapter._user_key == "config-user"

    def test_reads_device_from_config_extra(self):
        config = PlatformConfig(enabled=True, extra={"device": "my-phone"})
        adapter = PushoverAdapter(config)
        assert adapter._device == "my-phone"

    def test_empty_device_when_not_set(self):
        config = PlatformConfig(enabled=True)
        adapter = PushoverAdapter(config)
        assert adapter._device == ""


# ---------------------------------------------------------------------------
# PushoverAdapter.send()
# ---------------------------------------------------------------------------

class TestPushoverAdapterSend:
    """Test PushoverAdapter.send()."""

    @pytest.fixture
    def adapter(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "user"}, clear=True):
            return PushoverAdapter(config)

    def _mock_session(self, json_data, status=200):
        mock_resp = AsyncMock()
        mock_resp.status = status
        mock_resp.json = AsyncMock(return_value=json_data)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)
        return mock_session

    @pytest.mark.asyncio
    async def test_send_success(self, adapter):
        mock_session = self._mock_session({"status": 1, "request": "req-abc123"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.send("user", "Hello world")
        assert result.success is True
        assert result.message_id == "req-abc123"

    @pytest.mark.asyncio
    async def test_send_uses_chat_id_as_user(self, adapter):
        """chat_id is passed as the 'user' field to Pushover."""
        mock_session = self._mock_session({"status": 1, "request": "req-1"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await adapter.send("target-user-key", "msg")
        call_data = mock_session.post.call_args[1]["data"]
        assert call_data["user"] == "target-user-key"

    @pytest.mark.asyncio
    async def test_send_falls_back_to_user_key_when_chat_id_empty(self, adapter):
        """Empty chat_id (home-channel cron) falls back to configured user key."""
        mock_session = self._mock_session({"status": 1, "request": "req-1"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await adapter.send("", "msg")
        call_data = mock_session.post.call_args[1]["data"]
        assert call_data["user"] == "user"  # adapter._user_key

    @pytest.mark.asyncio
    async def test_send_api_error(self, adapter):
        mock_session = self._mock_session({"status": 0, "errors": ["invalid token"]})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.send("user", "Hello world")
        assert result.success is False
        assert "invalid token" in result.error

    @pytest.mark.asyncio
    async def test_send_http_error(self, adapter):
        """aiohttp.ClientError is caught and returned as a failed SendResult."""
        with patch("aiohttp.ClientSession") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                side_effect=aiohttp.ClientError("Connection refused")
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await adapter.send("user", "Hello world")
        assert result.success is False
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_send_missing_credentials(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {}, clear=True):
            adapter = PushoverAdapter(config)
            result = await adapter.send("user", "Hello")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_send_metadata_title(self, adapter):
        """metadata['title'] is passed to Pushover payload."""
        mock_session = self._mock_session({"status": 1, "request": "req-1"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await adapter.send("user", "msg", metadata={"title": "Alert"})
        call_data = mock_session.post.call_args[1]["data"]
        assert call_data.get("title") == "Alert"


# ---------------------------------------------------------------------------
# Message truncation
# ---------------------------------------------------------------------------

class TestPushoverMessageTruncation:
    """Test message truncation at MAX_MESSAGE_LENGTH."""

    @pytest.fixture
    def adapter(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "user"}, clear=True):
            return PushoverAdapter(config)

    def test_max_message_length_constant(self):
        assert MAX_MESSAGE_LENGTH == 1024

    @pytest.mark.asyncio
    async def test_truncates_long_message(self, adapter):
        long_text = "x" * 1100

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": 1, "request": "req-abc"})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.send("user", long_text)

        assert result.success is True
        call_data = mock_session.post.call_args[1]["data"]
        assert len(call_data["message"]) <= 1024
        assert call_data["message"].endswith("...")

    @pytest.mark.asyncio
    async def test_short_message_not_truncated(self, adapter):
        short_text = "Hello, world!"
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": 1, "request": "req-1"})
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            await adapter.send("user", short_text)

        call_data = mock_session.post.call_args[1]["data"]
        assert call_data["message"] == short_text


# ---------------------------------------------------------------------------
# connect() — must accept is_reconnect kwarg (gateway reconnect contract)
# ---------------------------------------------------------------------------

class TestPushoverConnect:
    """connect() must accept the is_reconnect kwarg from the gateway's
    reconnect watcher (BasePlatformAdapter.connect contract).

    Regression: the gateway calls ``connect(is_reconnect=True)`` on every
    reconnect. The original signature ``connect(self)`` raised TypeError,
    preventing reconnection for the full 240s retry cycle.
    """

    @pytest.mark.asyncio
    async def test_connect_accepts_is_reconnect_false(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "user"}, clear=True):
            adapter = PushoverAdapter(config)
        result = await adapter.connect(is_reconnect=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_accepts_is_reconnect_true(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "user"}, clear=True):
            adapter = PushoverAdapter(config)
        result = await adapter.connect(is_reconnect=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_default_no_kwarg(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "user"}, clear=True):
            adapter = PushoverAdapter(config)
        result = await adapter.connect()
        assert result is True


# ---------------------------------------------------------------------------
# get_chat_info() — now async
# ---------------------------------------------------------------------------

class TestPushoverGetChatInfo:
    """Test get_chat_info() — async in the plugin (matches base class signature)."""

    @pytest.mark.asyncio
    async def test_returns_pushover_info(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "my-user"}, clear=True):
            adapter = PushoverAdapter(config)
            info = await adapter.get_chat_info("any-chat-id")
        assert info["name"] == "Pushover"
        assert info["type"] == "user"
        assert info["chat_id"] == "my-user"


# ---------------------------------------------------------------------------
# send_image()
# ---------------------------------------------------------------------------

class TestPushoverSendImage:
    """Test send_image() — falls back to caption + URL as text."""

    @pytest.fixture
    def adapter(self):
        config = PlatformConfig(enabled=True)
        with patch.dict("os.environ", {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "user"}, clear=True):
            return PushoverAdapter(config)

    @pytest.mark.asyncio
    async def test_send_image_with_caption(self, adapter):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": 1, "request": "req-abc"})
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.send_image("user", "https://example.com/img.jpg", "Look at this")

        assert result.success is True
        call_data = mock_session.post.call_args[1]["data"]
        assert "Look at this" in call_data["message"]
        assert "https://example.com/img.jpg" in call_data["message"]

    @pytest.mark.asyncio
    async def test_send_image_without_caption(self, adapter):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"status": 1, "request": "req-abc"})
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.send_image("user", "https://example.com/img.jpg")

        assert result.success is True
        call_data = mock_session.post.call_args[1]["data"]
        assert call_data["message"] == "https://example.com/img.jpg"

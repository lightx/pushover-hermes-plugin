# Pushover Plugin for Hermes Agent — Implementation Plan

> **For Hermes:** Use the subagent-driven-development skill to implement this plan task-by-task. Complete Stream A fully (including Task A4 install verification) before starting Stream B.

**Goal:** Extract Pushover from hermes-agent core into a standalone pip-installable plugin, eliminating merge-conflict surface and leveraging the upstream `platform_registry`.

**Architecture:** Two parallel work streams.

- **Stream A** — Standalone plugin repo at `/home/lightx/project/pushover-hermes-plugin/`. This is the deliverable: a pip package with a `pyproject.toml` entry point that hermes discovers automatically on startup. **Must be completed and installed before Stream B begins.**
- **Stream B** — Hermes-agent branch `feat/pushover-plugin` (from `nix-add-uv-runtime-v2`) at `/home/lightx/source/hermes-agent`. Removes all hardcoded Pushover references from core. **Requires Stream A installed** — Task B3 deletes `gateway/platforms/pushover.py`; without the plugin installed, hermes loses Pushover entirely.

**Distribution model:** Pip/entry-point (recommended). NixOS users install via `services.hermes-agent.extraPythonPackages` with `buildPythonPackage`. The entry-point group is `hermes_agent.plugins`.

**Reference:** `plugins/platforms/irc/` is the canonical bundled platform plugin example.

---

## Verified facts (confirmed by reading actual source)

| Claim | Status | Detail |
|-------|--------|--------|
| `plugin.yaml` parsed by pip/entry-point loader | **NO** | `_scan_entry_points()` → `ep.load()` → `register(ctx)` directly. No yaml parsing. Keep `plugin.yaml` for `extraPlugins` NixOS path and docs only. |
| `platform_hint` fallback in `run_agent.py` | **YES** | Lines 4950-4961: checks `PLATFORM_HINTS` first, then `platform_registry.get(key).platform_hint`. Task B6 (removing hint from `prompt_builder.py`) is safe. |
| `plugin_name` field used by setup wizard | **NO** | Field defined on `PlatformEntry` with a docstring promising auto-enable, but zero code reads it. Harmless to omit from the `_PLATFORMS` dict. |
| `BasePlatformAdapter.listen()` is abstract | **NO** | Only `connect()`, `disconnect()`, `send()`, `get_chat_info()` are abstract. No `listen()` needed. |
| `BasePlatformAdapter.get_chat_info()` is async | **YES** | `@abstractmethod async def get_chat_info(...)` at line 3005-3006. Must be `async def` in the adapter or `await adapter.get_chat_info()` callers will get `TypeError`. |
| `send()` abstract signature | confirmed | `(self, chat_id: str, content: str, reply_to=None, metadata=None) -> SendResult` |
| Config field mapping for Pushover | confirmed | `PlatformConfig.api_key` = PUSHOVER_APP_TOKEN (app token). `PlatformConfig.token` = PUSHOVER_USER_KEY (user key). Proven by `_send_pushover(pconfig.api_key, pconfig.token, ...)` in send_message_tool.py. |
| `requires_env` rich dict format valid | **YES** | Documented. Valid for directory-based plugins. Irrelevant for pip (yaml not read). |

---

## Inventory of Pushover references in core (Stream B removals)

| File | Lines | What | Action |
|------|-------|------|--------|
| `gateway/config.py:72` | `PUSHOVER = "pushover"` | Enum member | **Remove** — `_missing_()` creates it dynamically |
| `gateway/config.py:~1202-1209` | Env overrides block | Auto-config from env vars | **Keep, update** — replace `Platform.PUSHOVER` with `Platform("pushover")` |
| `gateway/platforms/pushover.py` | Entire file (114 lines) | Adapter | **Delete** — replaced by plugin |
| `gateway/run.py:~3426-3430` | `elif platform == Platform.PUSHOVER:` | Adapter instantiation | **Remove** — plugin registry handles it |
| `gateway/run.py:~3523` | `Platform.PUSHOVER: "PUSHOVER_ALLOWED_USERS"` | Auth env map | **Remove** — plugin's `allowed_users_env` handles it |
| `gateway/run.py:~3550` | `Platform.PUSHOVER: "PUSHOVER_ALLOW_ALL_USERS"` | Auth allow-all map | **Remove** — plugin's `allow_all_env` handles it |
| `cron/scheduler.py:~81` | `"pushover"` in `_KNOWN_DELIVERY_PLATFORMS` | Security allowlist | **Keep** — guards against env-var enumeration |
| `cron/scheduler.py:~102` | `"pushover": "PUSHOVER_USER_KEY"` | Home target env var | **Keep** — cron home-channel resolution |
| `tools/send_message_tool.py:~251` | Pushover home-channel fallback | `if platform == Platform.PUSHOVER and pconfig.token:` | **Remove** — adapter `send()` handles via `chat_id or self._user_key` |
| `tools/send_message_tool.py:~484` | `Platform.PUSHOVER: 1024` | Max message length | **Remove** — plugin's `max_message_length=1024` handles it |
| `tools/send_message_tool.py:~636-637` | `elif platform == Platform.PUSHOVER:` | Send dispatch | **Remove** — runtime adapter handles it |
| `tools/send_message_tool.py:~1645-1673` | `_send_pushover()` function | Standalone send helper | **Remove** — adapter `send()` replaces it |
| `toolsets.py:~474-478` | `"hermes-pushover"` toolset | Toolset definition | **Remove** — outbound-only, no tools needed |
| `toolsets.py:~489` | `"hermes-pushover"` in gateway includes | Toolset inclusion | **Remove** |
| `agent/prompt_builder.py:~376-379` | `"pushover"` platform hint | LLM guidance | **Remove** — plugin's `platform_hint` + fallback at `run_agent.py:4950-4961` |
| `hermes_cli/gateway.py:~2591-2606` | Setup wizard entry | Interactive setup | **Keep** — no `plugin_name` key needed (field unused) |
| `hermes_cli/status.py:~383` | `"Pushover": (...)` | Status display | **Remove** — `platform_registry.plugin_entries()` (line ~408) shows it automatically |
| `tests/gateway/test_pushover.py` | Entire file (203 lines) | Unit tests | **Delete** from core — adapted version goes in plugin repo |
| `tests/integration/test_tools_init.py:~85-174` | `TestPushoverIntegration` class | Integration tests | **Remove** from core |

**Kept intentionally:**
- `cron/scheduler.py:_KNOWN_DELIVERY_PLATFORMS` — security guard
- `cron/scheduler.py:_HOME_TARGET_ENV_VARS` — home-channel resolution
- `gateway/config.py:_apply_env_overrides()` — env-var-only UX (updated to use `Platform("pushover")`)
- `hermes_cli/gateway.py` setup wizard entry — interactive setup UX

---

## Stream A — Standalone plugin repo

### Task A1: Repo structure + pyproject.toml

**Objective:** Turn `/home/lightx/project/pushover-hermes-plugin/` into a proper pip package.

**Final directory layout:**

```
pushover-hermes-plugin/
├── pyproject.toml
├── plugin.yaml                       # for extraPlugins NixOS path + docs
├── pushover_hermes_plugin/
│   ├── __init__.py
│   └── adapter.py
└── tests/
    └── test_pushover.py              # moved from hermes-agent core
```

**Step 1:** Initialise git (repo does not exist yet)

```bash
cd /home/lightx/project/pushover-hermes-plugin
git init
git checkout -b main
```

**Step 2:** Write `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pushover-hermes-plugin"
version = "1.0.0"
description = "Pushover platform plugin for Hermes Agent — outbound push notifications"
requires-python = ">=3.11"
dependencies = ["aiohttp>=3.9"]

[project.entry-points."hermes_agent.plugins"]
pushover-platform = "pushover_hermes_plugin"
```

> **No `readme` field** — `readme = "README.md"` causes a setuptools error when the file doesn't exist. Omit it until a README is written. Add it back when publishing.

> **Why this entry-point value?**
> The loader does `ep.load()` on `"pushover_hermes_plugin"`, which imports the package and returns its module. It then calls `module.register(ctx)`. The entry-point name (`pushover-platform`) is the key hermes uses for de-duplication — it matches `name` in `plugin.yaml`.

**Step 3:** Write `plugin.yaml` (docs / extraPlugins compatibility — not read by pip loader)

```yaml
name: pushover-platform
kind: platform
version: 1.0.0
description: >
  Pushover gateway adapter for Hermes Agent.
  Sends push notifications via the Pushover API.
  Outbound-only — no inbound message handling.
author: Benoit Beauchamp
requires_env:
  - name: PUSHOVER_APP_TOKEN
    description: "API Token from your Pushover app (pushover.net/apps)"
    secret: false
  - name: PUSHOVER_USER_KEY
    description: "Your Pushover User Key (shown on pushover.net front page)"
    secret: false
```

**Step 4:** Create the package

```bash
mkdir -p pushover_hermes_plugin tests
```

**Step 5:** Write `pushover_hermes_plugin/__init__.py`

```python
from .adapter import register

__all__ = ["register"]
```

**Step 6:** Commit scaffold

```bash
git add pyproject.toml plugin.yaml pushover_hermes_plugin/__init__.py
git commit -m "feat: scaffold pushover-hermes-plugin package"
```

---

### Task A2: Write the adapter

**Objective:** Write `pushover_hermes_plugin/adapter.py` — the full plugin adapter based on the existing `gateway/platforms/pushover.py`, updated for the plugin API.

**Key changes from the original `gateway/platforms/pushover.py`:**
- `super().__init__(config, Platform.PUSHOVER)` → `super().__init__(config, Platform("pushover"))`
- `send(self, chat_id, text, **kwargs)` → correct abstract signature `send(self, chat_id, content, reply_to=None, metadata=None)`
- Add `chat_id or self._user_key` fallback so home-channel cron delivery works (replaces the removed fallback in `send_message_tool.py`)
- `get_chat_info()` kept — it's abstract AND async in the base class, so must be `async def`
- `send_image()` kept as-is
- No `listen()` needed — not abstract
- No `connected` property — not in the original adapter; base class manages connection state; override risks conflicting with base class tracking
- `interactive_setup()`: inline simple `input()` prompts — do NOT import `_prompt_env_var` from `hermes_cli.gateway` (private helper, will break on upstream refactor)
- `check_requirements()`: check aiohttp import ONLY — not credentials. `check_fn` is called by `create_adapter()`; returning False blocks adapter creation and shows the install hint. Credential state belongs in `is_connected()` so the platform stays registered even before env vars are set.

```python
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
    """Check whether Pushover is configured in config.yaml."""
    token = getattr(config, "token", "") or ""
    api_key = getattr(config, "api_key", "") or ""
    return bool(token and api_key)


def is_connected(config) -> bool:
    """True if credentials available from env or config.yaml."""
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
    print("  ─── 🔔 Pushover Setup ───")
    print("  1. Log in at https://pushover.net")
    print("  2. Your User Key is on the front page — copy it")
    print("  3. Create an app at https://pushover.net/apps → Create New Application")
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
        emoji="🔔",
        pii_safe=True,
        allow_update_command=False,
        platform_hint=(
            "You are sending a Pushover push notification. Keep messages very short — "
            "Pushover notifications are brief alerts, max 1024 characters. No markdown "
            "rendering. Use plain text. Pushover is fire-and-forget; do not expect a reply."
        ),
    )
```

**Step 1:** Write the file, then syntax-check:

```bash
python3 -c "import ast; ast.parse(open('pushover_hermes_plugin/adapter.py').read()); print('OK')"
```

**Step 2:** Commit

```bash
git add pushover_hermes_plugin/adapter.py
git commit -m "feat: add PushoverAdapter with register() entry point"
```

---

### Task A3: Move and adapt tests

**Objective:** Port `tests/gateway/test_pushover.py` from hermes-agent (203 lines) into `tests/test_pushover.py` in this repo.

**Import changes:**
- `from gateway.platforms.pushover import PushoverAdapter, check_pushover_requirements` → `from pushover_hermes_plugin.adapter import PushoverAdapter, check_requirements`
- `Platform.PUSHOVER` → `Platform("pushover")`
- `check_pushover_requirements` → `check_requirements`
- `send(..., text=...)` → `send(..., content=...)`

**Step 1:** Copy and adapt the test file.

**Step 2:** Run tests (requires hermes-agent installed or on PYTHONPATH):

```bash
cd /home/lightx/source/hermes-agent
nix develop -c bash -c "cd /home/lightx/project/pushover-hermes-plugin && python -m pytest tests/ -v --tb=short"
```

**Step 3:** Commit

```bash
git add tests/
git commit -m "feat: add adapted unit tests from hermes-agent core"
```

---

### Task A4: Install and smoke test

**Step 1:** Install the plugin into the hermes venv

```bash
cd /home/lightx/source/hermes-agent
nix develop -c pip install -e /home/lightx/project/pushover-hermes-plugin
```

**Step 2:** Verify entry point discovery

```bash
nix develop -c python -c "
import importlib.metadata
eps = importlib.metadata.entry_points(group='hermes_agent.plugins')
names = [ep.name for ep in eps]
assert 'pushover-platform' in names, f'Not found. Got: {names}'
print('Entry point discovered:', names)
"
```

**Step 3:** Verify plugin registration

```bash
nix develop -c python -c "
from hermes_cli.plugins import PluginManager
pm = PluginManager()
pm.discover_and_load()
from gateway.platform_registry import platform_registry
entry = platform_registry.get('pushover')
assert entry is not None, 'pushover not in registry'
assert entry.label == 'Pushover'
assert entry.max_message_length == 1024
assert entry.allowed_users_env == 'PUSHOVER_ALLOWED_USERS'
assert entry.platform_hint.startswith('You are sending a Pushover')
print('Plugin registration OK')
print('platform_hint:', entry.platform_hint[:60])
"
```

**Step 4:** Verify `Platform("pushover")` resolves

```bash
nix develop -c python -c "
from hermes_cli.plugins import PluginManager
pm = PluginManager()
pm.discover_and_load()
from gateway.config import Platform
p = Platform('pushover')
assert p is not None
assert p.value == 'pushover'
print('Platform resolution OK:', p)
"
```

---

## Stream B — Hermes-agent core cleanup

### Task B1: Create branch

```bash
cd /home/lightx/source/hermes-agent
git checkout nix-add-uv-runtime-v2
git checkout -b feat/pushover-plugin
```

---

### Task B2: Remove Platform.PUSHOVER + update env overrides (gateway/config.py)

**File:** `gateway/config.py`

**Step 1:** Remove the enum member at line ~72:
```python
    PUSHOVER = "pushover"
```

**Step 2:** In `_apply_env_overrides()` (~lines 1202-1209), replace `Platform.PUSHOVER` with `Platform("pushover")`:

```python
# Before
    if pushover_app and pushover_user:
        if Platform.PUSHOVER not in config.platforms:
            config.platforms[Platform.PUSHOVER] = PlatformConfig()
        config.platforms[Platform.PUSHOVER].enabled = True
        config.platforms[Platform.PUSHOVER].api_key = os.getenv("PUSHOVER_APP_TOKEN", "")
        config.platforms[Platform.PUSHOVER].token = os.getenv("PUSHOVER_USER_KEY", "")

# After
    if pushover_app and pushover_user:
        try:
            pushover_platform = Platform("pushover")  # resolved via _missing_()
        except ValueError:
            # Plugin not registered yet (e.g. unit test without discover_and_load()).
            # _missing_() returns None → enum raises ValueError.
            # Use pass+else to skip only this block, not the rest of the function.
            pass
        else:
            if pushover_platform not in config.platforms:
                config.platforms[pushover_platform] = PlatformConfig()
            config.platforms[pushover_platform].enabled = True
            config.platforms[pushover_platform].api_key = pushover_app   # PUSHOVER_APP_TOKEN
            config.platforms[pushover_platform].token = pushover_user    # PUSHOVER_USER_KEY
```

> **Why keep this block?** `send_message` and cron need a `PlatformConfig` instance. Without it, env-var-only UX (no config.yaml) stops working.
>
> **Why `try/except/else` and not `return`?** `_apply_env_overrides()` processes multiple platforms. Using `return` inside the Pushover block would exit the entire function and skip env overrides for any platforms defined after Pushover. The `else` clause runs only when no exception was raised, cleanly scoping the guard to this block only.
>
> **Ordering:** Plugin `register()` is called during `discover_and_load()` at startup — before `_apply_env_overrides()` runs. The guard only fires in test/import contexts that bypass plugin loading.

**Step 3:** Scan for remaining `Platform.PUSHOVER` references:

```bash
grep -rn 'Platform\.PUSHOVER' --include='*.py' . | grep -v '__pycache__'
```

Any remaining hits outside of `plugins/` must be changed to `Platform("pushover")`.

**Step 4:** Syntax check + commit

```bash
python3 -c "import ast; ast.parse(open('gateway/config.py').read()); print('OK')"
git add gateway/config.py
git commit -m "feat(pushover-plugin): remove Platform.PUSHOVER enum, use dynamic resolution"
```

---

### Task B3: Remove Pushover from gateway/run.py

**Step 1:** Remove the adapter block (~lines 3426-3430):

```python
elif platform == Platform.PUSHOVER:
    from gateway.platforms.pushover import PushoverAdapter, check_pushover_requirements
    if not check_pushover_requirements():
        logger.warning("Pushover: PUSHOVER_APP_TOKEN or PUSHOVER_USER_KEY not set")
        return None
    return PushoverAdapter(config)
```

**Step 2:** Remove `Platform.PUSHOVER: "PUSHOVER_ALLOWED_USERS"` from auth map (~line 3523).

**Step 3:** Remove `Platform.PUSHOVER: "PUSHOVER_ALLOW_ALL_USERS"` from allow-all map (~line 3550).

**Step 4:** Delete the old adapter file:

```bash
git rm gateway/platforms/pushover.py
```

**Step 5:** Commit

```bash
git add gateway/run.py
git commit -m "feat(pushover-plugin): remove Pushover from gateway adapter and auth maps"
```

---

### Task B4: Remove Pushover from tools/send_message_tool.py

**Step 1:** Remove home-channel fallback (~line 251):
```python
        if platform == Platform.PUSHOVER and pconfig.token:
            chat_id = pconfig.token
```
This is now inside `PushoverAdapter.send()` via `effective_user = chat_id or self._user_key`.

**Step 2:** Remove `Platform.PUSHOVER: 1024` from `_MAX_LENGTHS` (~line 484). Plugin's `max_message_length=1024` handles it.

**Step 3:** Remove send dispatch (~lines 636-637):
```python
        elif platform == Platform.PUSHOVER:
            result = await _send_pushover(pconfig.api_key, pconfig.token, chunk)
```

**Step 4:** Remove `_send_pushover()` function (~lines 1645-1673).

**Step 5:** Commit

```bash
git add tools/send_message_tool.py
git commit -m "feat(pushover-plugin): remove Pushover-specific send logic from send_message_tool"
```

---

### Task B5: Remove Pushover from toolsets.py

**Step 1:** Remove the toolset definition (~lines 474-478):
```python
    "hermes-pushover": {
        "description": "Pushover bot toolset - send push notifications via Pushover",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
```

**Step 2:** Remove `"hermes-pushover"` from the `hermes-gateway` includes list (~line 489).

**Step 3:** Commit

```bash
git add toolsets.py
git commit -m "feat(pushover-plugin): remove hermes-pushover toolset"
```

---

### Task B6: Remove Pushover from agent/prompt_builder.py

**Step 1:** Remove the entry (~lines 376-379):
```python
    "pushover": (
        "You are sending a Pushover push notification. Keep messages very short — "
        ...
    ),
```

**Safe because:** Fallback confirmed at `run_agent.py:4950-4961` — checks `platform_registry.get("pushover").platform_hint` when key not in `PLATFORM_HINTS`.

**Step 2:** Commit

```bash
git add agent/prompt_builder.py
git commit -m "feat(pushover-plugin): remove Pushover from PLATFORM_HINTS (registry fallback at run_agent.py:4950)"
```

---

### Task B7: Remove Pushover from hermes_cli/status.py

**Step 1:** Remove (~line 383):
```python
        "Pushover": ("PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY"),
```

`status.py` already iterates `platform_registry.plugin_entries()` (~line 408) — Pushover appears automatically with a `(plugin)` tag.

**Step 2:** Commit

```bash
git add hermes_cli/status.py
git commit -m "feat(pushover-plugin): remove Pushover from static status list"
```

---

### Task B8: Keep hermes_cli/gateway.py setup wizard entry (no changes needed)

The existing setup entry for Pushover (~lines 2591-2606) works as-is. No `plugin_name` key is needed — the field exists on `PlatformEntry` but no wizard code reads it (verified). The setup wizard presents the interactive credential prompts and the plugin's `setup_fn` (our `interactive_setup()`) is called when the user selects Pushover in the menu. No changes required to `gateway.py`.

---

### Task B9: Remove core tests for Pushover

**Step 1:** Delete the unit test file (now lives in plugin repo):

```bash
git rm tests/gateway/test_pushover.py
```

**Step 2:** Remove `TestPushoverIntegration` class from `tests/integration/test_tools_init.py` (~lines 85-174).

**Step 3:** Commit

```bash
git add tests/
git commit -m "feat(pushover-plugin): remove Pushover tests from core (moved to plugin repo)"
```

---

### Task B10: Integration verification

**Step 1:** No stale `Platform.PUSHOVER` references:
```bash
grep -rn 'Platform\.PUSHOVER' --include='*.py' . | grep -v '__pycache__'
# Expected: no output
```

**Step 2:** No stale imports of the deleted adapter:
```bash
grep -rn 'gateway\.platforms\.pushover\|from gateway.platforms.pushover' --include='*.py' . | grep -v '__pycache__'
# Expected: no output
```

**Step 3:** Only expected references remain for "pushover" in core:
```bash
grep -rn '"pushover"\|pushover' --include='*.py' \
  gateway/config.py cron/scheduler.py hermes_cli/gateway.py \
  | grep -v '__pycache__'
```
Expected remaining hits:
- `gateway/config.py` — env overrides block using `Platform("pushover")`
- `cron/scheduler.py` — `_KNOWN_DELIVERY_PLATFORMS` and `_HOME_TARGET_ENV_VARS`
- `hermes_cli/gateway.py` — setup wizard entry

**Step 4:** Syntax check all modified files:
```bash
python3 -c "
import ast
files = [
    'gateway/config.py', 'gateway/run.py', 'tools/send_message_tool.py',
    'toolsets.py', 'agent/prompt_builder.py', 'hermes_cli/status.py',
]
for f in files:
    try:
        ast.parse(open(f).read())
        print(f'OK: {f}')
    except SyntaxError as e:
        print(f'SYNTAX ERROR {f}: {e}')
"
```

**Step 5:** Run tests (skip e2e):
```bash
nix develop -c pytest tests/ -x --tb=short -q --ignore=tests/e2e 2>&1 | tail -30
```

**Step 6:** Smoke test
```bash
nix develop -c python -c "import run_agent, cli, hermes_cli; print('OK')"
```

---

### Task B11: Update upstream-merge skill

**File:** `~/.hermes/skills/hermes/hermes-agent-upstream-merge/SKILL.md`

> **Note:** The skill is currently in `.archive/` — move it to `hermes/` before editing:
> ```bash
> mv ~/.hermes/skills/.archive/hermes-agent-upstream-merge ~/.hermes/skills/hermes/hermes-agent-upstream-merge
> ```

**Changes:**

1. In the **Known Conflict Files** table, update the Pushover row:
   - Current: `gateway/run.py` says "HEAD has ad-hoc `hermes_cli.plugins` hook"
   - Change to: note that Pushover is now a standalone plugin — any upstream changes to `gateway/platforms/pushover.py` are superseded by `pushover-hermes-plugin`

2. In the **Local-Only Additions** table, remove these rows (now handled by the plugin):
   - `tools/send_message_tool.py` — Pushover home-channel fallback
   - `gateway/run.py` — `elif platform == Platform.PUSHOVER:` adapter block
   - `gateway/run.py` — `Platform.PUSHOVER: "PUSHOVER_ALLOWED_USERS"` auth env map
   - `gateway/run.py` — `Platform.PUSHOVER: "PUSHOVER_ALLOW_ALL_USERS"` allow-all map

   Keep these rows (still local, not replaced by plugin):
   - `cron/scheduler.py` — `"pushover"` in `_KNOWN_DELIVERY_PLATFORMS`
   - `cron/scheduler.py` — `"pushover": "PUSHOVER_USER_KEY"` in `_HOME_TARGET_ENV_VARS`
   - `nix/devShell.nix` — `python313`

3. In the **Pushover Audit** section, update the expected pattern:
   - `gateway/run.py`: no longer has Pushover adapter block — handled by plugin registry
   - `gateway/config.py`: no longer has `PUSHOVER = "pushover"` enum — uses `Platform("pushover")` dynamic resolution
   - `tools/send_message_tool.py`: no longer has Pushover-specific fallback or `_send_pushover()` — adapter handles it

4. Add a note at the bottom of the Local-Only Additions section:

   > **Pushover is now a standalone plugin** (`pushover-hermes-plugin`). After merging upstream, verify the plugin is still installed (`pip show pushover-hermes-plugin`). Do NOT re-add Pushover adapter code to core — the plugin's `register()` entry point + `platform_registry` handles everything except the cron scheduler entries above.

No git commit needed — skills live outside the repo.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Stream B deletes core adapter before plugin installed | **Stream A must be installed first.** `gateway/platforms/pushover.py` deleted in B3 — hermes breaks if plugin isn't in the venv. |
| `Platform("pushover")` called before plugin loads | `try/except ValueError / else` pattern in `_apply_env_overrides()` — skips the Pushover block only, not the entire function. `_missing_()` returns None → enum raises ValueError for unregistered values. Plugin loads at startup before this runs. |
| `create_adapter()` returns None when no credentials | Expected. `check_fn` only checks aiohttp (always True when installed). `is_connected()` covers credential state. |
| Cron delivery fails | Keep `"pushover"` in `_KNOWN_DELIVERY_PLATFORMS` and `_HOME_TARGET_ENV_VARS` — not replaced by the plugin system. |
| `send_message` can't find pconfig | Keep env override block in `_apply_env_overrides()` using `Platform("pushover")`. |
| `interactive_setup()` breaks on hermes refactor | Inlined prompts + direct file write — no dependency on `hermes_cli.gateway` private helpers. |
| Venv stale after moving files | `rm .venv/.nix-stamp` then rebuild. |
| Plugin not found after pip install | Verify with `importlib.metadata.entry_points(group='hermes_agent.plugins')`. |

---

## NixOS distribution reference

```nix
# configuration.nix
services.hermes-agent.extraPythonPackages = [
  (pkgs.python312Packages.buildPythonPackage {
    pname = "pushover-hermes-plugin";
    version = "1.0.0";
    src = pkgs.fetchFromGitHub {
      owner = "benoitbeauchamp";   # update when published
      repo = "pushover-hermes-plugin";
      rev = "v1.0.0";
      hash = "sha256-...";        # nix-prefetch-url --unpack
    };
    format = "pyproject";
    build-system = [ pkgs.python312Packages.setuptools ];
  })
];
```

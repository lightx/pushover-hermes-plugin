# pushover-hermes-plugin

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that adds [Pushover](https://pushover.net) as a notification platform. Outbound-only — sends push notifications, no inbound message handling.

It also provides opt-in agent lifecycle notifications (finished, questions, errors, approvals, blockers) delivered via Pushover and/or native desktop notifications.

## What this plugin does on your machine

- **Network:** sends HTTPS POST requests to `https://api.pushover.net/1/messages.json` (Pushover's API) with your app token, user key and the notification text. No other network calls, no telemetry.
- **Notification content:** when lifecycle notifications are enabled, excerpts of the agent's replies, questions, errors and terminal commands awaiting approval are sent to Pushover. Use `PUSHOVER_NOTIFY_QUESTION=minimal` to send generic messages instead.
- **Shell commands:** runs `notify-send` only when native notifications are enabled (`PUSHOVER_NOTIFY_NATIVE=true` or `/notifications enable native`).
- **Files written:** `$HERMES_HOME/logs/pushover_hermes_plugin.log` (plugin log), `$HERMES_HOME/plugin-data/pushover-hermes-plugin/settings.json` (enable/disable state saved by `/notifications save`), and `$HERMES_HOME/.env` (only when you run the interactive setup wizard).
- **Background processes:** none.

## Requirements

- Python 3.11+
- `aiohttp >= 3.9, < 4`
- A [Pushover](https://pushover.net) account with an app token and user key
- Optional: `notify-send` (libnotify) for native desktop notifications

## Installation

### From a remote Git repository

```bash
hermes plugins install lightx/pushover-hermes-plugin --enable
```

### From a local clone (development)

```bash
git clone https://github.com/lightx/pushover-hermes-plugin.git
cd pushover-hermes-plugin
hermes plugins install file://$(pwd) --enable
```

This installs the plugin and enables it in a single step. To install without enabling:

```bash
hermes plugins install file://$(pwd) --no-enable
```

### Other plugin management commands

```bash
hermes plugins list                                  # table: enabled / disabled / not enabled
hermes plugins enable pushover-hermes-plugin         # add to allow-list
hermes plugins disable pushover-hermes-plugin        # remove from allow-list
hermes plugins update pushover-hermes-plugin         # pull latest
hermes plugins remove pushover-hermes-plugin         # uninstall
```

> **Upgrading from 1.0.x:** the plugin was renamed from `pushover-platform` to `pushover-hermes-plugin`. Replace `pushover-platform` with `pushover-hermes-plugin` in `plugins.enabled` (config.yaml), otherwise the gateway silently skips the plugin.

After installing, restart the gateway:

```bash
hermes gateway restart --system   # or: sudo hermes gateway restart --system
```

## Configuration

### Option 1 — Environment variables (recommended)

```bash
export PUSHOVER_APP_TOKEN=your_app_token   # from pushover.net/apps
export PUSHOVER_USER_KEY=your_user_key     # from pushover.net front page
```

### Option 2 — config.yaml

```yaml
gateway:
  platforms:
    pushover:
      enabled: true
      api_key: <PUSHOVER_APP_TOKEN>
      token: <PUSHOVER_USER_KEY>
      extra:
        device: ""   # optional: restrict to a specific device name
```

> **Note:** environment variables always take precedence over config.yaml values.

### Option 3 — Interactive setup

```bash
hermes gateway setup
```

Select Pushover from the platform list. The wizard prompts for your credentials and writes them to `~/.hermes/.env`.

## Access control

Restrict which Pushover user keys can receive notifications:

```bash
export PUSHOVER_ALLOWED_USERS=user_key_1,user_key_2   # comma-separated
export PUSHOVER_ALLOW_ALL_USERS=true                  # disable restriction
```

## Agent lifecycle notifications

Off by default. Enable with:

```bash
export PUSHOVER_NOTIFY_ENABLED=true     # Pushover lifecycle notifications
export PUSHOVER_NOTIFY_NATIVE=true      # native desktop notifications (notify-send)
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `PUSHOVER_NOTIFY_STATES` | `all` | Space-separated subset of `finished questions errors pre-approval post-approval blockers`, or `usual` (everything except `post-approval`) / `all` |
| `PUSHOVER_NOTIFY_QUESTION` | `full` | Detail level: `full`, `summary`, or `minimal` (no agent text sent) |
| `PUSHOVER_NOTIFY_DEVICE` | — | Restrict lifecycle notifications to one Pushover device |

`blockers` covers blocked kanban tasks and, on Hermes releases newer than v0.21.5, the masked sudo password prompt (the command will time out if nobody answers). On older releases the sudo alert is silently unavailable.

Hooks used: `post_llm_call`, `pre_approval_request`, `post_approval_response`, `pre_tool_call`, `post_tool_call`, `on_human_input_request`.

### `/notifications` command

```
/notifications status                     show current state
/notifications test pushover|native       send a test notification
/notifications enable pushover|native     turn a channel on
/notifications disable pushover|native    turn a channel off
/notifications save                       persist enable/disable state across restarts
```

## Logging

Plugin logs are written to `~/.hermes/logs/pushover_hermes_plugin.log`.

The log level defaults to `logging.level` from `~/.hermes/config.yaml`:

```yaml
logging:
  level: DEBUG   # inherited by pushover plugin
```

To override only for this plugin (useful for verbose debug without affecting other logs):

```bash
export PUSHOVER_LOG_LEVEL=DEBUG
```

After changing the log level, restart the gateway:

```bash
hermes gateway restart --system
```

## Behaviour

- Messages are truncated to 1024 characters (Pushover API limit)
- Images are sent as a text message containing the URL and caption
- `metadata["title"]` is forwarded as the notification title when present
- `PUSHOVER_HOME_CHANNEL` (defaults to `PUSHOVER_USER_KEY`) is the home channel for `send_message(target="pushover")`, `hermes send -t pushover` and cron `deliver=pushover`; `pushover:<user-or-group-key>` targets a specific key
- Fire-and-forget — no reply handling

## Credits

Lifecycle notifications, native notifications, the `/notifications` command, setup wizard and CI were contributed by [Cosmin Diaconu](https://github.com/bcdiaconu).

## License

[MIT](LICENSE) — provided as-is, no warranty.

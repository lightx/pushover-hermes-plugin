# pushover-hermes-plugin

A [Hermes Agent](https://github.com/benoitbeauchamp/hermes-agent) plugin that adds [Pushover](https://pushover.net) as a notification platform. Outbound-only — sends push notifications, no inbound message handling.

## Requirements

- Python 3.11+
- `aiohttp >= 3.9`
- A [Pushover](https://pushover.net) account with an app token and user key

## Installation

### From a remote Git repository

```bash
hermes plugins install user/repo --enable
```

### From a local clone (development)

```bash
git clone https://github.com/user/pushover-hermes-plugin.git
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
- Fire-and-forget — no reply handling

## License

[MIT](LICENSE) — provided as-is, no warranty.

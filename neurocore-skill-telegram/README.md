# neurocore-skill-telegram

Send Telegram messages from a NeuroCore flow (e.g. notifications, alerts,
human-approval pings) via the [Telegram Bot API](https://core.telegram.org/bots/api).

```bash
pip install neurocore-skill-telegram
export TELEGRAM_BOT_TOKEN=123456:ABC...
```

```yaml
components:
  - name: notify
    type: telegram
    config:
      chat_id: "123456789"
      parse_mode: Markdown
flow:
  type: sequential
  steps:
    - component: notify
```

Reads `telegram_text` (and optional `telegram_chat_id`, overriding config);
writes the Bot API response to `telegram_result`.

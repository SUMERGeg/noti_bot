"""Register Telegram webhook/menu without putting the token into shell history."""
import os

import httpx
from dotenv import load_dotenv


def main():
    load_dotenv()
    token = os.environ.get("BOT_TOKEN", "")
    url = os.environ.get("PUBLIC_URL", "").rstrip("/")
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not token or not secret or not url.startswith("https://"):
        raise SystemExit("Укажите BOT_TOKEN, WEBHOOK_SECRET и HTTPS PUBLIC_URL в .env")
    calls = {
        "setWebhook": {"url": url + "/telegram/webhook", "secret_token": secret, "allowed_updates": ["message"]},
        "setChatMenuButton": {"menu_button": {"type": "web_app", "text": "Мои карточки", "web_app": {"url": url}}},
        "setMyCommands": {"commands": [{"command": "start", "description": "Открыть мои карточки"}, {"command": "cards", "description": "Мои карточки и напоминания"}]},
    }
    try:
        for method, body in calls.items():
            result = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=body, timeout=20)
            result.raise_for_status()
            if not result.json().get("ok"):
                raise ValueError()
    except (httpx.HTTPError, ValueError):
        raise SystemExit("Telegram не принял настройки. Проверьте токен, HTTPS URL и WEBHOOK_SECRET.") from None
    print("Готово. Отправьте боту /start и откройте «Мои карточки».")


if __name__ == "__main__":
    main()

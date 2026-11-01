import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schedule import CardInput, next_due


def signed(user=42):
    values = {"auth_date": str(int(time.time())), "user": json.dumps({"id": user})}
    secret = hmac.new(b"WebAppData", b"test-token", hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, "\n".join(f"{k}={v}" for k, v in sorted(values.items())).encode(), hashlib.sha256).hexdigest()
    return {"Authorization": "tma " + urlencode(values)}


def card(**kw):
    return {"title": "Прочитать карточку", "description": "Мой текст", "times": ["12:00", "16:00"], "repeat": "daily", "weekdays": [], "monthdays": [], "timezone": "Europe/Moscow", **kw}


@pytest.fixture
def client(tmp_path):
    app = create_app(database_url=f"sqlite:///{tmp_path / 'test.db'}", bot_token="test-token", job_secret="jobs", webhook_secret="hook", public_url="https://example.com")
    with TestClient(app) as c:
        yield c


def test_daily_weekly_monthly_and_timezone():
    now = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    assert next_due(CardInput(**card()), now).isoformat() == "2026-11-01T13:00:00+00:00"
    assert next_due(CardInput(**card(repeat="weekly", weekdays=[0])), now).isoformat() == "2026-11-02T09:00:00+00:00"
    assert next_due(CardInput(**card(repeat="monthly", monthdays=[31])), now).isoformat() == "2026-12-31T09:00:00+00:00"


@pytest.mark.parametrize("change", [{"title": " "}, {"times": []}, {"times": ["25:00"]}, {"repeat": "weekly"}, {"repeat": "monthly", "monthdays": [32]}, {"timezone": "Bad/Zone"}])
def test_invalid_card(change):
    with pytest.raises(ValueError):
        CardInput(**card(**change))


def test_crud_persistence_and_ownership(client):
    assert client.get("/api/cards").status_code == 401
    assert client.get("/api/cards", headers={"Authorization": "tma forged"}).status_code == 401
    result = client.post("/api/cards", headers=signed(), json=card())
    assert result.status_code == 201
    ident = result.json()["id"]
    assert client.get("/api/cards", headers=signed()).json()[0]["description"] == "Мой текст"
    assert client.get("/api/cards", headers=signed(99)).json() == []
    assert client.put(f"/api/cards/{ident}", headers=signed(99), json=card()).status_code == 404
    assert client.put(f"/api/cards/{ident}", headers=signed(), json=card(title="Таблетка", description="")).json()["title"] == "Таблетка"
    assert client.delete(f"/api/cards/{ident}", headers=signed(99)).status_code == 404
    assert client.delete(f"/api/cards/{ident}", headers=signed()).status_code == 204
    assert client.get("/api/cards", headers=signed()).json() == []


def test_jobs_send_once_and_deep_link(client):
    from app.store import Card
    sent = []
    client.app.state.telegram_send = lambda method, body: sent.append((method, body))
    ident = client.post("/api/cards", headers=signed(), json=card()).json()["id"]
    with client.app.state.sessions.begin() as db:
        row = db.get(Card, ident)
        row.next_at = datetime.now(timezone.utc).replace(tzinfo=None)
    assert client.post("/jobs/tick").status_code == 401
    assert client.post("/jobs/tick", headers={"Authorization": "Bearer jobs"}).json()["sent"] == 1
    assert client.post("/jobs/tick", headers={"Authorization": "Bearer jobs"}).json()["sent"] == 0
    assert sent[0][1]["text"] == "Прочитать карточку"
    assert sent[0][1]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == f"https://example.com/?card={ident}"


def test_webhook_secret_and_start(client):
    sent = []
    client.app.state.telegram_send = lambda method, body: sent.append(body)
    update = {"message": {"chat": {"id": 42, "type": "private"}, "text": "/start"}}
    assert client.post("/telegram/webhook", json=update).status_code == 401
    assert client.post("/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": "hook"}, json=update).status_code == 200
    assert sent[0]["chat_id"] == 42
    assert sent[0]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == "https://example.com"


def test_failed_send_retries_without_losing_reminder(client):
    from app.store import Card
    def offline(method, body):
        raise RuntimeError("offline")
    client.app.state.telegram_send = offline
    ident = client.post("/api/cards", headers=signed(), json=card(description="")).json()["id"]
    with client.app.state.sessions.begin() as db:
        db.get(Card, ident).next_at = datetime.now(timezone.utc).replace(tzinfo=None)
    assert client.post("/jobs/tick", headers={"Authorization": "Bearer jobs"}).status_code == 503
    sent = []
    client.app.state.telegram_send = lambda method, body: sent.append(body)
    assert client.post("/jobs/tick", headers={"Authorization": "Bearer jobs"}).json()["sent"] == 1
    assert sent == [{"chat_id": 42, "text": "Прочитать карточку"}]


def test_dst_gap_and_repeated_hour():
    data = CardInput(**card(times=["02:30"], timezone="Europe/Berlin"))
    assert next_due(data, datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc)).isoformat() == "2026-03-30T00:30:00+00:00"
    assert next_due(data, datetime(2026, 10, 25, 0, 31, tzinfo=timezone.utc)).isoformat() == "2026-10-26T01:30:00+00:00"


def test_stale_reminder_skipped_and_auth_tampering(client):
    from datetime import timedelta
    from app.store import Card
    assert client.get("/api/cards", headers={"Authorization": signed()["Authorization"].replace("42", "99")}).status_code == 401
    sent = []
    client.app.state.telegram_send = lambda method, body: sent.append(body)
    ident = client.post("/api/cards", headers=signed(), json=card()).json()["id"]
    with client.app.state.sessions.begin() as db:
        db.get(Card, ident).next_at = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None)
    assert client.post("/jobs/tick", headers={"Authorization": "Bearer jobs"}).json()["sent"] == 0
    assert sent == []
    assert datetime.fromisoformat(client.get("/api/cards", headers=signed()).json()[0]["next_at"]) > datetime.now(timezone.utc)


@pytest.mark.parametrize("override,expected", [("", "https://noti-bot.onrender.com"), ("https://custom.example", "https://custom.example")])
def test_render_url_without_manual_configuration(tmp_path, monkeypatch, override, expected):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://noti-bot.onrender.com")
    monkeypatch.setenv("PUBLIC_URL", override)
    app = create_app(database_url=f"sqlite:///{tmp_path / 'render.db'}", webhook_secret="hook", dev_mode=False)
    sent = []
    app.state.telegram_send = lambda method, body: sent.append(body)
    with TestClient(app) as client:
        client.post("/telegram/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": "hook"}, json={"message": {"chat": {"id": 42, "type": "private"}, "text": "/start"}})
    assert sent[0]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"] == expected

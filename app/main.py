import asyncio
import hmac
import logging
import os
import threading
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.auth import telegram_user
from app.schedule import CardInput, next_due
from app.store import Base, Card

logger = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def utcnow():
    return datetime.now(timezone.utc)


def naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def serialize(row):
    return {"id": row.id, **{key: getattr(row, key) for key in CardInput.model_fields},
            "next_at": row.next_at.replace(tzinfo=timezone.utc).isoformat()}


def create_app(database_url=None, bot_token=None, job_secret=None, webhook_secret=None, public_url=None, dev_mode=None):
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///cards.db")
    if database_url.startswith(("postgres://", "postgresql://")):
        database_url = "postgresql+psycopg://" + database_url.split("://", 1)[1]
    token = bot_token if bot_token is not None else os.getenv("BOT_TOKEN", "")
    jobs = job_secret if job_secret is not None else os.getenv("JOB_SECRET", "")
    hook = webhook_secret if webhook_secret is not None else os.getenv("WEBHOOK_SECRET", "")
    url = (public_url or os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL", "")).rstrip("/")
    demo = dev_mode if dev_mode is not None else os.getenv("DEV_MODE", "false").lower() == "true"
    owner = int(os.getenv("OWNER_TELEGRAM_ID", "0"))
    if os.getenv("RENDER"):
        if demo or database_url.startswith("sqlite") or not all([token, jobs, hook, url.startswith("https://")]):
            raise RuntimeError("Render: задайте PostgreSQL DATABASE_URL, BOT_TOKEN, JOB_SECRET, WEBHOOK_SECRET; нужен HTTPS PUBLIC_URL или RENDER_EXTERNAL_URL; DEV_MODE должен быть false")
    engine = create_engine(database_url, pool_pre_ping=True,
                           connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})
    sessions = sessionmaker(engine, expire_on_commit=False)
    local_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        if engine.dialect.name == "postgresql":
            # Supabase exposes public tables via its API. Only our DB owner may
            # access cards; no anonymous/authenticated API policies are created.
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE cards ENABLE ROW LEVEL SECURITY"))
        task = None
        if os.getenv("LOCAL_SCHEDULER", "false").lower() == "true" and not demo:
            async def loop():
                while True:
                    try:
                        await asyncio.to_thread(tick)
                    except Exception:
                        logger.error("Ошибка локального планировщика")
                    await asyncio.sleep(30)
            task = asyncio.create_task(loop())
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        engine.dispose()

    app = FastAPI(title="Рядом · напоминания", lifespan=lifespan)
    app.state.sessions = sessions

    def send(method, body):
        if not token:
            raise RuntimeError("BOT_TOKEN не задан")
        # Do not log request URLs: they contain the bot token.
        try:
            result = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=body, timeout=8)
            result.raise_for_status()
            if not result.json().get("ok"):
                raise RuntimeError("Telegram отклонил запрос")
        except httpx.HTTPError:
            raise RuntimeError("Не удалось связаться с Telegram") from None

    app.state.telegram_send = send

    def user(authorization: str = Header(default="")):
        if demo:
            return 1
        ident = telegram_user(authorization, token)
        if owner and ident != owner:
            raise HTTPException(403, "Это личное приложение")
        return ident

    def find(db, ident, uid):
        row = db.scalar(select(Card).where(Card.id == ident, Card.user_id == uid).with_for_update())
        if row is None:
            raise HTTPException(404, "Карточка не найдена")
        return row

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/api/config")
    def config():
        return {"demo": demo}

    @app.get("/api/cards")
    def list_cards(uid: int = Depends(user)):
        with sessions() as db:
            return [serialize(c) for c in db.scalars(select(Card).where(Card.user_id == uid).order_by(Card.next_at, Card.id))]

    @app.post("/api/cards", status_code=201)
    def create_card(data: CardInput, uid: int = Depends(user)):
        now = utcnow()
        with sessions.begin() as db:
            row = Card(user_id=uid, **data.model_dump(), next_at=naive(next_due(data, now)), created_at=naive(now))
            db.add(row)
            db.flush()
            return serialize(row)

    @app.put("/api/cards/{ident}")
    def update_card(ident: int, data: CardInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = find(db, ident, uid)
            for key, value in data.model_dump().items():
                setattr(row, key, value)
            row.next_at = naive(next_due(data, utcnow()))
            return serialize(row)

    @app.delete("/api/cards/{ident}", status_code=204)
    def delete_card(ident: int, uid: int = Depends(user)):
        with sessions.begin() as db:
            db.delete(find(db, ident, uid))
        return Response(status_code=204)

    def tick():
        if demo:
            return {"sent": 0, "failed": 0}
        count = failed = 0
        now = utcnow()
        with local_lock:
            with sessions() as db:
                ids = list(db.scalars(select(Card.id).where(Card.next_at <= naive(now)).order_by(Card.next_at).limit(50)))
            for ident in ids:
                try:
                    with sessions.begin() as db:
                        row = db.scalar(select(Card).where(Card.id == ident, Card.next_at <= naive(now)).with_for_update(skip_locked=True))
                        if row is None:
                            continue
                        if naive(now) - row.next_at <= timedelta(hours=1):
                            body = {"chat_id": row.user_id, "text": row.title}
                            if row.description:
                                body["reply_markup"] = {"inline_keyboard": [[{"text": "Открыть карточку", "web_app": {"url": f"{url}/?card={row.id}"}}]]}
                            app.state.telegram_send("sendMessage", body)
                            count += 1
                        data = CardInput(**{key: getattr(row, key) for key in CardInput.model_fields})
                        row.next_at = naive(next_due(data, now))
                except Exception:
                    failed += 1
                    logger.error("Не удалось отправить напоминание card_id=%s; повтор при следующей проверке", ident)
        return {"sent": count, "failed": failed}

    @app.post("/jobs/tick")
    def run_jobs(authorization: str = Header(default="")):
        if not jobs or not hmac.compare_digest(authorization, f"Bearer {jobs}"):
            raise HTTPException(401, "Нет доступа")
        result = tick()
        if result["failed"]:
            from fastapi.responses import JSONResponse
            return JSONResponse(result, status_code=503)
        return result

    @app.post("/telegram/webhook")
    def webhook(update: dict, x_telegram_bot_api_secret_token: str = Header(default="")):
        if not hook or not hmac.compare_digest(hook, x_telegram_bot_api_secret_token):
            raise HTTPException(401, "Нет доступа")
        message = update.get("message", {})
        chat = message.get("chat", {})
        if chat.get("type") == "private" and (not owner or chat.get("id") == owner) and message.get("text", "").split(" ")[0] in ("/start", "/cards"):
            app.state.telegram_send("sendMessage", {"chat_id": chat["id"], "text": "Рядом 🌿\nВаши карточки и маленькие напоминания о важном.\n\nСоздайте карточку и выберите время — я напомню в этом чате.", "reply_markup": {"inline_keyboard": [[{"text": "Мои карточки", "web_app": {"url": url}}]]}})
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app

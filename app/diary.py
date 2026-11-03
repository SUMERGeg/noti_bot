from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import BigInteger, Date, Integer, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.store import Base


class Achievement(Base):
    __tablename__ = 'achievements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    text: Mapped[str] = mapped_column(Text)


class AchievementText(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    @field_validator('text')
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Напиши, за что хочешь себя похвалить')
        return value


class AchievementInput(AchievementText):
    day: date


def serialize(row):
    return {'id': row.id, 'day': row.day.isoformat(), 'text': row.text}


def diary_router(sessions, user):
    router = APIRouter(prefix='/api/achievements')

    def owned(db, ident, uid):
        row = db.scalar(select(Achievement).where(Achievement.id == ident, Achievement.user_id == uid).with_for_update())
        if row is None:
            raise HTTPException(404, 'Достижение не найдено')
        return row

    @router.get('')
    def week(start: date, uid: int = Depends(user)):
        with sessions() as db:
            return [serialize(row) for row in db.scalars(select(Achievement).where(Achievement.user_id == uid, Achievement.day >= start, Achievement.day < start + timedelta(days=7)).order_by(Achievement.day, Achievement.id))]

    @router.post('', status_code=201)
    def create(data: AchievementInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = Achievement(user_id=uid, **data.model_dump())
            db.add(row)
            db.flush()
            return serialize(row)

    @router.put('/{ident}')
    def edit(ident: int, data: AchievementText, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = owned(db, ident, uid)
            row.text = data.text
            return serialize(row)

    @router.delete('/{ident}', status_code=204)
    def remove(ident: int, uid: int = Depends(user)):
        with sessions.begin() as db:
            db.delete(owned(db, ident, uid))
        return Response(status_code=204)

    return router

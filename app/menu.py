import base64
import binascii
from datetime import date, timedelta
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select, update

from app.menu_store import Dish, MenuEntry, MenuSettings

CATEGORIES = ('Завтраки', 'Основные блюда', 'Гарниры', 'Салаты', 'Супы', 'Десерты', 'Перекусы', 'Напитки', 'Другое')
MEALS = ('breakfast', 'lunch', 'dinner', 'snack')
NUTRIENTS = ('calories', 'protein', 'fat', 'carbs')
Meal = Literal['breakfast', 'lunch', 'dinner', 'snack']


class DishInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str
    calories: float = Field(ge=0, le=100000, allow_inf_nan=False)
    protein: float = Field(ge=0, le=1000, allow_inf_nan=False)
    fat: float = Field(ge=0, le=1000, allow_inf_nan=False)
    carbs: float = Field(ge=0, le=1000, allow_inf_nan=False)
    note: str = Field(default='', max_length=20000)
    recipe_url: str = Field(default='', max_length=2000)
    photo: str = Field(default='', max_length=700000)
    favorite: bool = False

    @model_validator(mode='after')
    def validate_dish(self):
        self.title = self.title.strip()
        self.recipe_url = self.recipe_url.strip()
        if not self.title or self.category not in CATEGORIES:
            raise ValueError('Укажите название и категорию блюда')
        if self.recipe_url:
            parts = urlsplit(self.recipe_url)
            if parts.scheme not in ('http', 'https') or not parts.netloc:
                raise ValueError('Ссылка должна начинаться с https:// или http://')
        if self.photo:
            try:
                prefix, data = self.photo.split(',', 1)
                if prefix not in ('data:image/jpeg;base64', 'data:image/png;base64', 'data:image/webp;base64'):
                    raise ValueError()
                base64.b64decode(data, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('Некорректная фотография')
        return self


class PortionInput(BaseModel):
    grams: float = Field(gt=0, le=100000, allow_inf_nan=False)
    meal: Meal


class EntryInput(PortionInput):
    dish_id: int = Field(gt=0)
    day: date


class SettingsInput(BaseModel):
    calorie_goal: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    theme: Literal['light', 'dark'] = 'light'
    decimals: Literal[0, 1, 2] = 1


class CopyInput(BaseModel):
    source: date
    target: date
    scope: Literal['meal', 'day', 'week']
    source_meal: Meal = 'breakfast'
    target_meal: Meal = 'breakfast'

    @model_validator(mode='after')
    def validate_copy(self):
        if self.source == self.target and (self.scope != 'meal' or self.source_meal == self.target_meal):
            raise ValueError('Выберите другую дату или приём пищи')
        if self.scope == 'week' and (self.source.weekday() != 0 or self.target != self.source + timedelta(days=7)):
            raise ValueError('Неделя копируется с понедельника на следующую неделю')
        return self


def dish_data(row):
    return {'id': row.id, **{key: getattr(row, key) for key in DishInput.model_fields}}


def entry_data(row):
    return {'id': row.id, 'dish_id': row.dish_id, 'day': row.day.isoformat(), 'meal': row.meal,
            'grams': row.grams, **row.snapshot,
            'nutrition': {key: row.snapshot[key] * row.grams / 100 for key in NUTRIENTS}}


def zero():
    return {key: 0 for key in NUTRIENTS}


def menu_router(sessions, user):
    router = APIRouter(prefix='/api/menu')

    def owned(db, model, ident, uid):
        row = db.scalar(select(model).where(model.id == ident, model.user_id == uid).with_for_update())
        if row is None:
            raise HTTPException(404, 'Запись не найдена')
        return row

    @router.get('/dishes')
    def dishes(uid: int = Depends(user)):
        with sessions() as db:
            return [dish_data(row) for row in db.scalars(select(Dish).where(Dish.user_id == uid).order_by(Dish.title, Dish.id))]

    @router.post('/dishes', status_code=201)
    def create_dish(data: DishInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = Dish(user_id=uid, **data.model_dump())
            db.add(row)
            db.flush()
            return dish_data(row)

    @router.put('/dishes/{ident}')
    def edit_dish(ident: int, data: DishInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = owned(db, Dish, ident, uid)
            for key, value in data.model_dump().items():
                setattr(row, key, value)
            return dish_data(row)

    @router.delete('/dishes/{ident}', status_code=204)
    def remove_dish(ident: int, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = owned(db, Dish, ident, uid)
            db.execute(update(MenuEntry).where(MenuEntry.user_id == uid, MenuEntry.dish_id == ident).values(dish_id=None))
            db.delete(row)
        return Response(status_code=204)

    @router.get('/plan')
    def plan(start: date, uid: int = Depends(user)):
        end = start + timedelta(days=7)
        days = {start + timedelta(days=i): {'day': (start + timedelta(days=i)).isoformat(), 'totals': zero(),
                 'meals': {meal: {'entries': [], 'totals': zero()} for meal in MEALS}} for i in range(7)}
        with sessions() as db:
            entries = db.scalars(select(MenuEntry).where(MenuEntry.user_id == uid, MenuEntry.day >= start, MenuEntry.day < end).order_by(MenuEntry.id))
            for row in entries:
                data = entry_data(row)
                day = days[row.day]
                meal = day['meals'][row.meal]
                meal['entries'].append(data)
                for key in NUTRIENTS:
                    meal['totals'][key] += data['nutrition'][key]
                    day['totals'][key] += data['nutrition'][key]
        return {'days': list(days.values())}

    @router.post('/entries', status_code=201)
    def add_entry(data: EntryInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            dish = owned(db, Dish, data.dish_id, uid)
            snapshot = {key: getattr(dish, key) for key in ('title', 'category', *NUTRIENTS)}
            row = MenuEntry(user_id=uid, **data.model_dump(), snapshot=snapshot)
            db.add(row)
            db.flush()
            return entry_data(row)

    @router.patch('/entries/{ident}')
    def edit_entry(ident: int, data: PortionInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            row = owned(db, MenuEntry, ident, uid)
            row.grams, row.meal = data.grams, data.meal
            return entry_data(row)

    @router.delete('/entries/{ident}', status_code=204)
    def remove_entry(ident: int, uid: int = Depends(user)):
        with sessions.begin() as db:
            db.delete(owned(db, MenuEntry, ident, uid))
        return Response(status_code=204)

    @router.delete('/day/{day}', status_code=204)
    def clear_day(day: date, uid: int = Depends(user)):
        with sessions.begin() as db:
            db.execute(delete(MenuEntry).where(MenuEntry.user_id == uid, MenuEntry.day == day))
        return Response(status_code=204)

    @router.post('/copy')
    def copy_menu(data: CopyInput, uid: int = Depends(user)):
        length = 7 if data.scope == 'week' else 1
        with sessions.begin() as db:
            source = select(MenuEntry).where(MenuEntry.user_id == uid, MenuEntry.day >= data.source, MenuEntry.day < data.source + timedelta(days=length)).order_by(MenuEntry.id)
            target = delete(MenuEntry).where(MenuEntry.user_id == uid, MenuEntry.day >= data.target, MenuEntry.day < data.target + timedelta(days=length))
            if data.scope == 'meal':
                source = source.where(MenuEntry.meal == data.source_meal)
                target = target.where(MenuEntry.meal == data.target_meal)
            # Materialize snapshots before deleting the destination.
            copies = [dict(user_id=uid, day=data.target + (row.day - data.source), meal=data.target_meal if data.scope == 'meal' else row.meal,
                           dish_id=row.dish_id, snapshot=dict(row.snapshot), grams=row.grams) for row in db.scalars(source)]
            db.execute(target)
            db.add_all([MenuEntry(**values) for values in copies])
        return {'copied': len(copies)}

    @router.get('/settings')
    def settings(uid: int = Depends(user)):
        with sessions() as db:
            row = db.get(MenuSettings, uid)
            return {key: getattr(row, key) for key in SettingsInput.model_fields} if row else SettingsInput().model_dump()

    @router.put('/settings')
    def save_settings(data: SettingsInput, uid: int = Depends(user)):
        with sessions.begin() as db:
            db.merge(MenuSettings(user_id=uid, **data.model_dump()))
        return data.model_dump()

    return router

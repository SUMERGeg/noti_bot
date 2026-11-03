from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Float, Integer, JSON, String, Text, inspect, text
from sqlalchemy.orm import Mapped, mapped_column

from app.store import Base


class Dish(Base):
    __tablename__ = 'menu_dishes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))
    calories: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    nutrition_basis: Mapped[str] = mapped_column(String(16), default='per100g', server_default='per100g')
    portion_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default='')
    recipe_url: Mapped[str] = mapped_column(Text, default='')
    photo: Mapped[str] = mapped_column(Text, default='')
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)


class MenuEntry(Base):
    __tablename__ = 'menu_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(12))
    dish_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    # Legacy column stores the quantity in `unit`; API exposes actual grams separately.
    grams: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(12), default='grams', server_default='grams')


class MenuSettings(Base):
    __tablename__ = 'menu_settings'
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    calorie_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    theme: Mapped[str] = mapped_column(String(8), default='light')
    decimals: Mapped[int] = mapped_column(Integer, default=1)


def ensure_menu_units(engine):
    additions = {
        'menu_dishes': {'nutrition_basis': "VARCHAR(16) NOT NULL DEFAULT 'per100g'", 'portion_weight': 'FLOAT'},
        'menu_entries': {'unit': "VARCHAR(12) NOT NULL DEFAULT 'grams'"},
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            existing = {c['name'] for c in inspect(connection).get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    guard = 'IF NOT EXISTS ' if engine.dialect.name == 'postgresql' else ''
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {guard}{name} {definition}'))

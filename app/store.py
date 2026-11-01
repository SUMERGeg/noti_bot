from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    flag: Mapped[str] = mapped_column(String(24), default='', server_default='')
    times: Mapped[list] = mapped_column(JSON)
    repeat: Mapped[str] = mapped_column(String(10))
    weekdays: Mapped[list] = mapped_column(JSON)
    monthdays: Mapped[list] = mapped_column(JSON)
    timezone: Mapped[str] = mapped_column(String(100))
    next_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


def ensure_card_flag(engine):
    """Add the optional field to pre-existing databases; retain old cards."""
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            connection.execute(text("ALTER TABLE cards ADD COLUMN IF NOT EXISTS flag VARCHAR(24) NOT NULL DEFAULT ''"))
        elif 'flag' not in {column['name'] for column in inspect(connection).get_columns('cards')}:
            connection.execute(text("ALTER TABLE cards ADD COLUMN flag VARCHAR(24) NOT NULL DEFAULT ''"))

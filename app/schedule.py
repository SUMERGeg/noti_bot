from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator


class CardInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    times: list[str] = Field(min_length=1, max_length=24)
    repeat: Literal["daily", "weekly", "monthly"] = "daily"
    weekdays: list[int] = Field(default_factory=list)
    monthdays: list[int] = Field(default_factory=list)
    timezone: str = "Europe/Moscow"

    @model_validator(mode="after")
    def validate_schedule(self):
        self.title = self.title.strip()
        self.description = self.description.strip()
        if not self.title:
            raise ValueError("Укажите название")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Неизвестный часовой пояс")
        import re
        if any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in self.times):
            raise ValueError("Время должно быть в формате ЧЧ:ММ")
        self.times = sorted(set(self.times))
        if any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("Неверный день недели")
        if any(d < 1 or d > 31 for d in self.monthdays):
            raise ValueError("Неверное число месяца")
        self.weekdays = sorted(set(self.weekdays))
        self.monthdays = sorted(set(self.monthdays))
        if self.repeat == "weekly" and not self.weekdays:
            raise ValueError("Выберите дни недели")
        if self.repeat == "monthly" and not self.monthdays:
            raise ValueError("Выберите числа месяца")
        return self


def next_due(card: CardInput, after: datetime) -> datetime:
    """Next occurrence strictly after `after`; missing month dates are skipped.

    Nonexistent DST times are skipped; repeated wall-clock times fire once.
    """
    zone = ZoneInfo(card.timezone)
    start = after.astimezone(zone).date()
    for offset in range(370):
        day = start + timedelta(days=offset)
        if card.repeat == "weekly" and day.weekday() not in card.weekdays:
            continue
        if card.repeat == "monthly" and day.day not in card.monthdays:
            continue
        for slot in card.times:
            hour, minute = map(int, slot.split(":"))
            local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
            utc = local.astimezone(timezone.utc)
            if utc.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                continue
            if utc > after:
                return utc
    raise ValueError("Не удалось найти следующее напоминание")

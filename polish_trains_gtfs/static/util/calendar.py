# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from collections.abc import Iterable
from datetime import date

from impuls import DBConnection


class CalendarGenerator:
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        self.counter = 0
        self.assigned = dict[frozenset[date], str]()

    def clear(self) -> None:
        self.counter = 0
        self.assigned.clear()

    def upsert(self, db: DBConnection, days: Iterable[date]) -> str:
        key = frozenset(days)
        if cached := self.assigned.get(key):
            return cached

        id = f"{self.prefix}{self.counter}"
        self.counter += 1

        db.raw_execute("INSERT INTO calendars (calendar_id) VALUES (?)", (id,))
        db.raw_execute_many(
            "INSERT INTO calendar_exceptions (calendar_id, date, exception_type) VALUES (?, ?, 1)",
            ((id, str(date)) for date in key),
        )

        self.assigned[key] = id
        return id

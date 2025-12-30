# SPDX-FileCopyrightText: 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from impuls import Task, TaskRuntime


class LoadAgencies(Task):
    def __init__(self, r: str = "carriers.json") -> None:
        super().__init__()
        self.r = r

    def execute(self, r: TaskRuntime) -> None:
        data = r.resources[self.r].json()
        with r.db.transaction():
            r.db.raw_execute_many(
                "INSERT INTO agencies (agency_id, name, url, timezone, lang) "
                "VALUES (?, ?, 'https://example.com', 'Europe/Warsaw', 'pl')",
                ((i["code"], i["name"]) for i in data["carriers"]),
            )

# SPDX-FileCopyrightText: 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from impuls import Task, TaskRuntime


class LoadStops(Task):
    def __init__(self, r: str = "stations.json") -> None:
        super().__init__()
        self.r = r

    def execute(self, r: TaskRuntime) -> None:
        data = r.resources[self.r].json()
        with r.db.transaction():
            r.db.raw_execute_many(
                "INSERT INTO stops (stop_id, name, lat, lon) VALUES (?, ?, 0, 0)",
                ((i["id"], i["name"]) for i in data["stations"]),
            )

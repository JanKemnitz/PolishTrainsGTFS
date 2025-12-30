# SPDX-FileCopyrightText: 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from impuls import Task, TaskRuntime


class LoadRoutes(Task):
    def __init__(self, r: str = "categories.json") -> None:
        super().__init__()
        self.r = r

    def execute(self, r: TaskRuntime) -> None:
        data = r.resources[self.r].json()
        with r.db.transaction():
            r.db.raw_execute_many(
                "INSERT INTO routes (route_id, agency_id, short_name, long_name, type) "
                "VALUES (?, ?, ?, ?, 2)",
                (
                    (f"{i['carrierCode']}_{i['code']}", i["carrierCode"], i["code"], i["name"])
                    for i in data["commercialCategories"]
                ),
            )

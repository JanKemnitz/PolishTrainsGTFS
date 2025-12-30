# SPDX-FileCopyrightText: 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from impuls import Task, TaskRuntime
from impuls.model import Attribution, FeedInfo


class LoadDataVersion(Task):
    def __init__(self, r: str = "data_version.json") -> None:
        super().__init__()
        self.r = r

    def execute(self, r: TaskRuntime) -> None:
        data = r.resources[self.r].json()
        with r.db.transaction():
            r.db.create(
                FeedInfo(
                    publisher_name="Mikołaj Kuranowski",
                    publisher_url="https://mkuran.pl/gtfs",
                    lang="pl",
                    version=data["timestamp"],
                ),
            )
            r.db.create(
                Attribution(
                    id="1",
                    organization_name="Data: PKP Polskie linie Kolejowe S.A.",
                    url="https://www.plk-sa.pl/klienci-i-kontrahenci/api-otwarte-dane",
                    is_authority=True,
                    is_data_source=True,
                )
            )
            r.db.create(
                Attribution(
                    id="2",
                    organization_name="GTFS: Mikołaj Kuranowski",
                    url="https://mkuran.pl/gtfs/",
                    is_producer=True,
                )
            )

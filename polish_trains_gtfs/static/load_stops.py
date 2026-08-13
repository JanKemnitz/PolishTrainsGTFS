# SPDX-FileCopyrightText: 2025-2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT


from typing import cast

import impuls
from impuls.model import Stop

from ..geo import Station, load_stations
from .util import json


class LoadStops(impuls.Task):
    def __init__(self) -> None:
        super().__init__()
        self.to_update = dict[str, str]()

    def execute(self, r: impuls.TaskRuntime) -> None:
        self.to_update = {
            cast(str, i[0]): cast(str, i[1])
            for i in r.db.raw_execute("SELECT stop_id, name FROM stops")
        }
        stations = load_stations(r.resources["geo.osm"].stored_at)
        with r.db.transaction():
            for station in stations.values():
                self._apply(station, r.db)
        self._ensure_everything_curated()

    def _apply(self, station: Station, db: impuls.DBConnection) -> None:
        # Check if station is required
        if not any(id in self.to_update for id in station.all_ids()):
            return

        # Update or create the primary stop
        stop = Stop(
            id=station.id,
            name=station.name,
            lat=station.lat,
            lon=station.lon,
            extra_fields_json=json.dumps(
                {
                    "country": station.country,
                    "plk_secondary_id": ";".join(sorted(station.other_ids)),
                },
            ),
        )

        if station.id in self.to_update:
            db.update(stop)
            self.to_update.pop(station.id)
        else:
            db.create(stop)

        # Swap the secondary IDs
        for other_id in station.other_ids:
            if other_id in self.to_update:
                db.raw_execute(
                    "UPDATE stop_times SET stop_id = ? WHERE stop_id = ?",
                    (station.id, other_id),
                )
                db.raw_execute("DELETE FROM stops WHERE stop_id = ?", (other_id,))
                self.to_update.pop(other_id)

        # Mark request stops
        if station.request_stop:
            db.raw_execute(
                "UPDATE stop_times SET drop_off_type = 3, pickup_type = 3 "
                "WHERE stop_id = ? AND pickup_type = 0 AND drop_off_type = 0",
                (station.id,),
            )

    def _ensure_everything_curated(self) -> None:
        if self.to_update:
            raise impuls.errors.MultipleDataErrors(
                "LoadStationData",
                [
                    impuls.errors.DataError(f"Missing data for {id} {name!r}")
                    for id, name in self.to_update.items()
                ],
            )

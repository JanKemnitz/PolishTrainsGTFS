# SPDX-License-Identifier: MIT
# Kiedy Wjazd: brings back one stop per station (state before "stop-station structures").

from impuls import DBConnection, Task, TaskRuntime
from impuls.model import Stop

# Platform-level stops created by LoadStations, which are merged back into their station.
# Bus replacement stops (<id>_BUS*) are kept, they are physically separate places.
_PLATFORM_FILTER = (
    "s.parent_station IS NOT NULL AND s.location_type = 0 "
    "AND (s.stop_id = s.parent_station || '_FALLBACK' "
    "  OR s.stop_id LIKE s.parent_station || '\\_RAIL\\_%' ESCAPE '\\')"
)


class FlattenStations(Task):
    """Merges `<id>_RAIL_<platform>_<track>` and `<id>_FALLBACK` platforms back into
    the `<id>` station, so a station has a single stop_id with all of its departures.

    Kiedy Wjazd displays don't need platforms, and per-platform stops break saved
    configs (a line is split across many platforms and tracks change between trains).
    Only stop_id changes, trip_id and stop_sequence stay the same, so GTFS-RT
    matching by trip_id + stop_sequence is not affected.
    """

    def execute(self, r: TaskRuntime) -> None:
        with r.db.transaction():
            self.flatten(r.db)

    def flatten(self, db: DBConnection) -> None:
        mapping = [
            (str(row[0]), str(row[1]))
            for row in db.raw_execute(
                f"SELECT s.stop_id, s.parent_station FROM stops s WHERE {_PLATFORM_FILTER}"
            )
        ]
        if not mapping:
            self.logger.info("No platforms to flatten")
            return

        db.raw_execute_many(
            "UPDATE stop_times SET stop_id = ? WHERE stop_id = ?",
            ((station, platform) for platform, station in mapping),
        )
        db.raw_execute_many(
            "UPDATE transfers SET from_stop_id = ? WHERE from_stop_id = ?",
            ((station, platform) for platform, station in mapping),
        )
        db.raw_execute_many(
            "UPDATE transfers SET to_stop_id = ? WHERE to_stop_id = ?",
            ((station, platform) for platform, station in mapping),
        )

        stations = sorted({station for _, station in mapping})

        # Exits and platforms are not needed anymore
        exits = db.raw_execute(
            "DELETE FROM stops WHERE location_type = ? AND parent_station IS NOT NULL",
            (Stop.LocationType.EXIT.value,),
        ).rowcount
        db.raw_execute_many(
            "DELETE FROM stops WHERE stop_id = ?",
            ((platform,) for platform, _ in mapping),
        )

        # A station with departures must be a regular stop. Remaining children
        # (bus replacement stops) can't point to a regular stop, so they become standalone.
        db.raw_execute_many(
            "UPDATE stops SET parent_station = NULL WHERE parent_station = ?",
            ((station,) for station in stations),
        )
        db.raw_execute_many(
            "UPDATE stops SET location_type = ?, platform_code = '' WHERE stop_id = ?",
            ((Stop.LocationType.STOP.value, station) for station in stations),
        )

        self.logger.info(
            "Flattened %d platforms into %d stations, removed %d exits",
            len(mapping),
            len(stations),
            exits,
        )

# SPDX-FileCopyrightText: 2026 Jan Kemnitz
# SPDX-License-Identifier: MIT

import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, cast

from impuls import DBConnection, Task, TaskRuntime

Point = Tuple[float, float]  # (x, y) in km, x = east, y = north


class AssignDirections(Task):
    """
    Assigns direction_id (0 or 1) to every trip, in a way that is stable between runs.

    For each route a fixed axis A -> B is chosen: the two stations served by the route
    which are the farthest apart. A trip gets 0 when it travels along the axis (its
    first -> last vector points the same way as A -> B), 1 otherwise.

    The axis depends only on the set of stations served by the route, never on trip_ids,
    on the order of trips or on platforms, so the same physical train keeps its
    direction_id between runs. The axis is oriented towards north-east (A is the
    south-western end), with station ids as the tie-breaker for axes running NW-SE.
    All stop_ids are compared at the station level (<id>_RAIL_x_y -> <id>).
    """

    # When the axis runs almost exactly NW-SE, the north-east score is unreliable;
    # below this share of the axis length the station ids decide instead.
    NE_SCORE_MIN_SHARE = 0.1

    def __init__(self, task_name: str | None = None) -> None:
        super().__init__(name=task_name)
        self.assigned_count = 0
        self.skipped_count = 0

    def execute(self, r: TaskRuntime) -> None:
        self.assigned_count = 0
        self.skipped_count = 0
        positions = self.load_station_positions(r.db)
        route_ids = [
            cast(str, row[0])
            for row in r.db.raw_execute("SELECT route_id FROM routes ORDER BY route_id")
        ]
        self.logger.info(f"Assigning directions for {len(route_ids)} routes...")

        updates: List[Tuple[Optional[int], str]] = []
        for route_id in route_ids:
            updates.extend(self.process_route(r.db, route_id, positions))

        with r.db.transaction():
            r.db.raw_execute_many("UPDATE trips SET direction = ? WHERE trip_id = ?", updates)
        self.logger.info(
            f"Direction assignment completed: {self.assigned_count} assigned, "
            f"{self.skipped_count} skipped."
        )

    @staticmethod
    def station_of(stop_id: str) -> str:
        return stop_id.partition("_")[0]

    def load_station_positions(self, db: DBConnection) -> Dict[str, Point]:
        """Station position in km (equirectangular projection around Poland)."""
        raw: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        exact: Dict[str, Tuple[float, float]] = {}
        for stop_id, lat, lon in db.raw_execute("SELECT stop_id, lat, lon FROM stops"):
            stop_id = cast(str, stop_id)
            lat, lon = cast(float, lat), cast(float, lon)
            if lat == 0 and lon == 0:
                continue
            station = self.station_of(stop_id)
            if stop_id == station:
                exact[station] = (lat, lon)
            raw[station].append((lat, lon))

        positions: Dict[str, Point] = {}
        for station, coords in raw.items():
            lat, lon = exact.get(station) or (
                sum(c[0] for c in coords) / len(coords),
                sum(c[1] for c in coords) / len(coords),
            )
            positions[station] = (lon * 111.32 * math.cos(math.radians(52.0)), lat * 110.57)
        return positions

    def get_route_trips(self, db: DBConnection, route_id: str) -> Dict[str, List[str]]:
        """trip_id -> station ids in stop order (consecutive duplicates collapsed)."""
        rows = db.raw_execute(
            "SELECT t.trip_id, s.stop_id FROM trips t "
            "JOIN stop_times s ON t.trip_id = s.trip_id "
            "WHERE t.route_id = ? ORDER BY t.trip_id, s.stop_sequence",
            (route_id,),
        )
        trips: Dict[str, List[str]] = defaultdict(list)
        for trip_id, stop_id in rows:
            stations = trips[cast(str, trip_id)]
            station = self.station_of(cast(str, stop_id))
            if not stations or stations[-1] != station:
                stations.append(station)
        return trips

    def route_axis(self, stations: List[str], positions: Dict[str, Point]) -> Optional[Point]:
        """Unit vector from the south-western to the north-eastern end of the route."""
        known = sorted({s for s in stations if s in positions})
        if len(known) < 2:
            return None

        best: Optional[Tuple[float, str, str]] = None
        for i, a in enumerate(known):
            ax, ay = positions[a]
            for b in known[i + 1 :]:
                bx, by = positions[b]
                d = (bx - ax) ** 2 + (by - ay) ** 2
                if best is None or d > best[0]:
                    best = (d, a, b)
        assert best is not None
        dist2, a, b = best
        if dist2 <= 0:
            return None

        (ax, ay), (bx, by) = positions[a], positions[b]
        vx, vy = bx - ax, by - ay
        length = math.sqrt(dist2)
        ne_score = (vx + vy) / math.sqrt(2)
        if abs(ne_score) >= self.NE_SCORE_MIN_SHARE * length:
            flip = ne_score < 0
        else:
            flip = int(a) > int(b) if a.isdigit() and b.isdigit() else a > b
        if flip:
            vx, vy = -vx, -vy
        return (vx / length, vy / length)

    def trip_vector(self, stations: List[str], positions: Dict[str, Point]) -> Optional[Point]:
        known = [positions[s] for s in stations if s in positions]
        if len(known) < 2:
            return None
        first, last = known[0], known[-1]
        span = math.dist(first, last)
        far = max(known, key=lambda p: math.dist(first, p))
        # Loop-like trips (ending close to where they started): use the farthest point
        target = far if span < 0.2 * math.dist(first, far) else last
        v = (target[0] - first[0], target[1] - first[1])
        return v if v != (0.0, 0.0) else None

    def process_route(
        self, db: DBConnection, route_id: str, positions: Dict[str, Point]
    ) -> List[Tuple[Optional[int], str]]:
        trips = self.get_route_trips(db, route_id)
        axis = self.route_axis([s for st in trips.values() for s in st], positions)

        updates: List[Tuple[Optional[int], str]] = []
        for trip_id, stations in trips.items():
            v = self.trip_vector(stations, positions) if axis else None
            if axis is None or v is None:
                updates.append((None, trip_id))
                self.skipped_count += 1
                continue
            dot = v[0] * axis[0] + v[1] * axis[1]
            updates.append((0 if dot >= 0 else 1, trip_id))
            self.assigned_count += 1
        return updates

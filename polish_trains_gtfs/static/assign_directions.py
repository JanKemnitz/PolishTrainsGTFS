# SPDX-FileCopyrightText: 2026 Jan Kemnitz
# SPDX-License-Identifier: MIT

from collections import defaultdict
from typing import cast, Dict, List, Tuple

from impuls import Task, TaskRuntime, DBConnection


class AssignDirections(Task):
    """
    Automatically assigns direction_id (0 or 1) to trips based
    on the longest route variant (Reference Trip).
    """
    def __init__(self, task_name: str | None = None) -> None:
        super().__init__(name=task_name)
        self.assigned_count = 0
        self.skipped_count = 0
        self.heuristic_agencies = ['AR', 'IC', 'LKA', 'PR', 'KW']

    def execute(self, r: TaskRuntime) -> None:
        self.logger.info("Starting automatic direction assignment...")

        # Get route IDs excluding heuristic agencies
        placeholders = ", ".join(["?"] * len(self.heuristic_agencies))
        
        route_ids = [
            cast(str, row[0]) 
            for row in r.db.raw_execute(f"SELECT DISTINCT route_id FROM routes WHERE agency_id NOT IN ({placeholders})", self.heuristic_agencies)
        ]

        self.logger.info(f"Processing {len(route_ids)} routes...")

        all_updates: List[Tuple[int, str]] = []

        for route_id in route_ids:
            all_updates.extend(self.process_route(r.db, route_id))

        for agency in self.heuristic_agencies:
            self.logger.info(f"Processing heuristic agency {agency}...")
            heuristic_route_ids = [
                cast(str, row[0]) 
                for row in r.db.raw_execute(
                    "SELECT DISTINCT route_id FROM routes WHERE agency_id = ?", 
                    (agency,)
                )
            ]

            self.logger.info(f"Processing {len(heuristic_route_ids)} routes...")

            for route_id in heuristic_route_ids:
                all_updates.extend(self.process_heuristic_route(r.db, route_id))

        # Save changes to database
        if all_updates:
            self.logger.info(f"Updating direction_id for {len(all_updates)} trips.")
            with r.db.transaction():
                r.db.raw_execute_many(
                    "UPDATE trips SET direction = ? WHERE trip_id = ?",
                    all_updates
                )
            self.logger.info(f"Direction assignment completed: {self.assigned_count} assigned, {self.skipped_count} skipped.")
        else:
            self.logger.info("No directions assigned (no valid routes found?).")

    def get_route_trips(self, db: DBConnection, route_id: str) -> Dict[str, List[str]]:
        """
        Retrieves all trips for a given route and their stop sequences.
        Returns a dict mapping trip_id to list of stop_ids.
        """
        rows = db.raw_execute(
            """
            SELECT t.trip_id, s.stop_id
            FROM trips t
            JOIN stop_times s ON t.trip_id = s.trip_id
            WHERE t.route_id = ?
            ORDER BY t.trip_id, s.stop_sequence
            """,
            (route_id,)
        )

        trip_stops: Dict[str, List[str]] = defaultdict(list)
        for r_trip_id, r_stop_id in rows:
            trip_stops[cast(str, r_trip_id)].append(cast(str, r_stop_id))

        return trip_stops

    def process_heuristic_route(self, db: DBConnection, route_id: str) -> List[Tuple[int, str]]:
        """
        Processes routes by clustering trips based on geometric similarity.
        Used for agencies where simple reference trip matching is insufficient.
        """
        pool = self.get_route_trips(db, route_id)

        updates: List[Tuple[int, str]] = []

        while pool:
            # Select group leader (longest remaining trip)
            ref_trip_id = max(pool, key=lambda t: len(pool[t]))
            ref_stops = pool.pop(ref_trip_id)
            
            # Anchor direction based on simple start/end node ID comparison
            start_node = ref_stops[0]
            end_node = ref_stops[-1]
            base_dir = 0 if start_node <= end_node else 1
            
            updates.append((base_dir, ref_trip_id))
            self.assigned_count += 1

            ref_indices = {stop: i for i, stop in enumerate(ref_stops)}
            matched_trip_ids: List[str] = []

            for trip_id, stops in pool.items():
                common_stops = [s for s in stops if s in ref_indices]

                # Require minimum overlap to determine direction
                overlap_ratio = len(common_stops) / len(stops)
                if len(common_stops) < 2 or overlap_ratio < 0.3:
                    continue

                idx_first = ref_indices[common_stops[0]]
                idx_last = ref_indices[common_stops[-1]]

                # Match direction with leader
                is_same_direction = idx_first < idx_last
                final_dir = base_dir if is_same_direction else (1 - base_dir)
                
                updates.append((final_dir, trip_id))
                matched_trip_ids.append(trip_id)
                self.assigned_count += 1

            for tid in matched_trip_ids:
                del pool[tid]

        return updates

    def process_route(self, db: DBConnection, route_id: str) -> List[Tuple[int, str]]:
        """
        Analyzes a route by finding a reference trip (longest)
        and comparing other trips to it to determine direction.
        """
        trip_stops = self.get_route_trips(db, route_id)
        if not trip_stops:
            return []

        # Find reference trip (longest variant)
        ref_trip_id = max(trip_stops, key=lambda t: len(trip_stops[t]))
        ref_stops = trip_stops[ref_trip_id]
        ref_stop_indices = {stop: i for i, stop in enumerate(ref_stops)}

        updates: List[Tuple[int, str]] = []

        for trip_id, stops in trip_stops.items():
            if trip_id == ref_trip_id:
                updates.append((0, trip_id))
                self.assigned_count += 1
                continue

            common_stops = [s for s in stops if s in ref_stop_indices]
            if len(common_stops) < 2:
                self.skipped_count += 1
                continue

            # Determine direction based on stop sequence indices in reference trip
            idx_first = ref_stop_indices[common_stops[0]]
            idx_last = ref_stop_indices[common_stops[-1]]

            direction = 0 if idx_first < idx_last else 1
            updates.append((direction, trip_id))
            self.assigned_count += 1

        return updates
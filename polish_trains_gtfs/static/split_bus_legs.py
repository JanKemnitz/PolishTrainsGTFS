# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

import re

from impuls.model import Route
from impuls.tasks import SplitTripLegs


class SplitBusLegs(SplitTripLegs):
    def __init__(self) -> None:
        super().__init__(
            replacement_bus_short_name_pattern=re.compile(r"\bZKA\b", re.I),
            leg_trip_id_infix="_LEG",
        )

    def update_bus_replacement_route(self, route: Route) -> None:
        route.type = Route.Type.BUS
        route.short_name = f"ZKA {route.short_name}"
        route.long_name = f"{route.long_name} (Zastępcza Komunikacja Autobusowa)"
        route.color = "DE4E4E"
        route.text_color = "FFFFFF"

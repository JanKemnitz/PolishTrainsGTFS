# SPDX-FileCopyrightText: 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

import json
from collections.abc import Iterable, Mapping
from typing import Any, cast

import ijson  # type: ignore
from impuls import DBConnection, Task, TaskRuntime
from impuls.model import Date

# | Short Key | Long Key |
# |-----------|----------|
# | sid       | scheduleId |
# | oid       | orderId |
# | toid      | trainOrderId |
# | nm        | name |
# | cc        | carrierCode |
# | nn        | nationalNumber |
# | ian       | internationalArrivalNumber |
# | idn       | internationalDepartureNumber |
# | ccs       | commercialCategorySymbol |
# | pn        | posterNotes |
# | rel       | isRelated |
# | od        | operatingDates |
# | st        | stations |
# | id        | stationId |
# | ord       | orderNumber |
# | acc       | arrivalCommercialCategory |
# | atn       | arrivalTrainNumber |
# | apl       | arrivalPlatform |
# | atr       | arrivalTrack |
# | ady       | arrivalDay |
# | atm       | arrivalTime |
# | dcc       | departureCommercialCategory |
# | dtn       | departureTrainNumber |
# | dpl       | departurePlatform |
# | dtr       | departureTrack |
# | ddy       | departureDay |
# | dtm       | departureTime |
# | sti       | stopTypeId |
# | stn       | stopTypeName |
# | cn        | connections |
# | id        | id |
# | tc        | typeCode |
# | tn        | typeName |
# | sid       | stationId |
# | wn        | wagonNumbers |
# | t1o       | train1OrderId |
# | t1s       | train1StationOrder |
# | t1d       | train1DayOffset |
# | t2o       | train2OrderId |
# | t2s       | train2StationOrder |
# | t2d       | train2DayOffset |

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR


class LoadSchedules(Task):
    def __init__(self, r: str = "schedules.json") -> None:
        super().__init__()
        self.r = r

        self.calendar_id_counter = 0
        self.calendars = dict[frozenset[Date], int]()

    def clear(self) -> None:
        self.calendar_id_counter = 0
        self.calendars.clear()

    def execute(self, r: TaskRuntime) -> None:
        self.clear()
        with r.db.transaction(), r.resources[self.r].open_text(encoding="utf-8") as f:
            for route in ijson.items(f, "rt.item", use_float=True):
                self.process_route(r.db, route)

    def process_route(self, db: DBConnection, r: Mapping[str, Any]) -> None:
        trip_id = cast(int, r["sid"])
        route_id = f"{r['cc']}_{r['ccs']}"
        calendar_id = self.get_calendar_id(db, r["od"])
        order_id = cast(int, r["oid"])

        plk_number = cast(str, r["nn"])
        display_number = cast(str, r["idn"] or r["ian"] or plk_number)
        name = (cast(str, r["nm"]) or "").title()
        trip_short_name = merge_number_and_name(display_number, name)

        extra_fields = json.dumps({"order_id": str(order_id), "plk_train_number": plk_number})

        db.raw_execute(
            "INSERT INTO trips (trip_id, route_id, calendar_id, short_name, extra_fields_json)",
            (trip_id, route_id, calendar_id, trip_short_name, extra_fields),
        )
        for route_station in r["st"]:
            self.process_route_stop(db, trip_id, route_station)

    def process_route_stop(self, db: DBConnection, trip_id: int, s: Mapping[str, Any]) -> None:
        stop_id = cast(int, s["id"])
        sequence = cast(int, s["ord"])
        arrival = parse_time(s["atm"], s["ady"] or 0)
        departure = parse_time(s["dtm"], s["ddy"] or 0)
        platform = cast(str, s["dpl"] or s["apl"] or "")
        track = cast(str, s["dtr"] or s["atr"] or "")
        extra_fields = json.dumps({"track": track})
        db.raw_execute(
            "INSERT INTO stop_times (trip_id, stop_sequence, stop_id, arrival_time, "
            "departure_time, platform, extra_fields_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trip_id, sequence, stop_id, arrival, departure, platform, extra_fields),
        )

    def get_calendar_id(self, db: DBConnection, operating_dates: Iterable[str]) -> int:
        dates = frozenset(Date.from_ymd_str(i[:10]) for i in operating_dates)
        if calendar_id := self.calendars.get(dates):
            return calendar_id
        else:
            self.calendar_id_counter += 1
            calendar_id = self.calendar_id_counter

            db.raw_execute("INSERT INTO calendars (calendar_id) VALUES (?)", (calendar_id,))
            db.raw_execute_many(
                "INSERT INTO calendar_exceptions (calendar_id,date,exception_type) VALUES (?,?,1)",
                ((calendar_id, str(date)) for date in dates),
            )

            self.calendars[dates] = calendar_id
            return calendar_id


def merge_number_and_name(number: str, name: str) -> str:
    if number and name:
        if number in name:
            return name
        return f"{number} {name}"
    return number or name


def parse_time(x: str, day_offset: int = 0) -> int:
    parts = x.split(":")
    if len(parts) == 2:
        h, m = map(int, parts)
        s = 0
    elif len(parts) == 3:
        h, m, s = map(int, parts)
    else:
        raise ValueError(f"invalid time value: {x!r}")

    h += DAY * day_offset
    return h * HOUR + m * MINUTE + s

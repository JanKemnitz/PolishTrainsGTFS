#!/usr/bin/env python3
"""
Sprawdzenie co zwraca PLK API /operations/shortened
i porównanie z zakresem dat w lokalnym GTFS.
"""

import os
import sys
import zipfile
import json
import urllib.request
from collections import Counter
from datetime import date

# --- Konfiguracja ---
GTFS_PATH = "prop/output/polish_trains.zip"
API_URL = "https://pdp-api.plk-sa.pl/api/v1/operations/shortened"
PAGE_SIZE = 10_000

def get_apikey():
    key = "rSVIwmT7r59n0Og4Vd45UNUn2xvTDToiO5yN2qyIjwmOT_dDqomVzpK1Y1AmwxKu_-041Dap1nV_ZoxAtphQhg"
    if not key:
        # Spróbuj wczytać z prop/.env
        env_path = "prop/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PKP_PLK_APIKEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not key:
        print("BŁĄD: Ustaw zmienną PKP_PLK_APIKEY lub umieść ją w prop/.env", file=sys.stderr)
        sys.exit(1)
    return key

def get_feed_dates(gtfs_path):
    with zipfile.ZipFile(gtfs_path) as z:
        with z.open("feed_info.txt") as f:
            lines = f.read().decode("utf-8-sig").strip().splitlines()
    headers = lines[0].split(",")
    values = lines[1].split(",")
    row = dict(zip(headers, values))
    start = row["feed_start_date"].strip()
    end = row["feed_end_date"].strip()
    return start, end

def fetch_operations_page(apikey, page=1, page_size=PAGE_SIZE):
    import time
    params = f"page={page}&pageSize={page_size}&fullRoutes=true&carriersExclude=WKD,{int(time.time())}"
    req = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={"X-Api-Key": apikey}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def main():
    print("=== Sprawdzenie PLK API vs GTFS feed dates ===\n")

    # 1. Daty feedu
    if not os.path.exists(GTFS_PATH):
        print(f"BŁĄD: Nie znaleziono {GTFS_PATH}", file=sys.stderr)
        sys.exit(1)

    feed_start_raw, feed_end_raw = get_feed_dates(GTFS_PATH)
    feed_start = date(int(feed_start_raw[:4]), int(feed_start_raw[4:6]), int(feed_start_raw[6:8]))
    feed_end   = date(int(feed_end_raw[:4]),   int(feed_end_raw[4:6]),   int(feed_end_raw[6:8]))
    # realtime generator cofa start o 1 dzien
    effective_start = date.fromordinal(feed_start.toordinal() - 1)

    print(f"GTFS feed_start_date : {feed_start_raw}  (effective: {effective_start})")
    print(f"GTFS feed_end_date   : {feed_end_raw}")
    print()

    # 2. Pobranie pierwszej strony
    apikey = get_apikey()
    print(f"Pobieranie strony 1 z API (pageSize={PAGE_SIZE})...")
    data = fetch_operations_page(apikey, page=1, page_size=PAGE_SIZE)

    trains = data.get("tr", [])
    pg = data.get("pg", {})
    total = pg.get("tc", "?")
    has_next = pg.get("hn", False)

    print(f"Lacznie pociagow wg API : {total}")
    print(f"Pobrano na tej stronie  : {len(trains)}")
    print(f"Jest kolejna strona     : {has_next}")
    print()

    if not trains:
        print("Brak danych z API.")
        return

    # 3. Analiza OperatingDate
    date_counter = Counter()
    inside = 0
    outside = 0
    example_outside = []
    example_inside = []

    for t in trains:
        od_str = t.get("od", "")  # operating date
        od_str_clean = od_str.replace("-", "")
        try:
            od = date(int(od_str_clean[:4]), int(od_str_clean[4:6]), int(od_str_clean[6:8]))
        except Exception:
            date_counter[f"NIEPARSOWALNE: {od_str!r}"] += 1
            outside += 1
            continue

        date_counter[od.isoformat()] += 1
        if effective_start <= od <= feed_end:
            inside += 1
            if len(example_inside) < 3:
                example_inside.append(t)
        else:
            outside += 1
            if len(example_outside) < 5:
                example_outside.append(t)

    print("=== Rozklad dat OperatingDate w odpowiedzi API ===")
    for d_str, count in sorted(date_counter.items()):
        try:
            d = date.fromisoformat(d_str)
            in_feed = "w feedzie" if effective_start <= d <= feed_end else "POZA FEEDEM"
        except Exception:
            in_feed = "BLAD"
        print(f"  {d_str}: {count:5d} pociagow  [{in_feed}]")

    print()
    print(f"Pociagi WEWNATRZ zakresu feeda : {inside}")
    print(f"Pociagi POZA zakresem feeda    : {outside}")
    print()

    if example_outside:
        print("=== Przykladowe pociagi POZA feedem ===")
        for t in example_outside:
            print(f"  sid={t.get('sid')} oid={t.get('oid')} od={t.get('od')} s={t.get('s','?')}")
        print()

    if example_inside:
        print("=== Przykladowe pociagi WEWNATRZ feeda ===")
        for t in example_inside:
            print(f"  sid={t.get('sid')} oid={t.get('oid')} od={t.get('od')} s={t.get('s','?')}")
        print()

    # 4. Surowy przyklad jednego rekordu
    print("=== Surowy przyklad pierwszego rekordu z API ===")
    print(json.dumps(trains[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()


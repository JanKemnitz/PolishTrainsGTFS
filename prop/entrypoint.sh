#!/bin/bash

PORT=8081
OUTPUT_DIR="/app/output"
# REALTIME_LOOP_PERIOD="120m"
DEFAULT_SLEEP=86400 # 24h fallback

mkdir -p "$OUTPUT_DIR"

refresh_data() {
    echo "--- Starting static GTFS refresh ---"
    python3 -m polish_trains_gtfs.static -o "$OUTPUT_DIR/polish_trains.zip"
    
    # if [ $? -eq 0 ]; then
    #     echo "Static GTFS generated successfully."
    #     if [ ! -z "$REALTIME_PID" ]; then
    #         echo "Restarting realtime generator to pick up new static data..."
    #         kill $REALTIME_PID
    #         wait $REALTIME_PID 2>/dev/null
    #     fi
        
    #     echo "Starting realtime generator with loop period $REALTIME_LOOP_PERIOD..."
    #     /app/realtime_gen \
    #         -gtfs "$OUTPUT_DIR/polish_trains.zip" \
    #         -output "$OUTPUT_DIR/polish_trains.pb" \
    #         -loop "$REALTIME_LOOP_PERIOD" &
    #     REALTIME_PID=$!
    # else
    #     echo "Static GTFS generation failed! Skipping realtime restart."
    # fi
}

refresh_data

echo "Starting file server on port $PORT..."
(cd "$OUTPUT_DIR" && python3 -m http.server "$PORT") &
SERVER_PID=$!

cleanup() {
    echo "Shutting down..."
    kill $SERVER_PID
    # [ ! -z "$REALTIME_PID" ] && kill $REALTIME_PID
    exit
}
trap cleanup SIGINT SIGTERM

while true; do
    if [ -z "$SYNC_SCHEDULE" ]; then
        SLEEP_TIME=$DEFAULT_SLEEP
        echo "No SYNC_SCHEDULE set, sleeping for $SLEEP_TIME seconds."
    else
        # Calculate sleep until next cron match
        SLEEP_TIME=$(python3 -c "
import datetime, os, sys
try:
    from croniter import croniter
    sched = os.environ.get('SYNC_SCHEDULE')
    now = datetime.datetime.now()
    it = croniter(sched, now)
    diff = (it.get_next(datetime.datetime) - now).total_seconds()
    print(int(diff))
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    print(3600) # Fallback to 1h on error
")
        echo "Next static sync scheduled (cron: $SYNC_SCHEDULE) in ${SLEEP_TIME}s."
    fi

    sleep "$SLEEP_TIME"
    refresh_data
done
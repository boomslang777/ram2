#!/bin/bash

# Sunday startup script with retry logic
LOCK_FILE="/tmp/sunday_startup.lock"
LOG_TIMESTAMP="$(date +'%Y-%m-%d %H:%M:%S')"

if [ -f "$LOCK_FILE" ]; then
    echo "$LOG_TIMESTAMP - Startup already in progress" >> /var/log/trading_cron.log
    exit 1
fi

touch "$LOCK_FILE"

{
    echo "=== SUNDAY STARTUP STARTED ==="
    
    # Start Docker
    echo "[1/3] Starting Docker stack..."
    cd /root/a1-trader && docker compose up -d
    sleep 20
    
    # Start app with retries
    echo "[2/3] Starting trading app..."
    for i in {1..3}; do
        if /root/start_app.sh; then
            echo "App started successfully (attempt $i)"
            break
        else
            echo "App start failed (attempt $i)"
            sleep $((i*10))
        fi
    done
    
    # Final status check
    echo "[3/3] Verifying system status..."
    # Add your custom healthcheck command here
    
    echo "=== SUNDAY STARTUP COMPLETED ==="
} | awk -v TS="$LOG_TIMESTAMP" '{print TS " - " $0}'

rm -f "$LOCK_FILE"

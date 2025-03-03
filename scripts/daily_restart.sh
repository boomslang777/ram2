#!/bin/bash

# Daily restart script with error handling and status checks
LOCK_FILE="/tmp/daily_restart.lock"
LOG_TIMESTAMP="$(date +'%Y-%m-%d %H:%M:%S')"

# Prevent overlapping runs
if [ -f "$LOCK_FILE" ]; then
    echo "$LOG_TIMESTAMP - Restart already in progress" >> /var/log/trading_cron.log
    exit 1
fi

touch "$LOCK_FILE"

{
    echo "=== DAILY RESTART STARTED ==="
    
    # Stop Docker containers
    echo "[1/4] Stopping Docker stack..."
    cd /root/a1-trader && docker compose down
    
    # Wait for clean shutdown
    echo "[2/4] Waiting for cleanup..."
    sleep 20
    
    # Start Docker
    echo "[3/4] Starting Docker stack..."
    if ! cd /root/a1-trader && docker compose up -d; then
        echo "Docker startup failed!"
        exit 1
    fi
    
    # Wait for services to initialize
    echo "[4/4] Finalizing..."
    sleep 15
    
    echo "=== DAILY RESTART COMPLETED ==="
} | awk -v TS="$LOG_TIMESTAMP" '{print TS " - " $0}'

rm -f "$LOCK_FILE"

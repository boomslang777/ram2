#!/bin/bash

# Friday shutdown script
LOG_TIMESTAMP="$(date +'%Y-%m-%d %H:%M:%S')"

{
    echo "=== FRIDAY SHUTDOWN STARTED ==="
    
    echo "[1/2] Stopping Docker..."
    cd /root/a1-trader && docker compose down
    
    echo "[2/2] Stopping trading app..."
    /root/stop_app.sh
    
    echo "=== FRIDAY SHUTDOWN COMPLETED ==="
} | awk -v TS="$LOG_TIMESTAMP" '{print TS " - " $0}'

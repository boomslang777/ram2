#!/bin/bash

echo "Stopping all running instances..."

# Kill any process using the Vite ports (5173-5190)
for port in {5173..5190}; do
    # Try netstat first, fall back to ss if netstat isn't available
    if command -v netstat >/dev/null 2>&1; then
        pid=$(netstat -tulpn 2>/dev/null | grep ":$port" | awk '{print $7}' | cut -d'/' -f1)
    else
        pid=$(ss -tulpn 2>/dev/null | grep ":$port" | awk '{print $7}' | cut -d'=' -f2 | cut -d',' -f1)
    fi
    
    if [ ! -z "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null
    fi
done

# Find and kill all uvicorn (backend) processes
pkill -f "uvicorn app.main:app"

# Find and kill all npm/node processes related to vite
pkill -f "vite"
pkill -f "node.*vite"
pkill -f "npm run dev"

# Kill any remaining Python processes related to the app
pkill -f "python.*app.main"

# Wait a moment to ensure processes are killed
sleep 2

# Double check and force kill if necessary
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "Force killing backend processes..."
    pkill -9 -f "uvicorn app.main:app"
fi

if pgrep -f "vite" > /dev/null || pgrep -f "npm run dev" > /dev/null; then
    echo "Force killing frontend processes..."
    pkill -9 -f "vite"
    pkill -9 -f "npm run dev"
fi

# Clear any leftover .pid files
rm -f backend.pid frontend.pid 2>/dev/null

# Wait another moment for ports to be fully released
sleep 2

# Verify ports are free
for port in {5173..5190}; do
    # Try netstat first, fall back to ss if netstat isn't available
    if command -v netstat >/dev/null 2>&1; then
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            echo "Warning: Port $port is still in use"
        fi
    else
        if ss -tuln 2>/dev/null | grep -q ":$port "; then
            echo "Warning: Port $port is still in use"
        fi
    fi
done

echo "Cleanup complete"

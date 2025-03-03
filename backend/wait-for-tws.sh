#!/bin/bash

echo "Waiting for IB Gateway to be ready..."
sleep 20  # Give IB Gateway time to fully initialize

echo "Starting FastAPI application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000
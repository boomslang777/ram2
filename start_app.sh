#!/bin/bash

# Go to home directory and activate virtual environment
cd ~
source venv/bin/activate

# Start backend in the background, redirect logs to a file
cd backend
nohup uvicorn app.main:app --host 0.0.0.0 --port 80 --reload > ../backend.log 2>&1 &

# Wait a few seconds for backend to start
sleep 3

# Start frontend in the background, redirect logs to a file
cd ~/frontend
nohup npm run dev -- --host > ../frontend.log 2>&1 &
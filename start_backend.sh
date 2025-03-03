#!/bin/bash
cd ~
source venv/bin/activate
cd backend
nohup uvicorn app.main:app --host 0.0.0.0 --port 80 --reload > ../backend.log 2>&1 & 
#!/bin/bash
cd ~/frontend
nohup npm run dev -- --host > ../frontend.log 2>&1 & 
from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, time
import json
import pytz
import nest_asyncio
import asyncio

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

from app.trading.ib_handler import IBHandler
from app.models.settings import Settings
import asyncio
from fastapi import BackgroundTasks
import os
from pathlib import Path

import math
from starlette.websockets import WebSocketState
import time as time_lib
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://192.210.140.221:5173",
        "http://172.18.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Update the file path handling
BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"

# Create settings file if it doesn't exist
if not SETTINGS_PATH.exists():
    default_settings = Settings(
        trading_enabled=True,
        quantity=1,
        dte=0,
        otm_strikes=2,
        default_strike=0.0
    )
    with open(SETTINGS_PATH, "w") as f:
        json.dump(default_settings.dict(), f)

# Load settings
with open(SETTINGS_PATH, "r") as f:
    settings = Settings(**json.load(f))

# Initialize IB Handler with settings
ib_handler = IBHandler(settings)

# Track active WebSocket connections
active_connections = []

async def send_heartbeat(websocket: WebSocket):
    """Send periodic heartbeat to keep connection alive"""
    while True:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({"type": "heartbeat", "timestamp": time_lib.time()})
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
        except Exception as e:
            print(f"Heartbeat error: {e}")
            break

async def send_data_updates(websocket: WebSocket):
    """Send periodic data updates to client"""
    while True:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                positions = await ib_handler.get_positions()
                orders = await ib_handler.get_orders()
                pnl = await ib_handler.get_pnl()
                spy_price = await ib_handler.get_spy_price()

                message = {
                    "type": "data",
                    "timestamp": time_lib.time(),
                    "data": {
                        "positions": positions,
                        "orders": orders,
                        "pnl": pnl,
                        "spyPrice": spy_price
                    }
                }

                # print("Sending data update via WebSocket:", message)
                await websocket.send_json(message)
                # print("Data update sent successfully")
            await asyncio.sleep(1)  # Send updates every second
        except Exception as e:
            print(f"Data update error: {e}")
            break

@app.on_event("startup")
async def startup_event():
    await ib_handler.connect()
    # Start auto square-off task
    asyncio.create_task(ib_handler.auto_square_off_task())

@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully close all WebSocket connections and cleanup IB connection"""
    # First close all WebSocket connections
    for websocket in active_connections[:]:
        try:
            await websocket.close(code=status.WS_1001_GOING_AWAY)
            active_connections.remove(websocket)
        except Exception as e:
            print(f"Error closing WebSocket during shutdown: {e}")
    active_connections.clear()
    
    # Then disconnect from IB
    try:
        await ib_handler.disconnect()
    except Exception as e:
        print(f"Error disconnecting from IB during shutdown: {e}")

@app.post("/api/signal")
async def handle_signal(signal: dict):
    if not settings.trading_enabled:
        return {"status": "error", "message": "Trading is disabled"}
    
    # Check if it's past the configured square-off time
    est = pytz.timezone('US/Eastern')
    current_time = datetime.now(est).time()
    
    try:
        hour, minute = map(int, settings.auto_square_off_time.split(':'))
        cutoff_time = time(hour, minute)
    except (ValueError, AttributeError):
        cutoff_time = time(15, 55)  # Fallback to default
    
    # if current_time >= cutoff_time:
    #     return {"status": "error", "message": "Trading hours ended"}
    
    return await ib_handler.process_signal(signal)

@app.post("/api/quick-trade")
async def handle_quick_trade(signal: dict):
    if not settings.trading_enabled:
        return {"status": "error", "message": "Trading is disabled"}
    
    # Check if it's past the configured square-off time
    est = pytz.timezone('US/Eastern')
    current_time = datetime.now(est).time()
    
    try:
        hour, minute = map(int, settings.auto_square_off_time.split(':'))
        cutoff_time = time(hour, minute)
    except (ValueError, AttributeError):
        cutoff_time = time(15, 55)  # Fallback to default
    
    # if current_time >= cutoff_time:
    #     return {"status": "error", "message": "Trading hours ended"}
    
    return await ib_handler.quick_trade_spy(signal)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("WebSocket connection attempt...")
    await websocket.accept()
    print("WebSocket connection accepted")
    await ib_handler.register_websocket(websocket)
    
    try:
        # Keep connection alive and handle client messages
        while True:
            try:
                message = await websocket.receive_text()
                print(f"Received message from client: {message}")
                # Handle any client messages if needed
                await websocket.send_json({
                    "type": "acknowledgment",
                    "message": "Message received",
                    "timestamp": time_lib.time()
                })
            except WebSocketDisconnect:
                print("Client disconnected normally")
                break
            except Exception as e:
                print(f"Error processing message: {e}")
                break

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Cleanup
        try:
            print("Cleaning up WebSocket connection...")
            await ib_handler.unregister_websocket(websocket)
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
            print("WebSocket cleanup complete")
        except Exception as e:
            print(f"Error during WebSocket cleanup: {e}")

@app.get("/api/positions")
async def get_positions():
    try:
        positions = await ib_handler.get_positions()
        # Clean any invalid float values
        for pos in positions:
            if math.isnan(pos['unrealizedPNL']) or math.isinf(pos['unrealizedPNL']):
                pos['unrealizedPNL'] = 0.0
            if math.isnan(pos['avgCost']) or math.isinf(pos['avgCost']):
                pos['avgCost'] = 0.0
            if math.isnan(pos['marketPrice']) or math.isinf(pos['marketPrice']):
                pos['marketPrice'] = 0.0
        return positions
    except Exception as e:
        print(f"Error in get_positions endpoint: {e}")
        raise HTTPException(status_code=500, detail="Failed to get positions")

@app.get("/api/orders")
async def get_orders():
    return await ib_handler.get_orders()

class PositionClose(BaseModel):
    position_id: int

@app.post("/api/close-position")
async def close_position(data: PositionClose):
    try:
        result = await ib_handler.close_position(data.position_id)
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OrderCancel(BaseModel):
    order_id: int  # Change to int since orderId is an integer

@app.post("/api/cancel-order")
async def cancel_order(data: OrderCancel):
    try:
        result = await ib_handler.cancel_order(data.order_id)
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    return settings

@app.post("/api/settings")
async def update_settings(new_settings: Settings):
    global settings
    settings = new_settings
    ib_handler.settings = new_settings  # Update IBHandler settings
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings.dict(), f)
    return settings

@app.get("/api/spy-price")
async def get_spy_price():
    try:
        spy_price = await ib_handler.get_spy_price()
        if math.isnan(spy_price) or math.isinf(spy_price):
            spy_price = 0.0
        return {"price": spy_price}
    except Exception as e:
        print(f"Error in get_spy_price endpoint: {e}")
        raise HTTPException(status_code=500, detail="Failed to get SPY price")

class BuyOrderRequest(BaseModel):
    position_id: int
    quantity: int

class SellOrderRequest(BaseModel):
    position_id: int
    quantity: int

@app.post("/api/positions/{position_id}/buy")
async def place_buy_order(position_id: int, request: BuyOrderRequest):
    """Place a buy order for an existing position"""
    try:
        result = await ib_handler.place_buy_order(position_id, request.quantity)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/positions/{position_id}/sell")
async def place_sell_order(position_id: int, request: SellOrderRequest):
    """Place a sell order for an existing position"""
    try:
        result = await ib_handler.place_sell_order(position_id, request.quantity)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

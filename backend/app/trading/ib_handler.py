from ib_insync import *
import asyncio
from datetime import datetime, timedelta, time
import pytz
import math
import random
import aiohttp
import time as time_lib
from typing import Dict, Set
from fastapi import WebSocket
from starlette.websockets import WebSocketState

class IBHandler:
    def __init__(self, settings):
        self.ib = IB()
        self.settings = settings
        self.market_data_tickers = {}
        self.pnl = None
        self.pnl_singles = {}  # Store PnLSingle subscriptions by conId
        self.pnl_req_id = None  # Store main PnL reqId
        self.current_pnl = {
            'dailyPnL': 0.0,
            'unrealizedPnL': 0.0,
            'realizedPnL': 0.0,
            'totalPnL': 0.0
        }
        self.open_orders = {}
        self.positions = {}  # Store positions with conId as key
        self.current_spy_price = 610.0  # Set default price to 610
        self.active_websockets = []  # Changed from set() to list
        self.update_queue = asyncio.Queue()
        self.is_streaming = False
        
        # Hardcoded account ID
        self.account = 'U4252435'
        
        # Telegram settings
        self.telegram_token = "8075397061:AAGorHxVqKDupzMPYFSZigpqkXT3CCbS-v8"
        self.telegram_chat_id = "-4627066193"
        
        # Clear logs on startup
        self.clear_logs()
        
        # New attribute for PnL subscriptions
        self.pnl_subscriptions_allowed = True
        
    def clear_logs(self):
        """Clear log files on startup"""
        try:
            # Clear backend.log
            with open('backend.log', 'w') as f:
                f.write('')
            print("Cleared backend.log")
            
            # Clear frontend.log if it exists
            try:
                with open('frontend.log', 'w') as f:
                    f.write('')
                print("Cleared frontend.log")
            except FileNotFoundError:
                pass  # Frontend log might not exist
        except Exception as e:
            print(f"Error clearing logs: {e}")

    async def connect(self):
        try:
            print("Attempting to connect to IB Gateway...")
            print(f"Target: 127.0.0.1:4001")
            
            # Try to connect with increased timeout
            try:
                await self.ib.connectAsync('127.0.0.1', 4001, clientId=random.randint(1,1000), timeout=30)
                print("Successfully connected to IB Gateway")
            except asyncio.TimeoutError:
                print("Connection timed out. Please check:")
                print("1. Is IB Gateway running?")
                print("2. Is it configured to accept API connections on port 4001?")
                print("3. Are you able to connect to TWS/Gateway manually?")
                print("4. Is there a firewall blocking the connection?")
                raise
            except ConnectionRefusedError:
                print("Connection refused. IB Gateway is not accepting connections on port 4001")
                raise
            
            print(f"Using hardcoded account: {self.account}")
            
            # Set delayed market data type BEFORE any market data requests
            self.ib.reqMarketDataType(4)  # 3 = Delayed frozen, 4 = Delayed, 1 = Live
            print("Set market data type to delayed frozen")
            
            # Register all callbacks
            self.ib.openOrderEvent += self.order_status_monitor
            self.ib.positionEvent += self.position_monitor
            self.ib.updatePortfolioEvent += self.portfolio_monitor
            self.ib.pendingTickersEvent += self.market_data_monitor
            self.ib.pnlEvent += self.pnl_callback
            self.ib.pnlSingleEvent += self.on_pnl_single_update
            self.ib.errorEvent += self.on_error
            self.ib.disconnectedEvent += self.on_disconnect
            print("Registered all callbacks")
            
            # Initialize SPY market data
            await self.initialize_spy_market_data()
            
            # Get initial positions with error handling
            print("Getting initial positions...")
            try:
                positions = self.ib.positions(account=self.account)  # Specify account explicitly
                if positions:
                    for position in positions:
                        await self.position_monitor(position)
                else:
                    print("No positions found or positions not yet available")
            except Exception as e:
                print(f"Error getting initial positions: {e}")
                print("Positions may not be available until account is fully approved")
            
            # Try to subscribe to PnL updates
            try:
                await self.subscribe_to_pnl()
            except Exception as e:
                print(f"Error setting up PnL subscriptions: {e}")
                print("PnL data may not be available until account is fully approved")

            # Start the update broadcaster
            asyncio.create_task(self.broadcast_updates())
            
            print("Initial data sync complete")
            return
        except Exception as e:
            print(f"Connection error: {e}")
            raise

    async def initialize_spy_market_data(self):
        """Initialize SPY market data subscription"""
        try:
            if 'SPY' not in self.market_data_tickers:  # Only initialize if not already done
                self.ib.reqMarketDataType(4)  # Ensure delayed data
                await asyncio.sleep(0.1)
                
                spy = Stock(symbol='SPY', exchange='SMART', currency='USD')
                qualified = await self.ib.qualifyContractsAsync(spy)
                if qualified:
                    self.market_data_tickers['SPY'] = self.ib.reqMktData(qualified[0])
                    print("Successfully subscribed to SPY delayed market data")
                    await asyncio.sleep(1)  # Give time for initial data
        except Exception as e:
            print(f"Error initializing SPY market data: {e}")

    def market_data_monitor(self, tickers):
        """Monitor market data updates"""
        try:
            for ticker in tickers:
                contract = ticker.contract
                conId = contract.conId
                if conId in self.positions:
                    # For options and other instruments
                    price = ticker.last or ticker.close or ticker.bid or ticker.ask or 0.0
                    
                    if price and price > 0 and isinstance(price, (int, float)):
                        # For options, price is already in dollars
                        if contract.secType == 'OPT':
                            self.positions[conId]['marketPrice'] = float(price)
                        else:
                            self.positions[conId]['marketPrice'] = float(price)
                            
                        # print(f"Updated market price for {contract.localSymbol}: {self.positions[conId]['marketPrice']}")
                        
                elif contract.symbol == 'SPY' and contract.secType == 'STK':
                    # Handle SPY underlying price updates
                    price = ticker.last
                    if price and price > 0:
                        self.current_spy_price = float(price)
                        
        except Exception as e:
            print(f"Error in market data monitor: {e}")
            print(f"Ticker data: {vars(ticker) if ticker else 'No ticker'}")

    def order_status_monitor(self, trade):
        try:
            order = trade.order
            status = trade.orderStatus
            contract = trade.contract
            
            # Track all orders initially, remove only when fully processed
            self.open_orders[order.orderId] = {
                'orderId': order.orderId,
                'contract': {
                    'localSymbol': contract.localSymbol,
                    'secType': contract.secType,
                },
                'action': order.action,
                'totalQuantity': order.totalQuantity,
                'orderType': order.orderType,
                'status': status.status,
                'filled': status.filled,
                'remaining': status.remaining,
                'avgFillPrice': status.avgFillPrice or 0.0,
                'errorMessage': getattr(trade, 'errorMessage', '')  # Add error message if exists
            }
            
            # Only remove orders that are fully processed and complete
            if status.status in ['Filled', 'Cancelled', 'Inactive'] and status.remaining == 0:
                self.open_orders.pop(order.orderId, None)
                
            # Send notifications for significant events
            if status.status == 'Filled' and order.totalQuantity != 0:
                message = (
                    f"🔔 <b>Trade Executed</b>\n\n"
                    f"Symbol: {contract.localSymbol}\n"
                    f"Action: {order.action}\n"
                    f"Quantity: {order.totalQuantity}\n"
                    f"Fill Price: ${status.avgFillPrice:.2f}\n"
                    f"Order Type: {order.orderType}"
                )
                asyncio.create_task(self.send_telegram_message(message))
            # elif status.status == 'Cancelled':
            #     message = (
            #         f"❌ <b>Order Cancelled</b>\n\n"
            #         f"Symbol: {contract.localSymbol}\n"
            #         f"Action: {order.action}\n"
            #         f"Quantity: {order.totalQuantity}"
            #     )
            #     asyncio.create_task(self.send_telegram_message(message))
            elif hasattr(trade, 'errorMessage') and trade.errorMessage:
                message = (
                    f"⚠️ <b>Order Error</b>\n\n"
                    f"Symbol: {contract.localSymbol}\n"
                    f"Error: {trade.errorMessage}"
                )
                asyncio.create_task(self.send_telegram_message(message))
            
            # Only log significant order events
            if status.status in ['Filled', 'Cancelled', 'Inactive'] or hasattr(trade, 'errorMessage'):
                print(f'\nOrder Update - {contract.symbol}:')
                print(f'Order ID: {order.orderId}, Status: {status.status}')
                print(f'Filled: {status.filled}, Remaining: {status.remaining}')
                if hasattr(trade, 'log'):
                    for entry in trade.log:
                        if entry.errorCode:
                            print(f'Error {entry.errorCode}: {entry.message}')
            
        except Exception as e:
            print(f"Error in order status monitor: {e}")

    async def position_monitor(self, position):
        try:
            # Requalify contract to ensure correct exchange
            async def qualify_contract(contract):
                try:
                    qualified = await self.ib.qualifyContractsAsync(contract)
                    return qualified[0] if qualified else contract
                except Exception as e:
                    print(f"Error requalifying contract: {e}")
                    return contract
            
            # Use existing event loop instead of asyncio.run()
            qualified_contract = await qualify_contract(position.contract)
            
            print(f'\nPosition Update - {qualified_contract.localSymbol}:')
            avg_cost = float(position.avgCost) / 100 if position.avgCost else 0.0
            print(f'Position: {position.position}, Avg Cost: {avg_cost}')

            if position.position != 0:
                if qualified_contract.conId not in self.market_data_tickers:
                    print(f"Subscribing to market data for {qualified_contract.localSymbol} on {qualified_contract.exchange}")
                    await self._delayed_market_data_request(qualified_contract)

                self.positions[qualified_contract.conId] = {
                    'contract': {
                        'conId': qualified_contract.conId,
                        'localSymbol': qualified_contract.localSymbol,
                        'secType': qualified_contract.secType,
                        'exchange': qualified_contract.exchange or 'SMART',
                        'symbol': qualified_contract.symbol,
                        'right': qualified_contract.right if hasattr(qualified_contract, 'right') else None,
                        'strike': qualified_contract.strike if hasattr(qualified_contract, 'strike') else None,
                    },
                    'position': position.position,
                    'avgCost': avg_cost,
                    'marketPrice': 0.0,  # Will be updated by market_data_monitor
                    'unrealizedPNL': 0.0,  # Will be updated by pnlSingleEvent
                    'dailyPNL': 0.0,      # Added for daily PnL tracking
                    'realizedPNL': 0.0     # Added for realized PnL tracking
                }

                # Add subscription with validation
                if self.pnl_subscriptions_allowed:
                    await self._safe_subscribe_pnl_single(qualified_contract.conId)
                else:
                    print("Skipping PnL Single subscription - not allowed")
            else:
                # Remove closed positions and cancel market data subscription
                if qualified_contract.conId in self.market_data_tickers:
                    print(f"Canceling market data subscription for {qualified_contract.localSymbol}")
                    ticker = self.market_data_tickers[qualified_contract.conId]
                    self.ib.cancelMktData(ticker.contract)
                    del self.market_data_tickers[qualified_contract.conId]
                self.positions.pop(qualified_contract.conId, None)
                
        except Exception as e:
            print(f"Error in position monitor for {qualified_contract.localSymbol}: {e}")
            print(f"Debug - position data: avgCost={position.avgCost}, position={position.position}")

    async def _delayed_market_data_request(self, contract):
        """Helper method to request market data with a delay"""
        try:
            await asyncio.sleep(0.1)
            # Use blocking market data request
            self.market_data_tickers[contract.conId] = self.ib.reqMktData(contract)
        except Exception as e:
            print(f"Error requesting market data for {contract.localSymbol}: {e}")

    def portfolio_monitor(self, item):
        try:
            if item.contract.conId in self.positions:
                # Always divide market price by 100 for display
                market_price = float(item.marketPrice) / 100 if item.marketPrice else 0.0
                unrealized_pnl = float(item.unrealizedPNL) if item.unrealizedPNL else 0.0

                print(f'\nPortfolio Update Raw - {item.contract.localSymbol}:')
                print(f'Raw Market Price: {item.marketPrice}, Raw Unrealized PNL: {item.unrealizedPNL}')

                self.positions[item.contract.conId].update({
                    'marketPrice': market_price,
                    'unrealizedPNL': unrealized_pnl
                })
                
                print(f'\nPortfolio Update - {item.contract.localSymbol}:')
                print(f'Market Price: {market_price}, Unrealized PNL: {unrealized_pnl}')
            
        except Exception as e:
            print(f"Error in portfolio monitor: {e}")
            print(f"Debug - item data: {vars(item)}")

    async def get_orders(self):
        """Return only open orders"""
        return list(self.open_orders.values())

    async def disconnect(self):
        """Async disconnect to handle cleanup properly"""
        try:
            if not self.ib.isConnected():
                return

            # Cancel PnL subscriptions
            try:
                # Cancel main PnL subscription
                if self.pnl:
                    self.ib.cancelPnL(self.account, '')
                    self.pnl = None
                
                # Cancel all PnL Single subscriptions using proper parameters
                for pnl_single in list(self.pnl_singles.values()):
                    try:
                        self.ib.cancelPnLSingle(self.account, '', pnl_single.conId)
                    except Exception as e:
                        print(f"Error canceling PnL Single for {pnl_single.conId}: {e}")
                self.pnl_singles.clear()
                
            except Exception as e:
                print(f"Error canceling PnL subscriptions: {e}")

            # First unregister all callbacks
            try:
                self.ib.openOrderEvent -= self.order_status_monitor
                self.ib.positionEvent -= self.position_monitor
                self.ib.updatePortfolioEvent -= self.portfolio_monitor
                if self.pnl:
                    self.ib.pnlEvent -= self.pnl_callback
            except Exception as e:
                print(f"Error unregistering callbacks: {e}")

            # Then cancel PnL subscription
            try:
                if self.pnl:
                    self.ib.cancelPnL(self.account, '')
                    self.pnl = None
            except Exception as e:
                print(f"Error canceling PnL subscription: {e}")

            # Cancel market data subscriptions if any exist
            try:
                for ticker in list(self.market_data_tickers.values()):
                    if hasattr(ticker, 'contract'):
                        self.ib.cancelMktData(ticker.contract)
                        await asyncio.sleep(0.1)  # Give time for cancellation to process
                self.market_data_tickers.clear()
            except Exception as e:
                print(f"Error clearing market data tickers: {e}")

            # Finally disconnect
            self.ib.disconnect()

        except Exception as e:
            print(f"Error during disconnect: {e}")

    async def subscribe_to_pnl(self):
        """Subscribe to PnL updates with enhanced validation"""
        try:
            if not self.pnl_subscriptions_allowed:
                print("PnL subscriptions temporarily disabled")
                return

            print(f"Initializing PnL subscriptions for {self.account}")
            
            # Clean up any existing subscriptions first
            await self._cleanup_pnl_subscriptions()

            # Main PnL subscription with error handling
            try:
                self.pnl = self.ib.reqPnL(self.account, '')
                print(f"Main PnL subscription created: {self.pnl}")
                
                # Wait briefly for initial PnL data
                await asyncio.sleep(1)
                
                if hasattr(self.pnl, 'dailyPnL'):
                    print(f"Initial PnL values: dailyPnL={self.pnl.dailyPnL}")
                else:
                    print("Warning: PnL object missing expected attributes")
                
            except Exception as e:
                print(f"Failed to create main PnL subscription: {e}")
                self.pnl = None
                return

            # Position PnL subscriptions
            if self.positions:
                for conId in list(self.positions.keys()):
                    try:
                        await self._safe_subscribe_pnl_single(conId)
                        await asyncio.sleep(0.2)  # Rate limiting
                    except Exception as e:
                        print(f"Error subscribing to position {conId} PnL: {e}")
            else:
                print("No positions found for PnL subscriptions")

            print("PnL subscription process completed")
            
        except Exception as e:
            print(f"Error in PnL subscription process: {e}")

    async def _safe_subscribe_pnl_single(self, conId: int):
        """Safe PnL Single subscription with validation"""
        try:
            if conId in self.pnl_singles:
                return

            if not self.pnl_subscriptions_allowed:
                return

            print(f"Attempting PnL Single subscription for {conId}")
            pnl_single = self.ib.reqPnLSingle(
                account=self.account,
                modelCode='',
                conId=conId
            )
            
            if pnl_single:
                self.pnl_singles[conId] = pnl_single
                print(f"PnL Single subscription successful for {conId}")
            else:
                print(f"Failed to create PnL Single subscription for {conId}")

        except Exception as e:
            print(f"Failed to subscribe PnL Single for {conId}: {e}")
            if conId in self.pnl_singles:
                del self.pnl_singles[conId]

    async def _cleanup_pnl_subscriptions(self):
        """Properly cleanup all PnL subscriptions"""
        try:
            # Clean main PnL
            if self.pnl:
                try:
                    self.ib.cancelPnL(self.account, '')
                except Exception as e:
                    print(f"Error canceling main PnL: {e}")
                self.pnl = None

            # Clean PnL Singles
            for conId in list(self.pnl_singles.keys()):
                try:
                    self.ib.cancelPnLSingle(self.account, '', conId)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"Error canceling PnL Single {conId}: {e}")
                del self.pnl_singles[conId]

        except Exception as e:
            print(f"Error in subscription cleanup: {e}")
            self.pnl_singles.clear()

    def pnl_callback(self, pnl):
        try:
            print(f"Raw PnL update received: dailyPnL={pnl.dailyPnL}, unrealizedPnL={pnl.unrealizedPnL}, realizedPnL={pnl.realizedPnL}")
            
            # Convert values to float and handle None values
            daily_pnl = self.safe_float(pnl.dailyPnL)
            unrealized_pnl = self.safe_float(pnl.unrealizedPnL)
            realized_pnl = self.safe_float(pnl.realizedPnL)
            total_pnl = unrealized_pnl + realized_pnl
            
            # Update the current PnL dictionary
            self.current_pnl = {
                'dailyPnL': daily_pnl,
                'unrealizedPnL': unrealized_pnl,
                'realizedPnL': realized_pnl,
                'totalPnL': total_pnl
            }
            
            print(f"Processed PnL values: {self.current_pnl}")
            
            # Queue update for broadcasting
            asyncio.create_task(self.queue_update())
            
        except Exception as e:
            print(f"Error in PnL callback: {e}")

    def on_pnl_single_update(self, pnl_single):
        """Handle individual position PnL updates"""
        try:
            conId = pnl_single.conId
            if conId in self.positions:
                # Update all PnL values
                self.positions[conId].update({
                    'unrealizedPNL': self.safe_float(pnl_single.unrealizedPnL),
                    'dailyPNL': self.safe_float(pnl_single.dailyPnL),
                    'realizedPNL': self.safe_float(pnl_single.realizedPnL),
                    'value': self.safe_float(pnl_single.value)
                })
                print(f"Updated position {conId} PnL: unrealized={self.positions[conId]['unrealizedPNL']}, daily={self.positions[conId]['dailyPNL']}")
                
                # Queue update immediately for this position
                asyncio.create_task(self.queue_update())
        except Exception as e:
            print(f"Position PnL update error: {e}")

    async def queue_update(self):
        """Queue an update for broadcasting"""
        try:
            update_data = {
                'type': 'data',
                'timestamp': time_lib.time(),
                'data': {
                    'positions': list(self.positions.values()),
                    'orders': list(self.open_orders.values()),
                    'pnl': self.current_pnl,
                    'spyPrice': self.current_spy_price
                }
            }
            print(f"Queueing update with PnL: {update_data['data']['pnl']}")
            await self.update_queue.put(update_data)
        except Exception as e:
            print(f"Error queueing update: {e}")

    async def broadcast_updates(self):
        """Efficient update broadcaster"""
        while True:
            try:
                update = await self.update_queue.get()
                to_remove = []
                
                print(f"Broadcasting update with PnL: {update['data']['pnl']}")

                for i, ws in enumerate(self.active_websockets):
                    try:
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_json(update)
                            print(f"Successfully sent update to websocket")
                        else:
                            to_remove.append(i)
                            print(f"Found dead websocket")
                    except Exception as e:
                        print(f"Error sending to websocket: {e}")
                        to_remove.append(i)

                # Remove dead connections in reverse order to maintain correct indices
                for i in reversed(to_remove):
                    try:
                        self.active_websockets.pop(i)
                    except IndexError:
                        pass
                
            except Exception as e:
                print(f"Broadcast error: {e}")
                await asyncio.sleep(0.1)

    def safe_float(self, value) -> float:
        """Safe float conversion with validation"""
        try:
            if value is None:
                return 0.0
            result = float(value)
            return 0.0 if math.isnan(result) or math.isinf(result) else result
        except (ValueError, TypeError):
            return 0.0

    def on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB API errors"""
        error_msg = f"IB Error {errorCode}: {errorString}"
        print(error_msg)
        
        if errorCode == 10275:  # Positions not available
            print("Account not fully approved. Delaying PnL subscriptions.")
            self.pnl_subscriptions_allowed = False
        elif errorCode == 321 and "Invalid account code" in errorString:
            print("Account validation failed. Check account configuration.")
            self.pnl_subscriptions_allowed = False
            asyncio.create_task(self._cleanup_pnl_subscriptions())
        elif errorCode == 10091:  # Market data subscription
            print("Market data subscription required. Using delayed data.")
            self.ib.reqMarketDataType(3)  # Switch to delayed frozen data
        elif errorCode in [1100, 1101, 1102]:  # Connection-related errors
            asyncio.create_task(self.reconnect())
            
        # Log error details
        print(f"Request ID: {reqId}")
        if contract:
            print(f"Contract details: {contract.localSymbol if hasattr(contract, 'localSymbol') else contract.symbol}")

    async def reconnect(self):
        """Handle reconnection"""
        try:
            self.ib.disconnect()
            await asyncio.sleep(5)  # Wait before reconnecting
            await self.connect()
        except Exception as e:
            print(f"Reconnection error: {e}")

    def on_disconnect(self):
        """Handle disconnection"""
        print("Disconnected from IB")
        asyncio.create_task(self.reconnect())

    async def register_websocket(self, websocket: WebSocket):
        """Register new WebSocket connection"""
        if websocket not in self.active_websockets:
            self.active_websockets.append(websocket)

    async def unregister_websocket(self, websocket: WebSocket):
        """Unregister WebSocket connection"""
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)

    async def get_pnl(self):
        """Return current PnL values"""
        try:
            # Calculate total unrealized PnL from positions if available
            total_unrealized = sum(pos.get('unrealizedPNL', 0.0) for pos in self.positions.values())
            total_realized = self.current_pnl.get('realizedPnL', 0.0)
            
            # If we have position-based unrealized PnL, use it
            if total_unrealized != 0.0:
                self.current_pnl['unrealizedPnL'] = total_unrealized
                self.current_pnl['totalPnL'] = total_unrealized + total_realized
            
            # Clean any NaN or inf values
            for key in self.current_pnl:
                if math.isnan(self.current_pnl[key]) or math.isinf(self.current_pnl[key]):
                    self.current_pnl[key] = 0.0
            
            # Print current PnL values for debugging
            # print(f"Current PnL values: {self.current_pnl}")
            
            return self.current_pnl
        except Exception as e:
            print(f"Error getting PnL: {e}")
            return {
                'dailyPnL': 0.0,
                'unrealizedPnL': 0.0,
                'realizedPnL': 0.0,
                'totalPnL': 0.0
            }

    async def get_spy_price(self):
        """Return current SPY price"""
        try:
            if 'SPY' not in self.market_data_tickers:
                await self.initialize_spy_market_data()
            
            ticker = self.market_data_tickers.get('SPY')
            if ticker:
                price = ticker.last
                if price and price > 0:
                    self.current_spy_price = float(price)
                    return self.current_spy_price
            
            return self.current_spy_price
        except Exception as e:
            print(f"Error getting SPY price: {e}")
            return self.current_spy_price

    async def get_mes_contract(self):
        try:
            # Specify MES future contract with explicit exchange
            contract = Future(
                symbol='MES',
                lastTradeDateOrContractMonth='20250321',  # Add specific expiration
                exchange='CME',
                currency='USD'
            )
            
            # Qualify contract with explicit exchange
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                print("No qualified contracts found for MES")
                return None
            
            contract = qualified[0]
            print(f"Using qualified MES contract: {contract}")
            return contract
            
        except Exception as e:
            print(f"Error getting MES contract: {e}")
            return None

    async def get_spy_option(self, action=None, expiry=None):
        try:
            # Calculate strike price based on selection
            base_strike = round(self.current_spy_price)
            
            if 'Buy' in action:
                right = 'C'
                selection = self.settings.call_strike_selection
                if selection == "ATM":
                    strike = base_strike
                elif selection == "OTM-1":
                    strike = base_strike + 1
                elif selection == "OTM-2":
                    strike = base_strike + 2
                elif selection == "OTM-3":
                    strike = base_strike + 3
                else:
                    strike = base_strike
            else:
                right = 'P'
                selection = self.settings.put_strike_selection
                if selection == "ATM":
                    strike = base_strike
                elif selection == "OTM-1":
                    strike = base_strike - 1
                elif selection == "OTM-2":
                    strike = base_strike - 2
                elif selection == "OTM-3":
                    strike = base_strike - 3
                else:
                    strike = base_strike

            if not expiry:
                # Get option chain details
                contract = Stock('SPY', 'SMART', 'USD')
                qualified_contracts = await self.ib.qualifyContractsAsync(contract)
                if qualified_contracts:
                    conId = qualified_contracts[0].conId
                    symbol = qualified_contracts[0].symbol
                    print(f"Qualified contracts: {qualified_contracts}, conId: {conId}, symbol: {symbol}")
                else:
                    print("No qualified contracts found")
                chains = await self.ib.reqSecDefOptParamsAsync(
                    underlyingSymbol=symbol,
                    futFopExchange='',
                    underlyingSecType='STK',
                    underlyingConId=conId
                )
                
                if not chains:
                    print("No option chains found for SPY")
                    return None
                
                # Sort expirations and get the appropriate one
                chain = chains[0]  # SMART exchange chain
                expirations = sorted(chain.expirations)
                
                if not expirations:
                    print("No expirations found in the option chain")
                    return None
                
                # Select expiration based on dte setting
                expiry_index = min(self.settings.dte, len(expirations) - 1)
                expiry = expirations[expiry_index]

            print(f"Creating SPY option: Strike={strike}, Right={right}, Expiry={expiry}")
            
            # Properly specify the option contract
            contract = Option(
                symbol='SPY',
                lastTradeDateOrContractMonth=expiry,
                strike=strike,
                right=right,
                exchange='SMART',
                currency='USD',
                multiplier='100'
            )
            
            # First get contract details to ensure we have the correct contract
            details = await self.ib.reqContractDetailsAsync(contract)
            if not details:
                print("No contract details found")
                return None
                
            # Use the first contract from details
            contract = details[0].contract
            print(f"Using contract: {contract}")
            return contract
            
        except Exception as e:
            print(f"Error getting SPY option: {e}")
            return None

    async def get_positions(self):
        """Return list of current positions with properly formatted prices"""
        positions = list(self.positions.values())
        for pos in positions:
            if pos['contract']['secType'] == 'OPT':
                # Format market price for display
                pos['marketPrice'] = pos['marketPrice']  # Price is already in correct format
        return positions

    def is_regular_trading_hours(self) -> bool:
        """Check if current time is within regular trading hours (9:30 AM - 4:00 PM EST)"""
        est = pytz.timezone('US/Eastern')
        current_time = datetime.now(est).time()
        market_open = time(9, 30)
        market_close = time(16, 0)
        return market_open <= current_time <= market_close

    async def process_signal(self, signal):
        try:
            symbol = signal['symbol']
            action = signal['action']
            print(f"Processing signal: {symbol} {action}")
            
            # Handle exit orders
            if 'Exit' in action:
                positions = await self.ib.reqPositionsAsync()  # Specify account explicitly
                print("Current positions:", positions)
                position_found = None
                
                # Find matching position
                for pos in positions:
                    if 'MES' in symbol and pos.contract.symbol == 'MES':
                        position_found = pos
                        break
                    elif 'SPY' in symbol and pos.contract.symbol == 'SPY':
                        # For SPY, only look for option positions
                        if pos.contract.secType == 'OPT':
                            is_long = pos.position > 0
                            is_call = pos.contract.right == 'C'
                            if ('Buy' in action and is_long and is_call) or \
                               ('Sell' in action and is_long and not is_call):
                                position_found = pos
                                break
                
                if not position_found:
                    return {
                        "status": "error", 
                        "message": f"No matching open position found for {symbol}"
                    }
                
                print(f"Closing position: {position_found.contract}")
                
                # Qualify the contract first
                qualified_contracts = await self.ib.qualifyContractsAsync(position_found.contract)
                if not qualified_contracts:
                    return {"status": "error", "message": "Could not qualify contract"}
                
                qualified_contract = qualified_contracts[0]
                
                # Place exit order with exchange specified from qualified contract
                exit_action = 'SELL' if position_found.position > 0 else 'BUY'
                order = MarketOrder(
                    action=exit_action,
                    totalQuantity=abs(position_found.position),
                    account=self.account
                )
                
                # Only set outsideRTH if outside regular trading hours
                if not self.is_regular_trading_hours():
                    order.outsideRTH = True
                
                order.exchange = qualified_contract.exchange # Set account explicitly
                
                print(f"Order: {order}")
                trade = self.ib.placeOrder(qualified_contract, order)
                print(f"Trade: {trade}")
                
                # Wait briefly for order status and send notification
                await asyncio.sleep(1)
                avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
                
                # Send notification for position close
                message = (
                    f"🔄 <b>Position Exit Initiated</b>\n\n"
                    f"Symbol: {qualified_contract.localSymbol}\n"
                    f"Action: {exit_action}\n"
                    f"Quantity: {abs(position_found.position)}\n"
                    f"Order Type: MARKET\n"
                    f"Fill Price: {avg_price}"
                )
                await self.send_telegram_message(message)
                
                await asyncio.sleep(0.5)
                await self.resync_data()
                return {"status": "success", "order_id": trade.order.orderId}
            
            # Handle new position orders
            if 'MES' in symbol:
                # Get qualified contract
                contract = await self.get_mes_contract()
                if not contract:
                    return {"status": "error", "message": "Could not qualify MES contract"}
                
                # Set order parameters
                order_action = 'BUY' if 'Buy' in action else 'SELL'
                quantity = signal.get('quantity', self.settings.mes_quantity)
                
                # Create market order with proper exchange
                order = MarketOrder(
                    action=order_action,
                    totalQuantity=quantity,
                    account=self.account
                )
                
                # Only set outsideRTH if outside regular trading hours
                if not self.is_regular_trading_hours():
                    order.outsideRTH = True
                
                order.exchange = 'CME'
                
                # Place the order
                trade = self.ib.placeOrder(contract, order)
                print(f"Trade: {trade}")
                
                # Wait briefly for order status and send notification
                await asyncio.sleep(1)
                avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
                
                # Send notification for new position
                message = (
                    f"🔔 <b>New Position Initiated</b>\n\n"
                    f"Symbol: {contract.localSymbol}\n"
                    f"Action: {order_action}\n"
                    f"Quantity: {quantity}\n"
                    f"Order Type: MARKET\n"
                    f"Fill Price: ${avg_price:.2f}"
                )
                await self.send_telegram_message(message)
                
                await asyncio.sleep(0.5)
                await self.resync_data()
                return {"status": "success", "order_id": trade.order.orderId}
            
            elif 'SPY' in symbol:
                is_buy_signal = 'Buy' in action
                contract = await self.get_spy_option(
                    action='Buy' if is_buy_signal else 'Sell'  # This determines call/put selection
                )
                if not contract:
                    return {"status": "error", "message": "Could not qualify SPY option contract"}
                
                # Verify it's an option contract
                if contract.secType != 'OPT':
                    return {"status": "error", "message": "SPY signals must be for options only"}
                
                order_action = 'BUY'  # Always buy options, we use calls/puts for direction
                quantity = signal.get('quantity', self.settings.spy_quantity)
            else:
                return {"status": "error", "message": f"Unsupported symbol: {symbol}"}
            
            # Place the order
            order = MarketOrder(
                action=order_action,
                totalQuantity=quantity
            )
            order.outsideRTH = True
            
            print(f"Order: {order}")
            trade = self.ib.placeOrder(contract, order)
            print(f"Trade: {trade}")
            
            # Wait briefly for order status and send notification
            await asyncio.sleep(1)
            avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
            
            # Send notification for new position
            message = (
                f"🔔 <b>New Position Initiated</b>\n\n"
                f"Symbol: {contract.localSymbol}\n"
                f"Action: {order_action}\n"
                f"Quantity: {quantity}\n"
                f"Order Type: MARKET\n"
                f"Fill Price: ${avg_price:.2f}"
            )
            await self.send_telegram_message(message)
            
            await asyncio.sleep(0.5)
            await self.resync_data()
            return {"status": "success", "order_id": trade.order.orderId}
            
        except Exception as e:
            print(f"Error processing signal: {e}")
            return {"status": "error", "message": str(e)}

    def _clean_message(self, message):
        """Clean numeric values in message"""
        def clean_value(v):
            if isinstance(v, (int, float)):
                if math.isnan(v) or math.isinf(v):
                    return 0.0
                return float(v)
            elif isinstance(v, dict):
                return {k: clean_value(val) for k, val in v.items()}
            elif isinstance(v, list):
                return [clean_value(item) for item in v]
            return v
            
        return clean_value(message)

    async def auto_square_off_task(self):
        """Monitor and auto square off positions at configured time"""
        while True:
            try:
                if self.settings.auto_square_off_enabled:
                    est = pytz.timezone('US/Eastern')
                    current_time = datetime.now(est).time()
                    
                    # Parse the configured square off time
                    try:
                        hour, minute = map(int, self.settings.auto_square_off_time.split(':'))
                        cutoff_time = time(hour, minute)
                    except (ValueError, AttributeError):
                        # Fallback to default if time format is invalid
                        cutoff_time = time(15, 55)
                        print(f"Invalid square off time format, using default: {cutoff_time}")

                    if current_time >= cutoff_time:
                        print(f"Auto square-off triggered at {current_time}")
                        positions = await self.get_positions()
                        for pos in positions:
                            await self.close_position(pos['contract']['conId'])
                            print(f"Closed position: {pos['contract']['localSymbol']}")
                        
                        # Sleep until next day's session
                        next_session = datetime.now(est) + timedelta(days=1)
                        next_session = next_session.replace(hour=9, minute=30, second=0, microsecond=0)
                        sleep_seconds = (next_session - datetime.now(est)).total_seconds()
                        await asyncio.sleep(sleep_seconds)
                    else:
                        # Check every minute
                        await asyncio.sleep(60)
                else:
                    # If auto square-off is disabled, check less frequently
                    await asyncio.sleep(300)
                
            except Exception as e:
                print(f"Error in auto square off task: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying on error

    async def close_position(self, position_id: int):
        try:
            positions = await self.ib.reqPositionsAsync()
            for pos in positions:
                if pos.contract.conId == position_id:
                    # Ensure contract is properly qualified
                    contract = pos.contract
                    qualified_contracts = await self.ib.qualifyContractsAsync(contract)
                    if not qualified_contracts:
                        return {"status": "error", "message": "Could not qualify contract"}
                    
                    qualified_contract = qualified_contracts[0]
                    
                    # Create market order with proper exchange
                    action = 'SELL' if pos.position > 0 else 'BUY'
                    order = MarketOrder(
                        action=action,
                        totalQuantity=abs(pos.position),
                        account=self.account
                    )
                    order.outsideRth = True
                    order.exchange = qualified_contract.exchange  # Set the exchange from qualified contract
                    
                    # Place the order
                    trade = self.ib.placeOrder(qualified_contract, order)
                    await asyncio.sleep(1)
                    avg_price=trade.orderStatus.avgFillPrice
                    # Send notification for position close
                    message = (
                        f"🔄 <b>Position Close Initiated</b>\n\n"
                        f"Symbol: {qualified_contract.localSymbol}\n"
                        f"Action: {action}\n"
                        f"Quantity: {abs(pos.position)}\n"
                        f"Order Type: MARKET"
                        f"Fill price : {avg_price}"
                    )
                    await self.send_telegram_message(message)
                    
                    await asyncio.sleep(0.5)
                    await self.resync_data()
                    return {"status": "success", "message": "Position close order placed"}
            
            return {"status": "error", "message": "Position not found"}
        except Exception as e:
            print(f"Error closing position: {e}")
            return {"status": "error", "message": str(e)}

    async def place_buy_order(self, position_id: int, quantity: int):
        """Place a buy order for an existing position"""
        try:
            # Find the position in current positions
            positions = await self.ib.reqPositionsAsync()
            target_position = None
            
            for pos in positions:
                if pos.contract.conId == position_id:
                    target_position = pos
                    break
                    
            if not target_position:
                return {"status": "error", "message": "Position not found"}
            
            # Qualify the contract
            qualified_contracts = await self.ib.qualifyContractsAsync(target_position.contract)
            if not qualified_contracts:
                return {"status": "error", "message": "Could not qualify contract"}
            
            qualified_contract = qualified_contracts[0]
            
            # Place market order
            order = MarketOrder('BUY', quantity, account=self.account)
            
            # Only set outsideRTH if outside regular trading hours
            if not self.is_regular_trading_hours():
                order.outsideRTH = True
                
            order.exchange = qualified_contract.exchange
            
            # Place the order
            trade = self.ib.placeOrder(qualified_contract, order)
            
            # Wait briefly for order status
            await asyncio.sleep(1)
            avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
            
            # Send notification
            message = (
                f"🔔 <b>Buy Order Placed</b>\n\n"
                f"Symbol: {qualified_contract.localSymbol}\n"
                f"Action: BUY\n"
                f"Quantity: {quantity}\n"
                f"Order Type: MARKET\n"
                f"Fill Price: ${avg_price:.2f}"
            )
            await self.send_telegram_message(message)
            
            # Resync data after order placement
            await asyncio.sleep(0.5)
            await self.resync_data()
            
            return {"status": "success", "order_id": trade.order.orderId}
            
        except Exception as e:
            print(f"Error placing buy order: {e}")
            return {"status": "error", "message": str(e)}

    async def place_sell_order(self, position_id: int, quantity: int):
        """Place a sell order for an existing position"""
        try:
            # Find the position in current positions
            positions = await self.ib.reqPositionsAsync()
            target_position = None
            
            for pos in positions:
                if pos.contract.conId == position_id:
                    target_position = pos
                    break
                    
            if not target_position:
                return {"status": "error", "message": "Position not found"}
            
            # Verify quantity doesn't exceed current position
            if abs(quantity) > abs(target_position.position):
                return {"status": "error", "message": "Sell quantity cannot exceed current position size"}
            
            # Qualify the contract
            qualified_contracts = await self.ib.qualifyContractsAsync(target_position.contract)
            if not qualified_contracts:
                return {"status": "error", "message": "Could not qualify contract"}
            
            qualified_contract = qualified_contracts[0]
            
            # Place market order
            order = MarketOrder('SELL', quantity, account=self.account)
            
            # Only set outsideRTH if outside regular trading hours
            if not self.is_regular_trading_hours():
                order.outsideRTH = True
                
            order.exchange = qualified_contract.exchange
            
            # Place the order
            trade = self.ib.placeOrder(qualified_contract, order)
            
            # Wait briefly for order status
            await asyncio.sleep(1)
            avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
            
            # Send notification
            message = (
                f"🔔 <b>Sell Order Placed</b>\n\n"
                f"Symbol: {qualified_contract.localSymbol}\n"
                f"Action: SELL\n"
                f"Quantity: {quantity}\n"
                f"Order Type: MARKET\n"
                f"Fill Price: ${avg_price:.2f}"
            )
            await self.send_telegram_message(message)
            
            # Resync data after order placement
            await asyncio.sleep(0.5)
            await self.resync_data()
            
            return {"status": "success", "order_id": trade.order.orderId}
            
        except Exception as e:
            print(f"Error placing sell order: {e}")
            return {"status": "error", "message": str(e)}

    async def cancel_order(self, order_id):
        try:
            trades = self.ib.trades()
            for trade in trades:
                if trade.order.orderId == int(order_id):
                    self.ib.cancelOrder(trade.order)
                    await asyncio.sleep(0.5)  # Give some time for the cancel to process
                    await self.resync_data()  # Resync all data
                    return {"status": "success", "message": "Order cancelled"}
            return {"status": "error", "message": "Order not found"}
        except Exception as e:
            print(f"Error canceling order: {e}")
            return {"status": "error", "message": str(e)}

    async def resync_data(self):
        """Resync all data from IB"""
        try:
            print("Resyncing data from IB...")
            
            # Resync positions
            positions = self.ib.positions(account=self.account)
            self.positions.clear()  # Clear existing positions
            for position in positions:
                await self.position_monitor(position)
                
            # Resync orders
            trades = self.ib.trades()
            self.open_orders.clear()  # Clear existing orders
            for trade in trades:
                self.order_status_monitor(trade)
                
            # Resync portfolio data
            portfolio = self.ib.portfolio()
            for item in portfolio:
                self.portfolio_monitor(item)
                
            print("Data resync complete")
            
        except Exception as e:
            print(f"Error during data resync: {e}")

    def __del__(self):
        """Cleanup resources on object destruction"""
        try:
            if hasattr(self, 'ib') and self.ib.isConnected():
                # Create a new event loop for cleanup if needed
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Run disconnect asynchronously
                if loop.is_running():
                    loop.create_task(self.disconnect())
                else:
                    loop.run_until_complete(self.disconnect())
        except Exception as e:
            print(f"Error during cleanup: {e}")

    async def send_telegram_message(self, message):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }) as response:
                    if response.status != 200:
                        print(f"Failed to send Telegram message: {await response.text()}")
        except Exception as e:
            print(f"Error sending Telegram message: {e}")

    async def quick_trade_spy(self, signal):
        """Handle quick trade panel signals for both SPY options and MES futures"""
        try:
            if not self.settings.trading_enabled:
                return {"status": "error", "message": "Trading is disabled"}
            
            # Check if it's past the configured square-off time
            est = pytz.timezone('US/Eastern')
            current_time = datetime.now(est).time()
            
            try:
                hour, minute = map(int, self.settings.auto_square_off_time.split(':'))
                cutoff_time = time(hour, minute)
            except (ValueError, AttributeError):
                cutoff_time = time(15, 55)  # Fallback to default
            
            if current_time >= cutoff_time:
                return {"status": "error", "message": "Trading hours ended"}
            
            action = signal['action']
            instrument = signal.get('instrument', 'SPY')
            
            # Handle MES futures
            if instrument == 'MES':
                contract = await self.get_mes_contract()
                if not contract:
                    return {"status": "error", "message": "Could not qualify MES contract"}
                
                # For MES futures, "Buy MES" should be BUY, "Short MES" should be SELL
                order_action = 'BUY' if 'Buy' in action else 'SELL'
                quantity = signal.get('quantity', self.settings.mes_quantity)
                
                print(f"MES Order - Action: {order_action}, Quantity: {quantity}")
                
                # Place the order
                order = MarketOrder(
                    action=order_action,
                    totalQuantity=quantity,
                    account=self.account
                )
                
                # Only set outsideRTH if outside regular trading hours
                if not self.is_regular_trading_hours():
                    order.outsideRTH = True
                    
                order.exchange = 'CME'                
                print(f"Order: {order}")
                trade = self.ib.placeOrder(contract, order)
                print(f"Trade: {trade}")
                
                # Wait briefly for order status
                await asyncio.sleep(1)
                avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
                
                # Send notification
                message = (
                    f"🔔 <b>Quick Trade Executed</b>\n\n"
                    f"Symbol: MES\n"
                    f"Action: {order_action}\n"
                    f"Quantity: {quantity}\n"
                    f"Fill Price: ${avg_price:.2f}"
                )
                await self.send_telegram_message(message)
                
                await asyncio.sleep(0.5)
                await self.resync_data()
                return {"status": "success", "order_id": trade.order.orderId}
            
            # Handle SPY options
            else:
                # Get base strike price
                base_strike = round(self.current_spy_price)
                
                # Determine right and strike selection based on action
                if 'Buy Call' in action:
                    right = 'C'
                    selection = self.settings.call_strike_selection
                    if selection == "ATM":
                        strike = base_strike
                    elif selection == "OTM-1":
                        strike = base_strike + 1
                    elif selection == "OTM-2":
                        strike = base_strike + 2
                    elif selection == "OTM-3":
                        strike = base_strike + 3
                    else:
                        strike = base_strike
                elif 'Buy Put' in action:
                    right = 'P'
                    selection = self.settings.put_strike_selection
                    if selection == "ATM":
                        strike = base_strike
                    elif selection == "OTM-1":
                        strike = base_strike - 1
                    elif selection == "OTM-2":
                        strike = base_strike - 2
                    elif selection == "OTM-3":
                        strike = base_strike - 3
                    else:
                        strike = base_strike

                # Get option chain details
                contract = Stock('SPY', 'SMART', 'USD')
                qualified_contracts = await self.ib.qualifyContractsAsync(contract)
                if not qualified_contracts:
                    return {"status": "error", "message": "Could not qualify SPY contract"}
                
                conId = qualified_contracts[0].conId
                symbol = qualified_contracts[0].symbol
                
                # Get option chain
                chains = await self.ib.reqSecDefOptParamsAsync(
                    underlyingSymbol=symbol,
                    futFopExchange='',
                    underlyingSecType='STK',
                    underlyingConId=conId
                )
                
                if not chains:
                    return {"status": "error", "message": "No option chains found for SPY"}
                
                # Sort expirations and get the appropriate one
                chain = chains[0]
                expirations = sorted(chain.expirations)
                
                if not expirations:
                    return {"status": "error", "message": "No expirations found"}
                
                # Select expiration based on dte setting
                expiry_index = min(self.settings.dte, len(expirations) - 1)
                expiry = expirations[expiry_index]
                
                print(f"Creating SPY option: Strike={strike}, Right={right}, Expiry={expiry}")
                
                # Create the option contract
                contract = Option(
                    symbol='SPY',
                    lastTradeDateOrContractMonth=expiry,
                    strike=strike,
                    right=right,
                    exchange='SMART',
                    currency='USD',
                    multiplier='100'
                )
                
                # Get contract details
                details = await self.ib.reqContractDetailsAsync(contract)
                if not details:
                    return {"status": "error", "message": "Could not find matching option contract"}
                
                contract = details[0].contract
                print(f"Using contract: {contract}")
                
                # Place the order
                quantity = signal.get('quantity', self.settings.spy_quantity)
                order = MarketOrder(
                    action='BUY',
                    totalQuantity=quantity,
                    account=self.account
                )
                
                # Only set outsideRTH if outside regular trading hours
                if not self.is_regular_trading_hours():
                    order.outsideRTH = True
                    
                order.exchange = 'SMART'                
                print(f"Order: {order}")
                trade = self.ib.placeOrder(contract, order)
                print(f"Trade: {trade}")
                
                # Wait briefly for order status
                await asyncio.sleep(1)
                avg_price = trade.orderStatus.avgFillPrice if hasattr(trade.orderStatus, 'avgFillPrice') else 0.0
                
                # Send notification
                message = (
                    f"🔔 <b>Quick Trade Executed</b>\n\n"
                    f"Symbol: {contract.localSymbol}\n"
                    f"Action: {action}\n"
                    f"Quantity: {quantity}\n"
                    f"Strike: {strike}\n"
                    f"Expiry: {expiry}\n"
                    f"Fill Price: ${avg_price:.2f}"
                )
                await self.send_telegram_message(message)
                
                await asyncio.sleep(0.5)
                await self.resync_data()
                return {"status": "success", "order_id": trade.order.orderId}
            
        except Exception as e:
            print(f"Error in quick trade: {e}")
            return {"status": "error", "message": str(e)}


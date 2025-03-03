import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:80"

def send_signal(signal):
    try:
        print(f"\nSending signal: {signal}")
        response = requests.post(f"{BASE_URL}/api/signal", json=signal)
        response.raise_for_status()
        result = response.json()
        print(f"Response: {result}")
        return result
    except Exception as e:
        print(f"Error sending signal: {e}")
        return None

def print_menu():
    print("\n=== Trading Scenarios ===")
    print("1. Buy MES1!")
    print("2. Exit MES1! Long (Buy Exit)")
    print("3. Sell MES1!")
    print("4. Exit MES1! Short (Sell Exit)")
    print("5. Buy SPY Option")
    print("6. Exit SPY Long (Buy Exit)")
    print("7. Sell SPY Option")
    print("8. Exit SPY Short (Sell Exit)")
    print("0. Exit Program")

def execute_scenario(choice):
    scenarios = {
        1: {"symbol": "MES1!", "action": "Buy"},
        2: {"symbol": "MES1!", "action": "Buy Exit"},
        3: {"symbol": "MES1!", "action": "Sell"},
        4: {"symbol": "MES1!", "action": "Sell Exit"},
        5: {"symbol": "SPY", "action": "Buy"},
        6: {"symbol": "SPY", "action": "Buy Exit"},
        7: {"symbol": "SPY", "action": "Sell"},
        8: {"symbol": "SPY", "action": "Sell Exit"}
    }

    if choice not in scenarios:
        print("Invalid choice!")
        return

    signal = scenarios[choice]
    print(f"\nExecuting: {signal['action']} {signal['symbol']}")
    result = send_signal(signal)
    
    if result and result.get("status") == "success":
        print(f"✅ Order sent successfully")
        print(f"Order ID: {result.get('order_id')}")
    else:
        print("❌ Failed to send order")

    # Wait a bit to let the order process
    print("\nWaiting 3 seconds for order to process...")
    time.sleep(3)

def main():
    print("\n=== Trading Test Program ===")
    print("Make sure IB TWS is running and connected!")
    
    while True:
        print_menu()
        try:
            choice = int(input("\nEnter your choice (0-8): "))
            if choice == 0:
                print("\nExiting program...")
                break
            execute_scenario(choice)
        except ValueError:
            print("Please enter a valid number!")
        except KeyboardInterrupt:
            print("\nExiting program...")
            break
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
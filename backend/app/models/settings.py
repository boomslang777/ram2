from pydantic import BaseModel
from typing import Optional

class Settings(BaseModel):
    trading_enabled: bool = True
    spy_quantity: int = 1
    mes_quantity: int = 1
    dte: int = 0  # 0 for closest expiry, 1 for next expiry
    otm_strikes: int = 3  # Updated to 3 to include OTM-3
    call_strike_selection: str = "ATM"  # Can be "ATM", "OTM-1", "OTM-2", "OTM-3"
    put_strike_selection: str = "ATM"   # Can be "ATM", "OTM-1", "OTM-2", "OTM-3"
    auto_square_off_enabled: bool = True
    auto_square_off_time: str = "15:55"  # Default time in HH:MM format
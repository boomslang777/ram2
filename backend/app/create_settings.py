import json
from models.settings import Settings

default_settings = Settings(
    trading_enabled=True,
    quantity=1,
    dte=0,
    otm_strikes=2,
    default_strike=None
).dict()

with open("settings.json", "w") as f:
    json.dump(default_settings, f) 
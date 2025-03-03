from pathlib import Path
import json
from models.settings import Settings

def init_setup():
    base_dir = Path(__file__).resolve().parent
    settings_path = base_dir / "settings.json"

    if not settings_path.exists():
        default_settings = Settings(
            trading_enabled=True,
            quantity=1,
            dte=0,
            otm_strikes=2,
            default_strike=0.0
        )
        with open(settings_path, "w") as f:
            json.dump(default_settings.dict(), f)
        print(f"Created settings file at {settings_path}")

if __name__ == "__main__":
    init_setup() 
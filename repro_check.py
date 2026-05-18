import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.core.settings import get_settings
    from app.services.health import get_readiness_status
    from app.core.db import init_db
    
    settings = get_settings()
    print(f"Settings: ENVIRONMENT={settings.environment}, DATABASE_URL={settings.database_url}, STORAGE_PROVIDER={settings.storage_provider}, DATA_DIR={settings.data_dir}")
    
    print("Attempting to initialize database...")
    try:
        init_db()
        print("Database initialization successful.")
    except Exception as e:
        print(f"Database initialization failed: {e}")

    print("Checking readiness status...")
    status = get_readiness_status()
    print(f"Readiness Status: {status['status']}")
    print(f"Checks: {status['checks']}")
    
except Exception as e:
    print(f"Error during check: {e}")
    import traceback
    traceback.print_exc()

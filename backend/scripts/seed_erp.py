"""python scripts/seed_erp.py  -> creates data/erp.sqlite from data/erp_seed.json"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.mock_erp.store import init_db

init_db(Path(settings.data_dir) / "erp_seed.json", reset=True)
print("ERP db ready:", settings.erp_db)

from pathlib import Path
import sys

# Permite ejecutar este archivo directamente con: python scripts/<archivo>.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import ensure_indexes
from src.ml.model import train_all, predict_all
if __name__ == "__main__":
    ensure_indexes()
    for x in train_all():
        print(x.get("coin_id"),x.get("status"))
    for x in predict_all():
        print(x.get("coin_id"),x.get("status"))

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import database
from utils import database_path


if __name__ == "__main__":
    database.init_db()
    print(f"Initialized database at {database_path()}")

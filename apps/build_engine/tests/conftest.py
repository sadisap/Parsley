from __future__ import annotations

import sys
from pathlib import Path

BUILD_ENGINE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = BUILD_ENGINE_ROOT / 'src'
if str(BUILD_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ENGINE_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

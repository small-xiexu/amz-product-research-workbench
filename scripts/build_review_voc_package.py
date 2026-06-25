#!/usr/bin/env python3
"""CLI thin wrapper for P5 review VOC package — imports, normalizes, and structures review plugin exports.
P5 专用入口，只输出 review_voc_package.json，不写 md/xlsx 等渲染文件。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_review_voc_package import main


if __name__ == "__main__":
    raise SystemExit(main())

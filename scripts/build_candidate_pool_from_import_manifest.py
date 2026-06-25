#!/usr/bin/env python3
"""LEGACY FALLBACK — MCP 主路径已替代此入口，仅在 MCP 不可用时使用。

CLI 薄壳：业务逻辑见 packages/research_core/pipeline/build_candidate_pool_from_import_manifest.py。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import main

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""CLI 薄壳：业务逻辑见 packages/research_core/pipeline/build_research_package_from_candidate.py。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.research_core.pipeline.build_research_package_from_candidate import main

if __name__ == "__main__":
    main()

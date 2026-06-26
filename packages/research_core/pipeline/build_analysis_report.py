#!/usr/bin/env python3
"""Compatibility wrapper — delegates to build_report_seed + build_report_xlsx.

Deprecated: use the individual scripts directly.
  Stage 11: python3 -m packages.research_core.pipeline.build_report_seed <run_dir>
  Stage 12: python3 -m packages.research_core.pipeline.build_report_xlsx <run_dir>
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    import warnings
    warnings.warn(
        "build_analysis_report is deprecated. "
        "Use build_report_seed then build_report_xlsx.",
        DeprecationWarning,
        stacklevel=2,
    )
    from packages.research_core.pipeline.build_report_seed import main as seed_main
    from packages.research_core.pipeline.build_report_xlsx import main as xlsx_main
    rc = seed_main(argv)
    if rc != 0:
        return rc
    # seed returns 0 when report_data.json is missing (handoff mode)
    # Only run xlsx if report_data.json exists
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("run_dir", type=str)
    args_ns = parser.parse_args(argv)
    from pathlib import Path
    report_data = Path(args_ns.run_dir).expanduser().resolve() / "analysis" / "report_data.json"
    if report_data.exists():
        return xlsx_main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

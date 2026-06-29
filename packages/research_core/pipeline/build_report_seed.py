#!/usr/bin/env python3
"""Stage 11: Build report_data.seed.json from evidence packets.

Pure data extraction — no judgment, no AI analysis. All judgment-class fields
are marked ``"__ai_judgment__"`` for Report Generation Agent to fill in Stage 12.

Output: report_data.seed.json + analysis_packet.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from packages.research_core.pipeline.build_analysis_packet import (
    load_packets,
    _extract_product_name,
    build_analysis_packet,
)
from packages.research_core.pipeline.seed_report_data import (
    seed_report_data_from_analysis,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build report_data.seed.json from evidence packets (Stage 11)."
    )
    parser.add_argument(
        "run_dir", type=Path,
        help="Path to run directory (e.g. runs/20260623_加液马桶刷)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    packets = load_packets(run_dir)
    analysis = build_analysis_packet(run_dir, packets)

    # Step 1: Generate seed
    seed = seed_report_data_from_analysis(analysis, packets)
    report_seed_path = analysis_dir / "report_data.seed.json"
    report_seed_path.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote seed {report_seed_path}")

    # Step 2: Write analysis_packet (persisted intermediate for downstream QA)
    analysis_packet_path = analysis_dir / "analysis_packet.json"
    analysis_packet_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote analysis_packet {analysis_packet_path}")

    # Step 3: Validate seed field names against contract
    from packages.research_core.pipeline.constants import REQUIRED_REPORT_DATA_SECTIONS
    from packages.research_core.pipeline.constants import REQUIRED_REPORT_DATA_DECLARATIONS

    seed_keys = set(seed.keys())
    contract_sections = set(REQUIRED_REPORT_DATA_SECTIONS)
    contract_decls = set(REQUIRED_REPORT_DATA_DECLARATIONS)

    missing_sections = contract_sections - seed_keys
    missing_decls = contract_decls - seed_keys

    warnings: list[str] = []
    if missing_sections:
        warnings.append(
            f"[WARN] report_data.seed.json 缺少契约板块: {sorted(missing_sections)}"
        )
    if missing_decls:
        warnings.append(
            f"[WARN] report_data.seed.json 缺少契约声明字段: {sorted(missing_decls)}"
        )

    # Also warn about extra sections not in the contract
    extra = seed_keys - contract_sections - contract_decls - {
        "schema_version", "packet_id", "run_id", "generated_at",
        "snapshot_date", "evidence_sources",
    }
    if extra:
        warnings.append(
            f"[INFO] report_data.seed.json 含契约外字段（Agent 增强后正常）: {sorted(extra)}"
        )

    for w in warnings:
        print(w, file=sys.stderr)

    # Step 4: Indicate handoff
    product_name = _extract_product_name(run_dir)
    report_data_path = analysis_dir / "report_data.json"
    print()
    print(f"Stage 11 complete. Next: Stage 12 — Report Generation Agent")
    print(f"  1. Read {report_seed_path}")
    print(f"  2. Read {analysis_dir / 'integrated_operator_judgment.json'}")
    print(f"  3. Write {report_data_path}")
    print(f"  4. Write {analysis_dir / f'{product_name}_分析报告.html'}")
    print(f"  Then run: python3 -m packages.research_core.pipeline.build_report_xlsx {run_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

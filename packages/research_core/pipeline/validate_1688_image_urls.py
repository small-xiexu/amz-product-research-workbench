"""Validate 1688 candidate image URL reachability without visual review."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def validate_candidates(candidates: list[dict[str, Any]], timeout: float = 10.0, workers: int = 5) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(validate_candidate_image_url, candidate, timeout): index
            for index, candidate in enumerate(candidates)
        }
        results: list[dict[str, Any] | None] = [None] * len(candidates)
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [item or {} for item in results]


def validate_candidate_image_url(candidate: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = primary_image_url(candidate)
    status, detail = check_url(url, timeout)
    result = dict(candidate)
    result["image_url_status"] = status
    result["image_url_checked"] = bool(url)
    result["image_url_check_detail"] = detail
    return result


def primary_image_url(candidate: dict[str, Any]) -> str:
    if candidate.get("main_image_url"):
        return str(candidate.get("main_image_url"))
    for key in ("visual_evidence_image_urls", "product_image_urls", "image_urls"):
        values = candidate.get(key)
        if isinstance(values, list) and values:
            return str(values[0])
    return ""


def check_url(url: str, timeout: float) -> tuple[str, str]:
    if not url:
        return "not_provided", "No image URL provided."
    for method in ("HEAD", "GET"):
        try:
            request = Request(
                url,
                method=method,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                },
            )
            with urlopen(request, timeout=timeout) as response:
                status_code = getattr(response, "status", None) or response.getcode()
                if 200 <= int(status_code) < 400:
                    return "accessible", f"HTTP {status_code} via {method}."
                if int(status_code) in {401, 403, 405, 429}:
                    return "blocked", f"HTTP {status_code} via {method}."
                return "inaccessible", f"HTTP {status_code} via {method}."
        except HTTPError as exc:
            if exc.code == 405 and method == "HEAD":
                continue
            if exc.code in {401, 403, 429}:
                return "blocked", f"HTTP {exc.code} via {method}."
            return "inaccessible", f"HTTP {exc.code} via {method}."
        except (TimeoutError, URLError) as exc:
            if method == "HEAD":
                continue
            return "inaccessible", str(exc)
    return "inaccessible", "URL check failed."


def load_candidates(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("candidates", "valid_supplier_samples", "recommended_candidates"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Unsupported candidates JSON structure: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate 1688 candidate image URL reachability.")
    parser.add_argument("candidates_json", help="Path to supply_chain_candidates JSON.")
    parser.add_argument("output_json", help="Path to write checked candidates JSON.")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    input_path = Path(args.candidates_json).expanduser().resolve()
    output_path = Path(args.output_json).expanduser().resolve()
    candidates = load_candidates(input_path)
    checked = validate_candidates(candidates, timeout=args.timeout, workers=args.workers)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(checked, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {}
    for item in checked:
        status = item.get("image_url_status", "unknown")
        summary[status] = summary.get(status, 0) + 1
    print(json.dumps({"output": str(output_path), "count": len(checked), "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

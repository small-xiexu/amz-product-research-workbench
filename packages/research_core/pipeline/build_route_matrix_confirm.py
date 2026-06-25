"""Compatibility import path for the strict P3 route-matrix confirmation flow."""

from __future__ import annotations

from packages.research_core.pipeline.build_route_matrix_confirmation import (
    build_route_matrix_confirm,
    main,
    run_route_matrix_confirmation,
    write_route_matrix_confirm,
)

__all__ = [
    "build_route_matrix_confirm",
    "main",
    "run_route_matrix_confirmation",
    "write_route_matrix_confirm",
]

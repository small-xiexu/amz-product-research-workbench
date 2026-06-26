"""Pytest configuration: global test fixtures and flags."""

from packages.research_core.pipeline import build_mcp_candidate_pool
from packages.research_core.pipeline import build_route_matrix_confirmation

build_mcp_candidate_pool._ALLOW_GENERATION_FALLBACK = True
build_route_matrix_confirmation._ALLOW_GENERATION_FALLBACK = True

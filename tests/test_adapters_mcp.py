"""Tests for MCP snapshot input path in SellerSpriteAdapter and SorftimeAdapter."""

from __future__ import annotations

import unittest

from packages.research_core.adapters.base_adapter import ADAPTER_REGISTRY
from packages.research_core.adapters.seller_sprite_adapter import SellerSpriteAdapter
from packages.research_core.adapters.sorftime_adapter import SorftimeAdapter


# ── Shared fixtures ───────────────────────────────────────────────

def _ss_snapshot(products=None, concentration=None):
    """Build a minimal sellersprite_mcp snapshot."""
    tool_calls = []
    if products:
        for tool_name, items in products:
            tool_calls.append({
                "call_id": f"call_{tool_name}",
                "tool_name": tool_name,
                "params": {},
                "status": "success",
                "started_at": "2026-06-25T10:00:00Z",
                "finished_at": "2026-06-25T10:00:05Z",
                "normalized_preview": items,
            })
    if concentration:
        for tool_name, items in concentration:
            tool_calls.append({
                "call_id": f"call_{tool_name}",
                "tool_name": tool_name,
                "params": {},
                "status": "success",
                "started_at": "2026-06-25T10:00:00Z",
                "finished_at": "2026-06-25T10:00:05Z",
                "normalized_preview": items,
            })
    return {
        "schema_version": "mcp-snapshot-v1",
        "snapshot_id": "ss_test",
        "stage": "deep_dive",
        "depth": "deep",
        "source_type": "sellersprite_mcp",
        "marketplace": "US",
        "collected_at": "2026-06-25T10:00:00Z",
        "tool_calls": tool_calls,
        "data_gaps": [],
    }


def _sf_snapshot(category=None, keywords=None, products=None, depth="deep"):
    """Build a minimal sorftime_mcp snapshot."""
    tool_calls = []
    if category:
        for tool_name, data in category:
            tool_calls.append({
                "call_id": f"call_{tool_name}",
                "tool_name": tool_name,
                "params": {},
                "status": "success",
                "started_at": "2026-06-25T10:00:00Z",
                "finished_at": "2026-06-25T10:00:05Z",
                "normalized_preview": data,
            })
    if keywords:
        for tool_name, items in keywords:
            tool_calls.append({
                "call_id": f"call_{tool_name}",
                "tool_name": tool_name,
                "params": {},
                "status": "success",
                "started_at": "2026-06-25T10:00:00Z",
                "finished_at": "2026-06-25T10:00:05Z",
                "normalized_preview": items,
            })
    if products:
        for tool_name, items in products:
            tool_calls.append({
                "call_id": f"call_{tool_name}",
                "tool_name": tool_name,
                "params": {},
                "status": "success",
                "started_at": "2026-06-25T10:00:00Z",
                "finished_at": "2026-06-25T10:00:05Z",
                "normalized_preview": items,
            })
    return {
        "schema_version": "mcp-snapshot-v1",
        "snapshot_id": "sf_test",
        "stage": "deep_dive",
        "depth": depth,
        "source_type": "sorftime_mcp",
        "marketplace": "US",
        "collected_at": "2026-06-25T10:00:00Z",
        "tool_calls": tool_calls,
        "data_gaps": [],
    }


# ── SellerSpriteAdapter MCP tests ─────────────────────────────────

class SellerSpriteMCPTests(unittest.TestCase):
    """Task 1: SellerSpriteAdapter.from_mcp_snapshot() 各种场景。"""

    def test_from_mcp_snapshot_normalized_preview(self):
        """snapshot 中 normalized_preview 有数据时能正确提取产品。"""
        snapshot = _ss_snapshot(products=[
            ("product_research", [
                {"asin": "B0TEST001", "title": "Test Product 1", "brand": "BrandA",
                 "price": 19.99, "monthly_units": 500, "rating": 4.3, "rating_count": 120},
                {"asin": "B0TEST002", "title": "Test Product 2", "brand": "BrandB",
                 "price": 29.99, "monthly_units": 300, "rating": 4.1, "rating_count": 80},
            ]),
        ])

        adapter = SellerSpriteAdapter.from_mcp_snapshot(snapshot)
        products = adapter.fetch_products()

        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].asin, "B0TEST001")
        self.assertEqual(products[0].title, "Test Product 1")
        self.assertEqual(products[0].brand, "BrandA")
        self.assertEqual(products[0].price, 19.99)
        self.assertEqual(products[0].monthly_units, 500)
        self.assertEqual(products[0].data_freshness, "2026-06-25T10:00:00Z")

    def test_from_mcp_snapshot_empty_tool_calls(self):
        """tool_calls 为空时返回空产品列表。"""
        snapshot = _ss_snapshot()

        adapter = SellerSpriteAdapter.from_mcp_snapshot(snapshot)
        products = adapter.fetch_products()

        self.assertEqual(products, [])

    def test_from_mcp_snapshot_skips_failed_calls(self):
        """status != success 的 tool_call 被跳过。"""
        snapshot = {
            "schema_version": "mcp-snapshot-v1",
            "snapshot_id": "ss_test",
            "stage": "deep_dive",
            "depth": "deep",
            "source_type": "sellersprite_mcp",
            "marketplace": "US",
            "collected_at": "2026-06-25T10:00:00Z",
            "tool_calls": [
                {
                    "call_id": "call_err",
                    "tool_name": "product_research",
                    "params": {},
                    "status": "error",
                    "started_at": "2026-06-25T10:00:00Z",
                    "finished_at": "2026-06-25T10:00:01Z",
                    "normalized_preview": [{"asin": "B0FAIL001"}],
                },
                {
                    "call_id": "call_ok",
                    "tool_name": "market_research",
                    "params": {},
                    "status": "success",
                    "started_at": "2026-06-25T10:00:01Z",
                    "finished_at": "2026-06-25T10:00:05Z",
                    "normalized_preview": [{"asin": "B0OK001", "title": "OK Product"}],
                },
            ],
            "data_gaps": [],
        }

        adapter = SellerSpriteAdapter.from_mcp_snapshot(snapshot)
        products = adapter.fetch_products()

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].asin, "B0OK001")

    def test_from_mcp_snapshot_concentration_tools(self):
        """集中度工具的数据归入 concentration_records，去重合并。"""
        snapshot = _ss_snapshot(
            products=[
                ("product_research", [
                    {"asin": "B0SHARED", "title": "From Search", "price": 10.0},
                ]),
            ],
            concentration=[
                ("market_product_concentration", [
                    {"asin": "B0SHARED", "title": "From Conc", "price": 10.0},
                    {"asin": "B0CONC01", "title": "Conc Only", "price": 15.0},
                ]),
            ],
        )

        adapter = SellerSpriteAdapter.from_mcp_snapshot(snapshot)
        products = adapter.fetch_products()

        # 去重：B0SHARED 只出现一次，B0CONC01 新增
        self.assertEqual(len(products), 2)
        asins = {p.asin for p in products}
        self.assertIn("B0SHARED", asins)
        self.assertIn("B0CONC01", asins)

    def test_from_mcp_snapshot_wrapped_in_dict(self):
        """normalized_preview 是 dict 包裹时也能提取。"""
        snapshot = _ss_snapshot(products=[
            ("product_research", {
                "products": [
                    {"asin": "B0WRAP01", "title": "Wrapped Product"},
                ],
            }),
        ])

        adapter = SellerSpriteAdapter.from_mcp_snapshot(snapshot)
        products = adapter.fetch_products()

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].asin, "B0WRAP01")

    def test_from_mcp_snapshot_wrong_source_type_raises(self):
        """source_type 不匹配时抛出 ValueError。"""
        snapshot = _ss_snapshot()
        snapshot["source_type"] = "sorftime_mcp"

        with self.assertRaises(ValueError) as ctx:
            SellerSpriteAdapter.from_mcp_snapshot(snapshot)
        self.assertIn("sellersprite_mcp", str(ctx.exception))

    def test_legacy_init_still_works(self):
        """旧 manifest 路径（中文列名）仍然正常工作。"""
        adapter = SellerSpriteAdapter(
            search_records=[
                {"ASIN": "B0LEGACY1", "商品标题": "旧路径商品", "品牌": "老牌子",
                 "价格($)": "25.99", "月销量": "200", "评分": "4.5", "评分数": "60"},
            ],
            data_freshness="2026-06-01",
        )

        products = adapter.fetch_products()

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].asin, "B0LEGACY1")
        self.assertEqual(products[0].title, "旧路径商品")
        self.assertEqual(products[0].brand, "老牌子")
        self.assertEqual(products[0].price, 25.99)
        self.assertEqual(products[0].monthly_units, 200)


# ── SorftimeAdapter MCP tests ─────────────────────────────────────

class SorftimeMCPTests(unittest.TestCase):
    """Task 2: SorftimeAdapter.from_mcp_snapshot() + 字段增强。"""

    def test_from_mcp_snapshot_normalized_preview(self):
        """snapshot 中能正确提取 category/keyword/product 三类数据。"""
        snapshot = _sf_snapshot(
            category=[
                ("category_trend", {
                    "category_name": "Kitchen Tools",
                    "category_id": "12345",
                    "trend_direction": "增长",
                }),
            ],
            keywords=[
                ("keyword_detail", [
                    {"keyword": "garlic press", "monthly_search_volume": 5000,
                     "cpc": 1.25, "trend_direction": "均衡"},
                ]),
            ],
            products=[
                ("product_search", [
                    {"asin": "B0SF0001", "title": "SF Product", "brand": "SFBrand",
                     "price": 15.99, "monthly_units": 800, "rating": 4.2,
                     "rating_count": 200, "listing_date": "2025-03-15",
                     "seller": "SFSeller", "seller_location": "CN"},
                ]),
            ],
        )

        adapter = SorftimeAdapter.from_mcp_snapshot(snapshot)

        products = adapter.fetch_products()
        self.assertEqual(len(products), 1)
        p = products[0]
        self.assertEqual(p.asin, "B0SF0001")
        self.assertEqual(p.listing_date, "2025-03-15")
        self.assertEqual(p.seller, "SFSeller")
        self.assertEqual(p.seller_location, "CN")

        keywords = adapter.fetch_keywords()
        self.assertEqual(len(keywords), 1)
        self.assertEqual(keywords[0].keyword, "garlic press")
        self.assertEqual(keywords[0].monthly_search_volume, 5000)

        cat = adapter.fetch_category()
        self.assertIsNotNone(cat)
        self.assertEqual(cat.category_name, "Kitchen Tools")

    def test_from_mcp_snapshot_quick_depth(self):
        """depth=quick 时仍能正确提取数据。"""
        snapshot = _sf_snapshot(
            depth="quick",
            keywords=[
                ("keyword_list", [
                    {"keyword": "quick test", "monthly_search_volume": 100},
                ]),
            ],
        )

        adapter = SorftimeAdapter.from_mcp_snapshot(snapshot)
        keywords = adapter.fetch_keywords()

        self.assertEqual(len(keywords), 1)
        self.assertEqual(keywords[0].keyword, "quick test")

    def test_from_mcp_snapshot_deep_depth(self):
        """depth=deep 时能提取更多工具的数据。"""
        snapshot = _sf_snapshot(
            depth="deep",
            keywords=[
                ("keyword_detail", [
                    {"keyword": "deep kw 1", "monthly_search_volume": 3000},
                ]),
                ("keyword_extends", [
                    {"keyword": "deep kw 2", "monthly_search_volume": 1500},
                ]),
            ],
            products=[
                ("product_detail", [
                    {"asin": "B0DEEP01", "title": "Deep Product"},
                ]),
            ],
        )

        adapter = SorftimeAdapter.from_mcp_snapshot(snapshot)
        keywords = adapter.fetch_keywords()
        products = adapter.fetch_products()

        self.assertEqual(len(keywords), 2)
        self.assertEqual(len(products), 1)

    def test_from_mcp_snapshot_skips_failed_and_empty(self):
        """失败的调用和无 normalized_preview 的调用被跳过。"""
        snapshot = {
            "schema_version": "mcp-snapshot-v1",
            "snapshot_id": "sf_test",
            "stage": "deep_dive",
            "depth": "deep",
            "source_type": "sorftime_mcp",
            "marketplace": "US",
            "collected_at": "2026-06-25T10:00:00Z",
            "tool_calls": [
                {
                    "call_id": "call_empty",
                    "tool_name": "keyword_detail",
                    "params": {},
                    "status": "empty",
                    "started_at": "2026-06-25T10:00:00Z",
                    "finished_at": "2026-06-25T10:00:01Z",
                    "normalized_preview": [],
                },
                {
                    "call_id": "call_no_preview",
                    "tool_name": "product_search",
                    "params": {},
                    "status": "success",
                    "started_at": "2026-06-25T10:00:01Z",
                    "finished_at": "2026-06-25T10:00:02Z",
                },
                {
                    "call_id": "call_ok",
                    "tool_name": "keyword_list",
                    "params": {},
                    "status": "success",
                    "started_at": "2026-06-25T10:00:02Z",
                    "finished_at": "2026-06-25T10:00:05Z",
                    "normalized_preview": [
                        {"keyword": "only good one", "monthly_search_volume": 999},
                    ],
                },
            ],
            "data_gaps": [],
        }

        adapter = SorftimeAdapter.from_mcp_snapshot(snapshot)
        keywords = adapter.fetch_keywords()
        products = adapter.fetch_products()
        cat = adapter.fetch_category()

        self.assertEqual(len(keywords), 1)
        self.assertEqual(keywords[0].keyword, "only good one")
        self.assertEqual(products, [])
        self.assertIsNone(cat)

    def test_from_mcp_snapshot_wrong_source_type_raises(self):
        """source_type 不匹配时抛出 ValueError。"""
        snapshot = _sf_snapshot()
        snapshot["source_type"] = "sellersprite_mcp"

        with self.assertRaises(ValueError) as ctx:
            SorftimeAdapter.from_mcp_snapshot(snapshot)
        self.assertIn("sorftime_mcp", str(ctx.exception))

    def test_legacy_init_still_works(self):
        """旧 manifest 路径（扁平 dict）仍然正常工作。"""
        adapter = SorftimeAdapter({
            "fetched_at": "2026-06-01T10:00:00Z",
            "category_trend": {
                "name": "Test Category",
                "trend_direction": "均衡",
            },
            "keyword_data": [
                {"keyword": "legacy kw", "monthly_search_volume": 2000},
            ],
            "product_list": [
                {"asin": "B0LEGACY", "title": "Legacy Product", "price": 9.99,
                 "monthly_units": 100, "rating": 4.0, "rating_count": 50},
            ],
        })

        products = adapter.fetch_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].asin, "B0LEGACY")

        keywords = adapter.fetch_keywords()
        self.assertEqual(len(keywords), 1)
        self.assertEqual(keywords[0].keyword, "legacy kw")

        cat = adapter.fetch_category()
        self.assertIsNotNone(cat)
        self.assertEqual(cat.category_name, "Test Category")

    def test_enhanced_fields_listing_date_seller_location(self):
        """Sorftime 产品现在映射 listing_date / seller / seller_location。"""
        adapter = SorftimeAdapter({
            "fetched_at": "2026-06-25T10:00:00Z",
            "product_list": [
                {"asin": "B0ENHANCED", "title": "Enhanced",
                 "listing_date": "2024-08-01",
                 "seller": "TopSeller", "seller_location": "US"},
            ],
        })

        products = adapter.fetch_products()
        self.assertEqual(len(products), 1)
        p = products[0]
        self.assertEqual(p.listing_date, "2024-08-01")
        self.assertEqual(p.seller, "TopSeller")
        self.assertEqual(p.seller_location, "US")


# ── Registry tests ────────────────────────────────────────────────

class AdapterRegistryTests(unittest.TestCase):
    """Task 3: ADAPTER_REGISTRY 包含两个适配器。"""

    def test_registry_has_both_adapters(self):
        self.assertIn("seller_sprite", ADAPTER_REGISTRY)
        self.assertIn("sorftime", ADAPTER_REGISTRY)
        self.assertEqual(ADAPTER_REGISTRY["seller_sprite"], SellerSpriteAdapter)
        self.assertEqual(ADAPTER_REGISTRY["sorftime"], SorftimeAdapter)

    def test_base_adapter_from_mcp_snapshot_raises(self):
        """基类 from_mcp_snapshot 默认抛出 NotImplementedError。"""
        from packages.research_core.adapters.base_adapter import BaseDataAdapter

        with self.assertRaises(NotImplementedError):
            BaseDataAdapter.from_mcp_snapshot({})

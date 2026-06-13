"""市场结构计算包（按打标/质量/分布交叉/机会判断拆分）。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from packages.research_core.rules.market_structure.shared import *  # noqa: F401,F403
from packages.research_core.rules.market_structure.tagging import *  # noqa: F401,F403
from packages.research_core.rules.market_structure.quality import *  # noqa: F401,F403
from packages.research_core.rules.market_structure.opportunity import *  # noqa: F401,F403
from packages.research_core.rules.market_structure.distribution import *  # noqa: F401,F403
from packages.research_core.rules.market_structure.shared import (
    tag_value,
    avg,
    round_number,
    to_float,
    is_blank,
    safe_rate,
    format_percent,
    compact_text,
    REQUIRED_PRODUCT_FIELDS,
)
from packages.research_core.rules.market_structure.tagging import (
    tag_product,
    attribute_definitions,
    price_band,
    review_band,
    rating_band,
    listing_age_band,
    monthly_units_band,
    variant_band,
    lqs_band,
    yes_no_tag,
    product_route,
    feature_tags,
    tag_confidence,
    tag_notes,
)
from packages.research_core.rules.market_structure.quality import (
    build_data_quality,
    abnormal_items,
    quality_score,
    quality_level,
)
from packages.research_core.rules.market_structure.opportunity import (
    opportunity_clues,
    opportunity_type,
    build_opportunity_judgments,
    opportunity_judgment_summary,
    next_check_for_opportunity,
    pending_label_items,
)
from packages.research_core.rules.market_structure.distribution import (
    build_attribute_distributions,
    distribution_for,
    build_cross_analysis,
    cross_dimension,
    build_summary,
    bucket_value,
    distribution_summary,
    cross_summary,
    cell_interpretation,
)

__all__ = [
    'avg',
    'round_number',
    'to_float',
    'is_blank',
    'safe_rate',
    'format_percent',
    'compact_text',
    'tag_value',
    'tag_product',
    'attribute_definitions',
    'yes_no_tag',
    'product_route',
    'feature_tags',
    'tag_confidence',
    'tag_notes',
    'price_band',
    'review_band',
    'rating_band',
    'listing_age_band',
    'monthly_units_band',
    'variant_band',
    'lqs_band',
    'build_data_quality',
    'abnormal_items',
    'quality_score',
    'quality_level',
    'opportunity_clues',
    'opportunity_type',
    'build_opportunity_judgments',
    'opportunity_judgment_summary',
    'next_check_for_opportunity',
    'pending_label_items',
    'build_attribute_distributions',
    'distribution_for',
    'build_cross_analysis',
    'cross_dimension',
    'build_summary',
    'bucket_value',
    'distribution_summary',
    'cross_summary',
    'cell_interpretation',
    'build_market_structure_analysis',
]


def build_market_structure_analysis(products: list[dict[str, Any]], expected_count: int = 100) -> dict[str, Any]:
    """Build conservative quality checks, tags, distributions, and cross-analysis."""
    tagged_products = [tag_product(product) for product in products]
    quality = build_data_quality(tagged_products, expected_count)
    distributions = build_attribute_distributions(tagged_products)
    cross_analysis = build_cross_analysis(tagged_products)
    opportunity_judgments = build_opportunity_judgments(cross_analysis)
    pending_tags = pending_label_items(tagged_products)
    return {
        "summary": build_summary(quality, distributions, cross_analysis, opportunity_judgments),
        "data_quality": quality,
        "attribute_definitions": attribute_definitions(),
        "attribute_distributions": distributions,
        "cross_analysis": cross_analysis,
        "opportunity_judgments": opportunity_judgments,
        "pending_label_items": pending_tags,
        "tagged_products": tagged_products,
    }

"""后端配置：Provider 工厂、模型选择、密钥状态脱敏。

API key 可以来自网页保存的本地运行时配置，也可以回退到环境变量。
完整密钥只在后端使用，绝不下发前端。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from server.llm.base import LLMProvider


# 选品分析师系统提示（MVP 精简版，后续可从 skills/ 加载完整规范）
SYSTEM_PROMPT = """你是资深亚马逊选品分析师，带运营做交互式选品。核心原则：

1. 先听运营说自然语言意图，自动判断本轮更接近「无方向探索」还是「指定方向深挖」，不要要求运营先手动选模式。
   如果会话当前还是 pending，请先调用 `set_research_mode` 把模式和意图写回会话，再继续后续步骤。
2. 两种路径都可以继续引导卖家精灵导出：
   - 无方向探索：先引导运营导出「选市场 200 条」找 3-5 个候选方向，再收窄。
   - 指定方向深挖：先给 2-3 个主关键词 + 1 个备选词，引导导出搜索结果/市场分析/关键词反查。
3. 你拿不到卖家精灵数据，必须明确告诉运营导出哪些表，等其上传后再用工具盘点。
4. 工具职责：inspect_manual_exports 盘点上传文件，生成 manifest。
5. 关键节点（选主线、定 VOC ASIN 批次、补利润/合规、最终结论）必须暂停让运营决策。
6. 区分事实、推断、风险、下一步；利润或合规未回填时只能给 Wait，禁止强 Go。
7. 用简体中文，简洁、可执行；如果信息不足，先问最少但关键的问题。
"""


AVAILABLE_PROVIDERS = ["anthropic", "openai"]
AVAILABLE_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-20241022"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
}

PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass
class ProviderConfig:
    provider: str  # "anthropic" | "openai"
    model: str
    anthropic_base_url: str = ""
    openai_base_url: str = ""
    api_keys: dict[str, str] = field(default_factory=dict)
    sorftime_mcp_url: str = ""
    sorftime_api_key: str = ""


def default_provider_config() -> ProviderConfig:
    provider = _normalize_provider(os.environ.get("LLM_PROVIDER", "anthropic"))
    model = _clean(os.environ.get("LLM_MODEL")) or default_model(provider)
    sorftime_mcp_url, _ = _split_sorftime_mcp_url(_clean(os.environ.get("SORFTIME_MCP_URL")) or "https://mcp.sorftime.com")
    return ProviderConfig(
        provider=provider,
        model=model,
        anthropic_base_url=_clean(os.environ.get("ANTHROPIC_BASE_URL")),
        openai_base_url=_clean(os.environ.get("OPENAI_BASE_URL")),
        sorftime_mcp_url=sorftime_mcp_url,
    )


def load_provider_config(path: Path) -> ProviderConfig:
    config = default_provider_config()
    if not path.exists():
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config

    provider = _normalize_provider(data.get("provider", config.provider))
    api_keys = {
        key: value
        for key, value in {
            "anthropic": _clean((data.get("api_keys") or {}).get("anthropic")),
            "openai": _clean((data.get("api_keys") or {}).get("openai")),
        }.items()
        if value
    }
    sorftime_mcp_url, sorftime_url_key = _split_sorftime_mcp_url(_clean(data.get("sorftime_mcp_url")) or config.sorftime_mcp_url)
    return ProviderConfig(
        provider=provider,
        model=_clean(data.get("model")) or default_model(provider),
        anthropic_base_url=_clean(data.get("anthropic_base_url")) or config.anthropic_base_url,
        openai_base_url=_clean(data.get("openai_base_url")) or config.openai_base_url,
        api_keys=api_keys,
        sorftime_mcp_url=sorftime_mcp_url,
        sorftime_api_key=_clean(data.get("sorftime_api_key")) or sorftime_url_key,
    )


def save_provider_config(path: Path, config: ProviderConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": config.provider,
        "model": config.model,
        "anthropic_base_url": config.anthropic_base_url,
        "openai_base_url": config.openai_base_url,
        "api_keys": {key: value for key, value in config.api_keys.items() if value},
        "sorftime_mcp_url": config.sorftime_mcp_url,
        "sorftime_api_key": config.sorftime_api_key,
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    tmp_path.replace(path)


def merge_provider_config(current: ProviderConfig, update: dict[str, Any]) -> ProviderConfig:
    provider = _normalize_provider(update.get("provider", current.provider))
    api_keys = dict(current.api_keys)

    _update_secret(api_keys, "anthropic", update.get("anthropic_api_key"), bool(update.get("clear_anthropic_key")))
    _update_secret(api_keys, "openai", update.get("openai_api_key"), bool(update.get("clear_openai_key")))

    sorftime_api_key = current.sorftime_api_key
    sorftime_mcp_url = current.sorftime_mcp_url
    sorftime_url_key = ""
    if "sorftime_mcp_url" in update:
        sorftime_mcp_url, sorftime_url_key = _split_sorftime_mcp_url(update.get("sorftime_mcp_url"))
    if update.get("clear_sorftime_key"):
        sorftime_api_key = ""
    elif _clean(update.get("sorftime_api_key")):
        sorftime_api_key = _clean(update.get("sorftime_api_key"))
    elif sorftime_url_key:
        sorftime_api_key = sorftime_url_key

    model = _clean(update.get("model")) or current.model or default_model(provider)
    return ProviderConfig(
        provider=provider,
        model=model,
        anthropic_base_url=_clean(update.get("anthropic_base_url")) if "anthropic_base_url" in update else current.anthropic_base_url,
        openai_base_url=_clean(update.get("openai_base_url")) if "openai_base_url" in update else current.openai_base_url,
        api_keys=api_keys,
        sorftime_mcp_url=sorftime_mcp_url,
        sorftime_api_key=sorftime_api_key,
    )


def public_config(config: ProviderConfig) -> dict[str, Any]:
    anthropic_status = secret_status(config, "anthropic")
    openai_status = secret_status(config, "openai")
    sorftime_status = sorftime_secret_status(config)
    return {
        "provider": config.provider,
        "model": config.model,
        "anthropic_base_url": config.anthropic_base_url,
        "openai_base_url": config.openai_base_url,
        "sorftime_mcp_url": config.sorftime_mcp_url,
        "anthropic_key_set": anthropic_status["set"],
        "openai_key_set": openai_status["set"],
        "sorftime_key_set": sorftime_status["set"],
        "available_providers": AVAILABLE_PROVIDERS,
        "available_models": AVAILABLE_MODELS,
        "keys": {
            "anthropic": anthropic_status,
            "openai": openai_status,
            "sorftime": sorftime_status,
        },
    }


def build_provider(config: ProviderConfig) -> LLMProvider:
    """根据配置 + 后端密钥构建 Provider。"""

    if config.provider == "anthropic":
        from server.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=resolve_api_key(config, "anthropic"),
            model=config.model,
            base_url=config.anthropic_base_url or os.environ.get("ANTHROPIC_BASE_URL") or None,
        )
    if config.provider == "openai":
        from server.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=resolve_api_key(config, "openai"),
            model=config.model,
            base_url=config.openai_base_url or os.environ.get("OPENAI_BASE_URL") or None,
        )
    raise ValueError(f"未知 Provider：{config.provider}（可选 anthropic / openai）")


def default_model(provider: str) -> str:
    return AVAILABLE_MODELS.get(provider, AVAILABLE_MODELS["anthropic"])[0]


def resolve_api_key(config: ProviderConfig, provider: str) -> str:
    key, _ = _secret_value_and_source(config, provider)
    return key


def secret_status(config: ProviderConfig, provider: str) -> dict[str, Any]:
    key, source = _secret_value_and_source(config, provider)
    return {
        "set": bool(key),
        "source": source,
        "hint": _mask_secret(key) if key else None,
    }


def sorftime_secret_status(config: ProviderConfig) -> dict[str, Any]:
    key, source = _sorftime_secret_value_and_source(config)
    return {
        "set": bool(key),
        "source": source,
        "hint": _mask_secret(key) if key else None,
    }


def resolve_sorftime_api_key(config: ProviderConfig) -> str:
    key, _ = _sorftime_secret_value_and_source(config)
    return key


def _sorftime_secret_value_and_source(config: ProviderConfig) -> tuple[str, str | None]:
    saved = _clean(config.sorftime_api_key)
    if saved:
        return saved, "saved"
    env_key = _clean(os.environ.get("SORFTIME_MCP_KEY")) or _clean(os.environ.get("SORFTIME_API_KEY"))
    if env_key:
        return env_key, "env"
    _, env_url_key = _split_sorftime_mcp_url(os.environ.get("SORFTIME_MCP_URL"))
    if env_url_key:
        return env_url_key, "env"
    return "", None


def _split_sorftime_mcp_url(value: Any) -> tuple[str, str]:
    cleaned = _clean(value)
    if not cleaned:
        return "", ""
    parts = urlsplit(cleaned)
    if not parts.scheme or not parts.netloc:
        return cleaned, ""

    kept_query: list[tuple[str, str]] = []
    extracted_key = ""
    for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() == "key":
            extracted_key = extracted_key or _clean(query_value)
            continue
        kept_query.append((key, query_value))
    sanitized_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept_query), parts.fragment))
    return sanitized_url, extracted_key


def _secret_value_and_source(config: ProviderConfig, provider: str) -> tuple[str, str | None]:
    saved = _clean(config.api_keys.get(provider))
    if saved:
        return saved, "saved"
    env_key = PROVIDER_KEY_ENV.get(provider, "")
    env_value = _clean(os.environ.get(env_key))
    if env_value:
        return env_value, "env"
    return "", None


def _update_secret(api_keys: dict[str, str], provider: str, value: Any, clear: bool) -> None:
    if clear:
        api_keys.pop(provider, None)
        return
    cleaned = _clean(value)
    if cleaned:
        api_keys[provider] = cleaned


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"


def _normalize_provider(value: Any) -> str:
    provider = _clean(value).lower()
    if provider in AVAILABLE_PROVIDERS:
        return provider
    return "anthropic"


def _clean(value: Any) -> str:
    return str(value or "").strip()

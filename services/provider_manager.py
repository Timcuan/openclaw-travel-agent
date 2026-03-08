"""
Provider Manager – loads, initialises, and routes to enabled providers.

Flow:
  1. On startup, read config/providers.yaml
  2. Instantiate each enabled provider class
  3. Expose get_providers(travel_type) → list of Provider instances
  4. run_search(travel_type, params) → parallel search + merge

File: services/provider_manager.py
"""
import asyncio
import os
from pathlib import Path
from typing import Literal
import yaml

from providers.base_provider import Provider, NormalizedResult
from utils.logger import logger

TravelType = Literal["train", "flight", "hotel"]

# Lazy config + provider registry
_config: dict | None = None
_registry: dict[str, list[Provider]] = {}

CONFIG_PATH = Path(__file__).parent.parent / "config" / "providers.yaml"


# ─── Config loading ────────────────────────────────────────────────────────────

def _load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            _config = yaml.safe_load(f) or {}
    else:
        logger.warning(f"[ProviderManager] {CONFIG_PATH} not found – using defaults")
        _config = {}
    return _config


# ─── Provider class map ────────────────────────────────────────────────────────
# Maps config key → provider class (imported lazily to avoid circular imports)

def _get_provider_class(travel_type: str, key: str):
    mapping = {
        "train": {
            "kai":       ("providers.train.kai_provider",       "KAIProvider"),
            "tiket":     ("providers.train.tiket_provider",     "TiketProvider"),
            "traveloka": ("providers.train.traveloka_provider", "TravelokaProvider"),
        },
        "flight": {
            "amadeus":    ("providers.flight.amadeus_provider",    "AmadeusProvider"),
            "kiwi":       ("providers.flight.kiwi_provider",       "KiwiProvider"),
            "skyscanner": ("providers.flight.skyscanner_provider", "SkyscannerProvider"),
        },
        "hotel": {
            "liteapi": ("providers.hotel.liteapi_provider",  "LiteAPIProvider"),
            "booking": ("providers.hotel.booking_provider",  "BookingProvider"),
            "agoda":   ("providers.hotel.agoda_provider",    "AgodaProvider"),
        },
    }
    entry = mapping.get(travel_type, {}).get(key)
    if not entry:
        return None
    module_path, class_name = entry
    import importlib
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except (ImportError, AttributeError) as e:
        logger.error(f"[ProviderManager] Cannot load {module_path}.{class_name}: {e}")
        return None


# ─── Registry ──────────────────────────────────────────────────────────────────

def get_providers(travel_type: TravelType) -> list[Provider]:
    """Return list of enabled Provider instances for a travel type, sorted by priority."""
    if travel_type in _registry:
        return _registry[travel_type]

    cfg = _load_config()
    section = cfg.get(travel_type, {})
    providers: list[Provider] = []

    for key, provider_cfg in section.items():
        if not isinstance(provider_cfg, dict):
            continue
        if not provider_cfg.get("enabled", True):
            logger.debug(f"[ProviderManager] {travel_type}/{key} disabled")
            continue
        cls = _get_provider_class(travel_type, key)
        if cls is None:
            continue
        try:
            instance = cls(config=provider_cfg)
            providers.append(instance)
            logger.info(f"[ProviderManager] Loaded {instance.name} (priority={instance.priority})")
        except Exception as e:
            logger.error(f"[ProviderManager] Failed to init {key}: {e}")

    # Sort by priority
    providers.sort(key=lambda p: p.priority)
    _registry[travel_type] = providers
    return providers


def reload_providers():
    """Force reload of config and provider registry."""
    global _config, _registry
    _config = None
    _registry = {}
    logger.info("[ProviderManager] Registry cleared – will reload on next request")


# ─── Parallel search ──────────────────────────────────────────────────────────

async def run_search(
    travel_type: TravelType,
    params: dict,
) -> list[NormalizedResult]:
    """
    Run search across all enabled providers in parallel.

    Args:
        travel_type: 'train' | 'flight' | 'hotel'
        params: Search params dict.

    Returns:
        Merged list of NormalizedResult objects.
    """
    providers = get_providers(travel_type)
    if not providers:
        logger.warning(f"[ProviderManager] No enabled providers for {travel_type}")
        return []

    tasks = [p.search(params) for p in providers]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[NormalizedResult] = []
    for provider, outcome in zip(providers, raw):
        if isinstance(outcome, Exception):
            logger.error(f"[ProviderManager] {provider.name} failed: {outcome}")
        elif isinstance(outcome, list):
            results.extend(outcome)
            logger.info(f"[ProviderManager] {provider.name}: {len(outcome)} results")

    return results

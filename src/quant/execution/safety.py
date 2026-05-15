import os
from collections.abc import Mapping

from quant.models.execution import (
    TradingMode,
    TradingSafetyCheck,
    TradingSafetyConfig,
)

LIVE_TRADING_CONFIRMATION = "I_UNDERSTAND_LIVE_TRADING_RISK"


class LiveTradingNotAllowedError(RuntimeError):
    """Raised when a future live-trading path has not passed safety gates."""


def evaluate_trading_safety(
    config: TradingSafetyConfig,
) -> TradingSafetyCheck:
    """Return a fail-closed decision for the requested trading mode."""
    if config.mode in {TradingMode.PAPER, TradingMode.DRY_RUN}:
        return TradingSafetyCheck(mode=config.mode, allowed=True)

    issues: list[str] = []
    if not config.live_trading_enabled:
        issues.append("live trading is not explicitly enabled")
    if config.live_trading_confirmation != LIVE_TRADING_CONFIRMATION:
        issues.append("live trading confirmation phrase is missing")
    if config.max_order_notional is None:
        issues.append("max order notional limit is missing")
    if not config.broker_name:
        issues.append("broker name is missing")

    return TradingSafetyCheck(
        mode=config.mode,
        allowed=len(issues) == 0,
        issues=tuple(issues),
    )


def assert_trading_allowed(config: TradingSafetyConfig) -> TradingSafetyCheck:
    """Raise before a disallowed trading mode can reach a broker adapter."""
    check = evaluate_trading_safety(config)
    if not check.allowed:
        raise LiveTradingNotAllowedError(check.reason)
    return check


def load_trading_safety_config_from_env(
    env: Mapping[str, str] | None = None,
) -> TradingSafetyConfig:
    """Load safety config from explicit environment variables.

    The defaults are intentionally paper-only. A missing environment variable
    must never imply permission to send real orders.
    """
    source = env if env is not None else os.environ
    mode = TradingMode(source.get("QUANT_TRADING_MODE", TradingMode.PAPER))
    max_order_notional = source.get("QUANT_MAX_ORDER_NOTIONAL")
    return TradingSafetyConfig(
        mode=mode,
        live_trading_enabled=_parse_bool(
            source.get("QUANT_LIVE_TRADING_ENABLED", "false")
        ),
        live_trading_confirmation=source.get(
            "QUANT_LIVE_TRADING_CONFIRMATION"
        ),
        max_order_notional=(
            float(max_order_notional)
            if max_order_notional not in (None, "")
            else None
        ),
        broker_name=source.get("QUANT_BROKER"),
    )


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")

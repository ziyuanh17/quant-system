import pytest
from typer.testing import CliRunner

from quant.cli import app
from quant.execution import (
    LIVE_TRADING_CONFIRMATION,
    LiveTradingNotAllowedError,
    assert_trading_allowed,
    evaluate_trading_safety,
    load_trading_safety_config_from_env,
)
from quant.models.execution import (
    ShortSellingPolicy,
    TradingMode,
    TradingSafetyConfig,
)


def test_trading_safety_allows_paper_by_default() -> None:
    check = evaluate_trading_safety(TradingSafetyConfig())

    assert check.allowed
    assert check.mode == TradingMode.PAPER
    assert check.issues == ()


def test_trading_safety_rejects_live_without_all_gates() -> None:
    check = evaluate_trading_safety(
        TradingSafetyConfig(mode=TradingMode.LIVE)
    )

    assert not check.allowed
    assert "live trading is not explicitly enabled" in check.issues
    assert "live trading confirmation phrase is missing" in check.issues
    assert "max order notional limit is missing" in check.issues
    assert "broker name is missing" in check.issues


def test_trading_safety_allows_live_only_with_explicit_gates() -> None:
    check = evaluate_trading_safety(
        TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
            max_order_notional=500,
            broker_name="example-broker",
        )
    )

    assert check.allowed
    assert check.issues == ()


def test_assert_trading_allowed_fails_closed_for_live_mode() -> None:
    with pytest.raises(LiveTradingNotAllowedError):
        assert_trading_allowed(TradingSafetyConfig(mode=TradingMode.LIVE))


def test_trading_safety_config_loads_from_env_mapping() -> None:
    config = load_trading_safety_config_from_env(
        {
            "QUANT_TRADING_MODE": "live",
            "QUANT_LIVE_TRADING_ENABLED": "true",
            "QUANT_LIVE_TRADING_CONFIRMATION": LIVE_TRADING_CONFIRMATION,
            "QUANT_MAX_ORDER_NOTIONAL": "250",
            "QUANT_BROKER": "example-broker",
        }
    )

    assert config.mode == TradingMode.LIVE
    assert config.live_trading_enabled
    assert config.max_order_notional == 250
    assert config.broker_name == "example-broker"


def test_trading_safety_config_loads_explicit_short_policy() -> None:
    config = load_trading_safety_config_from_env(
        {
            "QUANT_SHORT_SELLING_ENABLED": "true",
            "QUANT_MAX_SHORT_POSITION_NOTIONAL": "500",
            "QUANT_MAX_TOTAL_SHORT_EXPOSURE_PCT_EQUITY": "0.25",
            "QUANT_MAX_GROSS_EXPOSURE_PCT_EQUITY": "1.5",
            "QUANT_MIN_BUYING_POWER_BUFFER_PCT": "0.1",
        }
    )

    assert config.short_selling_policy == ShortSellingPolicy(
        enabled=True,
        max_short_position_notional=500,
        max_total_short_exposure_pct_equity=0.25,
        max_gross_exposure_pct_equity=1.5,
        min_buying_power_buffer_pct=0.1,
    )


def test_trading_safety_config_rejects_enabled_short_policy_without_limits(
) -> None:
    with pytest.raises(
        ValueError,
        match="enabled short selling requires explicit limits",
    ):
        load_trading_safety_config_from_env(
            {"QUANT_SHORT_SELLING_ENABLED": "true"}
        )


def test_safety_check_cli_fails_live_without_gates() -> None:
    result = CliRunner().invoke(
        app,
        ["safety", "check", "--trading-mode", "live"],
    )

    assert result.exit_code == 1
    assert "Allowed: False" in result.output
    assert "live trading is not explicitly enabled" in result.output


def test_safety_check_cli_allows_paper_default() -> None:
    result = CliRunner().invoke(app, ["safety", "check"])

    assert result.exit_code == 0
    assert "Mode: paper" in result.output
    assert "Allowed: True" in result.output

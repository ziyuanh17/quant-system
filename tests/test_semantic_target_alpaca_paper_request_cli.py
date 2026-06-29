"""Test broker-free semantic-target Alpaca paper request preparation."""

from datetime import timedelta
from pathlib import Path

from typer.testing import CliRunner

import quant.cli
from quant.cli import app
from quant.models.operator import (
    SemanticTargetAlpacaPaperOperatorRequest,
    SemanticTargetAlpacaPaperReadinessReport,
)


def test_prepare_alpaca_paper_request_from_local_semantic_paper_request(
    tmp_path,
) -> None:
    source_request_path = _prepare_local_source_request(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "prepare-alpaca-paper-request",
            "--request-id",
            "alpaca-paper-request",
            "--source-request-path",
            str(source_request_path),
            "--output-root",
            str(tmp_path / "alpaca-inputs"),
            "--paper-output-root",
            str(tmp_path / "alpaca-output"),
            "--max-order-notional",
            "1000",
            "--allowed-max-quantity",
            "2",
            "--valid-for-seconds",
            "900",
        ],
    )

    assert result.exit_code == 0
    assert "Prepared only. No Alpaca API call was made." in result.output
    assert "Approved target: 2" in result.output
    request_path = _request_path_from_output(result.output)
    request = SemanticTargetAlpacaPaperOperatorRequest.model_validate_json(
        request_path.read_text()
    )
    assert request.alpaca_submission_enabled is True
    assert request.safety_config.broker_name == "alpaca-paper"
    assert request.safety_config.max_order_notional == 1000
    assert request.allowed_symbol == "AAPL"
    assert request.allowed_max_quantity == 2
    assert Path(request.portfolio_target_path).is_file()
    assert Path(request.risk_target_path).is_file()

    second = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "prepare-alpaca-paper-request",
            "--request-id",
            "alpaca-paper-request",
            "--source-request-path",
            str(source_request_path),
            "--output-root",
            str(tmp_path / "alpaca-inputs"),
            "--paper-output-root",
            str(tmp_path / "alpaca-output"),
            "--max-order-notional",
            "1000",
            "--allowed-max-quantity",
            "2",
            "--valid-for-seconds",
            "900",
        ],
    )
    assert second.exit_code == 0
    assert _request_path_from_output(second.output) == request_path


def test_inspect_alpaca_paper_request_reports_ready_without_broker(
    tmp_path, monkeypatch
) -> None:
    request_path = _prepare_alpaca_source_request(tmp_path)
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: True
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "inspect-alpaca-paper-request",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code == 0
    assert "Valid now: yes" in result.output
    assert "Approved target: 2" in result.output
    assert "Regular session open: yes" in result.output
    assert (
        "Inspection created no Alpaca or execution artifacts."
        in result.output
    )


def test_inspect_alpaca_paper_request_blocks_when_session_closed(
    tmp_path, monkeypatch
) -> None:
    request_path = _prepare_alpaca_source_request(tmp_path)
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: False
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "inspect-alpaca-paper-request",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code != 0
    assert "Valid now: no" in result.output
    assert (
        "Blocked because: regular US equity session is closed"
        in result.output
    )


def test_inspect_alpaca_paper_request_blocks_when_expired(
    tmp_path, monkeypatch
) -> None:
    request_path = _prepare_alpaca_source_request(tmp_path)
    request = SemanticTargetAlpacaPaperOperatorRequest.model_validate_json(
        request_path.read_text()
    )
    after_expiry = request.valid_until + timedelta(seconds=1)
    monkeypatch.setattr(quant.cli, "_current_utc", lambda: after_expiry)
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: True
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "inspect-alpaca-paper-request",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code != 0
    assert "Blocked because: alpaca paper request is expired" in result.output


def test_preflight_alpaca_paper_test_writes_ready_report(
    tmp_path, monkeypatch
) -> None:
    request_path = _prepare_alpaca_source_request(tmp_path)
    report_path = tmp_path / "readiness.json"
    planned_verification_report_path = tmp_path / "verification.json"
    monkeypatch.setenv("QUANT_ALPACA_PAPER_API_KEY", "paper-key")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_SECRET_KEY", "paper-secret")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_ACCOUNT_ID", "acct-fake")
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: True
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "preflight-alpaca-paper-test",
            "--request-path",
            str(request_path),
            "--report-path",
            str(report_path),
            "--planned-verification-report-path",
            str(planned_verification_report_path),
        ],
    )

    assert result.exit_code == 0
    assert "Ready: yes" in result.output
    assert "Credential environment present: yes" in result.output
    assert (
        "Preflight created no Alpaca or execution artifacts."
        in result.output
    )
    report = SemanticTargetAlpacaPaperReadinessReport.model_validate_json(
        report_path.read_text()
    )
    assert report.ready
    assert report.request_id == "alpaca-paper-request"
    assert report.credentials_present
    assert report.market_session_open
    assert (
        report.planned_verification_report_path
        == str(planned_verification_report_path)
    )


def test_preflight_alpaca_paper_test_blocks_missing_credentials_and_session(
    tmp_path, monkeypatch
) -> None:
    request_path = _prepare_alpaca_source_request(tmp_path)
    report_path = tmp_path / "readiness.json"
    monkeypatch.delenv("QUANT_ALPACA_PAPER_API_KEY", raising=False)
    monkeypatch.delenv("QUANT_ALPACA_PAPER_SECRET_KEY", raising=False)
    monkeypatch.delenv("QUANT_ALPACA_PAPER_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: False
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "preflight-alpaca-paper-test",
            "--request-path",
            str(request_path),
            "--report-path",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "Ready: no" in result.output
    assert "regular US equity session is closed" in result.output
    assert "credential environment is incomplete" in result.output
    report = SemanticTargetAlpacaPaperReadinessReport.model_validate_json(
        report_path.read_text()
    )
    assert not report.ready
    assert not report.credentials_present
    assert not report.market_session_open


def test_preflight_alpaca_paper_test_blocks_existing_verification_report(
    tmp_path, monkeypatch
) -> None:
    request_path = _prepare_alpaca_source_request(tmp_path)
    report_path = tmp_path / "readiness.json"
    planned_verification_report_path = tmp_path / "verification.json"
    planned_verification_report_path.write_text("{}\n")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_API_KEY", "paper-key")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_SECRET_KEY", "paper-secret")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_ACCOUNT_ID", "acct-fake")
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: True
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "preflight-alpaca-paper-test",
            "--request-path",
            str(request_path),
            "--report-path",
            str(report_path),
            "--planned-verification-report-path",
            str(planned_verification_report_path),
        ],
    )

    assert result.exit_code != 0
    assert "planned verification report path already exists" in result.output


def test_prepare_alpaca_paper_request_rejects_quantity_above_bound(
    tmp_path,
) -> None:
    source_request_path = _prepare_local_source_request(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "prepare-alpaca-paper-request",
            "--request-id",
            "too-large",
            "--source-request-path",
            str(source_request_path),
            "--output-root",
            str(tmp_path / "alpaca-inputs"),
            "--paper-output-root",
            str(tmp_path / "alpaca-output"),
            "--allowed-max-quantity",
            "1",
        ],
    )

    assert result.exit_code != 0
    assert "allowed maximum quantity" in result.output


def test_prepare_alpaca_paper_request_help_is_broker_free() -> None:
    result = CliRunner().invoke(
        app,
        ["semantic-target", "prepare-alpaca-paper-request", "--help"],
    )

    assert result.exit_code == 0
    assert "Prepare one reviewed Alpaca paper request" in result.output
    assert "scheduler" not in result.output.lower()
    assert "credential" not in result.output.lower()


def test_inspect_alpaca_paper_request_help_is_broker_free() -> None:
    result = CliRunner().invoke(
        app,
        ["semantic-target", "inspect-alpaca-paper-request", "--help"],
    )

    assert result.exit_code == 0
    assert "without broker access" in result.output
    assert "credential" not in result.output.lower()


def test_preflight_alpaca_paper_test_help_is_broker_free() -> None:
    result = CliRunner().invoke(
        app,
        ["semantic-target", "preflight-alpaca-paper-test", "--help"],
    )

    assert result.exit_code == 0
    assert "readiness evidence" in result.output
    assert "without broker access" not in result.output.lower()


def _prepare_alpaca_source_request(tmp_path: Path) -> Path:
    source_request_path = _prepare_local_source_request(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "prepare-alpaca-paper-request",
            "--request-id",
            "alpaca-paper-request",
            "--source-request-path",
            str(source_request_path),
            "--output-root",
            str(tmp_path / "alpaca-inputs"),
            "--paper-output-root",
            str(tmp_path / "alpaca-output"),
            "--max-order-notional",
            "1000",
            "--allowed-max-quantity",
            "2",
            "--valid-for-seconds",
            "900",
        ],
    )
    assert result.exit_code == 0, result.output
    return _request_path_from_output(result.output)


def _prepare_local_source_request(tmp_path: Path) -> Path:
    data_path = _write_entry_prices(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "semantic-paper",
            "prepare-momentum-request",
            "--request-id",
            "source-momentum-request",
            "--data",
            str(data_path),
            "--symbol",
            "AAPL",
            "--quantity",
            "2",
            "--fast-window",
            "2",
            "--slow-window",
            "3",
            "--min-rows",
            "4",
            "--initial-cash",
            "1000",
            "--output-root",
            str(tmp_path / "local-requests"),
        ],
    )
    assert result.exit_code == 0, result.output
    return _request_path_from_output(result.output)


def _write_entry_prices(tmp_path: Path) -> Path:
    path = tmp_path / "AAPL.csv"
    path.write_text(
        "date,symbol,open,high,low,close,volume\n"
        "2026-01-01,AAPL,10,11,9,10,1000\n"
        "2026-01-02,AAPL,10,11,9,10,1000\n"
        "2026-01-03,AAPL,10,11,9,10,1000\n"
        "2026-01-04,AAPL,20,21,19,20,1000\n"
    )
    return path


def _request_path_from_output(output: str) -> Path:
    for line in output.splitlines():
        if line.startswith("Request: "):
            return Path(line.removeprefix("Request: "))
    raise AssertionError(f"request path missing from output: {output}")

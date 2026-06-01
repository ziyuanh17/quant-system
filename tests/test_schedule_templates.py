import plistlib
from pathlib import Path


def test_alpaca_paper_launchd_template_is_review_only() -> None:
    template_path = Path(
        "configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example"
    )

    payload = plistlib.loads(template_path.read_bytes())

    assert payload["Label"] == "com.quant-system.alpaca-paper-refresh"
    assert payload["Disabled"] is True
    assert payload["WorkingDirectory"] == "/absolute/path/to/quant-system"
    assert payload["ProgramArguments"] == [
        "/bin/bash",
        "/absolute/path/to/quant-system/scripts/run_alpaca_paper_refresh.sh",
    ]
    assert payload["StartCalendarInterval"] == {
        "Weekday": [1, 2, 3, 4, 5],
        "Hour": 12,
        "Minute": 55,
    }

import subprocess
from pathlib import Path


def test_web_console_wrapper_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", "scripts/run_web_console.sh"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_web_console_wrapper_requires_api_key(tmp_path: Path) -> None:
    wrapper = Path("scripts/run_web_console.sh").resolve()
    result = subprocess.run(
        ["bash", str(wrapper)],
        cwd=tmp_path,
        env={
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
            "QUANT_CMD": "/usr/bin/true",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "QUANT_CONSOLE_API_KEY is required" in result.stderr

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_run_sh_skips_qlib_validation_for_vnpy_without_python_yaml(tmp_path: Path) -> None:
    """run.sh backend detection must not require Python yaml availability."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "configs").mkdir()
    (repo / "configs" / "experiment.yaml").write_text(
        """
backtest:
  backend: vnpy
  noqlib:
    app5_storage_root: /tmp/app5
    daily_interface: daily
    benchmark_mode: mean
""".lstrip(),
        encoding="utf-8",
    )
    (repo / ".env").write_text("CONDA_ENV_NAME=mining\n", encoding="utf-8")
    (repo / "run.sh").write_text(Path("run.sh").read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "run.sh").chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "conda",
        "#!/bin/sh\nif [ \"$1\" = \"shell.bash\" ]; then echo 'conda() { return 0; }'; fi\n",
    )
    _write_executable(fake_bin / "python", "#!/bin/sh\necho 'Python 3.test'\n")
    _write_executable(fake_bin / "python3", "#!/bin/sh\nexit 1\n")
    _write_executable(fake_bin / "quantaalpha", "#!/bin/sh\nexit 0\n")

    result = subprocess.run(
        ["bash", "run.sh", "test direction"],
        cwd=repo,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}", "EXPERIMENT_ID": "shared"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "Backend: vnpy (qlib data validation skipped, using App5 parquet)" in result.stdout
    assert "QLIB_DATA_DIR not set" not in result.stdout

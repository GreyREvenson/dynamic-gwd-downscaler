import os
import glob
from pathlib import Path

from twtmain import calculate_async_wrapper


def test_calculate_async_wrapper_creates_verbose_log(tmp_path):
    missing_yaml = tmp_path / "missing_namelist.yaml"

    result = calculate_async_wrapper(str(missing_yaml))

    assert result is None
    logs = list(tmp_path.glob("verbose_*.txt"))
    assert logs, "Expected verbose log file to be created"
    assert logs[0].stat().st_size > 0

import datetime
from pathlib import Path

import pytest
import yaml
import rasterio

from twtnamelist import Namelist


def test_namelist_parses_minimal_yaml(tmp_path):
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    fname = tmp_path / "namelist.yaml"
    data = {
        "domain_bbox": [0.0, 0.0, 1.0, 1.0],
        "start_date": "2020-01-01",
        "end_date": "2020-01-03",
        "overwrite": "TRUE",
        "verbose": "True",
        "wtd_resample_method": "cubic",
        "dem_rez": "10",
        "conus1_download_dir": str(download_dir),
    }
    fname.write_text(yaml.safe_dump(data))

    nl = Namelist(str(fname))

    assert nl.time.start_date == datetime.datetime(2020, 1, 1)
    assert nl.time.end_date == datetime.datetime(2020, 1, 3)
    assert nl.time.datetime_dim.shape[0] == 3
    assert nl.options.overwrite is True
    assert nl.options.verbose is True
    assert nl.options.resample_method == rasterio.enums.Resampling.cubic
    assert nl.options.dem_rez == 10.0
    assert nl.options.conus1_download_dir == download_dir
    assert nl.dirnames.project == tmp_path
    assert nl.fnames.domain == tmp_path / "input" / "domain.gpkg"


def test_namelist_missing_required_end_date(tmp_path):
    fname = tmp_path / "namelist.yaml"
    fname.write_text(yaml.safe_dump({"domain_bbox": [0, 0, 1, 1], "start_date": "2020-01-01"}))

    with pytest.raises(ValueError, match="required variable end_date"):
        Namelist(str(fname))


def test_namelist_invalid_start_date(tmp_path):
    fname = tmp_path / "namelist.yaml"
    fname.write_text(yaml.safe_dump({"domain_bbox": [0, 0, 1, 1], "start_date": "2020-01-01X", "end_date": "2020-01-02"}))

    with pytest.raises(ValueError, match="invalid start date"):
        Namelist(str(fname))


def test_namelist_invalid_conus1_download_dir(tmp_path):
    fname = tmp_path / "namelist.yaml"
    bad_path = tmp_path / "missing"
    fname.write_text(yaml.safe_dump({
        "domain_bbox": [0, 0, 1, 1],
        "start_date": "2020-01-01",
        "end_date": "2020-01-02",
        "conus1_download_dir": str(bad_path),
    }))

    with pytest.raises(FileNotFoundError, match="does not exist"):
        Namelist(str(fname))

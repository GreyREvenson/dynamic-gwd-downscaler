import os
import datetime

from twtwt import set_wtd_get_flag


def _write_singleband_tif(path, shape, dtype="float32"):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    arr = np.zeros(shape, dtype=dtype)
    transform = from_origin(-120.0, 45.0, 0.01, 0.01)
    profile = {
        "driver": "GTiff",
        "height": shape[0],
        "width": shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": np.nan,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)


def test_set_wtd_get_flag_missing_file(tmp_path):
    wtd_raw = tmp_path / "wtd_raw"
    wtd_raw.mkdir()
    dt_start = datetime.datetime(2020, 1, 1)
    dt_end = datetime.datetime(2020, 1, 2)

    flag = set_wtd_get_flag(
        dt_start=dt_start,
        dt_end=dt_end,
        dir_wtd=str(wtd_raw),
        overwrite=False,
        verbose=False,
    )

    assert flag is True


def test_set_wtd_get_flag_all_files_exist(tmp_path):
    wtd_raw = tmp_path / "wtd_raw"
    wtd_raw.mkdir()
    dt_start = datetime.datetime(2020, 1, 1)
    dt_end = datetime.datetime(2020, 1, 2)
    for dt in [dt_start, dt_end]:
        _write_singleband_tif(wtd_raw / f"wtd_{dt.strftime('%Y%m%d')}.tiff", (2, 2))

    flag = set_wtd_get_flag(
        dt_start=dt_start,
        dt_end=dt_end,
        dir_wtd=str(wtd_raw),
        overwrite=False,
        verbose=False,
    )

    assert flag is False

import os
import datetime

import numpy as np
import rasterio
from rasterio.transform import from_origin

from twtcalc import (
    _read_base_grid_and_array,
    calculate_inundation,
    calculate_summary_perc_inundated,
    calculate_strm_permanence,
)


def _write_singleband_tif(path, arr, crs="EPSG:4326", transform=None, nodata=None, dtype=None):
    if dtype is None:
        dtype = arr.dtype
    if transform is None:
        transform = from_origin(-120.0, 45.0, 0.01, 0.01)
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "tiled": True,
        "compress": "zstd",
        "BIGTIFF": "IF_SAFER",
        "blockxsize": 16,
        "blockysize": 16,
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)


def test_read_base_grid_and_array_converts_nodata(tmp_path):
    data = np.array([[1.0, 999.0], [2.0, 999.0]], dtype=np.float32)
    fname = tmp_path / "base.tif"
    _write_singleband_tif(fname, data, nodata=999.0)

    arr, profile = _read_base_grid_and_array(str(fname))

    assert arr.dtype == np.float32
    assert np.isnan(arr[0, 1])
    assert profile["count"] == 1


def test_calculate_inundation_summary_and_permanence(tmp_path):
    shape = (3, 3)
    transform = from_origin(-120.0, 45.0, 0.01, 0.01)

    fname_twi = tmp_path / "twi.tif"
    fname_dem = tmp_path / "dem.tif"
    fname_twi_mean = tmp_path / "twi_mean.tif"
    fname_trans = tmp_path / "soil_trans.tif"
    _write_singleband_tif(fname_twi, np.zeros(shape, dtype=np.float32), transform=transform)
    _write_singleband_tif(fname_dem, np.zeros(shape, dtype=np.float32), transform=transform)
    _write_singleband_tif(fname_twi_mean, np.zeros(shape, dtype=np.float32), transform=transform)
    _write_singleband_tif(fname_trans, np.ones(shape, dtype=np.float32), transform=transform)

    wtd_raw_dir = tmp_path / "wtd_raw"
    wtd_raw_dir.mkdir()

    day1 = np.array([[-1, 2, -2], [2, 1, 2], [-3, 2, -4]], dtype=np.float32)
    day2 = np.array([[-1, 2, -2], [2, 1, 2], [-3, 2, -4]], dtype=np.float32)
    dt_start = datetime.datetime(2020, 1, 1)
    dt_end = datetime.datetime(2020, 1, 2)
    for dt, arr in zip([dt_start, dt_end], [day1, day2]):
        _write_singleband_tif(wtd_raw_dir / f"wtd_{dt.strftime('%Y%m%d')}.tiff", arr, transform=transform)

    out_raw = tmp_path / "out_raw"
    out_raw.mkdir()
    calculate_inundation(
        dt_start=dt_start,
        dt_end=dt_end,
        wtd_raw_dir=str(wtd_raw_dir),
        inundation_out_dir=str(out_raw),
        fname_twi=str(fname_twi),
        fname_twi_mean=str(fname_twi_mean),
        fname_soil_trans=str(fname_trans),
        verbose=False,
        overwrite=True,
    )

    out_sum = tmp_path / "out_sum"
    out_sum.mkdir()
    fname_perc = calculate_summary_perc_inundated(
        dt_start=dt_start,
        dt_end=dt_end,
        inundation_raw_dir=str(out_raw),
        inundation_summary_dir=str(out_sum),
        fname_dem=str(fname_dem),
        verbose=False,
        overwrite=True,
    )

    fname_mask = tmp_path / "stream_mask.tif"
    _write_singleband_tif(fname_mask, np.ones(shape, dtype=np.uint8), transform=transform, dtype=np.uint8, nodata=0)

    fname_p, fname_np = calculate_strm_permanence(
        fname_perc_inundation=str(fname_perc),
        fname_strm_mask=str(fname_mask),
        verbose=False,
        overwrite=True,
    )

    assert os.path.isfile(fname_p)
    assert os.path.isfile(fname_np)

    with rasterio.open(fname_p) as src:
        perennial = src.read(1)

    expected = {(0, 0), (0, 2), (2, 0), (2, 2)}
    found = {tuple(x) for x in np.argwhere(perennial == 1)}
    assert expected.issubset(found)

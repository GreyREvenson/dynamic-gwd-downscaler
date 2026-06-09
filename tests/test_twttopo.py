import os
import numpy as np
import rasterio
from rasterio.transform import from_origin

from twttopo import calc_twi_mean


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


def test_calc_twi_mean(tmp_path):
    shape = (3, 3)
    transform = from_origin(-120.0, 45.0, 0.01, 0.01)

    fname_twi = tmp_path / "twi.tif"
    fname_wtd = tmp_path / "wtd_20200101.tif"
    fname_twi_mean = tmp_path / "twi_mean.tif"

    _write_singleband_tif(fname_twi, np.ones(shape, dtype=np.float32), transform=transform)
    _write_singleband_tif(fname_wtd, np.full(shape, 2.0, dtype=np.float32), transform=transform)

    calc_twi_mean(
        fname_twi=str(fname_twi),
        fname_twi_mean=str(fname_twi_mean),
        wtd_raw_dir=str(tmp_path),
        verbose=False,
        overwrite=True,
    )

    assert fname_twi_mean.exists()
    with rasterio.open(fname_twi_mean) as src:
        arr = src.read(1)

    assert arr.shape == shape
    assert np.isfinite(arr).all()

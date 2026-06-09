"""
Lightweight smoke test that runs the inundation daily step, summary percent,
and stream permanence on tiny synthetic rasters (no downloads).
"""

import os
import sys
import tempfile
import datetime
import numpy as np
import rasterio
from rasterio.transform import from_origin

sys.path.append(os.path.abspath('../src'))  # adjust as needed to import twtcalc

import twtcalc

def _write_singleband_tif(path, arr, crs="EPSG:4326", transform=None, nodata=None, dtype=None):
    if dtype is None:
        dtype = arr.dtype
    if transform is None:
        transform = from_origin(-120.0, 45.0, 0.01, 0.01)  # arbitrary
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

def run_smoke():
    with tempfile.TemporaryDirectory() as td:
        # Base grid (TWI) and DEM on same small grid
        shape = (3, 3)
        transform = from_origin(-120.0, 45.0, 0.01, 0.01)
        fname_twi = os.path.join(td, "twi.tif")
        fname_dem = os.path.join(td, "dem.tif")
        _write_singleband_tif(fname_twi, np.zeros(shape, dtype=np.float32), transform=transform)
        _write_singleband_tif(fname_dem, np.zeros(shape, dtype=np.float32), transform=transform, nodata=None)

        # TWI mean and soil transmissivity (constants)
        fname_twi_mean = os.path.join(td, "twi_mean.tif")
        _write_singleband_tif(fname_twi_mean, np.zeros(shape, dtype=np.float32), transform=transform)
        fname_trans = os.path.join(td, "soil_trans.tif")
        _write_singleband_tif(fname_trans, np.ones(shape, dtype=np.float32), transform=transform)

        # WTD daily rasters: negative values => inundated (threshold=0), positive => not
        wtd_raw_dir = os.path.join(td, "wtd_raw")
        os.makedirs(wtd_raw_dir, exist_ok=True)
        day1 = np.array([[-1, 2, -2],
                         [ 2, 1,  2],
                         [-3, 2, -4]], dtype=np.float32)
        day2 = np.array([[-1, 2, -2],
                         [ 2, 1,  2],
                         [-3, 2, -4]], dtype=np.float32)
        dt_start = datetime.datetime(2020, 1, 1)
        dt_end = datetime.datetime(2020, 1, 2)
        for idt, arr in zip([dt_start, dt_end], [day1, day2]):
            _write_singleband_tif(os.path.join(wtd_raw_dir, f"wtd_{idt.strftime('%Y%m%d')}.tiff"), arr, transform=transform)

        # Run daily inundation
        out_raw = os.path.join(td, "out_raw")
        os.makedirs(out_raw, exist_ok=True)
        twtcalc.calculate_inundation(
            dt_start=dt_start,
            dt_end=dt_end,
            wtd_raw_dir=wtd_raw_dir,
            inundation_out_dir=out_raw,
            fname_twi=fname_twi,
            fname_twi_mean=fname_twi_mean,
            fname_soil_trans=fname_trans,
            verbose=True,
            overwrite=True,
        )

        # Inclusive summary percent inundation
        out_sum = os.path.join(td, "out_sum")
        os.makedirs(out_sum, exist_ok=True)
        fname_perc = twtcalc.calculate_summary_perc_inundated(
            dt_start=dt_start,
            dt_end=dt_end,
            inundation_raw_dir=out_raw,
            inundation_summary_dir=out_sum,
            fname_dem=fname_dem,
            verbose=True,
            overwrite=True,
        )

        # Stream mask: mark all cells as streams
        fname_mask = os.path.join(td, "stream_mask.tif")
        _write_singleband_tif(fname_mask, np.ones(shape, dtype=np.uint8), transform=transform, dtype=np.uint8, nodata=0)

        # Permanence
        fname_p, fname_np = twtcalc.calculate_strm_permanence(
            fname_perc_inundation=fname_perc,
            fname_strm_mask=fname_mask,
            verbose=True,
            overwrite=True,
        )

        # Basic checks
        assert os.path.isfile(fname_p), "Perennial output missing"
        assert os.path.isfile(fname_np), "Nonperennial output missing"

        with rasterio.open(fname_p) as src:
            arr_p = src.read(1)
        # In our synthetic setup, the negative-value cells should be 100% inundated => perennial==1
        # day arrays: positions (0,0), (0,2), (2,0), (2,2) are negative in both days
        expected_ones = {(0,0), (0,2), (2,0), (2,2)}
        found_ones = set(map(tuple, np.argwhere(arr_p == 1)))
        assert expected_ones.issubset(found_ones), f"Perennial map missing expected cells: {expected_ones - found_ones}"

        print("Smoke test passed.")

if __name__ == "__main__":
    run_smoke()
import asyncio
import os
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

import twtsoils



def _write_singleband_tif(path, arr, crs="EPSG:4326", transform=None, dtype=None):
    if dtype is None:
        dtype = arr.dtype
    if transform is None:
        transform = from_origin(0.0, 2.0, 1.0, 1.0)
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)


def test_break_soil_texture_creates_child_file(tmp_path, monkeypatch):
    parent = tmp_path / "soil_texture_parent.gpkg"
    domain_file = tmp_path / "domain.gpkg"
    child = tmp_path / "soil_texture_child.gpkg"

    soil_gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0.0, 0.0, 2.0, 2.0)], crs="EPSG:4326")
    domain_gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0.0, 0.0, 2.0, 2.0)], crs="EPSG:4326")

    soil_gdf.to_file(parent, driver="GPKG")
    domain_gdf.to_file(domain_file, driver="GPKG")

    monkeypatch.setattr(twtsoils, "pyogrio", SimpleNamespace(read_info=lambda fname: {"crs": "EPSG:4326"}))

    original_read_file = gpd.read_file

    def fake_read_file(fname, bbox=None, engine=None):
        fname = os.path.abspath(str(fname))
        if fname == os.path.abspath(str(domain_file)):
            return domain_gdf
        if fname == os.path.abspath(str(parent)):
            return soil_gdf
        return original_read_file(fname, bbox=bbox, engine=engine)

    monkeypatch.setattr(twtsoils.geopandas, "read_file", fake_read_file)

    twtsoils.break_soil_texture(
        fname_texture_parent=str(parent),
        fname_texture_child=str(child),
        fname_domain=str(domain_file),
        verbose=False,
        overwrite=True,
    )

    assert child.exists()
    loaded = gpd.read_file(child)
    assert len(loaded) == 1
    assert loaded.geometry.iloc[0].equals(soil_gdf.geometry.iloc[0])


def test_set_soil_transmissivity_generates_raster(tmp_path):
    if twtsoils.make_geocube is None:
        pytest.skip("geocube is not installed")

    dem_path = tmp_path / "dem.tif"
    texture_path = tmp_path / "soil_texture.gpkg"
    transmissivity_path = tmp_path / "soil_transmissivity.tif"

    transform = from_origin(0.0, 2.0, 1.0, 1.0)
    arr = np.ones((2, 2), dtype=np.float32)
    _write_singleband_tif(dem_path, arr, transform=transform)

    texture_gdf = gpd.GeoDataFrame(
        {"texture": ["sand"]},
        geometry=[box(0.0, 0.0, 2.0, 2.0)],
        crs="EPSG:4326",
    )
    texture_gdf.to_file(texture_path, driver="GPKG")

    twtsoils.set_soil_transmissivity(
        fname_texture=str(texture_path),
        fname_dem=str(dem_path),
        fname_transmissivity=str(transmissivity_path),
        verbose=False,
        overwrite=True,
    )

    assert transmissivity_path.exists()
    with rasterio.open(transmissivity_path) as src:
        out_arr = src.read(1)
    assert out_arr.shape == arr.shape
    assert np.isfinite(out_arr).all()


def test_download_soil_texture_async(tmp_path, monkeypatch):
    domain = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0.0, 0.0, 2.0, 2.0)], crs="EPSG:4326")
    domain_buf = domain.copy()
    fname_texture = tmp_path / "downloaded_texture.gpkg"

    async def fake_spatial_query(*, geometry=None, table=None, spatial_relation=None, return_type=None):
        class Resp:
            def to_geodataframe(self):
                return gpd.GeoDataFrame({"mukey": [1]}, geometry=[box(0.0, 0.0, 2.0, 2.0)], crs="EPSG:4326")
        return Resp()

    async def fake_fetch_by_keys(keys, table, key_column=None, columns=None):
        class Resp:
            def to_pandas(self):
                import pandas as pd
                if table == "component":
                    return pd.DataFrame({"mukey": [1], "cokey": [10], "compname": ["comp"], "comppct_r": [100]})
                if table == "chorizon":
                    return pd.DataFrame({
                        "cokey": [10, 10],
                        "sandtotal_r": [60, 60],
                        "silttotal_r": [20, 20],
                        "claytotal_r": [20, 20],
                        "hzdept_r": [0, 10],
                        "hzdepb_r": [10, 20],
                    })
        return Resp()

    monkeypatch.setattr(twtsoils, "soildb", SimpleNamespace(spatial_query=fake_spatial_query, fetch_by_keys=fake_fetch_by_keys))
    monkeypatch.setattr(twtsoils, "soiltexture", SimpleNamespace(getTexture=lambda s, c: "sandy"))

    import asyncio
    asyncio.run(twtsoils.download_soil_texture(fname_texture=str(fname_texture), domain=domain, domain_buf=domain_buf, verbose=False, overwrite=True))

    assert fname_texture.exists()
    loaded = gpd.read_file(fname_texture)
    assert "texture" in loaded.columns





def test_download_soil_texture_writes_file(tmp_path, monkeypatch):
    if twtsoils.soildb is None:
        monkeypatch.setattr(twtsoils, "soildb", SimpleNamespace())

    monkeypatch.setattr(twtsoils, "soiltexture", SimpleNamespace(getTexture=lambda sand, clay: "sand"))

    soilsgdf = gpd.GeoDataFrame(
        {"mukey": [100]},
        geometry=[box(0.0, 0.0, 1.0, 1.0)],
        crs="EPSG:4326",
    )
    comps = pd.DataFrame(
        {"mukey": [100], "cokey": [200], "compname": ["A"], "comppct_r": [100]}
    )
    chorizons = pd.DataFrame(
        {
            "cokey": [200],
            "sandtotal_r": [60.0],
            "silttotal_r": [20.0],
            "claytotal_r": [20.0],
            "hzdept_r": [0.0],
            "hzdepb_r": [10.0],
        }
    )

    class FakeResponse:
        def __init__(self, df):
            self._df = df

        def to_geodataframe(self):
            return self._df

        def to_pandas(self):
            return self._df

    async def fake_spatial_query(*, geometry, table, spatial_relation, return_type):
        return FakeResponse(soilsgdf)

    async def fake_fetch_by_keys(keys, table, key_column, columns):
        if table == "component":
            return FakeResponse(comps)
        return FakeResponse(chorizons)

    monkeypatch.setattr(twtsoils.soildb, "spatial_query", fake_spatial_query)
    monkeypatch.setattr(twtsoils.soildb, "fetch_by_keys", fake_fetch_by_keys)

    domain = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[box(0.0, 0.0, 1.0, 1.0)],
        crs="EPSG:4326",
    )
    domain_buf = domain.copy()
    fname_texture = tmp_path / "downloaded_soil_texture.gpkg"

    asyncio.run(
        twtsoils.download_soil_texture(
            fname_texture=str(fname_texture),
            domain=domain,
            domain_buf=domain_buf,
            verbose=False,
            overwrite=True,
        )
    )

    assert fname_texture.exists()
    loaded = gpd.read_file(fname_texture)
    assert "texture" in loaded.columns
    assert loaded["texture"].iloc[0] == "sand"

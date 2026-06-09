import pytest
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box
import yaml

from twtmapfolium import twtfoliummap
from twtnamelist import Namelist


def test_twtfoliummap_add_twi_raises_for_missing_file(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_summary = tmp_path / "output" / "summary"
    output_summary.mkdir(parents=True)

    domain = gpd.GeoDataFrame(geometry=[box(0.0, 0.0, 1.0, 1.0)], crs="EPSG:4326")
    domain_file = input_dir / "domain.gpkg"
    domain.to_file(domain_file, driver="GPKG")

    namelist_yaml = tmp_path / "namelist.yaml"
    namelist_yaml.write_text(yaml.safe_dump({
        "domain_bbox": [0.0, 0.0, 1.0, 1.0],
        "start_date": "2020-01-01",
        "end_date": "2020-01-01",
    }))

    nl = Namelist(str(namelist_yaml))
    map_obj = twtfoliummap(nl)

    assert map_obj._resample_label(nl).lower().startswith("bilinear")
    with pytest.raises(FileNotFoundError):
        map_obj.add_twi()

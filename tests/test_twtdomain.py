from shapely.geometry import box
import geopandas as gpd
from twtdomain import set_domain, set_domain_buf


def test_set_domain_with_bbox(tmp_path):
    fname_domain = tmp_path / "domain.gpkg"
    domain = set_domain(
        fname_domain=str(fname_domain),
        domain_bbox=(0.0, 0.0, 1.0, 1.0),
        verbose=True,
        overwrite=True,
    )

    assert fname_domain.exists()
    assert domain.geometry.iloc[0].bounds == (0.0, 0.0, 1.0, 1.0)


def test_set_domain_buf_creates_buffer(tmp_path):
    fname_domain = tmp_path / "domain.gpkg"
    domain = gpd.GeoDataFrame(geometry=[box(0.0, 0.0, 1.0, 1.0)], crs="EPSG:4326")
    domain.to_file(fname_domain, driver="GPKG")

    fname_domain_buf = tmp_path / "domain_buf.gpkg"
    domain_buf = set_domain_buf(
        domain=domain,
        fname_domain_buf=str(fname_domain_buf),
        buf_dist_m=1000,
        verbose=True,
        overwrite=True,
    )

    assert fname_domain_buf.exists()
    assert domain_buf.geometry.iloc[0].area > domain.geometry.iloc[0].area

import math
import re
import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
from rasterio.transform import array_bounds

try:
    import folium
except ImportError:  # pragma: no cover
    folium = None

try:
    import branca
except ImportError:  # pragma: no cover
    branca = None

try:
    import geopandas
except ImportError:  # pragma: no cover
    geopandas = None

import twtnamelist

logger = logging.getLogger(__name__)

_BaseFoliumMap = folium.Map if folium is not None else object

class twtfoliummap(_BaseFoliumMap):
    def __init__(self, nl: twtnamelist.Namelist, *args, **kwargs):
        if folium is None:
            raise ImportError('folium is required to create twtfoliummap')
        super().__init__(*args, **kwargs)
        self._set_fnames(nl=nl)
        self._add_domain(nl=nl)
        self._add_nhd()

    def _set_fnames(self, nl: twtnamelist.Namelist):
        dstr = f"{nl.time.datetime_dim[0].strftime('%Y%m%d')}_to_{nl.time.datetime_dim[-1].strftime('%Y%m%d')}"
        doutput = nl.dirnames.output_summary
        self.fname_soil_texture = nl.fnames.soil_texture
        self.fname_transmissivity = nl.fnames.soil_transmissivity
        self.fname_nhd = nl.fnames.nhdp
        self.fname_twi = nl.fnames.twi
        self.fname_slope = nl.fnames.slope
        self.fname_flow_acc = nl.fnames.facc_sca
        self.fname_dem = nl.fnames.dem
        self.fname_dem_breached = nl.fnames.dem_breached
        self.fname_percinundated = Path(doutput) / f"percent_inundated_grid_{dstr}.tiff"
        self.fname_meanwtd = Path(doutput) / f"mean_wtd_{dstr}.tiff"
        self.fname_nonperennial = Path(doutput) / f"nonperennial_strms_{dstr}.tiff"
        self.fname_perennial = Path(doutput) / f"perennial_strms_{dstr}.tiff"

    def add_transmissivity(self):
        fname = Path(self.fname_transmissivity)
        if not fname.is_file():
            raise FileNotFoundError(f"add_transmissivity could not find {fname}")
        self._add_grid(
            name="Transmissivity Decay Factor (f)",
            fname=fname,
            cmap=branca.colormap.linear.viridis
        )

    def add_twi(self):
        fname = Path(self.fname_twi)
        if not fname.is_file():
            raise FileNotFoundError(f"add_twi could not find {fname}")
        self._add_grid(
            name="Topological Wetness Index (TWI)",
            fname=fname,
            cmap=branca.colormap.linear.viridis
        )

    def add_slope(self):
        fname = Path(self.fname_slope)
        if not fname.is_file():
            raise FileNotFoundError(f"add_slope could not find {fname}")
        self._add_grid(
            name="Slope (degrees)",
            fname=fname,
            cmap=branca.colormap.linear.Greys_07
        )

    def add_facc(self):
        fname = Path(self.fname_flow_acc)
        if not fname.is_file():
            raise FileNotFoundError(f"add_facc could not find {fname}")
        self._add_grid(
            name="Flow accumulation",
            fname=fname,
            cmap=branca.colormap.linear.viridis
        )

    def _resample_label(self, nl: twtnamelist.Namelist) -> str:
        try:
            return nl.options.resample_method.name
        except Exception:
            return str(nl.options.resample_method)

    def add_meanwtd(self, namelist: twtnamelist.Namelist, fname: Path | str = None):
        if fname is None:
            fname = Path(self.fname_meanwtd)
        else:
            fname = Path(fname)
        if not fname.is_file():
            raise FileNotFoundError(f"add_meanwtd could not find {fname}")
        label = self._resample_label(namelist)
        self._add_grid(
            name=f"Mean WTD (m) ({label})",
            fname=fname,
            cmap=branca.colormap.linear.viridis
        )

    def add_percinundated(self, namelist: twtnamelist.Namelist, fname: Path | str = None):
        if fname is None:
            fname = Path(self.fname_percinundated)
        else:
            fname = Path(fname)
        if not fname.is_file():
            raise FileNotFoundError(f"add_percinundated could not find {fname}")
        label = self._resample_label(namelist)
        self._add_grid(
            name=f"WTD-TWI %-Inundated ({label})",
            fname=fname,
            cmap=branca.colormap.linear.Reds_08
        )

    def add_nonperennial_strm_classification(self, fname: Path | str = None):
        if fname is None:
            fname = Path(self.fname_nonperennial)
        else:
            fname = Path(fname)
        if not fname.is_file():
            raise FileNotFoundError(f"add_nonperennial_strm_classification could not find {fname}")
        self._add_grid(
            name="WTD-TWI Non-perennial",
            fname=fname,
            cmap=branca.colormap.linear.Blues_07
        )

    def add_perennial_strm_classification(self, fname: Path | str = None):
        if fname is None:
            fname = Path(self.fname_perennial)
        else:
            fname = Path(fname)
        if not fname.is_file():
            raise FileNotFoundError(f"add_perennial_strm_classification could not find {fname}")
        cmap = {1: "#ff0000"}
        self._add_grid(
            name="WTD-TWI Perennial",
            fname=fname,
            cmap=cmap
        )
        html_legend = """
        <div style="position: fixed; 
        bottom: 10px; left: 10px; width: 150px; height: auto; 
        border:2px solid grey; z-index:9999; font-size:14px;
        background-color:white; opacity: 0.85; padding: 10px;">
        """
        # fix: remove the stray set literal in the f-string; original used {'Perennial'} 
        html_legend += f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {cmap[1]}; margin-right: 5px;"></div>Perennial</div>'
        html_legend += "</div>"
        self.get_root().html.add_child(folium.Element(html_legend))

    def _add_grid(self, name: str, fname: Path | str, cmap: "branca.colormap.ColorMap | dict"):
        """
        Add gridded data to a Folium map as a palettized PNG data-URI.

        - NaNs are transparent (palette index 0).
        - Continuous case (vmin != vmax) uses the provided ColorMap (branca) for the palette and adds a legend.
        - Binary/degenerate case (all finite pixels have the same value, e.g., 1/NaN) maps all finite pixels to a single color and adds a simple legend.
        """
        from PIL import Image

        fname = Path(fname)
        if not fname.is_file():
            raise FileNotFoundError(f"_add_grid could not find {fname}")
        if fname.suffix.lower() not in {".tif", ".tiff"}:
            raise ValueError(f"_add_grid fname does not end in .tif/.tiff: {fname}")

        def _hex_to_rgb(h: str):
            s = h.lstrip("#")
            if len(s) in (3, 4):
                s = "".join(ch * 2 for ch in s[:3])
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))

        def _parse_color_to_rgb(c):
            # Accept '#RRGGBB', '#RRGGBBAA', 'rgb(r,g,b)', 'rgba(r,g,b,a)', or tuples/lists
            if isinstance(c, str):
                c = c.strip()
                if c.startswith("#"):
                    return _hex_to_rgb(c)
                m = re.match(r"rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)", c)
                if m:
                    r, g, b = m.groups()
                    vals = [float(r), float(g), float(b)]
                    if max(vals) <= 1.0:
                        vals = [int(round(v * 255)) for v in vals]
                    else:
                        vals = [int(round(v)) for v in vals]
                    return tuple(np.clip(vals, 0, 255).astype(int).tolist())
                try:
                    return _hex_to_rgb("#" + c)
                except Exception:
                    return (31, 120, 180)  # default
            if isinstance(c, (tuple, list)) and len(c) >= 3:
                vals = list(c[:3])
                if any(isinstance(v, float) for v in vals) and max(vals) <= 1.0:
                    vals = [int(round(v * 255)) for v in vals]
                vals = [int(round(v)) for v in vals]
                return tuple(np.clip(vals, 0, 255).astype(int).tolist())
            return (31, 120, 180)

        folium_crs = "EPSG:3857"
        with rasterio.open(fname, "r") as src:
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src.crs, folium_crs, src.width, src.height, *src.bounds
            )
            vals = np.full((dst_height, dst_width), np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=vals,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=folium_crs,
                resampling=Resampling.nearest,
                src_nodata=src.nodata,
                dst_nodata=np.nan,
            )
            bounds_merc = array_bounds(dst_height, dst_width, dst_transform)
            bbox = transform_bounds(folium_crs, "EPSG:4326", *bounds_merc)

            finite_mask = np.isfinite(vals)
            if finite_mask.any():
                vmin = float(vals[finite_mask].min())
                vmax = float(vals[finite_mask].max())
            else:
                vmin, vmax = 0.0, 1.0

            cm_for_palette = None
            if isinstance(cmap, branca.colormap.ColorMap) and vmin != vmax and math.isfinite(vmin) and math.isfinite(vmax):
                cm_for_palette = cmap.scale(vmin, vmax)
                cm_for_palette.caption = name
                cm_for_palette.add_to(self)

            # Build 256-color palette: index 0 reserved for NaN (transparent)
            palette = np.zeros((256, 3), dtype=np.uint8)
            if cm_for_palette is not None:
                sample_vals = np.linspace(vmin, vmax, 255, dtype=np.float32)
                for i, v in enumerate(sample_vals, start=1):
                    palette[i] = _parse_color_to_rgb(cm_for_palette(float(v)))
            else:
                palette[1:, 0] = np.arange(1, 256, dtype=np.uint8)
                palette[1:, 1] = np.arange(1, 256, dtype=np.uint8)
                palette[1:, 2] = np.arange(1, 256, dtype=np.uint8)

            idx = np.zeros(vals.shape, dtype=np.uint8)
            if finite_mask.any() and vmin != vmax and math.isfinite(vmin) and math.isfinite(vmax):
                norm = np.clip((vals[finite_mask] - vmin) / (vmax - vmin), 0.0, 1.0)
                idx_vals = 1 + (norm * 254.0).astype(np.uint8)
                idx[finite_mask] = idx_vals
            elif finite_mask.any():
                idx[finite_mask] = 255
                chosen_rgb = (31, 120, 180)
                if isinstance(cmap, dict):
                    color_spec = cmap.get(1, cmap.get(float(vmin), cmap.get(int(vmin), "#1f78b4")))
                    chosen_rgb = _parse_color_to_rgb(color_spec)
                elif isinstance(cmap, branca.colormap.ColorMap):
                    try:
                        color_spec = cmap(float(vmin))
                    except Exception:
                        color_spec = cmap(0.5) if hasattr(cmap, "__call__") else "#1f78b4"
                    chosen_rgb = _parse_color_to_rgb(color_spec)
                palette[255] = chosen_rgb

            img = Image.fromarray(idx, mode="P")
            img.putpalette(palette.reshape(-1).tolist())
            img.info["transparency"] = 0  # index 0 transparent

            import io, base64
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

            overlay = folium.raster_layers.ImageOverlay(
                name=name,
                image=data_uri,
                bounds=[[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
                opacity=1.0,
                interactive=False,
                cross_origin=False,
            )
            overlay.add_to(self)
            return overlay

    def _add_vector(self, name: str, fname: Path | str, name_in_file: str, cmap: "branca.colormap.ColorMap | dict"):
        fname = Path(fname)
        if not fname.is_file():
            raise FileNotFoundError(f"_add_vector could not find {fname}")
        if fname.suffix.lower() not in {".gpkg", ".shp"}:
            raise ValueError(f"_add_vector fname does not end in .shp or .gpkg: {fname}")
        shp = geopandas.read_file(fname)
        shpfg = folium.FeatureGroup(name=name)

        def _get_geometry_lines(geometry):
            if geometry is None:
                return []
            geom_type = geometry.geom_type
            if geom_type == 'LineString':
                return [list(geometry.coords)]
            if geom_type == 'MultiLineString':
                return [list(part.coords) for part in geometry.geoms]
            if geom_type == 'Polygon':
                lines = [list(geometry.exterior.coords)]
                lines.extend([list(ring.coords) for ring in geometry.interiors])
                return lines
            if geom_type == 'MultiPolygon':
                lines = []
                for part in geometry.geoms:
                    lines.append(list(part.exterior.coords))
                    lines.extend([list(ring.coords) for ring in part.interiors])
                return lines
            return []

        for _, r in shp.iterrows():
            if isinstance(cmap, dict):
                color = cmap.get(r[name_in_file], '#000000')
            else:
                color = cmap(r[name_in_file])
            for coords in _get_geometry_lines(r.geometry):
                folium.PolyLine(
                    locations=[(lat, lon) for lon, lat in coords],
                    color=color
                ).add_to(shpfg)
        shpfg.add_to(self)

    def add_texture(self):
        fname = Path(self.fname_soil_texture)
        if not fname.is_file():
            raise FileNotFoundError(f"add_texture could not find {fname}")
        soils = geopandas.read_file(fname)
        textures = sorted(set(soils["texture"]))
        if len(textures) == 0:
            return
        cmap = branca.colormap.linear.viridis.scale(0, len(textures)).to_step(len(textures))
        texture_colors = {texture: cmap(i) for i, texture in enumerate(textures)}
        soilsfg = folium.FeatureGroup(name="Soil texture")
        for texture, texture_group in soils.groupby("texture"):
            for _, row in texture_group.iterrows():
                folium.GeoJson(
                    data=geopandas.GeoSeries(row["geometry"]).to_json(),
                    style_function=lambda x, color=texture_colors[texture]: {"fillColor": color, "color": "black", "fillOpacity": 1.0}
                ).add_to(soilsfg)
        soilsfg.add_to(self)
        html_legend = """
        <div style="position: fixed; 
        top: 10px; left: 60px; width: 200px; height: auto; 
        border:2px solid grey; z-index:9999; font-size:14px;
        background-color:white; opacity: 0.85; padding: 10px;">
        <b>Soil Texture</b><br>
        """
        for texture, color in texture_colors.items():
            html_legend += f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {color}; margin-right: 5px;"></div>{texture}</div>'
        html_legend += "</div>"
        self.get_root().html.add_child(folium.Element(html_legend))

    def _add_domain(self, nl: twtnamelist.Namelist):
        fname = Path(nl.fnames.domain)
        if not fname.is_file():
            raise FileNotFoundError(f"_add_domain could not find {fname}")
        domain = geopandas.read_file(fname)
        domainfg = folium.FeatureGroup(name="Domain")
        for _, r in domain.iterrows():
            folium.GeoJson(
                data=geopandas.GeoSeries(r["geometry"]).to_json(),
                style_function=lambda x: {"color": "black", "fillColor": "none"}
            ).add_to(domainfg)
        domainfg.add_to(self)
        domain_centroid = domain.to_crs("+proj=cea").centroid.to_crs(domain.crs)
        self.location = [domain_centroid.y.iloc[0], domain_centroid.x.iloc[0]]
        self.zoom_start = 10

    def _add_nhd(self):
        if self.fname_nhd and Path(self.fname_nhd).is_file():
            try:
                nhd = geopandas.read_file(self.fname_nhd)
                nhdfg = folium.FeatureGroup(name="NHD Flowlines")
                for _, r in nhd.iterrows():
                    folium.PolyLine(
                        locations=[(lat, lon) for lon, lat in r.geometry.coords],
                        color="#1f78b4",
                        weight=2,
                        opacity=0.8
                    ).add_to(nhdfg)
                nhdfg.add_to(self)
            except Exception:
                pass
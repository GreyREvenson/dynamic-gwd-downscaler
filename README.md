# Description

A Python-based tool that uses high-resolution topography, soil properties, and topmodel-principles to downscale dynamic coarse-resolution groundwater depth simulations and observations and predict fine-resolution groundwater-surface intersection dynamics (i.e., 'inundation') and identify wetlands and non-perennial streams.

**Core methodology**: The tool uses the Topographic Wetness Index (TWI) and soil transmissivity to model the spatial distribution of water table depth within coarse grid cells. Where the downscaled water table intersects or rises above the land surface, wetlands and streams are predicted. The tool integrates:

- **Coarse Groundwater Simulations**: E.g., Water table depth from ParFlow-CLM simulations
- **High-Resolution Topography**: DEMs to compute terrain wetness indices and flow networks
- **Soil Properties**: Transmissivity and texture for subsurface flow routing
- **Topmodel Framework**: Topmodel-based downscaling assumptions linking terrain and hydrology
- **Stream Networks**: NHDPlus flowlines for validation and stream reach classification

## Features

- **Groundwater Downscaling**: Apply topmodel-based methods to refine coarse-resolution water table depth to fine scales
- **Domain Definition**: Define study areas by HUC ID, bounding box, or lat/lon coordinates
- **Automated Data Retrieval**: Download water table depth data from HydroFrame, DEMs from 3DEP, soil data from SSURGO/gNATSGO
- **Topographic Analysis**: Compute TWI, flow accumulation, and terrain derivatives for downscaling
- **Hydrofacies Mapping**: Calculate water table depth relative to soil and topographic features
- **Groundwater-Stream Interaction**: Predict where groundwater intersects surface streams
- **Stream Classification**: Classify reaches as perennial, intermittent, or ephemeral based on groundwater emergence
- **Spatial Outputs**: Generate GeoPackage (GPKG) and GeoTIFF outputs for GIS analysis
- **Visualization**: Create maps and summaries of predicted water table depths and stream classifications

## Usage

### Basic Workflow

The tool follows this sequence to downscale groundwater depths and predict surface-groundwater interactions:

1. **Define Domain**: Specify study area (HUC, bounding box, or coordinates)
2. **Retrieve Data**: Acquire coarse water table depth grids, high-resolution DEM, soil properties
3. **Compute Topographic Indices**: Calculate TWI and flow accumulation from DEM
4. **Downscale Water Table**: Apply topmodel-based downscaling to refine water table depth to fine scales
5. **Predict Emergence**: Identify where downscaled water table intersects land surface
6. **Classify Streams**: Categorize stream reaches as perennial, intermittent, or ephemeral

**Running an analysis**:

1. **Prepare a Configuration File**: Create a YAML namelist file (see `examples/al_app_plateau/namelist.yaml`)

2. **Execute**:
```python
from src import twtmain
import asyncio
asyncio.run(twtmain.calculate('path/to/namelist.yaml'))
```

### Configuration (Namelist)

The YAML configuration file controls domain, time period, and downscaling parameters:

```yaml
# Domain definition (choose one):
domain_huc: '00000000'          # HUC ID (e.g., '12345678')
domain_bbox: [xmin, ymin, xmax, ymax]  # Bounding box coordinates
domain_latlon: [lat, lon]       # Point location

# Time period for water table data:
start_date: '2002-10-01'        # Start date (YYYY-MM-DD)
end_date: '2006-09-30'          # End date (YYYY-MM-DD)

# Downscaling and stream identification parameters:
facc_strm_threshold: 1000       # Flow accumulation threshold for stream channel initiation
dem_rez: 30                     # DEM resolution (meters) for topographic analysis
overwrite: False                # Recreate intermediate outputs
verbose: True                   # Enable detailed logging

# HydroFrame credentials (optional):
# hf_hydrodata_un: 'username'
# hf_hydrodata_pin: 'api_pin'
```

### Project Structure

**Core modules implement the downscaling pipeline**:

- **`twtmain.py`**: Main orchestration—coordinates data retrieval and downscaling workflow
- **`twtdomain.py`**: Domain definition and spatial clipping
- **`twtwt.py`**: Coarse water table depth data retrieval from HydroFrame/ParFlow
- **`twttopo.py`**: High-resolution DEM acquisition and topographic index computation (TWI, flow accumulation)
- **`twtsoils.py`**: Soil transmissivity and texture data retrieval and processing
- **`twtcalc.py`**: **Core downscaling and stream classification logic** — applies topmodel-based methods to refine water table depth using terrain and soil properties
- **`twtnamelist.py`**: Configuration file parsing
- **`twtmapfolium.py`**: Visualization using Folium maps

## Examples

Three example projects are provided in the `examples/` directory:

### 1. al_app_plateau
- Alabama Appalachian Plateau region
- Pre-processed domain available
- 5-year water table depth simulation (2002-2006)

### 2. buckhorn
- Buckhorn watershed test case
- Includes TWI and flow accumulation rasters
- Validation notebooks for comparison

### 3. conus1
- Continental US (CONUS) domain
- Multiple HUC levels (HUC6, HUC8, HUC12)
- Large-scale demonstration and subdomain processing

To run an example:
```bash
cd examples/al_app_plateau/execution
python run.py
```

## Testing

Run the test suite using pytest:

```bash
pytest                  # Run all tests
pytest tests/test_twtcalc.py  # Run specific test file
pytest -v              # Verbose output
```

**Test Coverage**: 
- Unit tests for individual modules
- Mock tests for external API calls
- 17 tests total, all passing

## Output Structure

After running an analysis, outputs are organized as:

```
output/
├── raw/              # Intermediate downscaling products
│   ├── twi.tiff      # Topographic Wetness Index (dimensionless terrain metric)
│   ├── twi_mean.tiff # Mean TWI by soil map unit
│   ├── facc_ncells.tiff # Flow accumulation (cells)
│   ├── facc_sca.tiff # Specific Catchment Area (m²/m)
│   ├── dem.tiff # Unmodified DEM
│   ├── dem_breached.tiff # hydro-conditioned DEM
│   ├── slope.tiff    # Terrain slope
│   ├── soil_texture.gpkg # Downsampled soil data
│   ├── soil_transmissivity.gpkg # Soil transmissivity (saturated conductivity × thickness)
│   ├── stream_mask.tiff # Binary stream channel mask
│   └── ...
└── summary/          # Final downscaling results
    ├── groundwater_depth_downscaled.tiff # Refined water table depth at fine scale
    ├── stream_classification.gpkg # Stream reaches classified by permanence
    ├── water_surface_intersection.tiff # Predicted groundwater-surface intersections
    └── analysis_summary.json # Summary statistics
```

**Key outputs explained**:
- **TWI**: Topographic Wetness Index used in downscaling (higher values = wetter convergent areas)
- **groundwater_depth_downscaled**: Water table depth refined from coarse resolution to fine scale using topmodel assumptions
- **stream_classification**: Reaches classified as perennial (water table > surface), intermittent, or ephemeral based on downscaling predictions
- **water_surface_intersection**: Probability or certainty that groundwater intersects surface

## Data Requirements

**Coarse-Resolution Groundwater Simulations/Observations** (the base for downscaling):
- Water table depth grids (e.g., 1 km resolution typical from ParFlow-CLM)
- Time-series or snapshot data (e.g., daily, monthly average water table depth)
- Regional or continental coverage (e.g., CONUS from HydroFrame)

**High-Resolution Topographic Data** (enables spatial downscaling):
- Digital Elevation Model (DEM) at fine resolution (typically 30 m from USGS 3DEP)
- Used to compute TWI and flow accumulation for terrain-based downscaling

**Soil Property Data** (controls subsurface flow and transmissivity):
- Soil texture and transmissivity (Ks × thickness) from SSURGO/gNATSGO databases
- Mapped to soil map units across domain

**Stream Network Reference** (for validation and classification):
- NHDPlus flowline networks
- Used to identify stream channels and classify reach permanence

**Data Acquisition**:
The tool can work with pre-existing files placed in `input/` directories, or automatically retrieve data from:
- **HydroFrame database**: Coarse water table depth grids
- **3DEP**: High-resolution DEMs
- **NHD+**: Stream flowline networks
- **SSURGO/gNATSGO**: Soil properties via NRCS Web Soil Survey or local GIS data

## Known Limitations

**Data Availability**:
- Parflow-CLM water table depth observations/simulations limited to specific model domains and periods (e.g., ParFlow CONUS1 2002-2006)
- HydroFrame data downloads require valid API credentials
- DEM resolution and availability depend on 3DEP coverage in region

**Downscaling Assumptions**:
- Topmodel-based downscaling assumes terrain-driven water table variability within grid cells
- Assumes transmissivity is spatially uniform or follows soil texture patterns
- Does not account for groundwater flow barriers (e.g., bedrock fractures, clay aquitards)
- Results are sensitive to TWI computation methods and DEM resolution
- Downscaling may not capture sub-grid heterogeneity in highly complex terrain

**Computational**:
- Large CONUS domains require significant disk space and processing time
- Processing speed depends on DEM resolution and domain size

## Future Development

- **Observations Integration**: Support for USGS and NWIS water table depth observations in addition to simulations
- **Uncertainty Quantification**: Propagate uncertainty from coarse simulations through downscaling
- **Enhanced Transmissivity Models**: Incorporate 3D soil property variation and bedrock depth
- **Cloud Optimization**: Cloud-optimized GeoTIFF support and cloud-based processing for large datasets

## Notes

- Hydro-conditioned DEM created using [whitebox least-cost breaching](https://www.whiteboxgeo.com/manuals/api/python/api-tools-reference.html?highlight=least%20cost%20fill#breach_depressions_least_cost)

## Contact

For questions or issues, please contact:

**Grey Evenson**  
evenson.grey@epa.gov

Hydrological and Aquatic Simulation and Analysis Branch  
Applied Science and Environmental Methods Division  
Office of Applied Science and Environmental Solutions  
US Environmental Protection Agency  
Cincinnati, OH

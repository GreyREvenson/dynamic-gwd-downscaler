import logging
import os
import sys
from pathlib import Path
import rasterio
import yaml
import datetime
import numpy

logger = logging.getLogger(__name__)

class Namelist:

    class DirectoryNames:
        project                 = None
        input                   = None
        output                  = None
        wtd_raw                 = None
        wtd_resampled           = None
        output_raw              = None
        output_summary          = None

    class Time:
        start_date              = None
        end_date                = None
        datetime_dim            = None

    class FileNames:
        domain                  = None
        domain_buf              = None
        twi                     = None
        twi_mean                = None
        soil_texture            = None
        soil_transmissivity     = None
        nhdp                    = None
        dem                     = None
        dem_breached            = None
        dem_namelist_input      = None
        facc_ncells             = None
        facc_sca                = None
        stream_mask             = None
        slope                   = None
        conus1_domain           = None
        soil_texture_namelist_input = None

    class Options:
        domain_hucid            = None    
        domain_bbox             = None
        domain_latlon           = None
        overwrite               = False
        verbose                 = False
        verbose_wbe             = False
        resample_method         = None
        facc_strm_thresh_ncells = 1000
        facc_strm_thresh_sca    = None
        write_wtd_resampled     = False
        hf_hydrodata_un         = None
        hf_hydrodata_pin        = None
        dem_rez                 = None
        conus1_download_dir     = None
        domain_buf_dist_m       = 1000
        usedask                 = False

    def __init__(self,filename:str):
        self._init_vars()
        self._set_user_inputs(filename)
        self._set_names()

    def _init_vars(self):
        self.dirnames = Namelist.DirectoryNames()
        self.fnames   = Namelist.FileNames()
        self.options  = Namelist.Options()
        self.time     = Namelist.Time()

    def _set_names(self):
        self._set_d_names()
        self._set_f_names()

    def _set_d_names(self):
        self.dirnames.input             = self.dirnames.project / 'input'
        self.dirnames.output            = self.dirnames.project / 'output'
        self.dirnames.wtd_raw           = self.dirnames.input / 'wtd' / 'raw'
        self.dirnames.wtd_resampled     = self.dirnames.input / 'wtd' / 'resampled'
        self.dirnames.output_raw        = self.dirnames.output / 'raw'
        self.dirnames.output_summary    = self.dirnames.output / 'summary'

    def _set_f_names(self):
        self.fnames.domain              = self.dirnames.input / 'domain.gpkg'
        self.fnames.domain_buf          = self.dirnames.input / 'domain_buf.gpkg'
        self.fnames.dem                 = self.dirnames.input / 'dem.tiff'
        self.fnames.dem_breached        = self.dirnames.input / 'dem_breached.tiff'
        self.fnames.twi                 = self.dirnames.input / 'twi.tiff'
        self.fnames.twi_mean            = self.dirnames.input / 'twi_mean.tiff'
        self.fnames.soil_texture        = self.dirnames.input / 'soil_texture.gpkg'
        self.fnames.soil_transmissivity = self.dirnames.input / 'soil_transmissivity.tiff'
        self.fnames.facc_ncells         = self.dirnames.input / 'facc_ncells.tiff'
        self.fnames.facc_sca            = self.dirnames.input / 'facc_sca.tiff'
        self.fnames.stream_mask         = self.dirnames.input / 'stream_mask.tiff'
        self.fnames.slope               = self.dirnames.input / 'slope.tiff'
        self.fnames.nhdp                = self.dirnames.input / 'nhdp_flowlines.gpkg'

    def read_inputyaml(self,fname:str):
        self.fnames.namlistyaml = Path(fname)
        with self.fnames.namlistyaml.open('r') as yamlf:
            try:
                data = yaml.safe_load(yamlf)
            except yaml.YAMLError as yerr:
                raise RuntimeError(f"Failed to parse YAML file {self.fnames.namlistyaml}: {yerr}")
        if data is None:
            raise ValueError(f"YAML file {self.fnames.namlistyaml} is empty or invalid")
        return data

    def _set_user_inputs(self,fname_yaml_input:str):
        """Set variables using read-in values"""
        self.dirnames.project = Path(fname_yaml_input).resolve().parent
        logger.debug(f'project directory set to: {self.dirnames.project}')
        userinput = self.read_inputyaml(fname_yaml_input)
        names_domain = ['domain_huc', 'domain_latlon', 'domain_bbox']
        if not any(name in userinput for name in names_domain):
            logger.warning(f"At least one of the required domain variables ({', '.join(names_domain)}) not found {fname_yaml_input}")
        if 'domain_huc' in userinput:
            self.options.domain_hucid = userinput['domain_huc']
        if 'domain_latlon' in userinput:
            self.options.domain_latlon = userinput['domain_latlon']
        if 'domain_bbox' in userinput:
            self.options.domain_bbox = userinput['domain_bbox']
        if 'start_date' not in userinput:
            raise ValueError(f'ERROR required variable start_date not found {fname_yaml_input}')
        try:
            year, month, day = [int(p) for p in str(userinput['start_date']).split('-')]
            self.time.start_date = datetime.datetime(year=year, month=month, day=day)
        except Exception as e:
            raise ValueError(f'ERROR invalid start date {userinput["start_date"]} in {fname_yaml_input}: {e}')
        if 'end_date' not in userinput:
            raise ValueError(f'ERROR required variable end_date not found {fname_yaml_input}')
        try:
            year, month, day = [int(p) for p in str(userinput['end_date']).split('-')]
            self.time.end_date = datetime.datetime(year=year, month=month, day=day)
        except Exception as e:
            raise ValueError(f'ERROR invalid end date {userinput["end_date"]} in {fname_yaml_input}: {e}')
        dt_dim = []
        idt = self.time.start_date
        while idt <= self.time.end_date:
            dt_dim.append(idt)
            idt += datetime.timedelta(days=1)
        self.time.datetime_dim = numpy.array(dt_dim)
        if 'facc_strm_threshold_ncells' in userinput:
            try:
                self.options.facc_strm_thresh_ncells = int(userinput['facc_strm_threshold_ncells'])
            except ValueError:
                raise ValueError(f'ERROR invalid entry for facc_strm_threshold_ncells of {userinput["facc_strm_threshold_ncells"]} in {fname_yaml_input}')
        if 'facc_strm_threshold_sca' in userinput:
            try:
                self.options.facc_strm_thresh_sca = int(userinput['facc_strm_threshold_sca'])
            except ValueError:
                raise ValueError(f'ERROR invalid entry for facc_strm_threshold_sca of {userinput["facc_strm_threshold_sca"]} in {fname_yaml_input}')
        self.options.overwrite = str(userinput.get('overwrite', '')).upper().find('TRUE') != -1
        self.options.verbose = str(userinput.get('verbose', '')).upper().find('TRUE') != -1
        if 'wtd_resample_method' in userinput:
            method = str(userinput['wtd_resample_method']).lower()
            if 'bilinear' in method:
                self.options.resample_method = rasterio.enums.Resampling.bilinear
            elif 'cubic' in method:
                self.options.resample_method = rasterio.enums.Resampling.cubic
            elif 'nearest' in method:
                self.options.resample_method = rasterio.enums.Resampling.nearest
            else:
                raise ValueError(f'ERROR invalid wtd resample method {userinput["wtd_resample_method"]} in {fname_yaml_input}')
        else:
            self.options.resample_method = rasterio.enums.Resampling.bilinear
        if 'hf_hydrodata_un' in userinput:
            self.options.hf_hydrodata_un = userinput['hf_hydrodata_un']
        if 'hf_hydrodata_pin' in userinput:
            self.options.hf_hydrodata_pin = userinput['hf_hydrodata_pin']
        self.options.write_wtd_resampled = str(userinput.get('write_wtd_resampled', '')).upper().find('TRUE') != -1
        if 'dem_rez' in userinput:
            try:
                self.options.dem_rez = float(userinput['dem_rez'])
            except ValueError:
                raise ValueError(f'ERROR invalid dem_rez {userinput["dem_rez"]} in {fname_yaml_input}')
        self.options.verbose_wbe = str(userinput.get('verbose_wbe', '')).upper().find('TRUE') != -1
        if 'conus1_download_dir' in userinput:
            self.options.conus1_download_dir = Path(userinput['conus1_download_dir'])
            if not self.options.conus1_download_dir.is_dir():
                raise FileNotFoundError(f'ERROR specified conus1 download directory {self.options.conus1_download_dir} does not exist {fname_yaml_input}')
        if 'conus1_domain' in userinput:
            self.fnames.conus1_domain = Path(userinput['conus1_domain'])
            if not self.fnames.conus1_domain.is_file():
                raise FileNotFoundError(f'ERROR specified conus1 domain file {self.fnames.conus1_domain} does not exist {fname_yaml_input}')
        self.options.usedask = str(userinput.get('usedask', '')).upper().find('TRUE') != -1
        if 'dem' in userinput:
            self.fnames.dem_namelist_input = Path(userinput['dem'])
            if not self.fnames.dem_namelist_input.is_file():
                raise FileNotFoundError(f'ERROR specified dem file {self.fnames.dem_namelist_input} does not exist {fname_yaml_input}')
        if 'soil_texture' in userinput:
            self.fnames.soil_texture_namelist_input = Path(userinput['soil_texture'])
            if not self.fnames.soil_texture_namelist_input.is_file():
                raise FileNotFoundError(f'ERROR specified soil texture file {self.fnames.soil_texture_namelist_input} does not exist {fname_yaml_input}')

        
import os
import asyncio
import datetime
import logging

import twtnamelist
import twtdomain
import twtwt
import twttopo
import twtsoils
import twtcalc
import hf_hydrodata

logger = logging.getLogger(__name__)

async def calculate(fname_namelist):
    # Load inputs
    fname_namelist = os.path.abspath(str(fname_namelist))
    namelist = twtnamelist.Namelist(filename=fname_namelist)

    # Domain
    kwargs = {
        'fname_domain': namelist.fnames.domain,
        'verbose': namelist.options.verbose,
        'overwrite': namelist.options.overwrite,
        'conus1_domain': namelist.fnames.conus1_domain
    }
    if namelist.options.domain_hucid is not None:
        kwargs.update({'domain_hucid': namelist.options.domain_hucid})
    elif namelist.options.domain_latlon is not None:
        kwargs.update({'domain_latlon': namelist.options.domain_latlon})
    elif namelist.options.domain_bbox is not None:
        kwargs.update({'domain_bbox': namelist.options.domain_bbox})
    else:
        if not os.path.isfile(namelist.fnames.domain):
            raise ValueError(f'calculate could not set domain from namelist options, and domain file {namelist.fnames.domain} does not exist')
    domain = twtdomain.set_domain(**kwargs)

    # Domain buffer
    kwargs = {
        'domain': domain,
        'fname_domain_buf': namelist.fnames.domain_buf,
        'buf_dist_m': namelist.options.domain_buf_dist_m,
        'verbose': namelist.options.verbose,
        'overwrite': namelist.options.overwrite
    }
    domain_buf = twtdomain.set_domain_buf(**kwargs)

    # Water table data: download or use provided
    kwargs = {
        'dt_start': namelist.time.start_date,
        'dt_end': namelist.time.end_date,
        'dir_wtd': namelist.dirnames.wtd_raw,
        'verbose': namelist.options.verbose
    }
    wtd_get_flag = twtwt.set_wtd_get_flag(**kwargs)
    if namelist.options.verbose and not wtd_get_flag:
        logger.info(f'found water table depth data for all dates in range in {namelist.dirnames.wtd_raw}')
    if wtd_get_flag and namelist.options.conus1_download_dir is None:
        kwargs = {
            'dt_start': namelist.time.start_date,
            'dt_end': namelist.time.end_date,
            'dir_wtd': namelist.dirnames.wtd_raw,
            'domain': domain_buf,
            'verbose': namelist.options.verbose,
            'overwrite': namelist.options.overwrite
        }
        hf_hydrodata.register_api_pin(namelist.options.hf_hydrodata_un, namelist.options.hf_hydrodata_pin)
        twtwt.download_hydroframe_data(**kwargs)
    elif wtd_get_flag and namelist.options.conus1_download_dir is not None:
        kwargs = {
            'dt_start': namelist.time.start_date,
            'dt_end': namelist.time.end_date,
            'wtd_in_dir': namelist.options.conus1_download_dir,
            'wtd_out_dir': namelist.dirnames.wtd_raw,
            'domain': domain_buf,
            'verbose': namelist.options.verbose,
            'overwrite': namelist.options.overwrite
        }
        twtwt.break_conus1_tiffs(**kwargs)

    # DEM: break or download
    if namelist.fnames.dem_namelist_input is not None and os.path.isfile(namelist.fnames.dem_namelist_input):
        kwargs = {
            'fname_dem_parent': namelist.fnames.dem_namelist_input,
            'fname_dem_child': namelist.fnames.dem,
            'fname_boundary': namelist.fnames.domain,
            'verbose': namelist.options.verbose,
            'overwrite': namelist.options.overwrite
        }
        twttopo.break_dem(**kwargs)
    else:
        kwargs = {
            'domain': domain,
            'dem_rez': namelist.options.dem_rez,
            'fname_dem': namelist.fnames.dem,
            'verbose': namelist.options.verbose,
            'overwrite': namelist.options.overwrite
        }
        try:
            await asyncio.wait_for(twttopo.download_dem(**kwargs), timeout=3600)
        except asyncio.TimeoutError:
            raise Exception(f"ERROR: DEM download timed out after 1 hour for {namelist.fnames.dem}. Consider downloading the DEM manually and providing the path in the namelist to avoid this issue.")
        except Exception as e:
            raise Exception(f"ERROR: DEM download failed for {namelist.fnames.dem} with error {e}. Consider downloading the DEM manually and providing the path in the namelist to avoid this issue.")
        if not os.path.isfile(namelist.fnames.dem):
            raise Exception(f"ERROR: DEM download failed. {namelist.fnames.dem} does not exist. Consider downloading the DEM manually and providing the path in the namelist to avoid this issue.")

    # Breach, flow accumulation, slope, TWI, mean TWI
    twttopo.breach_dem(
        fname_dem_breached=namelist.fnames.dem_breached,
        fname_dem=namelist.fnames.dem,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )
    twttopo.set_flow_acc(
        fname_dem_breached=namelist.fnames.dem_breached,
        fname_facc_ncells=namelist.fnames.facc_ncells,
        fname_facc_sca=namelist.fnames.facc_sca,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )
    twttopo.calc_stream_mask(
        fname_facc_ncells=namelist.fnames.facc_ncells,
        facc_threshold_ncells=namelist.options.facc_strm_thresh_ncells,
        fname_strm_mask=namelist.fnames.stream_mask,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )
    twttopo.calc_slope(
        fname_dem_breached=namelist.fnames.dem_breached,
        fname_slope=namelist.fnames.slope,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )
    twttopo.calc_twi(
        fname_facc_sca=namelist.fnames.facc_sca,
        fname_slope=namelist.fnames.slope,
        fname_twi=namelist.fnames.twi,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )
    twttopo.calc_twi_mean(
        fname_twi_mean=namelist.fnames.twi_mean,
        fname_twi=namelist.fnames.twi,
        wtd_raw_dir=namelist.dirnames.wtd_raw,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )

    # Soil texture/transmissivity
    if namelist.fnames.soil_texture_namelist_input is not None and os.path.isfile(namelist.fnames.soil_texture_namelist_input):
        twtsoils.break_soil_texture(
            fname_texture_parent=namelist.fnames.soil_texture_namelist_input,
            fname_texture_child=namelist.fnames.soil_texture,
            fname_domain=namelist.fnames.domain,
            verbose=namelist.options.verbose,
            overwrite=namelist.options.overwrite
        )
    else:
        try:
            await asyncio.wait_for(
                twtsoils.download_soil_texture(
                    fname_texture=namelist.fnames.soil_texture,
                    domain=domain,
                    domain_buf=domain_buf,
                    verbose=namelist.options.verbose,
                    overwrite=namelist.options.overwrite
                ),
                timeout=900
            )
        except asyncio.TimeoutError:
            raise Exception(f"ERROR: Soil texture download timed out after 15 minutes for {namelist.fnames.soil_texture}. Consider downloading the soil texture manually and providing the path in the namelist to avoid this issue.")

    twtsoils.set_soil_transmissivity(
        fname_texture=namelist.fnames.soil_texture,
        fname_transmissivity=namelist.fnames.soil_transmissivity,
        fname_dem=namelist.fnames.dem_breached,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )

    # Streams (NHD)
    try:
        twttopo.set_streams(
            fname_streams=namelist.fnames.nhdp,
            domain=domain,
            verbose=namelist.options.verbose,
            overwrite=namelist.options.overwrite
        )
    except Exception as e:
        logger.warning(f'failed to get NHD stream lines with error {e}')

    # Inundation daily
    twtcalc.calculate_inundation(
        dt_start=namelist.time.start_date,
        dt_end=namelist.time.end_date,
        wtd_raw_dir=namelist.dirnames.wtd_raw,
        inundation_out_dir=namelist.dirnames.output_raw,
        fname_soil_trans=namelist.fnames.soil_transmissivity,
        fname_twi=namelist.fnames.twi,
        fname_twi_mean=namelist.fnames.twi_mean,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )

    # Inundation summary (inclusive end)
    fname_perc_inundated = twtcalc.calculate_summary_perc_inundated(
        dt_start=namelist.time.start_date,
        dt_end=namelist.time.end_date,
        inundation_raw_dir=namelist.dirnames.output_raw,
        inundation_summary_dir=namelist.dirnames.output_summary,
        fname_dem=namelist.fnames.dem_breached,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )

    # Stream permanence
    twtcalc.calculate_strm_permanence(
        fname_perc_inundation=fname_perc_inundated,
        fname_strm_mask=namelist.fnames.stream_mask,
        verbose=namelist.options.verbose,
        overwrite=namelist.options.overwrite
    )
    return None

def calculate_async_wrapper(fname_namelist: str):
    """async wrapper for calculation; also log to a verbose file."""
    fname_verbose = os.path.join(
        os.path.dirname(fname_namelist),
        f"verbose_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
    )
    logger.info(f'processing {fname_namelist} {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    handler = logging.FileHandler(fname_verbose, mode='a', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        asyncio.run(calculate(fname_namelist))
    except Exception:
        logger.exception('Calculation failed')
    finally:
        root_logger.removeHandler(handler)
        handler.close()

    logger.info(f'ended {fname_namelist} {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    return
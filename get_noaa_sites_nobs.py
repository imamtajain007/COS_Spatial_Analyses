import os
import numpy as np
from datetime import datetime

from stem_pytools import noaa_ocs


class Consts(object):
    """Class to contain several constants useful for the climatological
    bounds

    ARGS:

    fname_griddesc (string): full path to the Models-3 I/O API
        GRIDDESC file describing the STEM domain grid.  Default is
        $HOME/Code/Regrid/GEOS-Chem_Regrid/GRIDDESC_GC
    noaa_dir (str): full path to the directory containing NOAA
        observation files.  Default is $PROJ/Data/NOAA_95244993
    topo_fname (string): full path to the Models-3 I/O API topography
        file.  Default is $SARIKA_INPUT/TOPO-124x124.nc
    wrf_height_fname (string): full path to the Models-3 I/O API WRF height
        file.  Default is $SARIKA_INPUT/wrfheight-124x124-22levs.nc

    ATTRIBUTES:

    fname_griddesc (string): full path to the Models-3 I/O API
        GRIDDESC file describing the STEM domain grid.
    noaa_dir (str): full path to the directory containing NOAA
        observation files.  Default is $PROJ/Data/NOAA_95244993
    topo_fname (string): full path to the Models-3 I/O API topography
        file.  Default is $SARIKA_INPUT/TOPO-124x124.nc
    wrf_height_fname (string): full path to the Models-3 I/O API WRF height
        file.  Default is $SARIKA_INPUT/wrfheight-124x124-22levs.nc
    pptv_2_molecules_m3 (real) = conversion factor for converting
        parts per trillion by volume (pptv) to molecules per m^3
    pptv_2_ppbv = conversion factor for converting parts per trillion
        by volume (pptv) to parts per billion by volume (ppbv)
    """

    def __init__(self,
                 fname_griddesc=os.path.join(os.environ['HOME'],
                                             'Code', 'Regrid',
                                             'GEOS-Chem_Regrid',
                                             'GRIDDESC_GC'),
                 noaa_dir=os.path.join(
                     os.getenv('PROJ'), 'Data', 'NOAA_95244993')):
        self.fname_griddesc = fname_griddesc
        self.noaa_dir = noaa_dir
        self.topo_fname = os.path.join(os.getenv('SARIKA_INPUT'),
                                       'TOPO-124x124.nc')
        self.wrfheight_fname = os.path.join(os.getenv('SARIKA_INPUT'),
                                            'wrfheight-124x124-22levs.nc')
        self.pptv_2_molecules_m3 = 1e-12
        self.pptv_2_ppbv = 1e-3


def todate(x):
    # from
    # http://stackoverflow.com/questions/29753060/how-to-convert-numpy-datetime64-into-datetime
    return datetime.fromtimestamp(x.astype('O')/1e9).date()


def count_unique_dates(gb):
    print 'site_code, unique Jul/Aug dates (all)'
    for this_group in gb:
        x = list(this_group)[1].datet.values
        unique_dates = np.unique(map(todate, x))
        print this_group[0], unique_dates.size

if __name__ == "__main__":

    sites = noaa_ocs.get_all_NOAA_airborne_data(Consts().noaa_dir)
    jul_aug = sites.obs.query('sample_month in [7, 8]')
    gb = jul_aug.groupby(by=('sample_site_code',))
    obs_count = gb.size
    count_unique_dates(gb)
    # obs_count = jul_aug.groupby(by=('sample_site_code',)).agg(
    #     {'sample_site_code': np.size,
    #      'datet': lambda x: todate(x).date()})
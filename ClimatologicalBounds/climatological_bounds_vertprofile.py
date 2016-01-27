import matplotlib
matplotlib.use('AGG')
import matplotlib.pyplot as plt
import os
import os.path
import numpy as np
import netCDF4
import pandas as pd
import brewer2mpl

from IOAPIpytools.ioapi_pytools import boundaries_from_csv
from stem_pytools import noaa_ocs
from stem_pytools import domain


def rm_nan(arr):
    """remove NaNs from a numpy array.  Return a flattened (i.e. 1-D)
    array containing all non-NaN values from arr.
    """
    return(arr[np.isfinite(arr)].flatten())


class site_clim_mean(object):
    """class to calculate climatological mean vertical OCS profile for
    a NOAA observation site.
    """

    def __init__(self, sitecode, alt_bin_size=1000, noaa_dir=None):
        """class constructor.

        ARGS:
        alt_bin_size (int): size of bins to group observation
            altitudes into (meters). Default is 1000 m.
        noaa_dir (str): full path to the directory containing NOAA
            observation files.  Default is $PROJ/Data/NOAA_95244993
        """

        if noaa_dir is None:
            noaa_dir = os.path.join(os.getenv('PROJ'), 'Data', 'NOAA_95244993')
        fname = os.path.join(
            noaa_dir,
            'ocs_{}_aircraft-pfp_1_hats_event.txt'.format(sitecode.lower()))
        self.alt_bin_size = alt_bin_size
        self.sitecode = sitecode
        self.noaa_site = noaa_ocs.NOAA_OCS.parse_file(fname)
        self.z_obs_mean = None
        self.z_all_agl = None
        self.x_stem = None
        self.y_stem = None

        self.get_jul_aug()
        self.get_z_lev_mean()
        self.get_all_z_agl()

    def get_jul_aug(self):
        jul_aug = self.noaa_site.obs.query('sample_month in [7, 8]')
        self.noaa_site.obs = jul_aug

    def get_z_lev_mean(self):
        d = domain.STEM_Domain()
        topo_dir = os.path.join(os.getenv('PROJ'), 'Data',
                                'STEM_124x124_NA_inputs')
        self.noaa_site.get_stem_xy(d.get_lon(), d.get_lat())
        self.noaa_site.get_stem_z(
            topo_fname=os.path.join(topo_dir, 'TOPO-124x124.nc'),
            wrfheight_fname=os.path.join(topo_dir,
                                         'wrfheight-124x124-22levs.nc'))

        bin_min = 0  # bottom of bottom altitude bin, meters
        bin_max = 16000   # top of top altitude bin, meters
        bin_width = 1000  # size of altitude bins, meters
        bin_edges = np.arange(bin_min, bin_max, bin_width)
        self.noaa_site.obs['altitude_bin'] = np.digitize(
            self.noaa_site.obs.sample_altitude, bin_edges)
        groups = self.noaa_site.obs.groupby('altitude_bin')
        self.z_obs_mean = groups.mean()
        self.z_obs_mean = self.z_obs_mean[['x_stem', 'y_stem',
                                           'sample_altitude',
                                           'analysis_value']]
        # # change the index (which is the z level after the groupby to
        # # a column)
        self.z_obs_mean.reset_index(drop=True, inplace=True)

        # a handful of obs are in adjacent STEM cells, resulting in
        # non-integral mean x or y cell locations after the mean is
        # taken.  I think that rounding will pick the the "mode" x and
        # y and convert to an integer in one step
        self.x_stem = np.int(np.unique(np.round(self.z_obs_mean['x_stem']))[0])
        self.y_stem = np.int(np.unique(np.round(self.z_obs_mean['y_stem']))[0])
        self.z_obs_mean['x_stem'][:] = self.x_stem
        self.z_obs_mean['y_stem'][:] = self.y_stem

        self.z_obs_mean['z_stem'] = domain.get_stem_z_from_altitude(
            self.z_obs_mean.sample_altitude.values,
            stem_x=self.z_obs_mean.x_stem.values,
            stem_y=self.z_obs_mean.y_stem.values)

        self.z_obs_mean = self.z_obs_mean[['x_stem', 'y_stem',
                                           'z_stem', 'sample_altitude',
                                           'analysis_value']]
        # after binning some z levels end up with multiple
        # observations; average them together.
        self.z_obs_mean = self.z_obs_mean.groupby('z_stem').mean()
        self.z_obs_mean.reset_index(inplace=True)


    def get_all_z_agl(self):
        """get all STEM Z cell heights above ground level (from surface to
        top of domain).
        """
        topo_fname = os.path.join(os.getenv('SARIKA_INPUT'), 'TOPO-124x124.nc')
        wrfheight_fname = os.path.join(os.getenv('SARIKA_INPUT'),
                                       'wrfheight-124x124-22levs.nc')
        dom = domain.STEM_Domain(fname_topo=topo_fname)
        dom.get_STEMZ_height(wrfheight_fname)

        if self.z_obs_mean is None:
            self.get_z_lev_mean()
        n_zlevs = dom.agl.shape[0]

        z_all_agl = pd.DataFrame({'z_stem': np.arange(n_zlevs) + 1,
                                  'z_agl': dom.agl[:, self.x_stem,
                                                   self.y_stem]})
        self.z_obs_mean = pd.merge(z_all_agl, self.z_obs_mean,
                                   how='outer', sort=True)
        self.z_obs_mean['ocs_interp'] = self.z_obs_mean['analysis_value']

        idx_min = self.z_obs_mean.sample_altitude.idxmin()
        idx_max = self.z_obs_mean.sample_altitude.idxmax()
        ocs_interp = np.interp(
            self.z_obs_mean.z_agl,
            rm_nan(self.z_obs_mean.sample_altitude.values),
            rm_nan(self.z_obs_mean.analysis_value.values),
            left=self.z_obs_mean.analysis_value[idx_min],
            right=self.z_obs_mean.analysis_value[idx_max])
        nan_idx = np.where(np.isnan(self.z_obs_mean['analysis_value']))
        self.z_obs_mean['ocs_interp'].iloc[nan_idx] = ocs_interp[nan_idx]

    def get_col_vals(self):
        """return array containing all July-August mean vertical column
        values, with missing values filled.  Missing values
        between the lowest (in altitude) observed value and the
        highest (in altitude) observed value are interpolated;
        missing values outside that range are set to the
        higest/lowest (in altitude) observed value.
        """
        return(self.z_obs_mean.ocs_interp.values)


def plot_vertical_profiles(sites_list):
    """plot vertical profiles of each site in the argument sites_list
    """
    # ax.set_color_cycle(palettable.colorbrewer.qualitative.Dark2_8.mpl_colors)
    bmap = brewer2mpl.get_map('Set2', 'qualitative', 8)
    colors = bmap.mpl_colors
    matplotlib.rcParams['axes.color_cycle'] = colors
    fig, ax = plt.subplots(figsize=(10, 10))
    for i, this_site in enumerate(sites_list):
        ax.plot(this_site.z_obs_mean.ocs_interp,
                this_site.z_obs_mean.z_agl,
                label=this_site.sitecode,
                linewidth=2)
        ax.scatter(this_site.z_obs_mean.analysis_value,
                   this_site.z_obs_mean.z_agl,
                   marker='o', s=60, c=colors[i])
    ax.set_title(('NOAA sites Jul-Aug climatological mean [COS],'
                  ' {} m altitude bins'.format(sites_list[0].alt_bin_size)))
    ax.set_ylabel('height above ground (m)')
    ax.set_xlabel('[COS] (pptv)')
    ax.set_ylim([0, 16000])
    ax.legend(loc='best')
    fig.savefig('jul_aug_column_profiles.pdf')
    plt.close(fig)


if __name__ == "__main__":

    THD = site_clim_mean('THD')
    PFA = site_clim_mean('PFA')
    ESP = site_clim_mean('ESP')
    TGC = site_clim_mean('TGC')
    NHA = site_clim_mean('NHA')
    SCA = site_clim_mean('SCA')
    CMA = site_clim_mean('CMA')

    plot_vertical_profiles([THD, PFA, ESP, TGC, NHA, SCA, CMA])

def do_not_run():

    # starting in "lower left" with SW corner of domain and going counter
    # clockwise, pfa could do north and northern pacific, esp a little
    # lower on the pacific, and thd for rest of pacific and southwestern,
    # tgc for rest of south, and maybe an average of nha/sca/cma for the
    # east (which shouldn't matter).

    bounds = np.hstack((np.tile(TGC.get_col_vals(), 31),
                        np.tile(NHA.get_col_vals(), 31),
                        np.tile(CMA.get_col_vals(), 31),
                        np.tile(SCA.get_col_vals(), 31),
                        np.tile(PFA.get_col_vals(), 126 + 42),
                        np.tile(ESP.get_col_vals(), 42),
                        np.tile(THD.get_col_vals(), 42 + 42),
                        np.tile(TGC.get_col_vals(), 82)))

    pptv_2_molecules_m3 = 1e-12
    pptv_2_ppbv = 1e-3
    fname_csv = 'simple_climatological_bounds.csv'
    fname_bdy = 'climatological_COS_bdy_22levs_124x124.nc'
    fname_griddesc = os.path.join(os.environ['HOME'],
                                  'Code', 'Regrid',
                                  'GEOS-Chem_Regrid', 'GRIDDESC_GC')
    nlevs = 22
    fdesc = ("PFA for N and N pacific, ESP a little "
             "lower on the pacific, and THD for rest of pacific and "
             "SW, TGC for rest of S, and NHA/CMA/SCA mean for the E "
             "(which shouldn't matter).")
    # delete_if_exists(fname_csv)
    # np.savetxt(fname_csv,
    #            bounds.reshape([-1, 1]) * pptv_2_molecules_m3,
    #            delimiter=',')

    if True:
        boundaries_from_csv(fname_csv, fname_bdy,
                            fname_griddesc, 'ARCNAGRID', nlevs, fdesc)

        # place the climatological bounds in the dummy boundary file
        nc = netCDF4.Dataset(fname_bdy, 'a')
        nc.variables['CO2_TRACER1'][...] = (bounds[np.newaxis, ...] *
                                            pptv_2_ppbv)
        nc.close()

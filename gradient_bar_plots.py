import matplotlib
matplotlib.use('AGG')

import os
import os.path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import spatial_analysis_utilities as sau
from stem_pytools import noaa_ocs
from stem_pytools import domain
from stem_pytools import aqout_postprocess as aq
from stem_pytools import calc_drawdown
import map_grid
import draw_c3c4LRU_map


def get_STEM_cos_conc(cpickle_fname=None, const_bounds_cos=4.5e-10):
    """get dict of Jul-Aug mean COS drawdowns for each STEM gridcell.
    Adjust GEOS-Chem boundaries concentration to reflect the *change*
    in [COS] for the dynamic boundaries relative to the constant
    boundaries.

    :param cpickle_fname: path to a cpickle file of [COS] mean,
        standard deviation ,time stamps calculated from AQOUT files.
        That cpickle file will typically be the output of
        stem_pytools.aqout_postprocess.assemble_data.
    :param const_bounds_cos: the COS concentration of the constant
        boundaries; this value will be subtracted out of the GEOS-Chem
        boundaries [COS]
    """
    cos_conc_daily = aq.load_aqout_data(cpickle_fname)
    keys_to_remove = ['casa_gfed_pctm_bnd', 'casa_gfed_KV']
    for k in keys_to_remove:
        if k in cos_conc_daily['cos_mean']:
            del cos_conc_daily['cos_mean'][k]
            del cos_conc_daily['cos_std'][k]
            del cos_conc_daily['t'][k]

    cos_conc_daily['cos_mean'] = calculate_GCbounds_cos(
        cos_conc_daily['cos_mean'])
    # aggregate daily means to a single July-August mean
    cos_conc = cos_conc_daily['cos_mean']

    cos_conc.update((k, calc_drawdown.calc_STEM_COS_drawdown(v)) for
                    k, v in cos_conc.items())
    cos_conc.update((k, map_grid.daily_to_JulAug(v))
                    for k, v in cos_conc.items())
    return(cos_conc)


def assemble_bar_plot_data(
        cpickle_fname=os.path.join(os.getenv('SCRATCH'),
                                   '2015-11-16_all_runs.cpickle')):
    noaa_dir = sau.get_noaa_COS_data_path()
    noaa_ocs_dd, ocs_daily = sau.get_JA_site_mean_drawdown(noaa_dir)

    d = domain.STEM_Domain()
    stem_lon = d.get_lon()
    stem_lat = d.get_lat()

    (noaa_ocs_dd['stem_x'],
     noaa_ocs_dd['stem_y']) = noaa_ocs.find_nearest_stem_xy(
        noaa_ocs_dd.sample_longitude,
        noaa_ocs_dd.sample_latitude,
        stem_lon,
        stem_lat)

    stem_ocs_dd = get_STEM_cos_conc(cpickle_fname)

    # place model drawdowns into the data frame
    for k, v in stem_ocs_dd.items():
        noaa_ocs_dd[k] = stem_ocs_dd[k][noaa_ocs_dd['stem_x'],
                                        noaa_ocs_dd['stem_y']]

    return(noaa_ocs_dd)


def calculate_GCbounds_cos(stem_ocs_dd, const_bounds=4.5e-10):
    do_not_adjust = ['sample_latitude', 'sample_longitude', 'analysis_value',
                     'ocs_dd', 'stem_x', 'stem_y']
    print "start"

    GC_runs = {}
    for k in stem_ocs_dd.keys():
        if k not in do_not_adjust:
            key_GC = '{}{}'.format(k, ', GC')
            data_GC = (stem_ocs_dd[k] - const_bounds +
                       stem_ocs_dd['GEOSChem_bounds'])
            print 'adding {} to dict'.format(key_GC)
            GC_runs.update({key_GC: data_GC})
    stem_ocs_dd.update(GC_runs)
    return(stem_ocs_dd)


def calc_dynamic_boundary_effect(ocs_conc, const_bounds=4.5e-10):
    """Calculate drawdown enhancement or reduction because of dynamic
     boundaries relative to static boundary conditions.  Subtract out
     the 450 pptv static boundary condition from the dynamic
     boundaries STEM [COS] to isolate the impact of the dynamic
     boundaries vs static boundaries.  Static boundary of 450 pptv
     coupled with no surface COS flux must result in [COS] = 450 pptv
     at all places, times.

    :param ocs_conc: array of [OCS], molecules m-3
    :param const_bounds: [COS] for the constant boundary conditions
    """
    ocs_conc -= const_bounds
    return(ocs_conc)


def normalize_drawdown(ocs_dd,
                       norm_site='NHA',
                       vars=['ocs_dd',
                             'casa_gfed_161',
                             'casa_gfed_C4pctLRU',
                             'canibis_C4pctLRU',
                             'canibis_161']):
    """
    Within each drawdown "product", normalize to the NHA value.  NHA
    is chosen because it is the maximum observed drawdown in the NOAA
    observations.
    """
    for this_var in vars:
        ocs_dd[this_var] = ocs_dd[this_var] / ocs_dd[this_var][norm_site]

    return(ocs_dd)


def draw_box_plot(df, sites_list):
    sns.set_style('ticks')
    sns.set_context('paper')
    g = sns.factorplot(x="sample_site_code",
                       y="drawdown",
                       hue='variable',
                       data=df[df.sample_site_code.isin(sites_list)],
                       kind="point",
                       palette=sns.color_palette(
                           "cubehelix",
                           len(df.variable.unique())),
                       x_order=sites_list,
                       aspect=1.25)
    g.despine(offset=10, trim=True)
    g.set_axis_labels("site", "[OCS] drawdown (normalized to NHA)")

    return(g)


def rename_columns(df):
    """rename drawdown columns into more human-readable strings.  The
    motivation for this is that these column names eventually become
    the labels in the barplot legends, and changing them here seemed
    easier (though less elegant, perhaps) than digging through the
    seaborn facetgrid object to access and change the legend labels
    and then redrawing the plot.

    """
    columns_dict = {'ocs_dd': 'NOAA obs',
                    'casa_gfed_161': 'CASA-GFED3, LRU=1.61',
                    'MPI_C4pctLRU': 'MPI, LRU=C3/C4',
                    'canibis_161': 'Can-IBIS, LRU=1.61',
                    'casa_gfed_187': 'CASA-GFED3, LRU=1.87',
                    'kettle_C4pctLRU': 'Kettle, LRU=C3/C4',
                    'kettle_161': 'Kettle, LRU=1.61',
                    'casa_m15_161': 'CASA-m15, LRU=1.61',
                    'MPI_161': 'MPI, LRU=1.61',
                    'casa_gfed_C4pctLRU': 'CASA-GFED3, LRU=C3/C4',
                    'casa_gfed_135': 'CASA-GFED3, LRU=1.35',
                    'canibis_C4pctLRU': 'Can-IBIS, LRU=C3/C4',
                    'casa_m15_C4pctLRU': 'CASA-m15, LRU=C3/C4',
                    'Fsoil_Kettle': 'Kettle Fsoil',
                    'Fsoil_Hybrid5Feb': 'Hybrid Fsoil',
                    'GEOSChem_bounds': 'GEOS-Chem boundaries',
                    'SiB_mech': 'SiB, mechanistic canopy',
                    'SiB_calc': 'SiB, prescribed canopy'}
    for this_col in df.columns.values:
        if this_col in columns_dict.keys():
            df.rename(columns=lambda x: x.replace(this_col,
                                                  columns_dict[this_col]),
                      inplace=True)
            print "replaced {} with {}".format(this_col,
                                               columns_dict[this_col])
    return(df)


def draw_gradient_map(gradient_sites_dict):
    """draw a NOAA observation site "spatial gradient" over the C3/C4 LRU
    map
    """
    lru_map = draw_c3c4LRU_map.draw_map()
    site_coords = noaa_ocs.get_all_NOAA_airborne_data(
        sau.get_noaa_COS_data_path())
    site_coords = site_coords.get_sites_lats_lons()

    markers = ['x', 'o', 's']
    count = 0
    for grad_name, grad_sites in gradient_sites_dict.items():
        this_gradient = site_coords.loc[grad_sites]
        print(this_gradient)

        black = '#000000'
        # #1b9e77   turquoise color from colorbrewer2 Dark2 palette
        print('drawing: {}'.format(grad_name))
        lru_map.map.plot(this_gradient['sample_longitude'].values,
                         this_gradient['sample_latitude'].values,
                         color=black,
                         linewidth=2.0,
                         latlon=True)
        lru_map.map.scatter(this_gradient['sample_longitude'].values,
                            this_gradient['sample_latitude'].values,
                            latlon=True,
                            color=black,
                            marker=markers[count],
                            linewidth=3,
                            s=160,
                            facecolors='None')
        count = count + 1
    return(lru_map)


def plot_all_gradients(ocs_dd, plot_vars, fname_suffix):

    ocs_dd_long = pd.melt(ocs_dd.reset_index(),
                          id_vars=['sample_site_code'],
                          value_vars=plot_vars,
                          value_name='drawdown')

    tmpdir = os.getenv('SCRATCH')
    g = draw_box_plot(ocs_dd_long, gradients['east_coast'])
    plt.gcf().savefig(
        os.path.join(tmpdir, 'barplots',
                     'barplots_eastcoast{}.svg'.format(fname_suffix)))

    g = draw_box_plot(ocs_dd_long, gradients['wet_dry'])
    plt.gcf().savefig(
        os.path.join(tmpdir, 'barplots',
                     'barplots_wetdry{}.svg'.format(fname_suffix)))

    g = draw_box_plot(ocs_dd_long, gradients['mid_continent'])
    plt.gcf().savefig(
        os.path.join(tmpdir, 'barplots',
                     'barplots_midcontinent{}.svg'.format(fname_suffix)))


if __name__ == "__main__":

    try:
        gradients = {'wet_dry': ['CAR', 'BNE', 'WBI', 'OIL', 'NHA'],
                     'east_coast': ['NHA', 'CMA', 'SCA'],
                     'mid_continent': ['ETL', 'DND', 'LEF', 'WBI',
                                       'BNE', 'SGP', 'TGC']}

        ocs_dd = assemble_bar_plot_data()

        ocs_dd_new = rename_columns(ocs_dd)
        dd_vars = ['NOAA obs', 'GEOS-Chem boundaries', 'CASA-GFED3, LRU=1.61',
                   'MPI, LRU=C3/C4', 'Can-IBIS, LRU=1.61',
                   'CASA-GFED3, LRU=1.87', 'Kettle, LRU=C3/C4',
                   'Kettle, LRU=1.61',
                   'SiB, mechanistic canopy', 'SiB, prescribed canopy',
                   'Hybrid Fsoil',
                   'CASA-m15, LRU=1.61', 'Kettle Fsoil', 'MPI, LRU=1.61',
                   'CASA-GFED3, LRU=C3/C4', 'CASA-GFED3, LRU=1.35',
                   'Can-IBIS, LRU=C3/C4', 'CASA-m15, LRU=C3/C4']
        dd_vars_GC = [''.join([k, ', GC']) for k in dd_vars[2:]]
        dd_vars = dd_vars + dd_vars_GC
        ocs_dd_new = normalize_drawdown(ocs_dd_new, vars=dd_vars)

        vars = ['NOAA obs',
                'CASA-GFED3, LRU=1.61',
                'CASA-GFED3, LRU=C3/C4',
                'Can-IBIS, LRU=1.61',
                'Can-IBIS, LRU=C3/C4',
                'SiB, mechanistic canopy',
                'SiB, prescribed canopy']
        plot_all_gradients(ocs_dd_new, vars, '_C3C4')

        vars = ['NOAA obs',
                'CASA-GFED3, LRU=C3/C4',
                'CASA-GFED3, LRU=C3/C4, GC',
                'Can-IBIS, LRU=C3/C4',
                'Can-IBIS, LRU=C3/C4, GC',
                'SiB, mechanistic canopy',
                'SiB, prescribed canopy',
                'SiB, mechanistic canopy, GC',
                'SiB, prescribed canopy, GC']

        plot_all_gradients(ocs_dd_new, vars, '_GC')

        # gradient_map = draw_gradient_map(gradients)
        # gradient_map.fig.savefig(os.path.join(tmpdir, 'gradients_map.pdf'))
    finally:
        plt.close('all')

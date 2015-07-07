import os
import os.path
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime
import socket
import numpy as np
import warnings

import stem_pytools.ecampbell300_data_paths as edp
from stem_pytools import STEM_parsers as sp
from stem_pytools import aqout_postprocess as aq
from stem_pytools.na_map import NAMapFigure
from stem_pytools import calc_drawdown
from timutils import colormap_nlevs


def colorbar_from_cmap_norm(cmap, norm, cax, format, vals):
    """
    create a colorbar in a specified axis from a colormap instance, a
    norm instance, and an array of values.

    This is a workaround for a problem I'm having where calling
    plt.colorbar on different matplotlib.contour.QuadContourSet
    created from the same cmap and norm produces different colorbars,
    all of which are messed up in one way or another.  This function
    creates a dummy mappable and creates the colorbar from it.
    """
    dummy_scm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    dummy_scm.set_array(vals)
    cb = plt.colorbar(dummy_scm, cax=cax, format=format)
    return(cb)


def get_JulAug_total_flux(which_flux='GPP', models=None):
    """
    calculate total July and August flux for 124 by 124 STEM domain
    for either (1) gross primary productivity or (2) COS plant flux.
    Fluxes are calculated for one or more model runs according to the
    models input parameter.

    INPUT PARAMETERS:
    flux: string; {GPP} | fCOS
    models: tuple of strings; model runs for which to calculate
        fluxes.  All elements must be members of
        stem_pytools.ecampbell300_data_paths.get_runs().  If
        unspecified fluxes are calculated for all models listed by
        get_runs().

    RETURN VALUE:
    A dict of 124 by 124 arrays containing fluxes.  Dict keys are the
    model runs specified by models input parameter.  Units are
    petagrams C m-2 for GPP; picomoles m-2 for fCOS.
    """
    Jul1 = datetime(2008, 7, 1)
    Aug31 = datetime(2008, 8, 31, 23, 59, 59)

    runs = edp.get_runs()

    if models is None:
        models = runs.keys()
    # models.sort()

    flux_mean = {}
    for k in models:

        t0 = Jul1
        t1 = Aug31
        if which_flux is 'GPP':
            gross_flux_varname = sp.get_CO2grossflux_varname(runs[k].gpp_path)
            print 'reading ', runs[k].gpp_path
            flux = sp.parse_STEM_var(nc_fname=runs[k].gpp_path,
                                     varname=gross_flux_varname,
                                     t0=t0,
                                     t1=t1)
            # convert GPP from Kg C m-2 s-1 to umol m-2 s-1
            C_mol_per_g = (1.0 / 12.0107)
            umol_per_mol = 1e6
            g_per_kg = 1e3
            C_umol_per_kg = g_per_kg * C_mol_per_g * umol_per_mol
            flux['data'] = flux['data'] * C_umol_per_kg

        elif which_flux is 'fCOS':
            gross_flux_varname = 'cos'
            print 'reading ', runs[k].fcos_path
            flux = sp.parse_STEM_var(nc_fname=runs[k].fcos_path,
                                     varname=gross_flux_varname,
                                     t0=t0,
                                     t1=t1)
            # convert fCOS from mol m-2 s-1 to pmol m-2 s-1
            pmol_per_mol = 1e12
            flux['data'] = flux['data'] * pmol_per_mol
            print('model: {}; mean fCOS: {}\n'.format(k,
                                                      np.mean(flux['data'])))


        flux_mean[k] = flux['data'].squeeze().mean(axis=0)
        # flux_mean[k] = ma.masked_less(flux_mean[k], -1e20)
        if flux_mean[k].sum() < 0:
            flux_mean[k] = flux_mean[k] * -1.0
    return(flux_mean)


def draw_map(t_str,
             ax,
             data,
             vmin,
             vmax,
             cmap=plt.get_cmap('Blues'),
             norm=plt.normalize):

    map = NAMapFigure(t_str=t_str,
                      cb_axis=None,
                      map_axis=ax,
                      fast_or_pretty='fast')

    lon, lat, topo = sp.parse_STEM_coordinates(
        os.path.join(os.getenv('SARIKA_INPUT'), 'TOPO-124x124.nc'))
    cm = map.map.contourf(lon, lat,
                          data,
                          cmap=cmap,
                          latlon=True,
                          norm=norm,
                          vmin=vmin,
                          vmax=vmax)
    return(map, cm)


def setup_panel_array(nrows=3, ncols=6):
    """
    create a figure containing a matrix of axes with nrows rows and
    ncols columns, and one additional column of axes on the right hand
    side of smaller width suitable for a colorbar.

    OUTPUTS
    fig: matplotlib.figure.Figure object
    ax: nrows by ncols numpy array of
        matplotlib.axes._subplots.AxesSubplot objects
    cbar_ax: nrows by 1 numpy array of
        matplotlib.axes._subplots.AxesSubplot objects (for colorbars)
    """
    fig = plt.figure(figsize=(30, 15))
    # two gridspects - one for maps, one for colorbars
    gs_maps = gridspec.GridSpec(nrows, ncols)
    gs_maps.update(hspace=0.01, wspace=0.0, left=0.0, right=0.87)
    gs_cb = gridspec.GridSpec(nrows, 1)
    gs_cb.update(hspace=0.5, wspace=0.0, left=0.93, right=0.96)
    # arrays to hold axis handles
    ax = np.empty((nrows, ncols), dtype='object')
    cbar_ax = np.empty((nrows, 1), dtype='object')
    for this_row in range(nrows):
        for this_col in range(ncols):
            ax[this_row, this_col] = plt.subplot(
                gs_maps[this_row, this_col])
        cbar_ax[this_row] = plt.subplot(gs_cb[this_row, 0])
    return(fig, ax, cbar_ax)


def daily_to_JulAug(arr):
    """
    calculate surface average of a daily-aggregated 4-D array.

    INPUT PARAMETERS:
    arr: numpy ndarray of shape [62, 22, 124, 124] containing daily
    data for July and August (62 days) at 22 vertical levels for the
    124 by 124 STEM grid.

    OUTPUT PARAMETERS:
    arr_out: numpy ndarray of shape [124, 124] containing the mean
       value arr[:, 0, :, :].  That is, the mean value for all days at
       the surface.
    """
    arr_out = np.mean(arr[:, 0, ...], axis=0).squeeze()
    return(arr_out)


def assemble_data(aqout_path=None, get_dd=True, get_GPP=True, get_fCOS=True,
                  models=None):
    if get_dd:

        cos_conc_daily = aq.load_aqout_data(aqout_path)

        # aggregate daily means to a single July-August mean
        cos_conc = cos_conc_daily['cos_mean']

        cos_conc.update((k, calc_drawdown.calc_STEM_COS_drawdown(v)) for
                        k, v in cos_conc.items())
        cos_conc.update((k, daily_to_JulAug(v)) for k, v in cos_conc.items())
        # for k, v in cos_conc.items():
        #     print "{} drawdown array: {}".format(k, v.shape)
    else:
        cos_conc = None
    try:
        if get_GPP:
            gpp = get_JulAug_total_flux(which_flux='GPP', models=models)
        else:
            gpp = None
        if get_fCOS:
            fCOS = get_JulAug_total_flux(which_flux='fCOS', models=models)
        else:
            fCOS = None
    except:
        print('Unable to read GPP or FCOS, returning placeholder')
        gpp = cos_conc
        fCOS = cos_conc

    return(cos_conc, gpp, fCOS)


def draw_all_panels(cos, gpp, fCOS, models=None, models_str=None):

    if models is None:
        models = ['MPI_161',
                  'canibis_161',
                  'kettle_161',
                  'casa_m15_161',
                  'casa_gfed_161',
                  'casa_gfed_135',
                  'casa_gfed_187']
    if models_str is None:
        models_str = ['MPI',
                      'Can-IBIS',
                      'Kettle',
                      'CASA-m15',
                      'CASA-GFED3',
                      'CASA-GFED3',
                      'CASA-GFED3']

    gpp_vmin = 0.0
    gpp_vmax = np.percentile(np.dstack([gpp[k] for k in models]).flatten(), 99)
    #gpp_vmax = 0.45  # np.dstack([GPP[k] for k in models]).flatten().max()
    fcos_vmin = 0.0  # np.dstack([fCOS[k] for k in models]).flatten().min()
    # fcos_vmax = np.percentile(np.dstack([fCOS[k] for k in models]).flatten(), 99)
    fcos_vmax = np.dstack([fCOS[k] for k in models]).flatten().max()
    cos_vmin = 0.0
    cos_vmax = np.dstack([cos[k] for k in models]).flatten().max()
    # cos_vmax = np.percentile(np.dstack([cos[k] for k in models]).flatten(), 99)
    # cos_vmax = 80

    print('ceil(max): {}'.format(
        np.ceil(np.dstack([cos[k] for k in models]).flatten().max())))

    fig, ax, cbar_ax = setup_panel_array(nrows=3, ncols=len(models))
    map_objs = np.empty(ax.shape, dtype='object')

    gpp_cmap, gpp_norm = colormap_nlevs.setup_colormap(
        gpp_vmin, gpp_vmax,
        nlevs=6,
        cmap=plt.get_cmap('Greens'),
        extend='max')
    print('nlevs: {}'.format(5))

    mod_objs = edp.get_runs()
    for i, this_mod in enumerate(models):
        # plot GPP drawdown maps
        print("plotting {model}({k}) GPP".format(model=models_str[i],
                                                 k=models[i]))

        map_objs[0, i], cm = draw_map(
            t_str='{}, LRU={}'.format(models_str[i],
                                      mod_objs[this_mod].LRU),
            ax=ax[0, i],   # axis 0 is left-most on row 3
            data=gpp[this_mod],
            vmin=gpp_vmin,
            vmax=gpp_vmax,
            cmap=gpp_cmap,
            norm=gpp_norm)

    all_gpp = np.dstack([v for v in gpp.values()]).flatten()
    cb = colorbar_from_cmap_norm(gpp_cmap,
                                 gpp_norm,
                                 cbar_ax[0, 0],
                                 '%0.2f',
                                 all_gpp)
    t = cbar_ax[0, 0].set_title('GPP ($\mu$mol C m$^{-2}$ s$^{-1}$)\n')
    t.set_y(1.09)
    t.set_fontsize(20)

    fcos_cmap, fcos_norm = colormap_nlevs.setup_colormap(
        fcos_vmin, fcos_vmax,
        nlevs=6,
        cmap=plt.get_cmap('Blues'),
        extend='neither')
    for i, this_mod in enumerate(models):
        # plot fCOS drawdown maps
        print("plotting {model}({k}) GPP".format(model=models_str[i],
                                                 k=models[i]))
        map_objs[1, i], cm = draw_map(t_str=None,
                                      ax=ax[1, i],
                                      data=fCOS[this_mod],
                                      vmin=fcos_vmin,
                                      vmax=fcos_vmax,
                                      cmap=fcos_cmap,
                                      norm=fcos_norm)
    all_fcos = np.dstack([v for v in fCOS.values()]).flatten()
    cb = colorbar_from_cmap_norm(fcos_cmap,
                                 fcos_norm,
                                 cbar_ax[1, 0],
                                 '%d',
                                 all_fcos)
    t = cbar_ax[1, 0].set_title('$F_{plant}$ (pmol COS m$^{-2}$ s$^{-1})$')
    t.set_y(1.09)
    t.set_fontsize(20)

    cos_cmap, cos_norm = colormap_nlevs.setup_colormap(
        cos_vmin,
        cos_vmax,
        nlevs=6,
        cmap=plt.get_cmap('Oranges'),
        extend='max')
    for i, this_mod in enumerate(models):
        # plot [COS] drawdown maps
        print("plotting {model}({k}) GPP".format(model=models_str[i],
                                                 k=models[i]))
        this_cos = cos[this_mod]
        if any(this_cos.flatten() < 0):
            warnings.warn('COS drawdown values < 0.0 set to 0.0')
            this_cos[this_cos < 0] = 0
        map_objs[2, i], cm = draw_map(t_str=None,
                                      ax=ax[2, i],
                                      data=this_cos,
                                      vmin=cos_vmin,
                                      vmax=cos_vmax,
                                      cmap=cos_cmap,
                                      norm=cos_norm)

        all_dd = np.dstack([v for v in cos.values()]).flatten()
    cb = colorbar_from_cmap_norm(cos_cmap,
                                 cos_norm,
                                 cbar_ax[2, 0],
                                 '%d',
                                 all_dd)
    t = cbar_ax[2, 0].set_title('STEM [COS] drawdown (ppt)')
    t.set_y(1.09)
    t.set_fontsize(20)
    return(fig, map_objs, cos_cmap, cos_norm)


def map_grid_main(models=None, models_str=None, aqout_data=None):

    if aqout_data is None:
        if 'Timothys-MacBook-Air.local' in socket.gethostname():
            aqout_data = (os.path.join(os.getenv('HOME'), 'work', 'Data',
                                       'STEM', 'aq_out_data.cpickle'))
        else:
            aqout_data = os.path.join(os.getenv('HOME'), 'thilton', 'Data',
                                      'STEM', 'aq_out_data.cpickle')
    cos_dd, gpp, fCOS = assemble_data(aqout_data, models=models)

    fig, map_objs, cos_cmap, cos_norm = draw_all_panels(cos_dd, gpp, fCOS,
                                                        models, models_str)
    return(fig, map_objs, cos_cmap, cos_norm)

if __name__ == "__main__":
    runs = edp.get_runs()
    models = [k for k in runs.keys()]
    models_str = [v.model for v in runs.values()]
    # [fig, map_objs, cos_cmap, cos_norm] = map_grid_main(models, models_str)
    [fig, map_objs, cos_cmap, cos_norm] = map_grid_main(
        models=['canibis_161', 'kettle_161', 'casa_m15_161',
                'casa_gfed_161', 'casa_gfed_135', 'casa_gfed_187'],
        models_str=['Can-IBIS', 'Kettle', 'CASA-m15',
                    'CASA-GFED3', 'CASA-GFED3', 'CASA-GFED3'])
    fig.savefig('/tmp/BASC_fig.pdf')
    # [fig, map_objs, cos_cmap, cos_norm] = map_grid_main(
    #     models=['kettle_C4pctLRU', 'casa_gfed_C4pctLRU', 'MPI_C4pctLRU',
    #             'casa_m15_C4pctLRU', 'canibis_C4pctLRU'],
    #     models_str=['Kettle', 'CASA-GFED3', 'MPI', 'CASA-m15', 'Can-IBIS'])
    # fig.savefig('/tmp/BASC_fig.pdf')

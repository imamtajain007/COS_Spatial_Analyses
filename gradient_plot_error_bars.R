library(plotrix)  # for panes
library(RColorBrewer)
library(tidyr)  # could also use reshape2
library(boot)

get_obs_CI <- function(fname='./site_daily_dd.csv') {
    data <- read.csv(fname)

    sites <- split(data[['ocs_dd']],
                   f=data[, 'sample_site_code'])

    site_means <- lapply(sites, mean, na.rm=TRUE)
    site_stderr <- lapply(sites, std.error, na.rm=TRUE)
    obs <- data.frame(Fplant='NOAA obs',
                      site=names(site_means),
                      dd=unlist(site_means))
    obs[['ci_lo']] <- obs[['dd']] - unlist(site_stderr) * 1.96
    obs[['ci_hi']] <- obs[['dd']] + unlist(site_stderr) * 1.96
    row.names(obs) <- paste(row.names(obs), '.obs', sep='')
    return(obs)
}


merge_obs <- function(dfboot) {
    obs <- get_obs_CI()
    return(rbind(dfboot, obs))
}


##' human-readable names for COS Fplant models
##'
##' The data frame column names are more machine-oriented: no spaces, caps, etc.  These are nicer-looking strings for e.g. plot labels.
##' @title
##' @return list of strings. The data frame column labels are the list
##' names and the human-readble strings are the list elements.
##' @author Timothy W. Hilton
##' @export
human_readable_model_names <- function() {
    return(list(canibis_161='Can-IBIS, LRU=1.61',
                canibis_C4pctLRU= 'Can-IBIS, LRU=C3/C4',
                casa_gfed_161='CASA-GFED3, LRU=1.61',
                casa_gfed_C4pctLRU='CASA-GFED3, LRU=C3/C4',
                SiB_calc='SiB, LRU=1.61',
                SiB_mech='SiB, mechanistic',
                'NOAA obs'='Observed'))
}

##' offsets are calculated from an arbitrary center
##'
##' @title calculate horizontal offsets for N points with specified
##' interval
##' @param npoints (int): number of points in the sequence
##' @param gapwidth (float): space between consecutive points
##' @return numeric array containing npoints horizontal offset values
##' @author Timothy W. Hilton
##' @export
calculate_hoffset <- function(npoints, gapwidth) {
    width_total <- gapwidth * (npoints - 1)
    offsets <- seq(from=-(width_total / 2.0),
                   to=(width_total / 2.0),
                   length.out=npoints)
    return(offsets)
}

##' Normalize all rows in a data frame to the row with label
##' norm_site.  Helper function for ci_normalizer -- should not be
##' called by user.
##'
##'
##' @title normalize data frame rows (helper function)
##' @param dd (data frame): data frame containing drawdown
##' observations, labeled by site code (rows) and model (columns)
##' @param norm_site (string): site code (also the row label) of the
##' site to normalize against.
##' @return dd, normalized to site_code
##' @author Timothy W. Hilton
##' @export
row_normalizer <- function(dd, norm_site='NHA') {
    num_idx = unlist(lapply(dd, is.numeric))
    norm_data <- dd[norm_site, num_idx]
    for (i in seq(1, nrow(dd))) {
        dd[i, num_idx] <- dd[i, num_idx] / norm_data
    }
    return(dd)
}
##' Normalization is calculated relative to the specified site.  The
##' normalized confidence intervals are calculated by finding the
##' large span within dd and ci, and nomalizing against the specified
##' site.
##'
##' @title Normalize a data frame containing confidence intervals.
##' @param dd (data frame): data frame containing drawdown
##' observations, labeled by site code (rows) and model (columns)
##' @param ci (data frame): data frame containing drawdown confidence
##' intervals, labeled by site code (rows) and model (columns)
##' @param norm_site (string): site code (also the row label) of the
##' site to normalize against.
##' @return list labeled "dd", "ci_hi", and "ci_lo".  Each element
##' contains a data frame labeled by site code (rows) and model
##' (columns) containing normalized drawdowns, upper confidence
##' intervals, and lower confidence intervals, respectively.
##' @author Timothy W. Hilton
##' @export
ci_normalizer <- function(dd, ci, norm_site='NHA') {
    dd_hi <- dd + ci
    dd_lo <- dd - ci

    ddnorm <- row_normalizer(dd, norm_site)
    ddnorm_hi <- row_normalizer(dd_hi, norm_site)
    ddnorm_lo <- row_normalizer(dd_lo, norm_site)

    ci_hi <- ddnorm_hi - ddnorm
    ci_lo <- ddnorm - ddnorm_lo

    return(list(dd=ddnorm, ci_hi=ci_hi, ci_lo=ci_lo))
}

##' return a dummy set of random "observations" and "confidence
##' intervals" with the same row and column labels that the real data
##' will have.  Useful for testing the plotting code and whether
##' plotrix is able to produce the plot I want.
##'
##' @title generate a set of random "observations" and "confidence
##' intervals"
##' @return list with labels "dd", "ci".  Each element contains a data
##' frame labeled by site code (rows) and model (columns) containing
##' normalized drawdowns and confidence intervals, respectively.
##' @author Timothy W. Hilton
##' @export
dummy_data <- function() {
    models <- c('CASA-GFED3', 'Can-IBIS', 'SiB mech')
    site_names <- c('NHA', 'CMA', 'SCA', 'WBI', 'THD')
    marker_sequence <- c('o', 'x', 5, '+', '*')
    marker_sequence <- c(0, 1, 3, 4, 5)

    dd <- as.data.frame(matrix(runif(length(models) * length(site_names)),
                               ncol=length(models)),
                        row.names=models)
    ci <- as.data.frame(matrix(runif(length(models) * length(site_names)),
                               ncol=length(models)),
                        row.names=models)
    names(dd) <- models
    names(ci) <- models
    return(list(dd=dd, ci=ci))
}

##' .. produce a scatter plot with error bars of STEM model component
##' drawdowns at NOAA sites.
##'
##' .. content for \details{} ..
##' @title
##' @param df (data frame): NOAA sites in rows, model component
##' drawdowns (pptv) in columns
##' @param dd_col (string): name of the column in df containing
##' drawdown values
##' @param ci_hi_col (string): name of the column in df containing
##' upper confidence interval widths
##' @param ci_lo_col (string): name of the column in df containing
##' lower confidence interval widths
##' @param t_str (string): Main title string for the plot
##' @param site_names (vector of strings): Three letter site codes;
##' the gradient will be plotted in this order from left to right.
##' @param norm_site (string): row label of a site to normalize the
##' data against.  If unspecified (default), no normalization is
##' performed.
##' @param legend_loc (string): location for the legend (see "legend"
##' documentation).  'none' results in no legend.
##' @param panel_lab (string): panel label to appear in the upper-left
##' corner of the panel
##' @return
##' @author Timothy W. Hilton
##' @export
gradient_CI_plot <- function(df,
                             dd_col='dd',
                             ci_hi_col='ci_hi',
                             ci_lo_col='ci_lo',
                             t_str='gradient plot',
                             site_names=list(),
                             norm_site='',
                             legend_loc='right',
                             panel_lab='') {

    n_sites <- length(site_names)
    models <- rev(sort(unique(df[['Fplant']])))
    idx <- which(models=='NOAA obs')
    models <- c(models[idx], models[-idx])
    n_models <- length(models)
    pal <- c("#000000", brewer.pal(n_models-1, 'Paired'))
    marker_sequence <- c(8, seq(0, n_models-1))
    x_offset <- calculate_hoffset(n_models, 0.075)
    ylab_str <- 'COS Drawdown (pptv)'

    if (nchar(norm_site) > 0) {
        ylab_str <- paste("COS Drawdown normalized to", norm_site)
        df_norm <- by(df, df[['Fplant']], function(x) {
            orig_row_names <- row.names(x)
            row.names(x) <- x[['site']]
            x <- row_normalizer(x, 'NHA')
            row.names(x) <- orig_row_names
            return(x)})
        df_norm <- do.call(rbind, df_norm)
        df <- df_norm
    }
    ylim <- range(df[df[['site']] %in% site_names, c('ci_lo', 'ci_hi')])
    idx = (df[['site']] %in% site_names) & (df[['Fplant']]==models[[1]])
    this_df <- df[idx, ]
    row.names(this_df) <- this_df[['site']]
    this_df <- this_df[site_names, ]

    xlim_max <- n_sites * 2.5
    if (legend_loc == 'none') {
        xlim_max = n_sites + max(x_offset)
    }

    cex_plt = 0.9
    with(this_df,
         plotCI(1:n_sites + x_offset[[1]],
                dd, uiw=(ci_hi - dd), liw=(dd - ci_lo),
                xaxt='n',
                main=t_str,
                ylab=ylab_str,
                xlab=NA,
                col=pal[[1]],
                ylim=ylim,
                xlim=c(1 + min(x_offset), xlim_max),
                pch=marker_sequence[[1]],
                cex=cex_plt,
                cex.axis=cex_plt,
                cex.main=cex_plt,
                cex.lab=cex_plt))
    axis(1, at=1:n_sites, labels=site_names, cex.axis=cex_plt)

    for (i in 2:n_models) {
        cat(paste('plotting models[', models[[i]], ']\n'))
        idx = (df[['site']] %in% site_names) & (df[['Fplant']]==models[[i]])
        this_df <- df[idx, ]
        row.names(this_df) <- this_df[['site']]
        this_df <- this_df[site_names, ]
        with(this_df,
             plotCI(x=1:n_sites + x_offset[[i]],
                    y=dd, uiw=ci_hi - dd, liw=dd - ci_lo,
                    add=TRUE,
                    col=pal[[i]],
                    pch=marker_sequence[[i]]))
    }
    mod_strs <- unlist(human_readable_model_names()[models])
    # place panel legend in upper-left corner.  Thanks to
    # http://stackoverflow.com/questions/19918566/relative-position-of-mtext-in-r
    # for the "at" code.
    mtext(panel_lab,
          side=3,
          line=-0.5,
          cex=1.2,
          at=par("usr")[1]-0.2*diff(par("usr")[1:2]))
    if (legend_loc != 'none') {
        legend(x=legend_loc, legend=mod_strs,
               pch=marker_sequence, col=pal, cex=cex_plt)
    }
}

myboot <- function(x) {
    boot(x[['dd']],
         statistic=function(data, ind) return(mean(data[ind])),
         R=5000)
}

df <- read.csv('./model_components_14Apr.csv')
df[['Fbounds']] <- 'CONST'
df[['Fbounds']][grepl('climatological', df[['model']])] <- 'CLIM'
components <- strsplit(x=as.character(df[['model']]), split='-')
df[['Fplant']] <- unlist(lapply(components, function(x) x[[1]]))
df[['Fsoil']] <- unlist(lapply(components, function(x) x[[2]]))
df[['Fanthro']] <- unlist(lapply(components, function(x) x[[3]]))

dfl <- split(df[, c('site_code', 'Fplant', 'Fsoil', 'Fanthro',
                    'Fbounds', 'dd')],
             f=df[, c('site_code', 'Fplant')], drop=TRUE)

boot_results <- lapply(dfl,
                       FUN=myboot)
boot_ci_results <- lapply(boot_results, boot.ci,
                          type=c("norm","basic", "perc", "bca"))
dfboot <- data.frame(row.names=names(boot_results),
                     dd=rep(NA, length(boot_results)),
                     ci_lo=rep(NA, length(boot_results)),
                     ci_hi=rep(NA, length(boot_results)),
                     Fplant=rep(NA, length(boot_results)),
                     site=rep(NA, length(boot_results)))
for (this_set in names(boot_results)) {
    dfboot[[this_set, 'dd']] <- boot_results[[this_set]][['t0']]
    dfboot[[this_set, 'ci_lo']] <- boot_ci_results[[this_set]][['basic']][[4]]
    dfboot[[this_set, 'ci_hi']] <- boot_ci_results[[this_set]][['basic']][[5]]
    dfboot[[this_set, 'site']] <- unlist(strsplit(this_set, '\\.'))[[1]]
    dfboot[[this_set, 'Fplant']] <- unlist(strsplit(this_set, '\\.'))[[2]]
}

dfboot_orig <- dfboot
dfboot <- merge_obs(dfboot)

if (TRUE) {

    norm_site <- ''
    plot_width <- 3.425197  # 8.7 cm in inches, as per PNAS
    plot_height <- 5.5
    if (nchar(norm_site) == 0){
        pdf(file='gradients_bootstrapCIs.pdf',
            width=plot_width, height=plot_height)
        cat('writing gradients_bootstrapCIs.pdf\n')
    } else {
        pdf(file='gradients_bootstrapCIs_norm.pdf',
            width=plot_width, height=plot_height)
        cat('writing gradients_bootstrapCIs_norm.pdf\n')
    }
    oldpar<-panes(matrix(1:3,nrow=3,byrow=TRUE))
    # par(mar=c(bottom, left, top, right)’)
    par(mar=c(2,5,1.6,1))
    gradient_CI_plot(dfboot, t_str='East Coast North-South',
                     site_names=c('NHA', 'CMA', 'SCA'),
                     norm_site=norm_site,
                     legend_loc='bottomright',
                     panel_lab='(a)')

    gradient_CI_plot(dfboot, t_str='Mid-Continent East-West',
                     site_names=c('CAR', 'WBI', 'AAO', 'HIL', 'CMA'),
                     norm_site=norm_site,
                     legend_loc='none',
                     panel_lab='(b)')

    gradient_CI_plot(dfboot, t_str='Mid-Continent North-South',
                     site_names=c('ETL', 'DND', 'LEF', 'WBI', 'BNE', 'SGP'),
                     norm_site=norm_site,
                     legend_loc='none',
                     panel_lab='(c)')
    par(oldpar)
    dev.off()


    ## write.csv(df[, c("site_code", "longitude",  "latitude",
    ##                  "dd", "Fbounds", "Fplant", "Fsoil", "Fanthro")],
    ##           file='model_components_26Feb.csv')
}

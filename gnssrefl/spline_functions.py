import numpy as np
from astropy.time import Time
from astropy.timeseries import LombScargle
import matplotlib.pyplot as plt
import os
import pickle
from scipy import interpolate
from scipy.optimize import least_squares
import scipy.signal as spectral

from matplotlib.dates import (date2num, DateFormatter)
import time
import subprocess
import sys

# my local functions
import gnssrefl.gps as g


# all codes below written by David Purnell
# https://github.com/purnelldj
# modifications by kristine larson, december 2021

# various numbers you need in the GNSS world
# mostly frequencies and wavelengths

# removed this since i now have access to gps.py
#class constants:
#    c= 299792458 # speed of light m/sec
#   GPS & galileo frequencies and wavelengths
#    fL1 = 1575.42 # MegaHz 154*10.23
#    fL2 = 1227.60 # 120*10.23
#    fL5 = 115*10.23 # L5
#  GPS & Galileo wavelengths
#    wL1 = c/(fL1*1e6) # meters wavelength
#    wL2 = c/(fL2*1e6)
#    wL5 = c/(fL5*1e6)

def make_wavelength_column(nr,snrdata,signal):
    """
    returns column with nr rows that has the relevant GNSS wavelength for
    the satellites storeid in column zero of snrdata.
    signal is L1, L2 etc
    """
    onecolumn = np.ones((nr,1))
    if signal == 'L2':
        onecolumn = 2*onecolumn
    if signal == 'L5':
        onecolumn = 5*onecolumn

    return onecolumn


def readklsnrtxt(snrfile, thedir, signal):
    """
    :param snrfile: variable with the file contents
    :directory where it is located
    :param signal: 'L1', 'L2' etc.
    :
    parses the contents of a snrfile from #gnssrefl - 
    the file itself is read in a separate function now, 

    returns variable snrdata with columns
    0 - satellite, usual (100 added for glonass, 200 added for galileo)
    1 - elev angle, deg
    2 - azimuth angle, deg
    3 - time in seconds since GPS began
    4 - SNR data in db-Hz
    5 - new column with wavelength in it, in meters.  might as well take care of that now

    if SNR data are zero for a given signal, the row is eliminated
    
    turned off l6,l7,l8 for now
    doesn't do beidou

    """
    # do a straight load of the file
    snrall = loadsnrfile(snrfile, thedir)

    nr,nc = snrall.shape
    # this is for the frequency information

    # will add Beidou later

    if signal == 'L1':
        snrdata = snrall[:,[0,1,2,3,6]]
        onecolumn = make_wavelength_column(nr,snrdata,signal)
    elif signal == 'L2':
        snrdata = snrall[:,[0,1,2,3,7]]
        onecolumn = make_wavelength_column(nr,snrdata,signal)
    # make sure the "9th" column is there
    elif (signal == 'L5') and (nc > 8):
        snrdata = snrall[:,[0,1,2,3,8]]
        onecolumn = make_wavelength_column(nr,snrdata,signal)
    elif signal == 'L1+L2':
        l1 = snrall[:,[0,1,2,3,6]]
        l1col = make_wavelength_column(nr,snrall,'L1')
        l2 = snrall[:,[0,1,2,3,7]]
        l2col = make_wavelength_column(nr,snrall,'L2')
        #print('vertically stacking L1 and L2 data')
        snrdata = np.vstack((l1,l2))
        onecolumn = np.vstack((l1col,l2col))
    elif signal == 'L1+L5':
        l1 = snrall[:,[0,1,2,3,6]]
        l1col = make_wavelength_column(nr,snrall,'L1')
        l5 = snrall[:,[0,1,2,3,8]]
        l5col = make_wavelength_column(nr,snrall,'L5')
        #print('vertically stacking L1 and L5 data')
        snrdata = np.vstack((l1,l5))
        onecolumn = np.vstack((l1col,l5col))
    elif signal == 'L1+L2+L5':
        l1 = snrall[:,[0,1,2,3,6]]
        l1col = make_wavelength_column(nr,snrall,'L1')

        l2 = snrall[:,[0,1,2,3,7]]
        l2col = make_wavelength_column(nr,snrall,'L2')

        l5 = snrall[:,[0,1,2,3,8]]
        l5col = make_wavelength_column(nr,snrall,'L5')

        #print('vertically stacking L1,L2 L5 data')
        tmp = np.vstack((l1,l2))
        snrdata = np.vstack((tmp,l5))

        tmp = np.vstack((l1col,l2col))
        onecolumn = np.vstack((tmp,l5col))
    else:
        print('Did not find what was requested or illegal frequency. Exiting.')
        sys.exit()

    # i do not have time at the moment to implement these frequencies
    #elif signal == 'L6':
    #    snrdata = snrall[:,[0,1,2,3,5]]
    #elif signal == 'L7':
    #    snrdata = snrall[:,[0,1,2,3,9]]
    #elif signal == 'L8':
    #    snrdata = snrall[:,[0,1,2,3,10]]

    # add frequency column 
    snrdata = np.hstack((snrdata, onecolumn))

    # remove the zeroes
    ii = (snrdata[:,4] != 0)
    print('Num of obs before ', len(snrdata))
    snrdata = snrdata[ii,:]
    print('Num of non-zero obs ', len(snrdata))

    # this could be done in the loading function
    stryear = str(int(snrfile[9:11]) + 2000)
    strdoy = snrfile[4:7]
    stryday = stryear + ':' + strdoy + ':00:00:00'
    #tobj = Time(stryday, format='yday')
    #gbase = tobj.gps
    # put the time tags into fake GPS time (seconds since GPS began?)
    #snrdata[:, 3] = snrdata[:, 3] + gbase

    return snrdata

def glonasswlen(prn, signal):
    """
    returns wavelength for glonass, meters
    this only works for L1 and L2
    this was written by david.  
    KL: i need to move it to my gps.py listing
    for now just use the speed of light constant variable
    """
    channel = [1, -4, 5, 6, 1, -4, 5, 6, -2, -7, 0, -1, -2, -7, 0, -1, 4, -3, 3, 2, 4, -3, 3, 2]
    offset = 101  # 101 onwards is glonass
    try:
        channel_t = np.array([channel[i-offset] for i in prn], dtype=float)
    except TypeError:
        channel_t = channel[prn-offset]
    if signal == 'L1':
        lcar = g.constants.c / (1602e06 + channel_t * 0.5625e06)
        #lcar = 299792458 / (1602e06 + channel_t * 0.5625e06)
    elif signal == 'L2':
        lcar = g.constants.c / (1246e06 + channel_t * 0.4375e06)
        #lcar = 299792458. / (1246e06 + channel_t * 0.4375e06)
    else:
        #print('signal not recognised')
        lcar = np.nan
    return lcar


def datetime2gps(dt):
    timeobj = Time(dt, format='datetime')
    gpstime = timeobj.gps
    return gpstime


def gps2datetime(gt):
    timeobj = Time(gt, format='gps', scale='utc')
    dt = timeobj.datetime
    return dt


def gps2datenum(gt):
    timeobj = Time(gt, format='gps', scale='utc')
    dt = timeobj.datetime
    dn = date2num(dt)
    return dn


def snr2arcs(snrdata, azilims, elvlims, rhlims, precision, year,doy,signal='L1', normalize=False, 
        snrfigs=False, lspfigs=False, polydeg=2, gaptlim=5*60, pktnlim=4, savefile=False, screenstats=False, l2c_only=False,**kwargs):
    """
    reads an array of snr data (output from readklsnrtxt) and organises into:
    reflector height estimates, stats and detrended snr data for inverse analysis
    :param snrdata: array of organised SNR data
    :param azilims: azimuth angle limits (e.g., [90, 270])
    :param elvlims: elevation angle limits (e.g., [5, 30])
    :param rhlims: upper and lower reflector height limits (in metres) for quality control
    :param signal: default 'L1' (C/A), can also use L2...if want to use L5 or whatever else you need to make some edits
    :param normalize: if you want to normalize the arcs so that they have the same amplitude
    :param snrfigs: if you want to produce some figures of SNR arcs
    :param lspfigs: if you want to produce some figures of Lomb-Scargle Periodograms
    :param polydeg: degree of polynomial to fit and subtract from SNR data
    :param gaptlim: if there is a gap in time bigger than [gaptlim] seconds in a particular arc then it will be ignored
    :param pktnlim: peak to noise ratio qc condition = the peak of the LSP / mean of LSP within the range [rhlims]
    :param savefile: if you want to save the output to a pickle file then use this parameter as the name (string)
    :param kwargs: see below
    tempres: if want to use different temporal resolution to input data (in seconds)
    satconsts: default use all given, otherwise specify from ['G', 'R', 'E'] (gps / glonass / galileo)
    :return rh_arr: numpy array of reflector height estimtes and stats
    :return snrdt_arr: numpy array of detrended SNR data for inverse analysis

    kl changed the pktnlim definition
    kl made multi frequency for rh_arr
    kl working on making snrdt_arr multi frequency
    kl added roughness
    """
    # get a list for lateron
    if 'l2c_only' in kwargs:
        l2c_only = kwargs.get('l2c_only')
    if l2c_only:
        print('L2c only')

    # get the list
    l2clist,l5list = l2c_l5_list(year,doy)
    # convert SNR to linear scale (from dB-Hz)
    snrdata[:, 4] = 10 ** (snrdata[:, 4] / 20)
    if lspfigs:
        print('Lomb Scargle Plots are being stored in the plots subdirectory')
        print('Creating these slows down the code and should never be done for routine processing')
    if snrfigs:
        print('SNR Plots are being stored in the plots subdirectory')
        print('Creating these slows down the code and should never be done for routine processing')

    # this is a decimator.  
    if 'tempres' in kwargs:
        tempres = kwargs.get('tempres')
        if (tempres != 1):
            print('Decimating the SNR file')
            tfilter = np.where(np.mod(snrdata[:, 3] - snrdata[0, 3], tempres) == 0)[0]
            snrdata = snrdata[tfilter]

    # remove satellite data from non-requested constellations
    if 'satconsts' in kwargs:
        satconsts = kwargs.get('satconsts')
        if 'G' not in satconsts:
            nogps = snrdata[:, 0] > 100
            snrdata = snrdata[nogps]
        if 'R' not in satconsts:
            noglo = np.logical_or(snrdata[:, 0] < 100, snrdata[:, 0] > 200)
            snrdata = snrdata[noglo]
        if 'E' not in satconsts:
            nogal = np.logical_or(snrdata[:, 0] < 200, snrdata[:, 0] > 300)
            snrdata = snrdata[nogal]
    # apply elevation and azimuth restrictions.   
    # KL: we usually do the DC first and then apply the restrictions DC  
    tfilter = np.logical_and(snrdata[:, 1] > elvlims[0], snrdata[:, 1] < elvlims[1])
    snrdata = snrdata[tfilter]
    if azilims[0] < azilims[1]:
        tfilter = np.logical_and(snrdata[:, 2] > azilims[0], snrdata[:, 2] < azilims[1])
    else:
        tfilter = np.logical_or(snrdata[:, 2] > azilims[0], snrdata[:, 2] < azilims[1])
    snrdata = snrdata[tfilter]

    print('Using Lomb Scargle precision of ', precision, ' m')
    # setting up arrays for the output of the LSP
    # changed this to 12 to accommodate frequency
    #rh_arr = np.empty((0, 11))
    rh_arr = np.empty((0, 12))
    # kl added a column for frequency
    #snrdt_arr = np.empty((0, 4), dtype=object)
    snrdt_arr = np.empty((0, 5), dtype=object)
    # get rid of satellite 51, 46 because not sure what it is
    # KL - not necessary - there are legal satellites > 32 in galileo
    #nobadsats = np.logical_or(snrdata[:, 0] < 33, snrdata[:, 0] > 99)
    #snrdata = snrdata[nobadsats, :]

    print('Using this signal: ', signal)
    # speed of light should be a declared constant
    if signal not in ['L1','L2','L5','L1+L2','L1+L5','L1+L2+L5']:
        print('code only currently works for L1, L2, L5 and combinations therein- exiting')
        sys.exit()
    print('Satellites:')
    satellite_list = np.unique(snrdata[:,0]); 
    print(satellite_list)
    signal_list = signal2list(signal)
    print('Frequencies: ', signal_list)
    # make a dictionary to keep track of the constellation/frequencies that are being used
    alld = {}
    # initialize values?
    kristine_dictionary(alld,'','')
    fout = open('my_lsp.txt', 'w+')
    for sat in satellite_list:
        # get the data for that satellite
        tfilter = (snrdata[:, 0] == sat)
        first_tempd = snrdata[tfilter]

        # added this so i can loop through more than one frequency.  hopefully
        for xsignal in signal_list:
            isignal = int(xsignal[1:2]) # integer version of frequency
            #print('Working on satellite/signal:', int(sat),xsignal,isignal)

            # frequency (integer) should be in column "5"
            sfilter = (first_tempd[:, 5] == isignal)
            tempd = first_tempd[sfilter]

            # this is still the same ....  
            # use the constants in gps.py
            if np.logical_or(sat < 100, np.logical_and(sat > 200, sat < 300)):
                if xsignal == 'L1':
                    lcar = g.constants.wL1
                elif xsignal == 'L2':
                    lcar = g.constants.wL2
                elif xsignal == 'L5':
                    lcar = g.constants.wL5
            elif np.logical_and(sat > 100, sat < 200):
                lcar = glonasswlen(int(sat), xsignal)

            # this restricts to L2C satellite but only if requested.
            # this does not mean the file has L2C data in it however.  unfortunately
            # particularly useful for trimble L2 data
            badone = False
            if ((sat < 100) & (xsignal == 'L2')) and l2c_only:
                if sat not in l2clist:
                    badone = True
                    #print('will not use this signal', xsignal, int(sat))

            # build up a dictionary that keeps track of which specific 
            # constellations/frequencies are observed
            alld = kristine_dictionary(alld,sat,xsignal)

            maxf = 2 * (rhlims[0] + rhlims[1]) / lcar
            precisionf = 2 * precision / lcar  # 1 mm was what he set - this is now a variable
            if (not np.isnan(maxf)) and (not badone):
                f = np.linspace(precisionf, maxf, int(maxf / precisionf))
                tempd = tempd[tempd[:, 3].argsort()]  # sort by time
                elv_tosort = np.array(tempd[:, 1], dtype=float)
                date_tosort = np.array(tempd[:, 3], dtype=float)
                ddate = np.ediff1d(date_tosort)
                delv = np.ediff1d(elv_tosort)
                bkpt = len(ddate)
                bkpt = np.append(bkpt, np.where(ddate > gaptlim)[0])  # gaps bigger than gaptlim
                bkpt = np.append(bkpt, np.where(np.diff(np.sign(delv)))[0])  # elevation rate changes direction
                bkpt = np.unique(bkpt)
                bkpt = np.sort(bkpt)
                for ii in range(len(bkpt)):
                    if ii == 0:
                        sind = 0
                    else:
                        sind = bkpt[ii - 1] + 1
                    eind = bkpt[ii] + 1
                    if eind - sind < 20:
                     #print('arc not big enough')
                        continue
                    elvt = np.array(tempd[sind:eind, 1], dtype=float)
                    if len(np.unique(elvt)) == 1:
                #print('unchanging elevation')
                        continue
                    azit = np.array(tempd[sind:eind, 2], dtype=float) # azimuth array
                    sinelvt = np.sin(elvt / 180 * np.pi) # sine elevation angle array
                    datet = np.array(tempd[sind:eind, 3], dtype=float) # seconds in GPSish time?
                    snrt = np.array(tempd[sind:eind, 4], dtype=float) # snr data (dc removed) 
                # here dave is removing the direct signal
                    z = np.polyfit(sinelvt, snrt, polydeg)
                    p = np.poly1d(z)
                # estimating the periodogram used to compute the dominant reflector 
                # frequency, and thus RH
                    snrdt = snrt - p(sinelvt)
                    pgram = LombScargle(sinelvt, snrdt, normalization='psd').power(f)

                # converting it into the proper units of RH (meters)
                    reflh = 0.5 * f * lcar
                # this is a very simplistic outlier detector
                    tfilter = np.logical_and(reflh > rhlims[0], reflh < rhlims[1])
                    pgram_sub = pgram[tfilter]
                    reflh_sub = reflh[tfilter]
                    maxind = np.argmax(pgram_sub)
                # KL pktn = np.max(pgram_sub) / np.mean(pgram)
                    pktn = np.max(pgram_sub) / np.mean(pgram_sub)

                # compute LSP with my code

                    maxF, maxA,peak2noise = simpleLSP(rhlims, lcar, precision,elvt, sinelvt, snrdt,sat,xsignal,screenstats,fout,pktnlim)

                    if maxind != 0 and maxind != len(pgram_sub) - 1 and pktn > pktnlim:  # no peaks at either end of window
                        # KL moved this to a function/added a column to save frequency information
                        temp_arr = save_lsp_results(datet,maxind,reflh_sub,sat,elvt,azit,pgram_sub,snrdt,pktn,isignal)
                        rh_arr = np.vstack((rh_arr, temp_arr))
                        if normalize:
                            snrdt = snrdt * 100 / (np.max(np.abs(snrdt)))
                        satt = np.empty((len(datet)), dtype=int)
                        satt[:] = sat
                        nr = len(datet)
                        onecol = isignal*np.ones((nr,1))
                        # i added an integer column for frequencies
                        #temp_arr = np.column_stack([datet, satt, sinelvt, snrdt])
                        temp_arr2 = np.column_stack([datet, satt, sinelvt, snrdt, onecol])
                        # stack em
                        snrdt_arr = np.vstack((snrdt_arr, temp_arr2))
                        # and plots moved to function to clean this up
                        aa = str( int( np.mean(azit)) )
                        arc_plots(lspfigs, snrfigs, reflh,pgram,sat,datet,elvlims,elvt,snrdt,aa)
    rh_arr = rh_arr[rh_arr[:, 0].argsort()]
    # make sure that arrays are sorted by time
    snrdt_arr = snrdt_arr[snrdt_arr[:, 0].argsort()]
    fout.close()
    if savefile:
        arcfilestr = 'arcsout.pkl'
        f = open(arcfilestr, 'wb')
        pickle.dump(rh_arr, f)
        pickle.dump(snrdt_arr, f)
        f.close()
    return rh_arr, snrdt_arr, alld


def residuals_cubspl_spectral(kval, knots, rh_arr):
    """
    function needed for inverse analysis
    """
    tfilter = np.logical_and(rh_arr[:, 0] >= knots[0], rh_arr[:, 0] <= knots[-1])
    rh_arr = rh_arr[tfilter]
    dt_even = 60
    t_even = np.linspace(knots[0], knots[-1], int((knots[-1] - knots[0]) / dt_even) + 1)
    cubspl_f = interpolate.interp1d(knots, kval, kind='cubic')
    cubspl_even = cubspl_f(t_even)
    dhdt_even = np.gradient(cubspl_even, dt_even)
    f = interpolate.interp1d(t_even, dhdt_even)
    tgpst = np.array(rh_arr[:, 0], dtype=float)
    reflh = np.array(rh_arr[:, 1], dtype=float)
    tane_dedt = np.array(rh_arr[:, 3], dtype=float)
    dhdt = f(tgpst)
    cubspl_adj = cubspl_f(tgpst) + dhdt * tane_dedt
    residual_spectral = cubspl_adj - reflh
    return residual_spectral


def residuals_cubspl_js(inparam, knots, satconsts, signal, snrdt_arr,final_list,Nfreq):
    """
    function needed for snr-fitting inverse analysis
    KL js must stand for joakim strandberg ???

    this has to be modified for multi-frequency
    fspecdict and Nfreq
    """
    if len(inparam) - Nfreq * 2 == len(knots):
        # then no roughness
        rh_kval = inparam[: - Nfreq * 2]
        satparams = inparam[- Nfreq * 2:]
        rough_in = False
    elif len(inparam) - Nfreq * 2 - 1 == len(knots):
        # roughness
        rh_kval = inparam[: - Nfreq * 2 - 1]
        satparams = inparam[- Nfreq * 2 - 1: -1]
        rough_in = inparam[-1]
    else:
        print('issue with length of input parameter array')
        return
    tmpc = 0
    res = np.empty(0)
    xsignal = signal
    signal_list = signal2list(xsignal)

    # G,R,E in first column and frequency in the second
    for satc in final_list:
        # this is where tmpc was originally
        tmpc = tmpc + 1
        c = satc[0:1] # constellation: E,G,R
        f = int(satc[1:2]) # frequency: 1,2,5
        
        # figuring out which satellites are which
        if c == 'G':
            tfilter = snrdt_arr[:, 1] < 100
        elif c == 'R':
            tfilter = np.logical_and(snrdt_arr[:, 1] > 100, snrdt_arr[:, 1] < 200)
        elif c == 'E':
            tfilter = np.logical_and(snrdt_arr[:, 1] > 200, snrdt_arr[:, 1] < 300)
        else:
            print('unknown satellite constellation')
        # take out the constellation
        constellation_tmp_arr = snrdt_arr[tfilter, :]
        # this is no longer a loop
        # for xsignal in signal_list:
        if True:
            #isignal = int(xsignal[1:2]) # integer f, i.e. 1,2,5
            isignal = f
            # now further restrict to a frequency for a given constellation
            ii = (constellation_tmp_arr[:,4] == isignal)
            tmp_arr = constellation_tmp_arr[ii,:]

            # this code expects L1 and not just a 1
            lcar = satfreq2waveL(c, 'L' + str(f), tmp_arr[:,1])
            #lcar = satfreq2waveL(satc, xsignal,tmp_arr[:,1])

            tgpst = np.array(tmp_arr[:, 0], dtype=float)
            sin_et = np.array(tmp_arr[:, 2], dtype=float)
            snr_dtt = np.array(tmp_arr[:, 3], dtype=float)
            cubspl_f = interpolate.interp1d(knots, rh_kval, kind='cubic')
            bf = np.logical_and(tgpst >= np.min(knots), tgpst <= np.max(knots))
            tgpst = tgpst[bf]
            sin_et = sin_et[bf]
            snr_dtt = snr_dtt[bf]

            h1 = cubspl_f(tgpst)
            modelsnr = satparams[int((tmpc - 1)*2)] * np.sin(4 * np.pi * h1 * sin_et / lcar) + satparams[int((tmpc - 1)*2 + 1)] * np.cos(4 * np.pi * h1 * sin_et / lcar)

            if rough_in:
                lk = 2 * np.pi / lcar
                modelsnr = modelsnr * np.exp(-4 * lk ** 2 * rough_in * sin_et ** 2)
            res = np.append(res, modelsnr - snr_dtt)
    return res



def snr2spline(station,year,doy, azilims, elvlims,rhlims, precision, kdt, snrfit=True, signal='L1', savefile=False, doplot=False, rough_in=0.1, **kwargs):
    """
    function analyses a kristine larson 'gnssrefl' format snr file and outputs a fitted spline
    note that the file must be 24 hours long or it wont work
    station, year, and doy
    : azilims: azimuth angle limits (e.g., [90, 270])
    : elvlims: elevation angle limits (e.g., [5, 30])

    :params rhlims: upper and lower reflector height limits (in metres) for quality control e.g., [5, 10] is 5 and 10 m
    : precision of the periodogram in meters
    :params kdt: spline knot spacing in seconds
    knots are spaced evenly except for at the start and end of the day
    the idea is that you could piece together the outpt from different days to have a continuous spline
    if kdt = 2 * 60 * 60 (2 hours), then knots at 0h, 1h, 3h,... 21h, 23h, 24h
    The idea is that you would ignore the first and last knots and then you could have a continuous spline
    with knots every 2 hours over multiple days
    :params snrfit: True or False if you want to do inverse modelling of the SNR data
    :params signal: 'L1', 'L2', currently under development
    :params savefile: set True if you want to save the output to a file
    :params doplot: set True if you want to produce a plot with the output from the analysis
    :params rough_in: 'roughness' parameter in the inverse modelling of SNR data (see Strandberg et al., 2016)
    :parans kwargs: see below
    tempres: if want to use different temporal resolution to input data (in seconds)
    satconsts: default use all given, otherwise specify from ['G', 'R', 'E'] (gps / glonass / galileo)
    :return invout: dictionary with outputs from inverse analysis
    """

    if 'rough_in' in kwargs:
        rough_in  = kwargs.get('rough_in')

    print('roughness',rough_in)

    risky = False
    if 'risky' in kwargs:
        risky = kwargs.get('risky')

    if risky: 
        print('You are a risk taker.')
    else:
        print('You are not a risk taker.')


    if 'screenstats' in kwargs:
        screenstats = kwargs.get('screenstats')

    snr_ending = 66
    if 'snr_ending' in kwargs:
        snr_ending = kwargs.get('snr_ending')
    
    if 'doy_end' in kwargs:
        doy_end = kwargs.get('doy_end')
    else:
        doy_end = doy


    if (doy == doy_end):
        print('Only doing one day')
        snrfile, snrdir, stryear, strdoy = define_inputfile(station,year,doy,snr_ending)
        snrdata = readklsnrtxt(snrfile, snrdir,signal)
        numdays = 1
    else:
        numdays = doy_end - doy + 1
        for d in range(doy, doy_end+1):
            snrfile, snrdir, stryear_temp, strdoy_temp = define_inputfile(station,year,d,snr_ending)
            snrtemp = readklsnrtxt(snrfile, snrdir,signal)
            if d == doy:
                #print('first day')
                snrdata = snrtemp
                # save these
                stryear = stryear_temp
                strdoy = strdoy_temp
            else:
                snrdata = np.vstack((snrdata, snrtemp))

    nr,nc = snrdata.shape
    print('Number of obs', nr, ' number of days', numdays)

    invout = {}
    # starting point - which is taken from the first day 
    stryday = stryear + ':' + strdoy + ':00:00:00'

    print(stryday)
    tobj = Time(stryday, format='yday')
    gbase = tobj.gps
    # Setting up knots ...
    knots = np.linspace(gbase + int(kdt/2), gbase + numdays*86400 - int(kdt/2), int(numdays*86400/kdt))
    print('Here be the knots:', knots)
    print('Knot spacing in seconds ',int(kdt/2))
    print('Number of knots',int(numdays*86400/kdt))
    knots = np.append(gbase, knots)  # add start and end of day for more stable output but dont use these points
    knots = np.append(knots, gbase + numdays*86400)


    print('sorting snr data into arcs')

    # arguments sent directly
    print('begin Lomb Scargle analysis')
    s1=time.time()
    rh_arr, snrdt_arr, fspecdict= snr2arcs(snrdata, azilims, elvlims, rhlims, precision, year, doy, signal=signal,**kwargs)
    s2=time.time()
    print('Time spent in snr2arcs: ',round(s2-s1,2), ' seconds')
    print(fspecdict)
    print('Found ' + str(np.ma.size(rh_arr, axis=0)) + ' arcs')
    if screenstats:
        print(' RH(m)  Sat  Azim  Dt  Pk2noise Freq  Hours since epoch0')
        for i in range(0,len(rh_arr)):
            print(" %5.2f %3.0f %5.1f %5.1f %5.1f  %1.0f %10.3f " % ( 
                rh_arr[i,1], rh_arr[i,2], rh_arr[i,6], rh_arr[i,9]/60, rh_arr[i,10], rh_arr[i,11],(rh_arr[i,0]-gbase)/3600 ))
    if np.ma.size(rh_arr, axis=0) == 0:
        print('no reflector height data - exit')
        exit()

    if 'satconsts' in kwargs:
        satconsts = kwargs.get('satconsts')
    else:
        allsats = np.unique(rh_arr[:, 2])
        satconsts = []
        if len(np.where(np.logical_and(allsats > 0, allsats < 100))[0]) > 0:
            satconsts = np.append(satconsts, 'G')
        if len(np.where(np.logical_and(allsats > 100, allsats < 200))[0]) > 0:
            satconsts = np.append(satconsts, 'R')
        if len(np.where(np.logical_and(allsats > 200, allsats < 300))[0]) > 0:
            satconsts = np.append(satconsts, 'E')
    if np.ma.size(rh_arr, axis=0) < 2:
        print('not enough data - exit')
        exit()

    # sort the results by time??
    temp_dn = np.sort(rh_arr[:, 0])
    temp_dn = np.append(gbase, temp_dn)
    temp_dn = np.append(temp_dn, gbase + numdays*86400)
    maxtgap = np.max(np.ediff1d(temp_dn))
    mintgap = np.min(np.ediff1d(temp_dn))
    if mintgap < 0:
        print('issue - values not in order')
        exit()
    print('max gap is ' + str(int(maxtgap / 60)) + ' minutes')

    if maxtgap > kdt * 1.05:  # giving 5% margin?
        print('Gap in data bigger than node spacing, which has risk of instabilities.')
        if (not risky):
            print('If you are a risk-taker, you need to set -risky True and rerun the code.')
            sys.exit()

    def residuals_spectral_ls(kval):
        residuals = residuals_cubspl_spectral(kval, knots, rh_arr)
        return residuals

    print('Now fitting a cubic spline to the arcs with rhdot included?')
    kval_0 = np.nanmean(rh_arr[:, 1]) * np.ones(len(knots))
    print('Number of knots here ', len(knots))
    s1=time.time()
    ls_spectral = least_squares(residuals_spectral_ls, kval_0, method='trf', bounds=rhlims)
    kval_spectral = ls_spectral.x
    print('Length of kval_spectral', len(kval_spectral))
    invout['knots'] = knots
    invout['kval_spectral'] = kval_spectral[1:-1]  # dont save first and last points
    s2=time.time()
    print(round(s2-s1,2), ' seconds')
    print('satellite constellations ', satconsts)
    if snrfit:
        s1=time.time()
        print('Now doing Joakim Strandberg SNR fitting inversion')
        kval_0 = kval_spectral
        print('kval_0', kval_0)
        final_list, Nfreq = smarterWay(fspecdict)
        print(final_list)
        print('Number of constellation specific frequencies', Nfreq)
        # consts = len(satconsts)
        #kval_0 = np.append(kval_0, np.zeros(consts * 2))
        # this should be correct .... 
        kval_0 = np.append(kval_0, np.zeros(Nfreq* 2))
        print('roughness', rough_in)
        kval_0 = np.append(kval_0, rough_in)

        aa,bb = snrdt_arr.shape
        print('Dimensions of the snrdt_arr variable', aa,bb)
        print('Now sending it ', Nfreq, ' different frequencies')
        def residuals_js_ls(inparam):
            residuals = residuals_cubspl_js(inparam, knots, satconsts, signal, snrdt_arr,final_list,Nfreq)
            return residuals
        print('Calling the least squares code')
        ls_js = least_squares(residuals_js_ls, kval_0, method='lm')
        invout_js = ls_js.x
        kval_js = invout_js[:len(knots)]
        outparams_js = invout_js[len(knots):]
        invout['kval_js'] = kval_js[1:-1]  # dont save first and last points
        invout['outparams_js'] = outparams_js
        s2 = time.time()
        print('Time spend in snrfit', round(s2-s1,2), ' seconds')

    if doplot:
        plotdt = 5 * 60
        tplot = np.linspace(gbase, gbase + numdays*86400, int(86400/plotdt + 1))
        tplot_dn = gps2datenum(tplot)
        cubspl_f = interpolate.interp1d(knots, kval_spectral, kind='cubic')
        rh_spectral_plot = cubspl_f(tplot)
        fig, ax = plt.subplots(figsize=(8, 4))
        rh_dn = gps2datenum(np.array(rh_arr[:, 0], dtype=float))
        plot_tracks(rh_arr, rh_dn)

        pspec, = plt.plot_date(tplot_dn, rh_spectral_plot, '-.',color='gray')
        pspec.set_label('cubspl')
        if snrfit:
            cubspl_f = interpolate.interp1d(knots, kval_js, kind='cubic')
            rh_js_plot = cubspl_f(tplot)
            pjs, = plt.plot_date(tplot_dn, rh_js_plot, '-',color='black')
            pjs.set_label('invmod')

        dformat = DateFormatter('%Y-%m-%d')
        ax.xaxis.set_major_formatter(dformat)
        ax.set_title(station.upper() + ' ' + signal)
        ax.set_xlim(gps2datenum(gbase), gps2datenum(gbase + numdays*86400))
        ax.set_xticks(np.linspace(gps2datenum(gbase), gps2datenum(gbase + numdays*86400), int(86400 / (60 * 60 * 6) + 1)))
        ax.xaxis.set_major_formatter(DateFormatter('%m-%d %H:%M'))
        #ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d %H:%M'))
        ax.legend(loc="best", prop={"size":8})
        #ax.legend(loc="upper right",bbox_to_anchor=(1. , 0.7),prop={"size":8})
        #plt.xticks(rotation =45); 
        ax.grid(True)
        ax.set_ylabel('RH meters')
        ax.invert_yaxis()
        plt.savefig('spline_out.png')
        plt.show()
        plt.close()

    if savefile:
        invfilestr = snrfile + '.inv'
        f = open(invfilestr, 'wb')
        pickle.dump(invout, f)
        pickle.dump(rh_arr, f)
        f.close()
        print('dumped a pickle')
    return invout

def define_inputfile(station,year,doy,snr_ending):
    """
    given station, year, day of year, returns
    snr filename and directory and string version of year and doy
    kl:
    22feb01 added snr ending as required input
    """
    cdoy = '{:03d}'.format(doy) ;
    cyy = '{:02d}'.format(year-2000)
    cyyyy = str(year)
    xdir = os.environ['REFL_CODE'] + '/' + cyyyy + '/snr/' + station + '/'
    snrfile = station + cdoy + '0.' + cyy + '.snr' + str(snr_ending)
    snrdir = ''
    if not os.path.isfile(snrfile):
        #print('SNR file does not exist in the local directory')
        if os.path.isfile(xdir + snrfile):
            #print('SNR file does exist in the REFL_CODE directory')
            snrdir = xdir
        else:
            print('No file found. Exiting')
            sys.exit()

    return snrfile,snrdir, cyyyy, cdoy

def arc_plots(lspfigs, snrfigs, reflh,pgram,sat,datet,elvlims,elvt,snrdt,azdesc):
    """
    moved these individual plots out of the way
    """
    if not os.path.isdir('plots'):
        print('make output directory for plots')
        subprocess.call(['mkdir','plots'])

    resol = 150
    nm = 'sat' + str(int(sat)) + '_' + gps2datetime(np.mean(datet)).strftime('%H-%M')  
    if lspfigs:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(reflh, pgram)
        ax.grid(True)
        ax.set_xlabel('RH (m)')
        ax.set_title('Satellite ' + str(int(sat)) + ' Azim:' + azdesc)
        ax.set_ylabel('unknown power units')
        plt.savefig('plots/' + nm + '_LSP.png',dpi=resol)
        plt.close(fig)
    if snrfigs:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(elvt, snrdt)
        plt.xlim(elvlims[0], elvlims[1])
        ax.set_title('Satellite ' + str(int(sat)) + ' Azim:' + azdesc)
        #plt.ylim(-100, 100)
        ax.grid(True)
        ax.set_xlabel('elevation angle (deg)')
        ax.set_ylabel('volts/volts?')
        plt.savefig('plots/' + nm + '_SNR.png',dpi=resol)
        plt.close(fig)

def signal2list(signal):
    """
    turns signal input (e.g. L1+L2) to a list
    """
    if (len(signal) == 2):
        signal_list = [signal]
    elif (len(signal) == 5):
        signal_list = [signal[0:2],signal[3:5]]
    elif (len(signal) == 8):
        signal_list = ['L1','L2','L5']

    return signal_list


def satfreq2waveL(satc, xsignal,fsatnos):
    """
    given satellite constellation ('G', 'E' ...)
    xsignal ('L1','L2' ...)
    satnos (satellite numbers)
    """
    if (satc == 'G'):
        if (xsignal == 'L1'):
            lcar = g.constants.wL1
        elif (xsignal == 'L2'):
            lcar = g.constants.wL2
        elif (xsignal == 'L5'):
            lcar = g.constants.wL5
    elif satc == 'R':
        if xsignal == 'L5':
            lcar = np.nan
        else:
            satnos = np.array(fsatnos, dtype=int)
            lcar = glonasswlen(satnos, xsignal)
    elif (satc == 'E'):
        if xsignal == 'L1':
            lcar = g.constants.wL1
        elif xsignal == 'L2':
            lcar = np.nan
        elif xsignal == 'L5':
            lcar = g.constants.wL5

    return lcar

def loadsnrfile(snrfile, thedir):
    """
    loads the snr file , but does not pick out the signal.
    using two functions will make it easier to use more than one frequency


    do time modification here now. column 4 is time since GPS began, in seconds
    """
    snrin = thedir + snrfile

    print('Reading file:', snrin)
    # this assumes someone has checked existence first
    snrdata = np.loadtxt(snrin)

    stryear = str(int(snrfile[9:11]) + 2000)
    strdoy = snrfile[4:7]
    stryday = stryear + ':' + strdoy + ':00:00:00'
    tobj = Time(stryday, format='yday')
    gbase = tobj.gps
    # put the time tags into fake GPS time (seconds since GPS began?)
    snrdata[:, 3] = snrdata[:, 3] + gbase

    return snrdata

def plot_tracks(rh_arr, rh_dn):
    """
    send the array of LSP results (rh_arr) with time variable for 
    plotting (rh_dn)
    """
    ms=4
    ii = (rh_arr[:,2] < 100) & (rh_arr[:,11] == 1)# GPS
    ii2 = (rh_arr[:,2] < 100) & (rh_arr[:,11] == 2)# GPS
    ii5 = (rh_arr[:,2] < 100) & (rh_arr[:,11] == 5)# GPS

    jj = (rh_arr[:,2] > 100) & (rh_arr[:,2] < 200)  & (rh_arr[:,11] == 1) # Glonass
    jj2 = (rh_arr[:,2] > 100) & (rh_arr[:,2] < 200)  & (rh_arr[:,11] == 2) # Glonass

    kk = (rh_arr[:,2] > 200) &  (rh_arr[:,11] == 1)# galileo
    kk5 = (rh_arr[:,2] > 200) & (rh_arr[:,11] == 5) # galileo


    if len(rh_dn[ii]) > 0:
        psec, = plt.plot_date(rh_dn[ii], rh_arr[ii, 1], 'o',color='blue',markersize=ms)
        psec.set_label('GPS L1')

    if len(rh_dn[ii2]) > 0:
        psec, = plt.plot_date(rh_dn[ii2], rh_arr[ii2, 1], '<',color='blue',markersize=ms)
        psec.set_label('GPS L2')

    if len(rh_dn[ii5]) > 0:
        psec, = plt.plot_date(rh_dn[ii5], rh_arr[ii5, 1], 's',color='blue',markersize=ms)
        psec.set_label('GPS L5')

    if len(rh_dn[kk]) > 0:
        psec, = plt.plot_date(rh_dn[kk], rh_arr[kk, 1], 'o',color='orange',markersize=ms)
        psec.set_label('GAL L1')

    if len(rh_dn[kk5]) > 0:
        psec, = plt.plot_date(rh_dn[kk5], rh_arr[kk5, 1], 's',color='orange',markersize=ms)
        psec.set_label('GAL L5')

    if len(rh_dn[jj]) > 0:
        psec, = plt.plot_date(rh_dn[jj], rh_arr[jj, 1], 'ro',markersize=ms)
        psec.set_label('GLO L1')

    if len(rh_dn[jj2]) > 0:
        psec, = plt.plot_date(rh_dn[jj2], rh_arr[jj2, 1], '<', color='red',markersize=ms)
        psec.set_label('GLO L2')

def kristine_dictionary(alld,sat,xsignal):
    """
    """
    if len(alld) == 0:
        alld['G1'] = False
        alld['G2'] = False 
        alld['G5'] = False
        alld['E1'] = False
        alld['E2'] = False
        alld['E5'] = False
        alld['R1'] = False
        alld['R2'] = False
        alld['R5'] = False
    else:
        if (sat < 100) and (xsignal == 'L1'):
            alld['G1'] = True
        if (sat < 100) and (xsignal == 'L2'):
            alld['G2'] = True
        if (sat < 100) and (xsignal == 'L5'):
            alld['G5'] = True
        if ((sat > 100) and (sat < 200)) and (xsignal == 'L1'):
            alld['R1'] = True
        if ((sat > 100) and (sat < 200)) and (xsignal == 'L2'):
            alld['R2'] = True

        if ((sat > 200) and (sat < 300))  and (xsignal == 'L1'):
            alld['E1'] = True
        if ((sat > 200) and (sat < 300))  and (xsignal == 'L5'):
            alld['E5'] = True

    return alld

def smarterWay(a):
    """
    just want to know how many true values there are in the a dictionary 
    and then write thtem to a list, as in ['G1','G2']
    sure to be a better way - but this works for now
    """
    i=0
    final_list = []
    for val in a:
        if a[val]:
            i=i+1
            final_list.append(val)
    return final_list, i

def freq_out(x,ofac,hifac):
    """
    inputs: x
    ofac: oversamping factor
    hifac
    outputs: two sets of frequencies arrays
    """
#
# number of points in input array
    n=len(x)
#
# number of frequencies that will be used
    nout=np.int(0.5*ofac*hifac*n)

    xmax = np.max(x)
    xmin = np.min(x)
    xdif=xmax-xmin
# starting frequency
    pnow=1.0/(xdif*ofac)
    pstart = pnow
    pstop = hifac*n/(2*xdif)
#
# simpler way
    pd = np.linspace(pstart, pstop, nout)
    return pd

def get_ofac_hifac(elevAngles, cf, maxH, desiredPrec):
    """
    computes two factors - ofac and hifac - that are inputs to the
    Lomb-Scargle Periodogram code.
    We follow the terminology and discussion from Press et al. (1992)
    in their LSP algorithm description.

    INPUT
    elevAngles:  vector of satellite elevation angles in degrees
    cf:(L-band wavelength/2 ) in meters
    maxH:maximum LSP grid frequency in meters
    desiredPrec:  the LSP frequency grid spacing in meters
    i.e. how precise you want he LSP reflector height to be estimated
    OUTPUT
    ofac: oversampling factor
    hifac: high-frequency factor
    """
# in units of inverse meters
    X= np.sin(elevAngles*np.pi/180)/cf

# number of observations
    N = len(X)
# observing Window length (or span)
# units of inverse meters
    W = np.max(X) - np.min(X)

# characteristic peak width, meters
    cpw= 1/W

# oversampling factor
    ofac = cpw/desiredPrec

# Nyquist frequency if the N observed data samples were evenly spaced
# over the observing window span W, in meters
    fc = N/(2*W)

# Finally, the high-frequency factor is defined relative to fc
    hifac = maxH/fc

    return ofac, hifac

def simpleLSP(rhlims, lcar, precision,elvt, sinelvt, snrdt,sat,xsignal,screenstats,fout,pktnlim):
    """
    input rhlims from dave's code (rhmin and rhmax)
    lcar is gnss wavelength in m
    precision of the periodogram, in meters
    elvt - elevation angles in degrees
    sinelvt, sine elevation angle
    snrdt - detrended snr data
    """
    maxH = rhlims[-1] # meters
    cf = lcar/2 # wavelength/2

    # get oversampling factor and hifac (how far in RH space)
    ofac, hifac = get_ofac_hifac(elvt, cf, maxH, precision)
    # scaled elevation angle
    scaledE = sinelvt /cf
    px = freq_out(scaledE,ofac,hifac)
    scipy_LSP = spectral.lombscargle(scaledE, snrdt, 2*np.pi*px)
    pz = 2*np.sqrt(scipy_LSP/len(sinelvt))
    # impose rh limits
    ii = (px >= rhlims[0]) & (px <= rhlims[1])
    px = px[ii]
    pz = pz[ii]
    noise = np.mean(pz)
    # don't allow max to be at hte beginning of the end

    ij = np.argmax(pz)
    maxF = px[ij]
    maxAmp = np.max(pz)
    #print(ij, maxF,len(px))
    bad = False
    if int(ij) == (len(px)-1): # end
        bad = True
        maxAmp = np.nan; maxF = np.nan ; peak2noise = np.nan
    if int(ij) == 0: # beginning
        bad = True
        maxAmp = np.nan; maxF = np.nan ; peak2noise = np.nan

    peak2noise = maxAmp/noise
    if (peak2noise < pktnlim): 
        bad = True
        #print('fail pk2noise',peak2noise, pktnlim)
    # won't print for now.  too messy to have two sets
    # "{0:4.0f} {1:3.0f} {2:s} {3:s}  {4:s} {5:2.0f} {6:2.0f}
    if screenstats and (not bad):
        fout.write("{0:5.2f} {1:5.2f} {2:5.1f} {3:3.0f} {4:s} \n".format(maxF, maxAmp,peak2noise, sat, xsignal))
    return maxF, maxAmp, peak2noise

def l2c_l5_list(year,doy):
    """
    for given year and day of year, returns a satellite list of
    L2C and L5 transmitting satellites

    to update this numpy array, the data are stored in a simple triple of PRN number, launch year,
    and launch date.
    author: kristine larson
    date: march 27, 2021
    june 24, 2021: updated for SVN78
    """

    # this numpy array
    l2c=np.array([[1 ,2011 ,290], [3 ,2014 ,347], [4 ,2018 ,357], [5 ,2008 ,240],
        [6 ,2014 ,163], [7 ,2008 ,85], [8 ,2015 ,224], [9 ,2014 ,258], [10 ,2015 ,343],
        [11, 2021, 168],
        [12 ,2006 ,300], [14 ,2020 ,310], [15 ,2007 ,285], [17 ,2005 ,270],
        [18 ,2019 ,234], [23 ,2020 ,182], [24 ,2012 ,319], [25 ,2010 ,240],
        [26 ,2015 ,111], [27 ,2013 ,173], [29 ,2007 ,355], [30 ,2014 ,151], [31 ,2006 ,270], [32 ,2016 ,36]])
    # indices that meet your criteria
    ij=(l2c[:,1] + l2c[:,2]/365.25) < (year + doy/365.25)
    l2csatlist = l2c[ij,0]
    firstL5 = 2010 + 148/365.25 # launch may 28, 2010  - some delay before becoming healthy

    newlist = l2c[ij,:]
    ik= (newlist[:,1] + newlist[:,2]/365.25) > firstL5
    l5satlist = newlist[ik,0]

    return l2csatlist, l5satlist

def save_lsp_results(datet,maxind,reflh_sub,sat,elvt,azit,pgram_sub,snrdt,pktn,isignal):
    """
    just cleaning up - move the temp_arr definition to a function
    each column is defined below.
    inputs are datet (seconds in GPSish time), 
    reflh_sub (windowed rh?)
    sat - satellite number
    elvt - array of elevation angles(deg)
    azit - array of azimuth angles (deg)
    snrdt - is detrended SNR data (DC component removed)
    pktn - peak 2 noise via Dave's definition
    isignal - frequency, 1,2, or 5
    """

    temp_arr = np.empty((1, 12), dtype=object)
    # saving some stats for each satellite arc
    temp_arr[0, 0] = int(np.round(np.mean(datet)))                          # time of arc in seconds?
    temp_arr[0, 1] = reflh_sub[maxind]                                      # reflector height (meters)
    temp_arr[0, 2] = sat                                                    # sat prn
    dthdt = ((elvt[-1] - elvt[0]) / 180 * np.pi) / (datet[-1] - datet[0])
    temp_arr[0, 3] = np.tan(np.mean(elvt) / 180 * np.pi) / dthdt            # tane / (de/dt)
    temp_arr[0, 4] = np.min(elvt)                                           # min elv (deg)
    temp_arr[0, 5] = np.max(elvt)                                           # max elv (deg)
    temp_arr[0, 6] = np.mean(azit)                                          # mean azimuth (deg)
    temp_arr[0, 7] = np.max(pgram_sub)                                      # peak of lsp
    temp_arr[0, 8] = np.var(snrdt)                                          # variance of lsp
    temp_arr[0, 9] = datet[-1] - datet[0]                                   # length (in time) of arc (seconds?)
    temp_arr[0, 10] = pktn                                                  # peak-to-noise ratio
    temp_arr[0, 11] = isignal                                               # frequency, integer

    return temp_arr


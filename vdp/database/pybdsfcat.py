"""This module contains the function used to read in a 
source list text file of the kind generated by `PyBDSF`'s 
`write_catalog()` function and stores each line (source)
in a list of objects defined by the class DetectedSource.

"""
import os
import sys
import math
import dbclasses


def read_catalog(fname):
    """Generates a list of DetectedSource objects
    by reading in the source list text file generated
    by PyBDSF.
    
    Parameters
    ----------
    fname : str
        Directory path to the `PyBDSF` text file.

    Returns
    -------
    sources : List of DetectedSource objects
        DetectedSource objects with attribute
        values set from `PyBDSF` output source
        list text file.
    """
    if not os.path.exists(fname):
        print 'ERROR: no such file %s\n' % fname
        sys.exit(0)
    fin = open(fname, 'r')
    # skip first 6 lines, they are header
    for i in range(6):
        line = fin.readline()
        if not line:
            print 'ERROR reading file header! %s\n' % fname
            sys.exit(0) 
    # initialize list for sources:
    sources = []
    # read file:
    while 1:
        # read source data line
        line = fin.readline()
        # check if at end of file
        if not line: break
        # or if line is blank this is an odd file where the
        # table repeats, break! 
        if not line.strip(): break
        # passed checks, proceed
        # append a pybdsf_source object to sources list:
        sources.append(dbclasses.DetectedSource())
        # split data line and append to sources list
        line = line.split()
        sources[-1].src_id = line[0]
        sources[-1].isl_id = line[1]
        sources[-1].ra = float(line[2]) # deg
        sources[-1].e_ra = float(line[3]) # deg
        sources[-1].dec = float(line[4]) # deg
        sources[-1].e_dec = float(line[5]) # deg
        sources[-1].total_flux = float(line[6]) * 1000. # integrated flux in mJy
        sources[-1].e_total_flux = float(line[7]) * 1000. # mJy
        sources[-1].peak_flux = float(line[8]) * 1000. # peak flux in mJy/beam
        sources[-1].e_peak_flux = float(line[9]) * 1000. # mJy/beam
        sources[-1].ra_max = float(line[10]) # RA in deg
        sources[-1].e_ra_max = float(line[11]) # deg
        sources[-1].dec_max = float(line[12]) # Dec in deg
        sources[-1].e_dec_max = float(line[13]) # deg
        sources[-1].maj = float(line[14]) * 3600. # arcsec
        sources[-1].e_maj = float(line[15]) * 3600. # arcsec
        sources[-1].min = float(line[16]) * 3600. # arcsec
        sources[-1].e_min = float(line[17]) * 3600. # arcsec
        sources[-1].pa = float(line[18]) # deg
        sources[-1].e_pa = float(line[19]) # deg
        sources[-1].dc_maj = float(line[26]) * 3600. # arcsec
        sources[-1].e_dc_maj = float(line[27]) * 3600. # arcsec
        sources[-1].dc_min = float(line[28]) * 3600. # arcsec
        sources[-1].e_dc_min = float(line[29]) * 3600. # arcsec
        sources[-1].dc_pa = float(line[30]) # deg
        sources[-1].e_dc_pa = float(line[31]) # deg
        sources[-1].total_flux_isl = float(line[38]) * 1000. # mJy
        sources[-1].total_flux_islE = float(line[39]) * 1000. # mJy
        sources[-1].rms_isl = float(line[40]) * 1000. # mJy/beam
        sources[-1].mean_isl = float(line[41]) * 1000. # mJy/beam
        sources[-1].resid_rms = float(line[42]) * 1000. # mJy/beam
        sources[-1].resid_mean = float(line[43]) * 1000. # mJy/beam
        sources[-1].code = line[44] # 'S', 'C', or 'M'

    fin.close()
    
    return sources


def read_obit(fname):
    if not os.path.exists(fname):
        print 'ERROR: no such file %s\n' % fname
        sys.exit(0)
    fin = open(fname, 'r')
    # skip first 5 (or 6!) lines, they are header
    for i in range(5):
        line = fin.readline()
        if not line: 
            print 'ERROR reading VL Table file header! %s\n' % fname
            sys.exit(0)
        if line[0] == 'm':
            line = fin.readline()

    # initialize list for sources:
    sources = []
    # read file:
    while 1:
        # read source data line
        line = fin.readline()
        # check if at end of file
        if not line: break
        # or if line is blank this is an odd file where the
        # table repeats, break! 
        if not line.strip(): break
        # passed checks, proceed
        # append an obit_source class to sources list:
        sources.append(dbclasses.DetectedSource())
        # split data line and append to sources list
        line = line.split()
        sources[-1].src_id = line[0]
        hr = float(line[1])
        mn = float(line[2])
        sc = float(line[3])
        sources[-1].ra = (15.0*(hr+(mn/60.0)+(sc/3600.0))) # RA in deg
        decdegstr = line[4]
        deg = math.fabs(float(decdegstr))
        mn = float(line[5])
        sc = float(line[6])
        dectmp = deg+(mn/60.0)+(sc/3600.0) # Dec in deg
        if decdegstr[0] == '-':
            dectmp *= -1.0      
        sources[-1].dec = dectmp
        sources[-1].peak_flux = float(line[7]) # peak flux in mJy/beam
        sources[-1].total_flux = float(line[8]) # integrated flux in mJy
        sources[-1].rms_isl = float(line[9]) # mJy/beam
        sources[-1].maj = float(line[10]) # arcsec
        sources[-1].min = float(line[11]) # arcsec
        sources[-1].pa = float(line[12]) # deg
        sources[-1].resid_rms = float(line[13]) # mJy/beam
        sources[-1].resid_peak = float(line[14]) # mJy/beam
        sources[-1].xpix = float(line[15]) # pixel number, x axis
        sources[-1].ypix = float(line[16]) # pixel number, y axis
        # read error estimates line
        line = fin.readline()
        if not line: break
        line = line.split()
        sources[-1].e_ra = float(line[0]) # arcsec
        sources[-1].e_dec = float(line[1]) # arcsec
        sources[-1].e_peak_flux = float(line[2]) # mJy/beam
        sources[-1].e_total_flux = float(line[3]) # mJy
        sources[-1].e_maj = float(line[4]) # arcsec
        sources[-1].e_min = float(line[5]) # arcsec
        sources[-1].e_pa = float(line[6]) # deg

    # print 'read %d sources from:\n  %s' % (len(sources),fname)
    fin.close()
    
    return sources
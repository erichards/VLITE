"""This module defines classes and their methods for
Image and DetectedSource objects.

"""
import os
import re
import logging
import numpy as np
from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy.time import Time
import ephem
from database import pybdsfcat
from sourcefinding import beam_tools


# create logger
dbclasses_logger = logging.getLogger('vdp.database.dbclasses')


class Image(object):
    """A class to hold information about the FITS image file.

    Parameters
    ----------
    image : str
        Directory path to the FITS image file location.

    Attributes
    ----------
    id : int
        Numerical index. Incremented by PostgreSQL upon insertion
        into the database **image** table.
    filename : str
        Full directory path for the image file.
    imsize : str
        Image size in pixels -- (``NAXIS1``, ``NAXIS2``).
    obs_ra : float
        Right ascension of image pointing center (degrees).
    obs_dec : float
        Declination of image pointing center (degrees).
    pixel_scale : float
        Spatial conversion from pixel to angular size on the sky
        (arcseconds / pixel.)
    obj : str
        Name of observed object in the header.
    obs_date : date
        Date when observations were taken.
    map_date : date
        Date when data was imaged.
    obs_freq : float
        Rest frequency of the observations (MHz).
    pri_freq : float
        Frequency of the simultaneously acquired primary
        band data (GHz).
    bmaj : float
        Size of the beam semi-major axis (arcsec).
    bmin : float
        Size of the beam semi-minor axis (arcsec).
    bpa : float
        Beam position angle (degrees).
    noise : float
        Noise estimate from the image center (mJy/beam).
    peak : float
        Peak brightness in the image (mJy/beam).
    config : str
        Very Large Array configuration.
    nvis : int
        Number of visibilities in the data after calibration.
    mjdtime : float
        Modified Julian Date (days since 0h Nov 17, 1858).
    tau_time : float
        Integration time on source in seconds.
    duration : float
        Total time spanned by the observations in seconds.
    nsrc : int
        Number of sources extracted during source finding.
    rms_box : str
        PyBDSF parameter used during source finding.
        From PyBDSF docs: "The first integer, boxsize, is the 
        size of the 2-D sliding box [in pixels] for calculating 
        the rms and mean over the entire image. The second, stepsize, 
        is the number of pixels by which this box is moved for the next 
        measurement."
    error_id : int
        Numerical code assigned when an image fails a quality
        check. Each number has a corresponding explanation in
        the database **error** table.
    stage : int
        Highest processing stage completed. 1 = read image,
        2 = source finding, 3 = source association, 4 = catalog matching.
    radius : float
        Radius defining the circular field-of-view in which
        sources were extracted (degrees).
    nearest_problem : str
        Name of the closest (in angular separation) source which is known
        to cause difficulties in imaging.
    separation : float
        Angular separation between the nearest problem source
        and the image pointing center (degrees).
    """
    # A class variable to count the number of images
    num_images = 0
    
    def __init__(self, image):
        if image.endswith('IMSC.fits'):
            pri_freq = 3
        else:
            pri = re.findall('\/([0-9.]+[A-Z])', image)
            try:
                if pri[0][-1:] == 'M':
                    pri_freq = float(pri[0][:-1]) / 1000. # GHz
                else:
                    pri_freq = float(pri[0][:-1]) # GHz
                # project code 13B-266 is at 1.5 GHz
                if pri_freq == 13:
                    pri_freq = 1.5
            except IndexError:
                pri_freq = None
        self.id = None
        self.filename = image
        self.imsize = None
        self.obs_ra = None
        self.obs_dec = None
        self.pixel_scale = None
        self.obj = None
        self.obs_date = None
        self.map_date = None
        self.obs_freq = None
        self.pri_freq = pri_freq
        self.bmaj = None
        self.bmin = None
        self.bpa = None
        self.noise = None
        self.peak = None
        self.config = None
        self.nvis = None
        self.mjdtime = None
        self.tau_time = None
        self.duration = None
        self.nsrc = None
        self.rms_box = None
        self.error_id = None
        self.stage = 1
        self.radius = None
        self.nearest_problem = None
        self.separation = None


    @classmethod
    def image_count(cls):
        """Returns the number of Image objects initialized."""
        return cls.num_images


    def read(self):
        """Reads FITS image data and header."""
        try:
            data, header = fits.getdata(self.filename, header=True)
            return data, header
        except:
            dbclasses_logger.error('\nERROR: Problem reading image.')


    def write(self, data, header, owrite=False):
        """Writes FITS image data and header."""
        try:
            fits.writeto(self.filename, data, header, overwrite=owrite)
        except TypeError: # astropy version < 1.3
            fits.writeto(self.filename, data, header, clobber=owrite)


    def header_attrs(self, hdr):
        """Extracts all keywords of interest from the FITS image
        header and stores their values as attributes of the
        initialized Image object. If a header keyword is missing
        from the image metadata, then that attribute value is
        set to ``None``. The error_id attribute is also set to 1
        if the missing header keyword is deemed important enough.        

        """
        try:
            naxis1 = hdr['NAXIS1']
            naxis2 = hdr['NAXIS2']
            self.imsize = str((naxis1, naxis2)) # pixels
        except KeyError:
            self.imsize = None
            self.error_id = 1
        try:
            self.obs_ra = hdr['OBSRA'] # deg
        except KeyError:
            self.obs_ra = None
            self.error_id = 1
        if self.obs_ra == 0:
            try:
                self.obs_ra = hdr['CRVAL1'] # deg
                self.error_id = None
            except KeyError:
                self.obs_ra = None
                self.error_id = 1
        try:
            self.obs_dec = hdr['OBSDEC'] # deg
        except KeyError:
            self.obs_dec = None
            self.error_id = 1
        if self.obs_dec == 0:
            try:
                self.obs_dec = hdr['CRVAL2'] # deg
                self.error_id = None
            except KeyError:
                self.obs_dec = None
                self.error_id = 1
        try:
            self.pixel_scale = abs(hdr['CDELT1']) * 3600. # arcsec/pixel
        except KeyError:
            try:
                self.pixel_scale = abs(hdr['CDELT2']) * 3600. # arcsec/pixel
            except KeyError:
                self.pixel_scale = None
                self.error_id = 1
        try:
            self.obj = hdr['OBJECT']
        except KeyError:
            self.obj = None
        try:
            self.obs_date = hdr['DATE-OBS']
        except KeyError:
            self.obs_date = None
            self.error_id = 1
        try:
            self.map_date = hdr['DATE-MAP']
        except KeyError:
            self.map_date = None
        try:
            self.obs_freq = hdr['RESTFREQ'] / 10**6. # MHz
        except KeyError:
            try:
                if hdr['CTYPE3'] == 'FREQ' or hdr['CTYPE3'] == 'SPECLNMF':
                    self.obs_freq = hdr['CRVAL3'] / 10**6. # MHz
                else:
                    self.obs_freq = hdr['CRVAL4'] / 10**6. # MHz
            except KeyError:
                self.obs_freq = None
                self.error_id = 1
        try:
            self.bmaj = hdr['BMAJ'] * 3600. # arcsec
            self.bmin = hdr['BMIN'] * 3600. # arcsec
            self.bpa = hdr['BPA'] # deg
        except KeyError:
            try:
                self.bmaj = hdr['CLEANBMJ'] * 3600. # arcsec
                self.bmin = hdr['CLEANBMN'] * 3600. # arcsec
                self.bpa = hdr['CLEANBPA'] # deg
            except KeyError:
                try:
                    # Search for beam params in AIPS history
                    hl = list(hdr['HISTORY'])
                    for line in hl:
                        x = re.findall('BMAJ=\s+([0-9]\S+)', line)
                        y = re.findall('BMIN=\s+([0-9]\S+)', line)
                        z = re.findall('BPA=\s+([0-9]\S+)', line)
                        if len(x) > 0:
                            self.bmaj = float(x[0]) * 3600. # arcsec
                        if len(y) > 0:
                            self.bmin = float(y[0]) * 3600. # arcsec
                        if len(z) > 0:
                            self.bpa = float(z[0]) # deg
                except KeyError:
                    self.bmaj = None
                    self.bmin = None
                    self.bpa = None
                    self.error_id = 1
        try:
            self.noise = hdr['ACTNOISE'] * 1000. # mJy/beam
        except KeyError:
            self.noise = None
            self.error_id = 1
        try:
            self.peak = hdr['PEAK'] * 1000. # mJy/beam
        except KeyError:
            try:
                self.peak = hdr['DATAMAX'] * 1000. # mJy/beam
            except KeyError:
                self.peak = None
        try:
            self.config = hdr['CONFIG']
        except KeyError:
            self.config = None
        try:
            self.nvis = hdr['NVIS']
        except KeyError:
            self.nvis = None
            self.error_id = 1
        try:
            self.mjdtime = int(hdr['MJDTIME']) + hdr['STARTIME']
        except KeyError:
            self.mjdtime = None
            self.error_id = 1
        try:
            self.tau_time = hdr['TAU_TIME'] # sec
        except KeyError:
            self.tau_time = None
            self.error_id = 1
        try:
            self.duration = hdr['DURATION'] # sec
        except KeyError:
            self.duration = None
            self.error_id = 1


    def set_radius(self, scale):
        """Sets the radius attribute of the Image object.

        Parameters
        ----------
        scale : float
            Fraction between 0 and 1 of the image radius to use.
            The full size of the image field-of-view is multiplied
            by this number.
        """        
        try:
            naxis = float(self.imsize.strip(')').split(',')[1])
            r = (naxis / 2.) * scale
            self.radius = round((r * self.pixel_scale) / 3600., 2) # in deg
        except AttributeError:
            try:
                data, hdr = self.read()
                r = (hdr['NAXIS2'] / 2.) * scale
                self.radius = round(r * hdr['CDELT2'], 2) # in deg
            except KeyError:
                self.radius = None


    def image_qa(self, params):
        """Performs quality checks on the image pre-source finding
        to flag images with the following issues:

        1. missing necessary header keywords (self.error_id = 1)
        2. number of visibilities (nvis) < min_nvis
        3. noise*sqrt(int. time) <= 0 or > max_sensitivity
        4. beam semi-major/semi-minor axis > max_ellip (too elliptical)
        5. target is NCP or a planet
        6. a known bright radio source is in the field-of-view (Cas A, Cygnus A, Taurus A, Hercules A, Virgo A (M87), Perseus A (3C84), the Sun, the Moon, Jupiter, Galactic Center)

        Images that fail checks 1-5 are aborted and do not proceed
        to source finding. Images are flagged if they fail check 6,
        but do continue on.

        """
        dbclasses_logger.info('Performing preliminary image quality checks...')
        
        # Check if image was missing any necessary header keywords
        if self.error_id == 1:
            dbclasses_logger.info('IMAGE FAILED QA: missing necessary header '
                                  'keyword(s).')
            return
        
        # Check number of visibilities (NVIS)
        min_nvis = params['min nvis']
        if self.nvis < min_nvis:
            dbclasses_logger.info('IMAGE FAILED QA: number of visibilities '
                                  '(NVIS) {} < allowed minimum of {}.'.
                                  format(self.nvis, min_nvis))
            self.error_id = 2
            return
        else: pass
        
        # Check image sensitivity metric (noise * sqrt(int. time))
        max_sensitivity = params['max sensitivity metric']
        sensitivity_metric = self.noise * np.sqrt(self.tau_time)
        if sensitivity_metric <= 0:
            dbclasses_logger.info('IMAGE FAILED QA: sensitivity metric '
                                  '(noise x sqrt(int. time)) {} <= 0.'.
                                  format(sensitivity_metric))
            self.error_id = 3
            return
        if sensitivity_metric > max_sensitivity:
            dbclasses_logger.info('IMAGE FAILED QA: sensitivity metric '
                                  '(noise x sqrt(int. time)) {} > allowed '
                                  'maximum of {}.'.format(
                                      sensitivity_metric, max_sensitivity))
            self.error_id = 3
            return
        else: pass

        # Check beam ellipticity
        max_ellip = params['max beam axis ratio']
        axis_ratio = self.bmaj / self.bmin
        if axis_ratio > max_ellip:
            dbclasses_logger.info('IMAGE FAILED QA: beam axis ratio {} > '
                                  'allowed maximum of {}.'.format(
                                      axis_ratio, max_ellip))
            self.error_id = 4
            return
        else: pass

        # VLITE can't do planets or the NCP
        if self.obj == 'NCP' or self.obj == 'ncp':
            dbclasses_logger.info('IMAGE FAILED QA: pointing is at NCP.')
            self.error_id = 5
            return
        else: pass
        # Some planet observations have obs_ra, obs_dec = 0, 0
        if self.obs_ra == 0. and self.obs_dec == 0.:
            dbclasses_logger.info('IMAGE FAILED QA: planet observation with '
                                  'RA, Dec = 0, 0')
            self.error_id = 5
            return
        else: pass

        # Check angular separation from problem sources
        sun = ephem.Sun()
        moon = ephem.Moon()
        jup = ephem.Jupiter()
        # convert from MJD to UTC ISO format
        jdt = Time(self.mjdtime, format='mjd', scale='utc')
        sun.compute(jdt.iso)
        moon.compute(jdt.iso)
        jup.compute(jdt.iso)
        bad_sources = {'Sun' : SkyCoord(str(sun.a_ra), str(sun.a_dec),
                                        unit=('hourangle', 'deg')),
                       'Moon' : SkyCoord(str(moon.a_ra), str(moon.a_dec),
                                         unit=('hourangle', 'deg')),
                       'Jupiter' : SkyCoord(str(jup.a_ra), str(jup.a_dec),
                                            unit=('hourangle', 'deg')),
                       'Cas A' : SkyCoord(350.866250, 58.811667, unit='deg'),
                       'Cen A' : SkyCoord(201.365000, -43.019167, unit='deg'),
                       'Cyg A' : SkyCoord(299.867917, 40.733889, unit='deg'),
                       'Her A' : SkyCoord(252.783750, 4.992500, unit='deg'),
                       'Orion A' : SkyCoord(83.818750, -5.389722, unit='deg'),
                       'Per A' : SkyCoord(49.950417, 41.511667, unit='deg'),
                       'Tau A' : SkyCoord(83.633333, 22.014444, unit='deg'),
                       'Virgo A' : SkyCoord(187.705833, 12.391111, unit='deg'),
                       'GC' : SkyCoord(266.416833, -29.007806, unit='deg')}

        image_center = SkyCoord(self.obs_ra, self.obs_dec, unit='deg')

        min_sep = 999999.99
        for src, loc in bad_sources.items():
            ang_sep = image_center.separation(loc).degree
            while ang_sep < min_sep:
                min_sep = ang_sep
                self.nearest_problem = src
                self.separation = ang_sep
        if min_sep <= self.radius:
            dbclasses_logger.info('IMAGE QA WARNING: {} is in the '
                                  'field-of-view'.format(self.nearest_problem))
            self.error_id = 6
            return
        else: pass

        dbclasses_logger.info('...image passed.')


    def source_qa(self, sources, params):
        """Approximates the expected number of sources in an
        image based on source counts from WENSS scaled by
        noise and fitted beam. See EP's PythonTools.

        """
        max_src_metric = params['max source count metric']

        dbclasses_logger.info('Performing source count quality checks...')
        # First, check if there are any sources
        if len(sources) < 1:
            dbclasses_logger.info('IMAGE FAILED QA: no sources were detected.')
            self.error_id = 8
            return
        else: pass

        # Get number of actual sources within central 1.5 degrees
        nsrc_cut = 0
        for src in sources:
            if src.dist_from_center <= 1.5:
                nsrc_cut += 1

        # Estimate number of expected sources within central 1.5 degrees
        nsrc_exp = beam_tools.expected_nsrc(self.pri_freq, self.noise)
        # Compute metric for determining if source count is way off
        nsrc_metric = (float(nsrc_cut) - nsrc_exp) / nsrc_exp

        if nsrc_metric > max_src_metric:
            dbclasses_logger.info('IMAGE FAILED QA: source count metric '
                                  '{} > allowed max {}.'.format(
                                      nsrc_metric, max_src_metric))
            self.error_id = 9
            return
        else: pass

        dbclasses_logger.info('...image passed.')


    def log_attrs(self, pybdsfdir):
        """Image object method to assign values to object 
        attributes which come from source finding using info 
        in the PyBDSF output log file. This is useful when 
        source finding has already been run on an image and the 
        results are being recorded after the fact using the 
        PyBDSF output files.

        Parameters
        ----------
        pybdsfdir : str
            Directory path to the PyBDSF output files.

        Returns
        -------
        rms_box : str
            PyBDSF parameter used during source finding.
        gresid_std : float
            Standard deviation of the background in the residual 
            image after removing gaussian fitted sources.
        raw_rms : float
            Estimated noise in the image before source extraction.
        """
        prefix = re.findall('.*\/(.*)', img.filename)[0]
        logname = prefix + '.pybdsf.log'
        log = os.path.join(pybdsfdir, logname)
        with open(path) as f:
            log = f.read()
        x = re.findall('.*rms_box.*:\s(\(.*\))', log)
        rms_box = x[-1]
        y = re.findall('.*std. dev:\s(.*)\s\(', log)
        gresid_std = float(y[-1]) * 1000. # mJy/beam
        z = re.findall('.*raw rms =\s+(.*) mJy', log)
        raw_rms = float(z[-1])
        return rms_box, gresid_std, raw_rms


class DetectedSource(object):
    """Class of objects to store elliptical Gaussian fit 
    properties of sources found and measured by PyBDSF. 
    Attribute values are translated from the class of objects 
    output by PyBDSF.

    Attributes
    ----------
    src_id : int
        Uniquely identifies the source in a given image.
    isl_id : int
        Uniquely identifies an island in a given image from
        which sources are formed.
    image_id : int
        Uniquely identifies the image the source comes from.
    ra : float
        Right ascension (degrees).
    e_ra : float
        Error on the right ascension (degrees).
    dec : float
        Declination (degrees).
    e_dec : float
        Error on the declination (degrees).
    total_flux : float
        Total integrated flux (mJy).
    e_total_flux : float
        Error on the total integrated flux (mJy).
    peak_flux : float
        Peak flux density per beam (mJy/beam).
    e_peak_flux : float
        Error on the peak flux (mJy/beam).
    ra_max : float
        Right ascension of the source maximum brightness (degrees).
    e_ra_max : float
        Error on the right ascension of the maximum (degrees).
    dec_max : float
        Declination of the source maximum brightness (degrees).
    e_dec_max : float
        Error on the declination of the maximum (degrees).
    maj : float
        FWHM of the source major axis (arcsec).
    e_maj : float
        Error on the source major axis size (arcsec).
    min : float
        FWHM of the source minor axis (arcsec).
    e_min : float
        Error on the source minor axis size (arcsec).
    pa : float
        Position angle of the source major axis measured east
        of north (degrees).
    e_pa : float
        Error on the source position angle (degrees).
    dc_maj : float
        FWHM of the deconvolved major axis (arcsec).
    e_dc_maj : float
        Error on the deconvolved major axis (arcsec).
    dc_min : float
        FWHM of the deconvolved minor axis (arcsec).
    e_dc_min : float
        Error on the deconvolved minor axis (arcsec).
    dc_pa : float
        Position angle of the deconvolved major axis measured
        east of north (degrees).
    e_dc_pa : float
        Error on the deconvolved position angle (degrees).
    total_flux_isl : float
        Total integrated flux density of the island (mJy).
    total_flux_islE : float
        Error on the total integrated flux density of the island (mJy).
    rms_isl : float
        Average background rms of the island (mJy/beam).
    mean_isl : float
        Average background mean of the island (mJy/beam).
    resid_rms : float
        Average residual background rms of the island (mJy/beam).
    resid_mean : float
        Average residual background mean of the island (mJy/beam).
    code : str
        Defines source structure: 'S' = isolated single-Gaussian source,
        'C' = single-Gaussian source in island with other sources,
        'M' = multi-Gaussian source.
    assoc_id : int
        Links to associated source in the database **assoc_source** table.
    dist_from_center : float
        Angular separation between the source location and image
        pointing center (degrees).
    id : int
        Uniquely identifies the source in the **assoc_source** table.
    res_class : str
        Resolution class of the image in which the source was found.
        'A': res <= 15", 'B': 15" < res <= 35", 'C': 35" < res <= 60",
        'D': res > 60".
    ndetect : int
        Number of times this same source has been detected in other
        VLITE images.
    nmatches : int
        Number of catalogs which contain this source.
    detected : bool
        Whether or not the source was detected in the image (used
        for the **vlite_unique** table).

    References
    ----------
    Refer to the PyBDSF documentation[1]_ for definitions 
    of their output columns.

    .. [1] http://www.astron.nl/citt/pybdsm/write_catalog.html#definition-of-output-columns
    """
    def __init__(self):
        self.src_id = None
        self.isl_id= None
        self.image_id = None
        self.ra = None
        self.e_ra = None
        self.dec = None
        self.e_dec = None
        self.total_flux = None
        self.e_total_flux = None
        self.peak_flux = None
        self.e_peak_flux = None
        self.ra_max = None
        self.e_ra_max = None
        self.dec_max = None
        self.e_dec_max = None
        self.maj = None
        self.e_maj = None
        self.min = None
        self.e_min = None
        self.pa = None
        self.e_pa = None
        self.dc_maj = None
        self.e_dc_maj = None
        self.dc_min = None
        self.e_dc_min = None
        self.dc_pa = None
        self.e_dc_pa = None
        self.total_flux_isl = None
        self.total_flux_islE = None
        self.rms_isl = None
        self.mean_isl = None
        self.resid_rms = None
        self.resid_mean = None
        self.code = None
        self.assoc_id = None
        self.dist_from_center = None
        # assoc_source attributes
        self.id = None
        self.res_class = None
        self.ndetect = None
        self.nmatches = None
        # vlite_unique attribute
        self.detected = None


    def cast(self, origsrc):
        """Attributes of a ``bdsf.gaul2srl.Source`` object
        output from ``bdsf.process_image`` are re-cast to define
        attributes of a DetectedSource object.

        Parameters
        ----------
        origsrc : ``bdsf.gaul2srl.Source`` instance
            Object which stores all the measured properties
            of a source extracted from an image in PyBDSF.

        """
        self.src_id = origsrc.source_id
        self.isl_id= origsrc.island_id
        self.ra = origsrc.posn_sky_centroid[0] # deg
        self.e_ra = origsrc.posn_sky_centroidE[0] # deg
        self.dec = origsrc.posn_sky_centroid[1] # deg
        self.e_dec = origsrc.posn_sky_centroidE[1] # deg
        self.total_flux = origsrc.total_flux * 1000. # mJy
        self.e_total_flux = origsrc.total_fluxE * 1000. # mJy
        self.peak_flux = origsrc.peak_flux_centroid * 1000. # mJy/beam
        self.e_peak_flux = origsrc.peak_flux_centroidE * 1000. # mJy/beam
        self.ra_max = origsrc.posn_sky_max[0] # deg
        self.e_ra_max = origsrc.posn_sky_maxE[0] # deg
        self.dec_max = origsrc.posn_sky_max[1] # deg
        self.e_dec_max = origsrc.posn_sky_maxE[1] # deg
        self.maj = origsrc.size_sky[0] * 3600. # arcsec
        self.e_maj = origsrc.size_skyE[0] * 3600. # arcsec
        self.min = origsrc.size_sky[1] * 3600. # arcsec
        self.e_min = origsrc.size_skyE[1] * 3600. # arcsec
        self.pa = origsrc.size_sky[2] # deg
        self.e_pa = origsrc.size_skyE[2] # deg
        self.dc_maj = origsrc.deconv_size_sky[0] * 3600. # deconvolved
        self.e_dc_maj = origsrc.deconv_size_skyE[0] * 3600.
        self.dc_min = origsrc.deconv_size_sky[1] * 3600.
        self.e_dc_min = origsrc.deconv_size_skyE[1] * 3600.
        self.dc_pa = origsrc.deconv_size_sky[2]
        self.e_dc_pa = origsrc.deconv_size_skyE[2]
        self.total_flux_isl = origsrc.total_flux_isl * 1000. # mJy
        self.total_flux_islE = origsrc.total_flux_islE * 1000. # mJy
        self.rms_isl = origsrc.rms_isl * 1000. # mJy/beam
        self.mean_isl = origsrc.mean_isl * 1000. # mJy/beam
        self.resid_rms = origsrc.gresid_rms * 1000. # mJy/beam
        self.resid_mean = origsrc.gresid_mean * 1000. # mJy/beam
        self.code = origsrc.code


    def calc_center_dist(self, imobj):
        """Calculates a detected source's angular distance
        from the image pointing center in degrees and sets
        the ``dist_from_center`` attribute.

        Parameters
        ----------
        imobj : ``database.dbclasses.Image`` instance
            Initialized Image object with attribute values
            set from header info.
        """
        img_center = SkyCoord(imobj.obs_ra, imobj.obs_dec, unit='deg')
        src_loc = SkyCoord(self.ra, self.dec, unit='deg')
        self.dist_from_center = img_center.separation(src_loc).degree


    def correct_flux(self, pri_freq):
        """Applies a 1-D radial correction to all flux measurements
        from PyBDSF. The correction factor has been empirically derived
        from flux comparisons of sources as a function of angular
        distance from the image center. The scale factor increases
        farther from the pointing center as the beam power decreases.

        Parameters
        ----------
        pri_freq : float
            Primary frequency of the observations in GHz.
        """
        # Correct for beam response - only 1D (sym. beam) for now
        pb_power = beam_tools.find_nearest_pbcorr(self.dist_from_center,
                                                  pri_freq)
        # List of attributes to correct
        attrs = ['total_flux', 'e_total_flux', 'peak_flux', 'e_peak_flux',
                 'total_flux_isl', 'total_flux_islE', 'rms_isl', 'mean_isl',
                 'resid_rms', 'resid_mean']
        for attr in attrs:
            corr_val = getattr(self, attr) / pb_power
            setattr(self, attr, corr_val)
        # Compute S/N of source detection
        self.snr = (self.peak_flux - self.mean_isl) / self.rms_isl
        # Add 20% systematic uncertainty to all flux errors
        self.e_total_flux = np.sqrt(
            (self.total_flux * 0.2)**2. + self.e_total_flux**2.)
        self.e_peak_flux = np.sqrt(
            (self.peak_flux * 0.2)**2. + self.e_peak_flux**2.)
        self.total_flux_islE = np.sqrt(
            (self.total_flux_isl * 0.2)**2. + self.total_flux_islE**2.)


def dict2attr(obj, dictionary):
    """Converts dictionary key-value pairs to object attributes.
    
    Parameters
    ----------
    obj : class instance
        Any object initialized from a class.
    dictionary : dict
        Dictionary key-value pairs become attribute-value pairs.
    """
    for key in dictionary.keys():
        setattr(obj, key, dictionary[key])


def translate_from_txtfile(img, pybdsfdir):
    """Creates a list of DetectedSource objects
    from reading in a source list text file output
    by PyBDSF.
    
    Parameters
    ----------
    img : ``database.dbclasses.Image`` instance
        Initialized Image object with attribute
        values set from header info.
    pybdsfdir : str
        Directory path to PyBDSF files.

    Returns
    -------
    img : ``database.dbclasses.Image`` instance
        Initialized Image object with attribute
        values updated with source finding results.
    sources : list of DetectedSource objects
        DetectedSource objects with attribute values
        set from PyBDSF output source list text file.
    """
    # Set the file path
    prefix = re.findall('.*\/(.*)\.', img.filename)[0]
    srl = prefix + '.pybdsm.srl'
    catalog = os.path.join(pybdsfdir, srl)
    # Read the catalog
    dbclasses_logger.info('Extracting sources from {}.'.format(srl))
    sources = pybdsfcat.read_catalog(catalog)

    # Count the number of sources
    img.nsrc = len(sources)

    # Extract rms_box size and noise from log file
    img.rms_box, img.noise, raw_rms = img.log_attrs(pybdsfdir)

    return img, sources


def translate(img, out):
    """Method to translate PyBDSF output within the
    pipeline to DetectedSource objects and update 
    the Image object.

    Parameters
    ----------
    img : ``database.dbclasses.Image`` instance
        Initialized Image object with attribute values
        set from header info.
    out : ``bdsf.image.Image`` instance
        The object output by PyBDSF after running its
        source finding task ``process_image()``. Contains
        a list of ``bdsf.gaul2srl.Source`` objects which
        are translated into DetectedSource objects.

    Returns
    -------
    newsrcs : list
        List of ``database.dbclasses.DetectedSource`` objects.
        Attributes of each object are set from the PyBDSF
        output object.    
    """
    # Translate PyBDSF output source objects to DetectedSource objects
    newsrcs = []
    for oldsrc in out.sources:
        newsrcs.append(DetectedSource())
        newsrcs[-1].cast(oldsrc)
        newsrcs[-1].image_id = img.id
        newsrcs[-1].calc_center_dist(img)

    return newsrcs


def init_image(impath):
    """Initializes an object of the Image class and sets values 
    for its attributes from the fits file header using
    the ``header_attrs`` object method.

    """
    imobj = Image(impath)
    data, hdr = imobj.read()
    # Use header info to set attributes
    imobj.header_attrs(hdr)
    # Fix header keywords for PyBDSF, if necessary
    header_changed = False
    if hdr['CTYPE3'] == 'SPECLNMF':
        hdr['CTYPE3'] = 'FREQ'
        header_changed = True
    try:
        hdr['BMAJ']
    except KeyError:
        hdr['BMAJ'] = imobj.bmaj / 3600. # deg
        hdr['BMIN'] = imobj.bmin / 3600.
        hdr['BPA'] = imobj.bpa
        header_changed = True
    if header_changed:
        imobj.write(data, hdr, owrite=True)

    return imobj

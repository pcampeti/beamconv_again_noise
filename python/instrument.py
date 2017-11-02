import os
import sys
import time
import warnings
import numpy as np
import qpoint as qp
import healpy as hp
import tools
from detector import Beam

class Instrument(object):
    '''
    Initialize a (ground-based) telescope and specify its properties.
    '''

    def __init__(self, location='spole', lat=None, lon=None,
                 ghost_dc=0.):
        '''
        Set location of telescope on earth.

        Arguments
        ---------
        location : str, optional
            Predefined locations. Current options:
                spole    : (lat=-89.9, lon=169.15)
                atacama  : (lat=-22.96, lon=-67.79)
        lon : float, optional
            Longitude in degrees
        lat : float, optional
            Latitude in degrees
        ghost_dc : float, optional
            Ghost level. Not implemented yet

        '''

        if location == 'spole':
            self.lat = -89.9
            self.lon = 169.15

        elif location == 'atacama':
            self.lat = -22.96
            self.lon = -67.79

        if lat:
            self.lat = lat
        if lon:
            self.lon = lon

        if not self.lat or not self.lon:
            raise ValueError('Specify location of telescope')

    def set_focal_plane(self, nrow=1, ncol=1, fov=10):
        '''
        Create detector pointing offsets on the sky, i.e. in azimuth and
        elevation, for a square grid of detectors. Every point on the grid
        houses two detectors with orthogonal polarization angles.

        This function bypasses the creation of a Beam list

        Arguments
        ---------

        nrow : int (default: 1)
            Number of detectors per row
        ncol : int (default: 1)
            Number of detectors per column
        fov : float
            Angular size of side of square focal plane on
            sky in degrees

        '''

        self.nrow = nrow
        self.ncol = ncol
        self.ndet = nrow * ncol # note, no pairs
        self.azs = np.zeros((nrow, ncol), dtype=float)
        self.els = np.zeros((nrow, ncol), dtype=float)
        self.polangs = np.zeros(nrow*ncol, dtype=float)

        x = np.linspace(-fov/2., fov/2., ncol)
        y = np.linspace(-fov/2., fov/2., nrow)
        xx, yy = np.meshgrid(x, y)

        self.azs = xx.flatten()
        self.els = yy.flatten()


    def create_focal_plane(self, nrow=1, ncol=1, fov=10.):
        '''
        Create detector pointing offsets on the sky, i.e. in azimuth and
        elevation by generating a list of Pointing objects.

        Arguments
        ---------
        nrow : int (default: 1)
            Number of detectors per row
        ncol : int (default: 1)
            Number of detectors per column
        fov : float (default: 10.)
            Angular size of side of square focal plane on
            sky in degrees

        '''

        self.nrow = nrow
        self.ncol = ncol
        self.ndet = 2 * nrow * ncol

        nsr = np.ceil(np.log10(self.nrow))
        nsc = np.ceil(np.log10(self.ncol))

        x = np.linspace(-fov/2., fov/2., ncol)
        y = np.linspace(-fov/2., fov/2., nrow)
        xx, yy = np.meshgrid(x, y)

        beams = []

        self.azs = np.zeros((nrow, ncol), dtype=float)
        self.els = np.zeros((nrow, ncol), dtype=float)

        for j, xi in enumerate(x):
            for i, yi in enumerate(y):

                if nsr < 2 and nsc < 2:
                    det_str = 'r{:02d}c{:02d}a'.format(i, j)
                else:
                    det_str = 'r{:03d}c{:03d}a'.format(i, j)

                beami = Beam(az=xi, el=yi, name=det_str, polangle=0.,
                    pol='A', btype='Gaussian')
                beams.append(beami)

                beami = Beam(az=xi, el=yi, name=det_str, polangle=90.,
                    pol='B', btype='Gaussian')
                beams.append(beami)

                self.azs[i][j] = xi
                self.els[i][j] = yi

        self.azs = self.azs.flatten()
        self.els = self.els.flatten()

        self.beams = beams

        assert (len(self.beams) == self.ndet), 'Wrong number of detecors!'

    def kill_channels(self, killfrac=0.2):
        '''
        Randomly identifies detectors in the beams list and sets their 'dead'
        attribute to True.

        Arguments
        ---------

        killfrac : 0 < float < 1  (default: 0.2)
            The relative number of detectors to kill

        '''

        killidx = np.random.randint(0, self.ndet, np.floor(killfrac*self.ndet))

        for beam in self.beams[killidx]:
            beam.dead = True


    def load_beam_directory(bdir):
        '''
        Loads a collection of beam maps to use for a scanning simulation. The
        beam maps should be stored as a collection of pickled dictionaries.

        Arguments
        ---------

        bdir : str
            The path to the directory containing beam maps

        '''

        beams = []
        file_list = sorted(glob.glob(bdir+'*.pkl'))

        for filei in file_list:

            bdata = pickle.load(open(filei, 'r'))
            pointings.append(Pointing(bdict=bdata))

        self.beams = beams


    def get_blm(self, lmax, channel=None, fwhm=None, pol=True):
        '''
        Load or create healpix-formatted blm array(s) for specified
        channels.

        Arguments
        ---------
        channel
        lmax
        fwhm : float
            FWHM of symmetric gaussian beam in arcmin. If this
            option is set, return blm array(s) with symmetric
            gaussian beam in appropriate slices in blm

        Returns
        -------
        blm (blm, blmm2) : (tuple of) array(s).
            Healpix-formatted beam blm array.
            Also returns blmm2 if pol is set

        '''

        # for now, just create a blm array with sym, gaussian beam
        if fwhm:
            return tools.gauss_blm(fwhm, lmax, pol=True)

    def get_blm_spider(self):
        pass

    def get_ghost(self):
        pass
    # function that introduces ghosts, i.e add detector offsets and corresponding beams


class ScanStrategy(qp.QMap, Instrument):
    '''
    Given an instrument, create a scan strategy in terms of
    azimuth, elevation, position and polarization angle.
    '''

    _qp_version = (1, 10, 0)

    def __init__(self, duration, sample_rate=100, **kwargs):
        '''
        Initialize scan parameters

        Arguments
        ---------
        duration : float
            Mission duration in seconds.
        sample_rate : float
             Sample rate in Hz.
        '''

        # extract Instrument class specific kwargs.
        instr_kw = tools.extract_func_kwargs(
                   Instrument.__init__, kwargs)

        # Initialize the instrument and qpoint.
        Instrument.__init__(self, **instr_kw)

      # Checking qpoint version
        if qp.version() < self._qp_version:
            raise RuntimeError(
                 'qpoint version {} required, found version {}'.format(
                     self._qp_version, qp.version()))

        qp.QMap.__init__(self, nside=256, pol=True, fast_math=True,
                         mean_aber=True, accuracy='low')
#                         fast_pix=True, interp_pix=True,
#                         interp_missing=True)

        ctime_kw = tools.extract_func_kwargs(self.set_ctime, kwargs)
        self.set_ctime(**ctime_kw)
        self.set_sample_rate(sample_rate)
        self.set_mission_len(duration)

        self.rot_dict = {}
        self.hwp_dict = {}
        self.set_instr_rot()
        self.set_hwp_mod()

        self.set_nsides(**tools.extract_func_kwargs(self.set_nsides,
                                                  kwargs))

    def __del__(self):
        '''
        Call QPoint destructor explicitely to make sure
        the c code frees up memory before exiting.
        '''
        self.__del__


    def set_ctime(self, ctime0=None):
        '''
        Set starting time.

        Arguments
        ---------
        ctime0 : int, optional
            Unix time in seconds. If None, use current time.
        '''
        if ctime0:
            self.ctime0 = ctime0
        else:
            self.ctime0 = time.time()

    def set_sample_rate(self, sample_rate=None):
        '''
        Set detector/pointing sample rate in Hz

        Arguments
        ---------
        sample_rate : float
            Sample rate in Hz
        '''

        self.fsamp = float(sample_rate)

    def set_mission_len(self, duration=None):
        '''
        Set total duration of mission.

        Arguments
        ---------
        duration : float
            Mission length in seconds
        '''

        self.mlen = duration
        self.nsamp = int(self.mlen * self.fsamp)

    def set_nsides(self, nside_spin=256, nside_out=256):
        '''
        Set the nside parameter of the spin maps that are
        scanned and the output maps.

        Arguments
        ---------
        nside_spin : int
            Nside of spin maps
        nside_out : int
            Nside of output maps.
        '''

        self.nside_spin = nside_spin
        self.nside_out = nside_out

    def set_instr_rot(self, period=None, start_ang=0.,
                      angles=None):
        '''
        Have the instrument periodically rotate around
        the boresight.

        Arguments
        ---------
        period : float
            Rotation period in seconds. If left None,
            keep instrument unrotated.
        start_ang : float, optional
            Starting angle of the instrument in deg.
            Default = 0 deg.
        angles : array-like, optional
            Set of rotation angles. If left None, cycle
            through 45 degree steps. If set, ignores
            start_ang
        '''

        self.rot_dict['period'] = period
        self.rot_dict['angle'] = start_ang
        self.rot_dict['remainder'] = 0.

        if angles is None:
            angles = np.arange(start_ang, 360+start_ang, 45)
            np.mod(angles, 360, out=angles)

        # init rotation generator
        self.rot_angle_gen = tools.angle_gen(angles)

    def set_hwp_mod(self, mode=None,
                    freq=None, start_ang=0.,
                    angles=None, reflectivity=None):
        '''
        Modulate the polarized sky signal using a stepped or
        continuously rotating half-wave plate.

        Arguments
        ---------
        mode : str
            Either "stepped" or "continuous"
        freq : float, optional
            Rotation or step frequency in Hz
        start_ang : float, optional
            Starting angle for the HWP in deg
        angles : array-like, optional
            Rotation angles for stepped HWP. If not set,
            use 22.5 degree steps.
        reflectivity : float, optional
            Not yet implemented
        '''

        self.hwp_dict['mode'] = mode
        self.hwp_dict['freq'] = freq
        self.hwp_dict['angle'] = start_ang
        self.hwp_dict['remainder'] = 0 # sec remaining for step
        self.hwp_dict['reflectivity'] = reflectivity

        if angles is None:
            angles = np.arange(start_ang, 360+start_ang, 22.5)
            np.mod(angles, 360, out=angles)

        # init hwp ang generator
        self.hwp_angle_gen = tools.angle_gen(angles)

    def partition_mission(self, chunksize):
        '''
        Divide up the mission in equal-sized chunks
        of nsample = chunksize. (final chunk can be
        smaller).

        Arguments
        ---------
        chunksize : int
            Chunk size in samples

        Returns
        -------
        chunks : list of dicts
            Dictionary with start and end of each
            chunk
        '''
        nsamp = self.nsamp

        chunksize = nsamp if chunksize >= nsamp else chunksize
        nchunks = int(np.ceil(nsamp / float(chunksize)))
        chunks = []
        start = 0

        for chunk in xrange(nchunks):
            end = start + chunksize - 1
            end = nsamp - 1 if end >= (nsamp - 1) else end
            chunks.append(dict(start=start, end=end))
            start += chunksize

        self.chunks = chunks
        return chunks

    def subpart_chunk(self, chunk):
        '''
        Sub-partition a chunk into sub-chunks given
        by the instrument rotation period (only
        when it is smaller than the chunk size).

        Arguments
        ---------
        chunk : dict
            Chunk dict containing start and end sample
            indices.

        Returns
        -------
        subchunks : list of dicts
            List of subchunk dicts that contain
            start and end sample indices.
        '''

        period = self.rot_dict['period']

        if not period:
        # No instrument rotation, so no need for subchunks
            return [chunk]

        rot_chunk_size = period * self.fsamp
        chunksize = chunk['end'] - chunk['start'] + 1

        # Currently, rotation periods longer than computation chunks
        # are not implemented. So warn user and rotate per comp. chunk.
        if rot_chunk_size > chunksize:
            warnings.warn(
              'Rotation period * fsamp > chunk size: instrument rotates per chunk')
            return [chunk]

        nchunks = int(np.ceil(chunksize / rot_chunk_size))
        subchunks = []
        start = chunk['start']

        for sidx, subchunk in enumerate(xrange(nchunks)):
            if sidx == 0 and self.rot_dict['remainder'] != 0:
                end = int(start + self.rot_dict['remainder'])
            else:
                end = int(start + rot_chunk_size - 1)

            if end > chunk['end']:
                self.rot_dict['remainder'] = end - chunk['end'] + 1
                end = chunk['end']

            subchunks.append(dict(start=start, end=end))
            start += int(rot_chunk_size)

        return subchunks

    def allocate_maps(self):
        '''
        Allocate space in memory for map-related numpy arrays
        '''

        self.vec = np.zeros((3, 12*self.nside_out**2), dtype=float)
        self.proj = np.zeros((6, 12*self.nside_out**2), dtype=float)

    def scan_instrument(self, verbose=True, mapmaking=True,
                        **kwargs):
        '''
        Cycles through chunks, scans and calculates
        detector tods. Optionally: also bin tods into
        maps.

        Arguments
        ---------
        verbose : bool [default True]
            Prints status reports
        mapmaking : bool, optional
            If True, bin tods into vec and proj.
        kwargs : dict
            Extra kwargs are assumed input to
            constant_el_scan()
        '''

        if verbose:
            print('  Scanning with {:d} x {:d} grid of detectors'.format(
                self.nrow, self.ncol))

        for cidx, chunk in enumerate(self.chunks):

            if verbose:
                print('  Working on chunk {:03}: samples {:d}-{:d}'.format(cidx,
                    chunk['start'], chunk['end']))

            # Make the boresight move
            ces_kwargs = kwargs.copy()
            ces_kwargs.update(chunk)
            self.constant_el_scan(**ces_kwargs)

            # if required, loop over boresight rotations
            for subchunk in self.subpart_chunk(chunk):

                # rotate instrument if needed
                if self.rot_dict['period']:
                    self.rot_dict['angle'] = self.rot_angle_gen.next()

                # Cycling through detectors and scanning
                for chnidx in xrange(self.ndet):
                    
                    az_off = self.azs[chnidx]
                    el_off = self.els[chnidx]
                    polang = self.polangs[chnidx]

                    self.scan(az_off=az_off, el_off=el_off, 
                              polang=polang, **subchunk)

                    if mapmaking:
                        self.bin_tod()

                        # Adding to global maps
                        self.vec += self.depo['vec']
                        self.proj += self.depo['proj']

    def constant_el_scan(self, ra0=-10, dec0=-57.5, az_throw=90,
            scan_speed=1, el_step=None, vel_prf='triangle',
            start=None, end=None):

        '''
        Let boresight scan back and forth in azimuth, starting
        centered at ra0, dec0, while keeping elevation constant. Populates
        scanning quaternions.

        Arguments
        ---------
        ra0 : float
            Ra coordinate of centre of scan in degrees
        dec0 : float
            Ra coordinate of centre of scan in degrees
        az_throw : float
            Scan width in azimuth (in degrees)
        scan_speed : float
            Max scan speed in degrees per second
        el_step : float, optional
            Offset in elevation (in degrees). Defaults
            to zero when left None.
        vel_prf : str
            Velocity profile. Current options:
                triangle : (default) triangle wave with total
                           width=az_throw
        start : int
            Starting sample
        end : int
            End at this sample
        '''

        chunk_len = end - start + 1 # Note, you end on "end"
        ctime = np.arange(start, end+1, dtype=float)
        ctime /= float(self.fsamp)
        ctime += self.ctime0

        # use qpoint to find az, el corresponding to ra0, el0
        az0, el0, _ = self.radec2azel(ra0, dec0, 0,
                                       self.lon, self.lat, ctime[0])

        # Scan boresight, note that it will slowly drift away from az0, el0
        if vel_prf is 'triangle':
            scan_period = 2 * az_throw / float(scan_speed) # in deg.
            if scan_period == 0.:
                az = np.zeros(chunk_len)
            else:
                az = np.arcsin(np.sin(2 * np.pi * np.arange(chunk_len, dtype=int)\
                                          / scan_period / self.fsamp))
                az *= az_throw / (np.pi)
            az += az0

        # step in elevation if needed
        if el_step:
            el = el0 + el_step * np.ones_like(az)
        else:
            el = el0 * np.ones_like(az)

        # return quaternion with ra, dec, pa
        self.q_bore = self.azel2bore(az, el, None, None, self.lon, self.lat, ctime)

    def scan(self, az_off=None, el_off=None, polang=0,
             start=None, end=None):
        '''
        Update boresight pointing with detector offset, and
        use it to bin spinmaps into a tod.

        Arguments
        ---------

        az_off : float (default: None)
            The detector azimuthal offset relative to borsight [deg]
        el_off : float (default: None)
            The detector elevation offset relative to borsight [deg].
            Use ScanStrategy attribute if n
        polang : float (default: None)
            Detector polarization angle
        start  :
        end    :

        '''

        # NOTE nicer if you give q_off directly instead of az_off, el_off
        # we use a offset quaternion without polang. 
        # We apply polang at the beam level later.
        q_off = self.det_offset(az_off, el_off, 0)

        # Rotate offset given rot_dict['angle']
        ang = np.radians(self.rot_dict['angle'])

        # works, but shouldnt it be switched around? No, that would
        # rotate the polang of the centroid, but not the centroid
        # around the boresight. It's q_bore * q_rot * q_off
        q_rot = np.asarray([np.cos(ang/2.), 0., 0., np.sin(ang/2.)])
        q_off = tools.quat_left_mult(q_rot, q_off) # works
#        q_off = tools.quat_left_mult(q_off, q_rot)  # no

        # store for mapmaking
        self.q_off = q_off
        self.polang = polang

        ctime = np.arange(start, end+1, dtype=float)
        ctime /= float(self.fsamp)
        ctime += self.ctime0
        self.ctime = ctime
        tod_size = ctime.size

        tod_c = np.zeros(tod_size, dtype=np.complex128)

        # normal chunk len
        nrml_len = self.chunks[0]['end'] - self.chunks[0]['start'] + 1
        if len(self.chunks) > 1:
            shrt_len = self.chunks[-1]['end'] - self.chunks[-1]['start'] + 1
        else:
            shrt_len = nrml_len

        if self.q_bore.shape[0] == nrml_len:
            qidx_start = np.mod(start, nrml_len)
            qidx_end = qidx_start + end - start

        else: # we know we're in the last big chunk
            qidx_start = start - (len(self.chunks)-1) * nrml_len
            qidx_end = end - (len(self.chunks)-1) * nrml_len

        self.qidx_start = qidx_start
        self.qidx_end = qidx_end

        # more efficient if you do bore2pix, i.e. skip
        # the allocation of ra, dec, pa etc. But you need pa....
        # Perhaps ask Sasha if she can make bore2pix output pix
        # and pa (instead of sin2pa, cos2pa)
        ra, dec, pa = self.bore2radec(q_off, ctime, self.q_bore[qidx_start:qidx_end+1],
            q_hwp=None, sindec=False, return_pa=True)
        
        np.radians(pa, out=pa)
        pix = tools.radec2ind_hp(ra, dec, self.nside_spin)

        # expose pixel indices for test centroid
        self.pix = pix

        # Fill complex array
        for nidx, n in enumerate(xrange(-self.N+1, self.N)):

            exppais = np.exp(1j * n * pa)
            tod_c += self.func_c[nidx][pix] * exppais

        # if needed, compute hwp angle array.
        if self.hwp_dict['freq']:

            freq = self.hwp_dict['freq'] # cycles per sec for cont.
            start_ang = np.radians(self.hwp_dict['angle'])

            if self.hwp_dict['mode'] == 'continuous':

                hwp_ang = np.linspace(start_ang,
                       start_ang + 2 * np.pi * tod_size / float(freq * self.fsamp),
                       num=tod_size, endpoint=False, dtype=float) # radians (w = 2 pi freq)

                # update mod 2pi start angle for next chunk
                self.hwp_dict['angle'] = np.degrees(np.mod(hwp_ang[-1], 2*np.pi))
                self.hwp_ang = hwp_ang

            if self.hwp_dict['mode'] == 'stepped':

                step_size = int(self.fsamp / float(freq)) # samples per step
                start_ang = self.hwp_dict['angle']
                hwp_ang = np.zeros(tod_size, dtype=float)
                nsteps = int(np.ceil(tod_size / float(step_size)))

                startidx = 0
                for sidx, step in enumerate(xrange(nsteps+1)):
                    if sidx == 0 and self.hwp_dict['remainder'] != 0:
                        hwp_ang[:self.hwp_dict['remainder']] += np.radians(start_ang)
                        startidx = self.hwp_dict['remainder']
                    else:
                        if startidx + step_size > tod_size:

                            endidx = tod_size - 1
                            self.hwp_dict['remainder'] = startidx + step_size - endidx
                            hwp_ang[startidx:endidx] += np.radians(
                                self.hwp_angle_gen.next())

                            # we're in the last chunk
                            break

                        else:
                            endidx = startidx + step_size

                            hwp_ang[startidx:endidx] += np.radians(
                                self.hwp_angle_gen.next())

                        startidx += step_size

                # update mod 2pi start angle for next chunk
                self.hwp_dict['angle'] = np.degrees(np.mod(hwp_ang[-1], 2*np.pi))
                self.hwp_ang = hwp_ang
        else:
            hwp_ang = 0.
            self.hwp_ang = 0

        # modulate by hwp angle and polarization angle
        expm2 = np.exp(1j * (4 * hwp_ang + 2 * np.radians(polang)))
        tod_c[:] = np.real(tod_c * expm2 + np.conj(tod_c * expm2)) / 2.
        tod = np.real(tod_c) # shares memory with tod_c

        # add unpolarized tod
        for nidx, n in enumerate(xrange(-self.N+1, self.N)):

            if n == 0: #avoid expais since its one anyway
                tod += np.real(self.func[n][pix])

            if n > 0:
                tod += 2 * np.real(self.func[n,:][pix]) * np.cos(n * pa)
                tod -= 2 * np.imag(self.func[n,:][pix]) * np.sin(n * pa)

        self.tod = tod

    def get_spinmaps(self, alm, blm, max_spin=5, verbose=True):
        '''
        Compute convolution of map with different spin modes
        of the beam. Computed per spin, so creates spinmmap
        for every s<= 0 for T and for every s for pol.

        Arguments
        ---------
        alm : tuple of array-like
            Tuple containing alm, almE and almB
        blm : tuple of array-like
            Tuple containing blm, blmp2 and blmm2
        max_spin : int, optional
            Maximum spin value describing the beam

        '''

        # Turning off healpy printing
        if not verbose:
            sys.stdout = open(os.devnull, 'w') # Suppressing screen output

        self.N = max_spin + 1
        nside = self.nside_spin
        lmax = hp.Alm.getlmax(alm[0].size)


        # Unpolarized sky and beam first
        self.func = np.zeros((self.N, 12*nside**2),
                             dtype=np.complex128) # s <=0 spheres

        start = 0
        for n in xrange(self.N): # note n is s
            end = lmax + 1 - n
            if n == 0: # scalar transform

                flmn = hp.almxfl(alm[0], blm[0][start:start+end], inplace=False)
                self.func[n,:] += hp.alm2map(flmn, nside)

            else: # spin transforms

                bell = np.zeros(lmax+1, dtype=np.complex128)
                # spin n beam
                bell[n:] = blm[0][start:start+end]

                flmn = hp.almxfl(alm[0], bell, inplace=False)
                flmmn = hp.almxfl(alm[0], np.conj(bell), inplace=False)

                flmnp = - (flmn + flmmn) / 2.
                flmnm = 1j * (flmn - flmmn) / 2.
                spinmaps = hp.alm2map_spin([flmnp, flmnm], nside, n, lmax, lmax)
                self.func[n,:] = spinmaps[0] + 1j * spinmaps[1]

            start += end

        # Pol
        self.func_c = np.zeros((2*self.N-1, 12*nside**2), dtype=np.complex128) # all spin spheres

        almp2 = -1 * (alm[1] + 1j * alm[2])
        almm2 = -1 * (alm[1] - 1j * alm[2])

        blmm2 = blm[1]
        blmp2 = blm[2]

        start = 0
        for n in xrange(self.N):
            end = lmax + 1 - n

            bellp2 = np.zeros(lmax+1, dtype=np.complex128)
            bellm2 = bellp2.copy()

            bellp2[np.abs(n):] = blmp2[start:start+end]
            bellm2[np.abs(n):] = blmm2[start:start+end]

            ps_flm_p = hp.almxfl(almp2, bellm2, inplace=False) + \
                hp.almxfl(almm2, np.conj(bellm2), inplace=False)
            ps_flm_p /= -2.

            ps_flm_m = hp.almxfl(almp2, bellm2, inplace=False) - \
                hp.almxfl(almm2, np.conj(bellm2), inplace=False)
            ps_flm_m *= 1j / 2.

            ms_flm_p = hp.almxfl(almm2, bellp2, inplace=False) + \
                hp.almxfl(almp2, np.conj(bellp2), inplace=False)
            ms_flm_p /= -2.

            ms_flm_m = hp.almxfl(almm2, bellp2, inplace=False) - \
                hp.almxfl(almp2, np.conj(bellp2), inplace=False)
            ms_flm_m *= 1j / 2.

            if n == 0:
                spinmaps = [hp.alm2map(-ps_flm_p, nside),
                            hp.alm2map(-ms_flm_m, nside)]

                self.func_c[self.N-n-1,:] = spinmaps[0] - 1j * spinmaps[1]

            else:
                # positive spin
                spinmaps = hp.alm2map_spin([ps_flm_p, ps_flm_m],
                                           nside, n, lmax, lmax)
                self.func_c[self.N+n-1,:] = spinmaps[0] + 1j * spinmaps[1]

                # negative spin
                spinmaps = hp.alm2map_spin([ms_flm_p, ms_flm_m],
                                           nside, n, lmax, lmax)
                self.func_c[self.N-n-1,:] = spinmaps[0] - 1j * spinmaps[1]

            start += end

        # Turning printing back on
        if not verbose:
            sys.stdout = sys.__stdout__

    def bin_tod(self, init=True):
        '''
        Take internally stored tod and pointing
        and bin into map and projection matrices.
        '''

        # this works, but you should use the c code from qpoint
#        q_hwp = np.zeros((self.ctime.size, 4), dtype=float)
#        q_hwp[:,0] = np.cos(-self.hwp_ang)
#        q_hwp[:,3] = np.sin(-self.hwp_ang)

        q_hwp = self.hwp_quat(np.degrees(self.hwp_ang))

        self.init_point(q_bore=self.q_bore[self.qidx_start:self.qidx_end+1],
                        ctime=self.ctime, q_hwp=q_hwp)

        # use q_off quat with polang (and instr. ang) included.
        q_off = self.q_off
        polang = -np.radians(self.polang)
        q_polang = np.asarray([np.cos(polang/2.), 0., 0., np.sin(polang/2.)])
        q_off = tools.quat_left_mult(q_off, q_polang) 

        if init:
            self.init_dest(nside=self.nside_out, pol=True, reset=True)

        q_off = q_off[np.newaxis]
        tod = self.tod[np.newaxis]
        vec, proj = self.from_tod(q_off, tod=tod)


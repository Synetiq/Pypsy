import numpy as np
import scipy.signal
import Pypsy.signal.utilities
import Pypsy.signal.analysis

__author__ = 'Brennon Bortz'


class Signal(object):
    """
    `Signal` represents a basic signal and timestamps for this signal.

    Parameters
    ----------
    data : :py:class:`numpy.ndarray`
        The signal's data. ``data[x]`` is the value of the signal at ``time[x]``.
    time : :py:class:`numpy.ndarray`
        The times (in seconds) at which the signal was sampled. ``time[x]`` is the time at which the measure of the
        signal at ``data[x]`` was taken.

    Attributes
    ----------
    data : :py:class:`numpy.ndarray`
        The signal's data. ``data[x]`` is the value of the signal at ``time[x]``.
    time : :py:class:`numpy.ndarray`
        The times (in seconds) at which the signal was sampled. ``time[x]`` is the time at which the measure of the
        signal at ``data[x]`` was taken.
    original_data : :py:class:`numpy.ndarray`
        The data with which the signal was originally instantiated
    original_time : :py:class:`numpy.ndarray`
        The times (in seconds) at which the signal was sampled with which the signal was originally instantiated

    Raises
    ------
    ValueError
        If ``data`` and ``time`` are not the same length
    TypeError
        TypeError
        If either of ``time`` or ``data`` are not array-like (cannot be converted to a :py:class:`numpy.ndarray` using
        :py:meth:`numpy.array()`)

    Examples
    --------
    >>> data = [0, 1, 2]
    >>> time = [0.0, 0.1, 0.2]
    >>> sig = Signal(data, time)
    >>> sig.data.tolist() == data
    True
    >>> sig.time.tolist() == time
    True

    >>> sig.data[0] = 15
    >>> sig.data.tolist()
    [15.0, 1.0, 2.0]
    >>> sig.original_data.tolist() == data
    True

    >>> Signal(data, time[:-1])
    Traceback (most recent call last):
        ...
    ValueError: data and time must be the same length.

    >>> Signal(data, None)
    Traceback (most recent call last):
        ...
    ValueError: data and time must be the same length.
    """

    data = np.array([])
    time = np.array([])

    def __init__(self, data, time):
        data = np.asarray(data, dtype=np.float64)
        time = np.asarray(time, dtype=np.float64)

        # data and time must be the same length
        if data.size != time.size:
            raise ValueError('data and time must be the same length.')

        # Store original copy of data and time, and working copies
        self.data = np.array(data)
        self.time = np.array(time)
        self.original_data = np.array(data)
        self.original_time = np.array(time)


class EDASignal(Signal):
    """
    `EDASignal` represents an electrodermal activity signal. It includes facilities for the decomposition of
    electrodermal activity into its tonic and phasic components. These facilities are a port of Ledalab from
    `Ledalab <http://www.ledalab.de>`_ from MATLAB.

    Parameters
    ----------
    data : :py:class:`numpy.ndarray`
        The signal's data. ``data[x]`` is the value of the signal at ``time[x]``.
    time : :py:class:`numpy.ndarray`
        The times (in seconds) at which the signal was sampled. ``time[x]`` is the time at which the measure of the
        signal at ``data[x]`` was taken.

    Attributes
    ----------
    phasic_data : :py:class:`numpy.ndarray`
        The phasic EDA component. This array is populated by :py:meth:`Pypsy.signal.EDASignal.decompose_signal`.
    phasic_driver : :py:class:`numpy.ndarray`
        The driver of the phasic EDA component. This array is populated by
        :py:meth:`Pypsy.signal.EDASignal.decompose_signal`
    tau : :py:class:`numpy.ndarray`
        The :math:`\\tau_1` and :math:`\\tau_2` parameters used to decompose the signal. These parameters are initially
        :math:`\\tau_1 = 1` and :math:`\\tau_2 = 3.75`, and are automatically adjusted when
        :py:meth:`Pypsy.signal.EDASignal.decompose_signal` is called with ``optimize=True``.
    tonic_data : :py:class:`numpy.ndarray`
        The tonic EDA component. This array is populated by :py:meth:`Pypsy.signal.EDASignal.decompose_signal`.
    tonic_driver : :py:class:`numpy.ndarray`
        The driver of the tonic EDA component. This array is populated by
        :py:meth:`Pypsy.signal.EDASignal.decompose_signal`.

    Examples
    --------
    >>> data = [1, 2, 3]
    >>> time = [0.1, 0.2, 0.3]
    >>> sig = EDASignal(data, time)
    """

    def __init__(self, data, time):
        super().__init__(data, time)

        self.composite_driver = np.array([], dtype=np.float64)
        self.composite_driver_remainder = np.array([], dtype=np.float64)
        self.kernel = np.array([], dtype=np.float64)
        self.phasic_data = np.array([], dtype=np.float64)
        self.phasic_driver = np.array([], dtype=np.float64)
        self.phasic_driver_raw = np.array([], dtype=np.float64)
        self.tau = np.array([1., 3.75])
        self.tonic_data = np.array([], dtype=np.float64)
        self.tonic_driver = np.array([], dtype=np.float64)
        self.error = dict()
        self.error['MSE'] = None
        self.error['RMSE'] = None
        self.error['discreteness'] = None
        self.error['negativity'] = None
        self.error['compound'] = None

    def decompose_signal(self, optimize=False):
        """
        Decompose the EDA signal into its tonic and phasic components. This decomposition is identical to the continuous
        analysis performed by `Ledalab <http:www.ledalab.de>`_.

        Parameters
        ----------
        optimize : bool
            When ``True``, the parameters in ``self.tau`` are optimized to minimize error. When ``False``, the current
            values of ``self.tau`` are used for decomposition.
        """

        import Pypsy.optimization

        if optimize:
            x, history = Pypsy.optimization.cgd(self.tau, self._decompose, np.array([.3, 2]), .01, 20, .05)
        else:
            self._decompose(self.tau)

    def _decompose(self, tau):

        # Ensure that parameters are within limits
        tau[0] = Pypsy.constrain(tau[0], .001, 10)
        tau[1] = Pypsy.constrain(tau[1], .001, 20)

        if tau[1] < tau[0]:
            tau = tau[::-1]

        if np.abs(tau[0] - tau[1]) < .01:

            # FIXME: Shouldn't this be tau[1] = tau[0] + .01
            tau[1] = tau[1] + .01

        # Resample at 25Hz
        Pypsy.signal.utilities.resample_signal(self, 25.0)

        d = self.data.copy()
        t = self.time.copy() # Set in MATLAB as leda2.analysis0.target.t

        # FIXME: Sample rate should be calculated
        sr = 25. # Set in MATLAB as leda2.analysis0.target.sr
        smoothwin = 1.6 # Set in MATLAB as leda2.analysis0.smoothwin * 8
        dt = 1./sr
        winwidth_max = 3
        swin = np.round(np.min(np.array([smoothwin, winwidth_max]) * sr))

        # Data preparation

        # Set tb to be original timestamps, shifted to zero, and adding one
        # timestep
        tb = t - t[0] + dt

        # Get a smoothed Bateman output with predefined parameters
        bg = Pypsy.signal.analysis.bateman_gauss(tb, 5, 1, 2, 40, .4)

        # Get the index of the max of the Bateman output
        idx = np.argmax(bg)

        # prefix is Bateman output up to one beyond the max, normalized by the
        # value at one beyond the max, and then multiplied by the first value in
        # the EDA vector
        prefix = (bg[0:idx+1] / bg[idx+1]) * d[0]

        # Remove any zero values from prefix
        # prefix = nonzeros(prefix);
        prefix = prefix[np.nonzero(prefix)]

        # n_prefix is the length of the prefix vector
        n_prefix = prefix.size

        # Prepend prefix to skin conductance vector
        d_ext = np.concatenate([prefix, d])

        # Append a n_prefix length vector of negative timepoints leading up to 0 to
        # t (negative timesteps running the duration of the prefix we added to the
        # EDA vector)
        # start = t[0] - dt
        # end = t[0] - (n_prefix * dt)
        # count = np.int64(np.abs(start - end) / dt)
        # t_ext = np.linspace(start, end, num=count)
        t_ext = np.arange(t[0] - dt, t[0] - n_prefix * dt, -dt)
        t_ext = t_ext[::-1]
        t_ext = np.concatenate([t_ext, t])

        # Redefine tb as above but now with prefixed timestamps
        tb = t_ext - t_ext[0] + dt

        # Define initial taus
        tau1 = tau[0]
        tau2 = tau[1]

        # kernel is a smoothed Bateman output using our tb timestamps, onset of 0,
        # an amplitude of zero (the amplitude is scaled in this case within
        # bateman.m), the user-provided taus, and a standard deviation for the
        # Gaussian window of 0
        kernel = Pypsy.signal.analysis.bateman_gauss(tb, 0, 0, tau1, tau2, 0)

        # Adaptive kernel size
        # Find the index of the maximum amplitude of the kernel
        midx = np.argmax(kernel)

        # Subset kernel vector from the index after the max amplitude to the end
        kernelaftermx = kernel[midx:]

        # Put these two pieces back together, but only keeping the tail up to the
        # point that it falls below 10e-05
        kernel_start = kernel[0:midx+1]
        kernel_end = kernelaftermx[kernelaftermx > .00001]
        kernel = np.concatenate([kernel_start, kernel_end])

        # Normalize vector such that its entries sum to 1
        kernel = kernel / np.sum(kernel)

        # Set the value of a 'significant' peak in EDA
        # The second value in this max is hardcoded into Ledalab and is
        # leda2.set.sigPeak/max(kernel)*10
        sigc = np.max([.1, .001 / np.max(kernel) * 10])

        # ESTIMATE TONIC

        # Deconvolve the kernel from the prefixed data. The last entry in this data
        # vector is repeated for the duration of the kernel vector. The result of
        # this deconvultion is the tonic driver function.
        extended_d_ext = np.concatenate([d_ext, d_ext[-1] * np.ones(kernel.size)])
        driverSC, remainderSC = scipy.signal.deconvolve(extended_d_ext, kernel)

        # Smooth the driver function with a Gaussian
        driverSC_smooth = Pypsy.signal.utilities.smooth(driverSC, swin, 'gauss')

        # Remove prefix from driver, smoothed driver, and remainder. Also trim tail
        # of remainder.
        driverSC = driverSC[n_prefix:d.size + n_prefix]
        driverSC_smooth = driverSC_smooth[n_prefix:d.size + n_prefix]
        remainderSC = remainderSC[n_prefix:d.size + n_prefix]

        # Segment driver sections (hardcoded 12 is from leda2.set.segmWidth)
        onset_idx, impulse, overshoot, impMin, impMax = Pypsy.signal.analysis.segment_driver(
            driverSC_smooth,
            np.zeros(driverSC_smooth.size),
            sigc,
            np.round(sr * 12)
        )

        # Estimate tonic
        tonic_driver, tonic_data = Pypsy.signal.analysis.interimpulse_fit(driverSC_smooth, kernel, impMin, impMax, t, d, 25.)

        # Build tonic and phasic data
        phasic_data = d - tonic_data
        phasicDriverRaw = driverSC - tonic_driver
        phasicDriver = Pypsy.signal.utilities.smooth(phasicDriverRaw, swin, 'gauss')

        # Compute model error

        ### Have excluded a number of measures of error that can be brought over
        ### from Ledalab
        # err1d = deverror(phasicDriver, [0, .2]);

        # succnz here returns a the ratio of driver instance greater than a criterion
        # value to the entire signal
        err1s = Pypsy.signal.utilities.nonzero_portion(phasicDriver, max(.01, max(phasicDriver) / 20.), 2., sr)

        # Get the negative portion of the phasic driver
        phasicDriverNeg = phasicDriver.copy()
        phasicDriverNeg[phasicDriverNeg > 0] = 0

        # Compute measures of discreteness (chunks of non-zero data) and negativity
        err_discreteness = err1s
        err_negativity = np.sqrt(np.mean(phasicDriverNeg**2))

        # Hardcoded alpha (in MATLAB)
        alpha = 5.
        # Main error measure
        err = err_discreteness + err_negativity * alpha

        # Other error measures
        err_MSE = Pypsy.signal.analysis.fit_error(self.data, tonic_data + phasic_data, 0, 'MSE')
        err_RMSE = np.sqrt(err_MSE)

        # Save results
        self.tau = np.array([tau1, tau2])
        self.phasic_driver = phasicDriver
        self.tonic_driver = tonic_driver
        self.composite_driver = driverSC_smooth
        self.composite_driver_remainder = remainderSC
        self.kernel = kernel
        self.phasic_data = phasic_data
        self.tonic_data = tonic_data
        self.phasic_driver_raw = phasicDriverRaw

        self.error['mse'] = err_MSE
        self.error['rmse'] = err_RMSE
        self.error['discreteness'] = err_discreteness
        self.error['negativity'] = err_negativity
        self.error['compound'] = err
        # self.chi2 = err_chi2;
        # self.deviation = [err1d, 0];

        return err, tau

    def to_file(self, path):
        """
        Serializes an ``EDASignal`` in a file stored at ``path``.

        Parameters
        ----------
        path : str
            The path at which to store the serialized signal.

        Examples
        --------
        >>> data = np.random.rand(2)
        >>> time = np.array([0.1, 0.2])
        >>> e = EDASignal(data, time)
        >>> e.composite_driver = np.random.rand(2)
        >>> e.composite_driver_remainder = np.random.rand(2)
        >>> e.data = np.random.rand(2)
        >>> e.kernel = np.random.rand(2)
        >>> e.phasic_data = np.random.rand(2)
        >>> e.phasic_driver = np.random.rand(2)
        >>> e.phasic_driver_raw = np.random.rand(2)
        >>> e.tau = np.random.rand(2)
        >>> e.time = np.random.rand(2)
        >>> e.tonic_data = np.random.rand(2)
        >>> e.tonic_driver = np.random.rand(2)
        >>> e.error['mse'] = np.random.rand()
        >>> e.error['rmse'] = np.random.rand()
        >>> e.error['discreteness'] = np.random.rand()
        >>> e.error['negativity'] = np.random.rand()
        >>> e.error['compound'] = np.random.rand()
        >>> e.to_file('tests/test.eda_signal')
        >>> e1 = EDASignal.from_file('tests/test.eda_signal')
        >>> np.all(e.composite_driver == e1.composite_driver)
        True
        >>> np.all(e.composite_driver_remainder == e1.composite_driver_remainder)
        True
        >>> np.all(e.data == e1.data)
        True
        >>> np.all(e.kernel == e1.kernel)
        True
        >>> np.all(e.phasic_data == e1.phasic_data)
        True
        >>> np.all(e.phasic_driver == e1.phasic_driver)
        True
        >>> np.all(e.phasic_driver_raw == e1.phasic_driver_raw)
        True
        >>> np.all(e.tau == e1.tau)
        True
        >>> np.all(e.time == e1.time)
        True
        >>> np.all(e.tonic_data == e1.tonic_data)
        True
        >>> np.all(e.tonic_driver == e1.tonic_driver)
        True
        >>> e.error['mse'] == e1.error['mse']
        True
        >>> e.error['rmse'] == e1.error['rmse']
        True
        >>> e.error['discreteness'] == e1.error['discreteness']
        True
        >>> e.error['negativity'] == e1.error['negativity']
        True
        >>> e.error['compound'] == e1.error['compound']
        True
        """
        import pickle

        # Create dict of signal object
        out_dict = dict()

        out_dict['composite_driver'] = self.composite_driver
        out_dict['composite_driver_remainder'] = self.composite_driver_remainder
        out_dict['data'] = self.data
        out_dict['kernel'] = self.kernel
        out_dict['tau'] = self.tau
        out_dict['phasic_data'] = self.phasic_data
        out_dict['phasic_driver'] = self.phasic_driver
        out_dict['phasic_driver_raw'] = self.phasic_driver_raw
        out_dict['time'] = self.time
        out_dict['tonic_data'] = self.tonic_data
        out_dict['tonic_driver'] = self.tonic_driver

        out_dict['error'] = dict()
        out_dict['error']['mse'] = self.error['mse']
        out_dict['error']['rmse'] = self.error['rmse']
        out_dict['error']['discreteness'] = self.error['discreteness']
        out_dict['error']['negativity'] = self.error['negativity']
        out_dict['error']['compound'] = self.error['compound']

        with open(path, 'wb') as out_file:
            pickle.dump(out_dict, out_file, pickle.HIGHEST_PROTOCOL)


    @classmethod
    def from_file(cls, path):
        """
        Deserializes an ``EDASignal`` from the file at ``path``.

        Parameters
        ----------
        path : str
            A path to the file at which an ``EDASignal`` was serialized using
            :py:meth:`Pypsy.signal.EDASignal.to_file()`

        Returns
        -------
        out : :py:class:`Pypsy.signal.EDASignal`
            An instantiated ``EDASignal``

        Raises
        ------
        FileNotFoundError
            If no file exists at ``path``
        RuntimeError
            If the file at ``path`` does not contain a valid ``EDASignal``

        Examples
        --------
        >>> sig = EDASignal.from_file('tests/test.eda_signal')
        >>> type(sig)
        <class 'Pypsy.signal.EDASignal'>

        >>> EDASignal.from_file('tests/__init__.py')
        Traceback (most recent call last):
            ...
        RuntimeError: No valid signal found in 'tests/__init__.py'

        >>> EDASignal.from_file('tests/nonexistent.eda_signal')
        Traceback (most recent call last):
            ...
        FileNotFoundError: [Errno 2] No such file or directory: 'tests/nonexistent.eda_signal'
        """

        import pickle

        # Deserialize signal
        with open(path, 'rb') as in_file:
            try:
                in_dict = pickle.load(in_file)
            except:
                raise RuntimeError('No valid signal found in %r' % path)

        # Initialize the signal
        out_signal = EDASignal(in_dict['data'], in_dict['time'])

        # Set attribute values
        out_signal.composite_driver = in_dict['composite_driver']
        out_signal.composite_driver_remainder = in_dict['composite_driver_remainder']
        out_signal.data = in_dict['data']
        out_signal.kernel = in_dict['kernel']
        out_signal.tau = in_dict['tau']
        out_signal.phasic_data = in_dict['phasic_data']
        out_signal.phasic_driver = in_dict['phasic_driver']
        out_signal.phasic_driver_raw = in_dict['phasic_driver_raw']
        out_signal.time = in_dict['time']
        out_signal.tonic_data = in_dict['tonic_data']
        out_signal.tonic_driver = in_dict['tonic_driver']

        out_signal.error['mse'] = in_dict['error']['mse']
        out_signal.error['rmse'] = in_dict['error']['rmse']
        out_signal.error['discreteness'] = in_dict['error']['discreteness']
        out_signal.error['negativity'] = in_dict['error']['negativity']
        out_signal.error['compound'] = in_dict['error']['compound']

        return out_signal


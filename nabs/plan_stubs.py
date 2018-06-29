import math
import logging

from bluesky.plans import count
from bluesky.plan_stubs import subscribe, mv
from bluesky.preprocessors import stub_wrapper
from scipy.constants import golden_ratio

from nabs.streams import AverageStream
from nabs.utils import InvertedSignal


logger = logging.getLogger(__name__)


def measure_average(detectors, num, delay=None, stream=None):
    """
    Measure an average over a number of shots from a set of detectors

    Parameters
    ----------
    detectors : list
        List of detectors to read

    num : int
        Number of shots to average together

    delay: iterable or scalar, optional
        Time delay between successive readings. See ``bluesky.count`` for more
        details

    stream : AverageStream, optional
        If a plan will call :func:`.measure_average` multiple times, a single
        ``AverageStream`` instance can be created and then passed in on each
        call. This allows other callbacks to subscribe to the averaged data
        stream. If no ``AverageStream`` is provided then one is created for the
        purpose of this function.

    Returns
    -------
    averaged_event : dict
        A dictionary of all the measurements taken from the list of detectors
        averaged for ``num`` shots. The keys follow the same naming convention
        as that will appear in the event documents i.e "{name}_{field}"

    Notes
    -----
    The returned average dictionary will only contain keys for 'number' or
    'array' fields. Field types that can not be averaged such as 'string' will
    be ignored, do not expect them in the output.
    """
    # Create a stream and subscribe if not given one
    if not stream:
        stream = AverageStream(num=num)
        yield from subscribe('all', stream)
        # Manually kick the LiveDispatcher to emit a start document because we
        # will not see the original one since this is subscribed after open_run
        stream.start({'uid': None})
    # Ensure we sync our stream with request if using a prior one
    else:
        stream.num = num
    # Measure our detectors
    yield from stub_wrapper(count(detectors, num=num, delay=delay))
    # Return the measured average as a dictionary for use in adaptive plans
    return stream.last_event


def golden_section_search(signal, motor, tolerance, limits,
                          average=None, maximize=False):
    """
    Use golden-section search to find the extrema of a signal

    The algorithm is fed the starting range in which the extrema is contained
    within and a tolerance in which we would like to know the position of the
    extrema. For the algorithm to succeed it is a requirement that the
    underlying distribution is unimodal. After beginning the scan, "probe"
    points will be chosen to help determine how to narrow the range which
    contains the extrema. These probes are chosen using the golden ratio so the
    scan will complete in a deterministic number of iterations based on the
    starting range and desired resolution.

    Parameters
    ----------
    signal: ophyd.Signal
        Signal whose distribution we are investigating

    motor: ophyd.OphydObject
        Object that is ``set`` to probe different points of the distribution.

    tolerance: float
        The size of the range we would like to narrow the position of our
        extrema. Note that this is not the tolerance that we will know the
        "value" of the extrema, but instead the resolution we will be sure that
        it lies within on the "x" axis

    limits: tuple
        Starting bounds that we know the extrema lie within

    average : int, optional
        Option to average the signal we are reading to limit the affect of
        noise on our measurements

    maximize : bool, optional
        By default, the plan will minimize the relationship between the signal
        and the motor. If you would instead like to maximize the signal, mark
        this as True

    Returns
    -------
    bounds: tuple
        The range in which we have determined the extrema to lie within.
    """
    # This is boiler plate code and should be packaged into a
    # pre-processor, for now we repeat it as to not subscribe numerous
    # streams
    average = average or 1
    stream = AverageStream(num=average)
    yield from subscribe('all', stream)
    stream.start({'uid': None})

    # Create an inverted signal if we need to maximize
    if maximize:
        raw = signal
        signal = InvertedSignal(raw)
        detectors = [signal, raw, motor]
    else:
        detectors = [signal, motor]

    # Measurement plan
    def measure_probe(position):
        # Move motor
        yield from mv(motor, position)
        # Return measurement
        ret = yield from measure_average(detectors, average,
                                         stream=stream)
        return ret[signal.name]

    # If we have already found what we are looking for stop the scan
    (a, b) = limits
    region_size = b - a
    if region_size <= tolerance:
        return (a, b)
    # Determine the number of steps to converge
    n = math.ceil(math.log(tolerance/region_size)
                  / math.log(1/golden_ratio))
    logger.debug("Beginning golden-section search, "
                 "narrowing extrema location to %r "
                 "will require %r steps",
                 tolerance, n)
    # Place holders for probe values
    c = b - region_size/golden_ratio
    d = a + region_size/golden_ratio
    # Examine our new probe locations
    low_probe = yield from measure_probe(c)
    high_probe = yield from measure_probe(d)
    # Begin iteratively narrowing range
    for step in range(n - 1):
        logger.debug("Iteration %s: Extrema is between %s and %s",
                     step + 1, a, b)
        if low_probe < high_probe:
            # Readjust region of interest
            b = d
            d = c
            high_probe = low_probe
            region_size /= golden_ratio
            # Calculate next probe
            c = b - region_size/golden_ratio
            # Measure next probe
            low_probe = yield from measure_probe(c)
        else:
            # Readjust region of interest
            a = c
            c = d
            low_probe = high_probe
            region_size /= golden_ratio
            # Calculate next probe
            d = a + region_size/golden_ratio
            # Measure next probe
            high_probe = yield from measure_probe(d)
    # Return the final banding region
    if low_probe < high_probe:
        final_region = (a, d)
    else:
        final_region = (c, b)
    logger.debug("Extrema determined to be within %r",
                 final_region)
    return final_region

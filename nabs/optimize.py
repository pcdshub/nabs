import math
import logging

import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
from scipy.constants import golden_ratio

from nabs.plan_stubs import measure_average
from nabs.streams import AverageStream
from nabs.utils import InvertedSignal, ErrorSignal

logger = logging.getLogger(__name__)


def minimize(*args, **kwargs):
    """
    Minimize the value of an ophyd.Signal
    """
    # Add plan name into metadata
    _md = {'plan_name': 'minimize'}
    _md.update(kwargs.get('md', {}))
    # Run the plan
    return (yield from optimize(*args, maximize=False, md=_md, **kwargs))


def maximize(*args, **kwargs):
    """
    Maximize the value of an ophyd.Signal
    """
    # Add plan name into metadata
    _md = {'plan_name': 'maximize'}
    _md.update(kwargs.get('md', {}))
    # Run the plan
    return (yield from optimize(*args, maximize=True, **kwargs))


def walk_to_target(signal, motor, target, tolerance, **kwargs):
    # Add walk information to metadata
    _md = {'plan_name': 'walk_to_target',
           'target': target}
    _md.update(kwargs.get('md', {}))
    # Create a signal whose value is the absolute error
    error = ErrorSignal(signal, target)
    return (yield from minimize(error, motor, tolerance, **kwargs))


def optimize(signal, motor, tolerance,
             average=None, limits=None, method='golden',
             maximize=False, md=None):
    """
    The optimization methods within ``nabs`` take a similar approach to the
    methodology behind ``scipy.optimize``. Different use cases will have
    different requirements and it is impossible to devise a single plan that
    will be optimal for all of them. Instead, ``optimize`` supports different
    "methods" each with their own strengths and weaknesses. Select between
    these with the ``method`` parameter. Keep in mind that different
    methodologies will interpret certain keywords differently. For instance,
    the ``tolerance`` of the optimization may be interpreted in ways specific
    to the algorithm chosen. For more information, see the docstring for the
    specific method.

    Parameters
    ----------
    signal: ophyd.Signal
        Signal to maximize

    motor: ophyd.OphydObject
        Any set-able object

    tolerance: float, optional
        The tolerance in which our motor is

    average: int, optional
        Choice to take an average of points at each point in the scan

    limits: tuple, optional
        Limit the region the scan will search within. If this is not provided,
        the soft limits of the signal will be used. In this case, these must be
        configured or the scan will not be allowed to continue.

    method: str, optional
        Choice of optimization methods

    maximize: bool, optional
        Whether to maximize or minimize the signal

    md: dict, optional
        metadata
    """
    # Decide the limits
    if not limits:
        # Use the motor limits
        if hasattr(motor, 'limits') and any(motor.limits):
            logger.warning("No limits provided. "
                           "Using the motor soft limits %r",
                           motor.limits)
            limits = motor.limits
        # No provided limits or motor limits. Not allowed.
        else:
            raise ValueError("No limits provided or set on motor")

    # Create plan metadata
    _md = {'detectors': [signal],
           'motors': [motor],
           'plan_args': {'signal': repr(signal),
                         'motor': repr(motor),
                         'tolerance': tolerance,
                         'average': average,
                         'limits': limits,
                         'method': method,
                         'maximize': maximize},
           'plan_name': 'optimize',
           'hints': {}}
    try:
        dimensions = [(motor.hints['fields'], 'primary')]
    except (AttributeError, KeyError):
        pass
    else:
        _md['hints'].setdefault('dimensions', dimensions)

    @bpp.stage_decorator([signal, motor])
    @bpp.run_decorator(md=_md)
    def inner_optimize():
        # Golden Section Search
        if method == 'golden':
            # Search the system for the minimum
            ret = yield from golden_section_search(signal, motor, tolerance,
                                                   average=average,
                                                   limits=limits,
                                                   maximize=maximize)
            # Go to the minimum of the range
            logger.debug("Moving motor to center of discovered range ...")
            yield from bps.mv(motor, (ret[1] + ret[0])/2)
        else:
            raise ValueError("Unknown optimization methodology {!r}"
                             "".format(method))

    return (yield from inner_optimize())


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
    yield from bps.subscribe('all', stream)
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
        yield from bps.mv(motor, position)
        # Return measurement
        ret = yield from measure_average(detectors, average,
                                         stream=stream)
        logger.debug("Found a values of %r at %r",
                     ret[signal.name], position)
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


# Add the optimization docstring to both minimize and maximize
maximize.__doc__ += optimize.__doc__
minimize.__doc__ += optimize.__doc__

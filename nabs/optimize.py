import logging

import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps

from nabs.plan_stubs import golden_section_search

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


# Add the optimization docstring to both minimize and maximize
maximize.__doc__ += optimize.__doc__
minimize.__doc__ += optimize.__doc__

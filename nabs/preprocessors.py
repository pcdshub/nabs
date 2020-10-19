"""
nabs.preprocessors

Much like bluesky.preprocessors, this module contains "wrapper" functions
that take a plan as an argument and yield messages from a new, modified plan,
as well as "decorator" functions that can be applied to bluesky plans to
modify them in standard ways.
"""
from functools import wraps

from bluesky.plan_stubs import configure, read, trigger
from bluesky.preprocessors import plan_mutator


def _get_daq():
    """
    Helper function to get the active DAQ object.

    This also wraps the pcdsdaq import because pcdsdaq is an optional
    dependency of nabs.
    """

    from pcdsdaq.daq import get_daq  # NOQA
    return get_daq()


def daq_step_scan_wrapper(plan, events=None, duration=None, record=True,
                          use_l3t=False):
    """
    Wrapper to turn an open plan into a standard LCLS DAQ step plan.

    This inserts the DAQ object into every `trigger` and `read` pair,
    ensuring events are taken at every bundle, and yields an appropriate
    `configure` message using the input arguments and all motors moved prior to
    the first data point.

    The DAQ trigger and the DAQ read always go first, before any other triggers
    or reads, to ensure all events are recorded.

    Parameters
    ----------
    plan : plan
        A bluesky plan that yields bluesky Msg objects.

    events : int, optional
        Number of events to take at each step. If omitted, uses the
        duration argument or the last configured value.

    duration : int or float, optional
        Duration of time to spend at each step. If omitted, uses the events
        argument or the last configured value.

    record : bool, optional
        Whether or not to record the run in the DAQ. Defaults to True because
        we don't want to accidentally skip recording good runs.

    use_l3t : bool, optional
        Whether or not the use the l3t filter for the events argument. Defaults
        to False to avoid confusion from unconfigured filters.
    """

    daq = _get_daq()
    motor_cache = set()
    first_calib_cycle = True
    first_trigger = True
    first_read = True

    def daq_first_cycle(msg):
        yield from configure(events=events, duration=duration, record=record,
                             use_l3t=use_l3t, controls=list(motor_cache))
        yield from daq_next_cycle(msg)

    def daq_next_cycle(msg):
        yield from trigger(daq, group=msg.kwargs['group'])

    def daq_mutator(msg):
        nonlocal first_calib_cycle
        nonlocal first_trigger
        nonlocal first_read
        # Reset "first" flags after closing a bundle
        if msg.command in ('save', 'drop'):
            first_trigger = True
            first_read = True
        # Insert daq trigger before first trigger
        elif msg.command == 'trigger' and first_trigger:
            first_trigger = False
            # Configure before the first begin (after we've found all motors)
            if first_calib_cycle:
                first_calib_cycle = False
                return daq_first_cycle(msg), None
            else:
                return daq_next_cycle(msg), None
        # Insert daq read before first read
        elif msg.command == 'read' and first_read:
            first_read = False
            return read(daq), None
        # Gather all moving devices for the daq controls configuration arg
        elif msg.command == 'set':
            motor_cache.add(msg.obj)
        # If didn't mutate, return the (None, None) signal for plan_mutator
        return None, None

    return (yield from plan_mutator(plan, daq_mutator))


def daq_step_scan_decorator(plan):
    """
    Decorator to turn a plan function into a standard LCLS DAQ step plan.

    This adds the standard DAQ configuration arguments
    events, duration, record, and use_l3t onto the plan function,
    adds these to the docstring, and wraps the plan in the
    :func:`daq_step_scan_wrapper` to insert the DAQ object into every
    `trigger` and `read` pair and configure before the first scan point.
    """

    @wraps(plan)
    def inner(*args, events=None, duration=None, record=True, use_l3t=False,
              **kwargs):
        return (yield from daq_step_scan_wrapper(plan(*args, events=events,
                                                      duration=duration,
                                                      record=record,
                                                      use_l3t=use_l3t,
                                                      **kwargs)))
    return inner

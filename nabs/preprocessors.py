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


def daq_step_scan_wrapper(plan):
    """
    Wrapper to turn an open plan into a standard LCLS DAQ step plan.

    This simply inserts the DAQ object into every `trigger` and `read` pair,
    ensuring events are taken at every bundle.

    The DAQ trigger and the DAQ read always go first, before any other triggers
    or reads, to ensure all events are recorded.
    """
    daq = _get_daq()
    first_trigger = True
    first_read = True

    def insert_daq_trigger_and_read(msg):
        nonlocal first_trigger
        nonlocal first_read
        # Reset flags after closing a bundle
        if msg.command in ('save', 'drop'):
            first_trigger = True
            first_read = True
        # Insert daq trigger before first trigger
        elif msg.command == 'trigger' and first_trigger:
            first_trigger = False
            return trigger(daq, group=msg.kwargs['group']), None
        # Insert daq read before first read
        elif msg.command == 'read' and first_read:
            first_read = False
            return read(daq), None

    return (yield from plan_mutator(plan, insert_daq_trigger_and_read))


def daq_step_scan_decorator(plan):
    """
    Decorator to turn a plan function into a standard LCLS DAQ step plan.

    This adds the standard DAQ configuration arguments
    events, duration, record, and use_l3t onto the plan function,
    adds these to the docstring, and wraps the plan in the
    :func:`daq_step_scan_wrapper` to insert the DAQ object into every
    `trigger` and `read` pair.
    """
    daq = _get_daq()

    @wraps(plan)
    def inner(*args, events=None, duration=None, record=True, use_l3t=False,
              **kwargs):
        yield from configure(daq, events=events, duration=duration,
                             record=record, use_l3t=use_l3t)
        return (yield from daq_step_scan_wrapper(plan(*args, **kwargs)))

    inner.__doc__ += """
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

    return inner

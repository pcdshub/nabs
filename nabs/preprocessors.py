"""
Wrappers and decorators to modify existing plans.

This is the LCLS counterpart to bluesky.preprocessors.

This module contains "wrapper" functions that take a plan as an argument
and yield messages from a new, modified plan, as well as "decorator"
functions that can be applied to bluesky plan functions to return new
plan functions with modifications.
"""
from functools import wraps

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import make_decorator


def _get_daq():
    """
    Helper function to get the active DAQ object.

    This also wraps the pcdsdaq import because pcdsdaq is an optional
    dependency of nabs. This will fail unless pcdsdaq is installed.

    Returns
    -------
    daq: Daq
        The DAQ (data aquisition) system bluesky-compatible control object.
    """

    from pcdsdaq.daq import get_daq  # NOQA
    return get_daq()


def daq_step_scan_wrapper(plan, events=None, duration=None, record=True,
                          use_l3t=False):
    """
    Wrapper to turn an open plan into a standard LCLS DAQ step plan.

    This inserts the DAQ object into every `trigger` and `read` pair,
    ensuring events are taken at every bundle. It also stages the daq and
    yields an appropriate `configure` message using the input arguments
    and all motors moved prior to the first data point.

    The DAQ trigger and the DAQ read always go first, before any other triggers
    or reads, to ensure all events are recorded.

    If the DAQ is manually passed into the wrapped plan, and it is the first
    detector in the list, we will skip adding a redundant trigger/read. If the
    DAQ is manually passed in as the second detector or later we will end up
    with two triggers and two reads, which can cause problems.

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

    Returns
    -------
    daq_step_plan : plan
        The same plan as before, but modified appropriately to the run the DAQ
        at every step. This will be an open generator.

    See Also
    --------
    :func:`daq_step_scan_decorator`
    """

    daq = _get_daq()
    motor_cache = set()
    first_calib_cycle = True
    first_trigger = True
    first_read = True

    def daq_first_cycle(msg):
        yield from bps.configure(daq, events=events, duration=duration,
                                 record=record, use_l3t=use_l3t,
                                 controls=list(motor_cache))
        if msg.obj is not daq:
            yield from daq_next_cycle(msg)

    def daq_next_cycle(msg):
        yield from bps.trigger(daq, group=msg.kwargs['group'])

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
            elif msg.obj is not daq:
                return daq_next_cycle(msg), None
        # Insert daq read before first read
        elif msg.command == 'read' and first_read:
            first_read = False
            if msg.obj is not daq:
                return bps.read(daq), None
        # Gather all moving devices for the daq controls configuration arg
        elif msg.command == 'set':
            motor_cache.add(msg.obj)
        # If didn't mutate, return the (None, None) signal for plan_mutator
        return None, None

    @bpp.stage_decorator([daq])
    def daq_step_plan():
        return (yield from bpp.plan_mutator(plan, daq_mutator))

    return (yield from daq_step_plan())


def daq_step_scan_decorator(plan):
    """
    Decorator to turn a plan function into a standard LCLS DAQ step plan.

    This adds the standard DAQ configuration arguments
    events, duration, record, and use_l3t onto the plan function
    and wraps the plan in the :func:`daq_step_scan_wrapper` to properly
    execute a step scan.

    See :func:`daq_step_scan_standard_args` for argument specifications for the
    standard DAQ configuration arguments.

    Parameters
    ----------
    plan : plan
        A bluesky plan that yields bluesky Msg objects.

    Returns
    -------
    daq_step_plan : plan
        The same plan as before, but modified appropriately for DAQ use.
        This will be a callable generator function.

    See Also
    --------
    :func:`daq_step_scan_wrapper`
    :func:`daq_step_scan_standard_args`
    """

    @wraps(plan)
    def inner(*args, **kwargs):
        events = kwargs.pop('events', None)
        duration = kwargs.pop('duration', None)
        record = kwargs.pop('record', True)
        use_l3t = kwargs.pop('use_l3t', False)
        return (yield from daq_step_scan_wrapper(plan(*args, **kwargs),
                                                 events=events,
                                                 duration=duration,
                                                 record=record,
                                                 use_l3t=use_l3t))
    return inner


def daq_step_scan_standard_args(events=None, duration=None, record=True,
                                use_l3t=False):
    """
    No-op function to hold template parameter info for generated docs.

    Parameters
    ----------
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

    pass


def daq_during_wrapper(plan, record=True, use_l3t=False, controls=None):
    """
    Wrap a plan so that the DAQ runs at the same time.

    This can be used with an ordinary bluesky plan that you'd like the daq
    to run along with. This also stages the DAQ so that the run start/stop
    will be synchronized with the bluesky runs.

    Note that this is not a calib cycle scan. See
    :func:`daq_step_scan_wrapper` and :func:`daq_step_scan_decorator`
    for the calib cycle variant.

    All configuration must be done by supplying config kwargs to this wrapper.

    This must be applied outside the run_wrapper.

    The :func:`daq_during_decorator` is the same as the
    :func:`daq_during_wrapper`, but it is meant to be used as a function
    decorator.

    Parameters
    ----------
    plan : plan
        A bluesky plan that yields bluesky Msg objects.

    record : bool, optional
        Whether or not to record the run in the DAQ. Defaults to True because
        we don't want to accidentally skip recording good runs.

    use_l3t : bool, optional
        Whether or not the use the l3t filter for the events argument. Defaults
        to False to avoid confusion from unconfigured filters.

    controls : list of readables, optional
        If provided, values from these will make it into the DAQ data
        stream as variables. For this purpose, the position and value
        attributes will be checked.

    Returns
    -------
    daq_during_plan : plan
        The same plan as before, but modified appropriately to run the DAQ at
        the same time.
    """
    daq = _get_daq()

    @bpp.stage_decorator([daq])
    def daq_during_plan():
        yield from bps.configure(daq, events=0, record=record,
                                 use_l3t=use_l3t, controls=controls)
        return (yield from bpp.fly_during_wrapper(plan, flyers=[daq]))

    return (yield from daq_during_plan())


daq_during_decorator = make_decorator(daq_during_wrapper)

"""
Wrappers and decorators to modify existing plans.

This is the LCLS counterpart to `bluesky.preprocessors`.

This module contains "wrapper" functions that take a plan as an argument
and yield messages from a new, modified plan, as well as "decorator"
functions that can be applied to ``bluesky`` plan functions to return new
plan functions with modifications.
"""
import numbers
from functools import wraps

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
from bluesky.utils import make_decorator

from . import utils


def _get_daq():
    """
    Helper function to get the active DAQ object.

    This also wraps the `pcdsdaq` import because `pcdsdaq` is an optional
    dependency of ``nabs``. This will fail unless `pcdsdaq` is installed.

    Returns
    -------
    daq : `pcdsdaq.daq.Daq`
        The DAQ (data aquisition) system `bluesky`-compatible control object.
    """

    from pcdsdaq.daq import get_daq  # NOQA
    return get_daq()


class _Dummy:
    """
    Class to sub in for the DAQ when we need to drop a message.

    You can't just remove a message entirely with
    `bluesky.preprocessors.plan_mutator`, you need
    to yield a compatible message. To accomplish this we sub in a dummy object
    for the daq to create a no-op with the right return value.
    """
    def stage(self):
        return [self]

    def unstage(self):
        return [self]


def daq_step_scan_wrapper(plan, events=None, duration=None, record=True,
                          use_l3t=False):
    """
    Wrapper to turn an open plan into a standard LCLS DAQ step plan.

    This inserts the DAQ object into every `bluesky.plan_stubs.trigger` and
    `bluesky.plan_stubs.read` pair, ensuring events are taken at every
    bundle. It also stages the `pcdsdaq.daq.Daq` and yields an appropriate
    `bluesky.plan_stubs.configure` message using the input arguments
    and all motors moved prior to the first data point.

    The DAQ trigger and the DAQ read always go first, before any other triggers
    or reads, to ensure all events are recorded.

    If the DAQ is manually passed into the wrapped plan, and it is the first
    detector in the list, we will skip adding a redundant trigger/read. If the
    DAQ is manually passed in as the second detector or later we will end up
    with two triggers and two reads, which can cause problems. Running a scan
    like this will raise a ``TypeError``.

    See `daq_step_scan_decorator` for the function decorator version.

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
    """

    daq = _get_daq()
    motor_cache = set()

    class State:
        first_calib_cycle = True
        first_trigger = True
        first_read = True
        daq_has_triggered = False

    def daq_first_cycle(msg):
        yield from bps.configure(daq, events=events, duration=duration,
                                 record=record, use_l3t=use_l3t,
                                 controls=list(motor_cache))
        return (yield from add_daq_trigger(msg))

    def add_daq_trigger(msg):
        if msg.obj is not daq:
            yield from bps.trigger(daq, group=msg.kwargs['group'])
        return (yield msg)

    def add_daq_read(msg):
        if msg.obj is not daq:
            yield from bps.read(daq)
        return (yield msg)

    def drop_daq_msg(msg):
        if msg.command == 'stage':
            return (yield from bps.stage(_Dummy()))
        if msg.command == 'unstage':
            return (yield from bps.unstage(_Dummy()))

    def daq_mutator(msg):
        # Reset "first" flags after closing a bundle
        if msg.command in ('save', 'drop'):
            State.first_trigger = True
            State.first_read = True
            State.daq_has_triggered = False
        # Insert daq trigger before first trigger
        elif msg.command == 'trigger':
            if msg.obj is daq:
                if State.daq_has_triggered:
                    raise TypeError('Scan misconfigured; daq cannot be passed '
                                    'unless it is the first detector.')
                else:
                    State.daq_has_triggered = True
            if State.first_trigger:
                State.first_trigger = False
                # Configure before the first begin (after all motors found)
                if State.first_calib_cycle:
                    State.first_calib_cycle = False
                    return daq_first_cycle(msg), None
                return add_daq_trigger(msg), None
        # Insert daq read before first read
        elif msg.command == 'read' and State.first_read:
            State.first_read = False
            return add_daq_read(msg), None
        # Gather all moving devices for the daq controls configuration arg
        elif msg.command == 'set':
            motor_cache.add(msg.obj)
        # Strip redundant DAQ stages from inner plan
        elif msg.command in ('stage', 'unstage') and msg.obj is daq:
            return drop_daq_msg(msg), None
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
    and wraps the plan in the `daq_step_scan_wrapper` to properly
    execute a step scan.

    See `daq_step_scan_standard_args` for argument specifications for the
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

    plan.__signature__ = utils.add_named_kwargs_to_signature(
        plan,
        kwargs=dict(events=None, duration=None, record=True, use_l3t=False),
    )
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

    This can be used with an ordinary ``bluesky`` plan that you'd like the daq
    to run along with. This also stages the DAQ so that the run start/stop
    will be synchronized with the bluesky runs.

    Note that this is not a calib cycle scan. See
    `daq_step_scan_wrapper` and `daq_step_scan_decorator`
    for the calib cycle variant.

    All configuration must be done by supplying config kwargs to this wrapper.

    This must be applied outside the run_wrapper.

    The `daq_during_decorator` is the same as the
    `daq_during_wrapper`, but it is meant to be used as a function
    decorator.

    Internally, this uses the flyer interface of the `pcdsdaq.daq.Daq`
    object.

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

    controls : list of positioners or signals, optional
        If provided, values from these will make it into the DAQ data
        stream as variables. For this purpose, the ``.position`` and
        ``.value`` attributes will be checked, followed by the ``.get()``
        method.

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


def step_size_decorator(plan):
    """
    Grab the last argument (number of steps), and intepret as
    - step size if float
    - number of steps if integer

    Only works on step scans in one dimension.

    Parameters
    ----------
    plan : plan
        A bluesky plan that yields bluesky Msg objects.  Must be
        a scan in one dimension, with the last argument being
        the number of scan points / step size.

    Returns
    -------
    step_size_plan : plan
        The same plan as before, but modified appropriately to
        differentiate between step size and number of steps.
        This will be a callable generator function.
    """

    @wraps(plan)
    def inner(*args, **kwargs):
        if 'num' in kwargs:
            # Currently unneeded, since daq_ascan and daq_dscan
            # do not support num kwarg
            n = kwargs.pop('num')
        else:
            # assumes (det_list, motor, start, stop, num)
            det_list, motor, start, stop, n = args

        if not isinstance(n, (numbers.Integral, numbers.Real)):
            raise TypeError("Step size / number of steps is "
                            "neither float nor integer.")

        if isinstance(n, numbers.Integral):
            # interpret as number of steps (default)
            result = yield from plan(*args, **kwargs)
        elif isinstance(n, numbers.Real):
            # correct step size sign
            n = np.sign(stop - start) * np.abs(n)
            if np.abs(n) > np.abs(stop - start):
                raise ValueError(f"Step size provided {n} greater "
                                 "than the range provided "
                                 f"{np.abs(stop - start)}.")
            step_list = utils.orange(start, stop, n)
            n_steps = len(step_list)

            if n_steps == 0:
                raise ValueError("Number of steps is 0 with the "
                                 "provided range and step size.")

            result = yield from plan(det_list, motor, start,
                                     step_list[-1], n_steps,
                                     **kwargs)

        return result

    return inner


daq_during_decorator = make_decorator(daq_during_wrapper)

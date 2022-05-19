"""
Standalone ``bluesky`` plans for data collection.

This is the LCLS counterpart to `bluesky.plans`.

All plans in this module will work as-is when passed into a
`bluesky.run_engine.RunEngine`, including starting and stopping a run.

Plans preceded by "daq" incorporate running the LCLS DAQ in the plan.
"""
import logging
import math
import time
from collections import defaultdict
from itertools import chain, cycle

import bluesky.plan_stubs as bps
import bluesky.plans as bp
import bluesky.preprocessors as bpp
import numpy as np
from bluesky import plan_patterns
from toolz import partition

from . import preprocessors as nbpp
from .plan_stubs import get_sample_targets, update_sample

logger = logging.getLogger(__name__)


def duration_scan(detectors, *args, duration=0, per_step=None, md=None):
    """
    Generalized version of the `delay_scan` movement pattern.

    This is a bluesky plan that moves motors among points for a fixed
    duration of time, rather than through a finite number of points.

    For each motor, a list of points must be provided. Each motor will be moved
    through its list of points simultaneously if multiple motors are provided.

    This will take a reading at every scan step by default via
    `bluesky.plan_stubs.trigger_and_read.`

    At the end of the scan, the motors will be returned to their original
    positions.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    *args :
        For one dimension, ``motor, [point1, point2, ....]``.
        In general:

        .. code-block:: python

            motor1, [point1, point2, ...],
            motor2, [point1, point2, ...],
            ...,
            motorN, [point1, point2, ...]

        Motors can be any 'settable' object (motor, temp controller, etc.)

    duration : float
        The time to run in seconds.

    per_step : plan, optional
        An alternate plan to run for every scan point. Defaults to
        `bluesky.plan_stubs.one_nd_step`.

    md : dict, optional
        Additional metadata to include in the bluesky start document.
    """
    if per_step is None:
        per_step = bps.one_nd_step

    pos_lists = {}
    pos_cycles = {}
    motors = []
    detectors = list(detectors)

    for motor, pos_list in partition(2, args):
        pos_list = list(pos_list)
        pos_lists[motor] = pos_list
        pos_cycles[motor] = cycle(pos_list)
        motors.append(motor)

    # md handling lifted from bluesky.plans.list_scan for consistency
    md_args = list(chain(*((repr(motor), pos_list)
                           for motor, pos_list in pos_lists.items())))

    _md = {'detectors': [det.name for det in detectors],
           'motors': [mot.name for mot in motors],
           'plan_args': {'detectors': list(map(repr, detectors)),
                         'args': md_args,
                         'duration': duration,
                         'per_step': repr(per_step)},
           'plan_name': 'duration_scan',
           'plan_pattern': 'inner_list_product',
           'plan_pattern_module': plan_patterns.__name__,
           'plan_pattern_args': dict(args=md_args),
           'hints': {},
           }

    _md.update(md or {})

    x_fields = []
    for motor in motors:
        x_fields.extend(getattr(motor, 'hints', {}).get('fields', []))

    default_dimensions = [(x_fields, 'primary')]

    default_hints = {}
    if len(x_fields) > 0:
        default_hints.update(dimensions=default_dimensions)

    md = md or {}

    _md['hints'] = default_hints
    _md['hints'].update(md.get('hints', {}) or {})
    _md['disable_plots'] = True
    # end borrowed md handling block

    @bpp.stage_decorator(detectors + motors)
    @bpp.reset_positions_decorator()
    @bpp.run_decorator(md=_md)
    def inner():
        # Start timing after a dummy yield so it doesn't start early
        yield from bps.null()
        start = time.monotonic()
        # Where last position is stored
        pos_cache = defaultdict(lambda: None)
        while time.monotonic() - start < duration:
            step = {motor: next(cyc) for motor, cyc in pos_cycles.items()}
            yield from per_step(detectors, step, pos_cache)

    return (yield from inner())


def delay_scan(detectors, time_motor, time_points, sweep_time,
               duration=math.inf):
    """
    A ``bluesky`` plan that sets up and executes the delay scan.

    A delay scan is one that moves a
    `pcdsdevices.epics_motor.DelayNewport` back and forth.
    Underneath, this moves a physical motor that changes the path length
    of an optical laser, thus changing the timing of the laser shot by
    introducing a delay.

    This is a `duration_scan` in one dimension that also sets the stage
    velocity to match the configured sweep time and returns the motor to the
    starting position at the end of the scan.

    See `daq_delay_scan` for the version with DAQ support.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    time_motor : `pcdsdevices.epics_motor.DelayNewport`
        The movable device in egu seconds.

    time_points : list of float
        The times in second to move between.

    sweep_time : float
        The duration we take to move from one end of the range to the other.

    duration : float, optional
        If provided, the time to run in seconds. If omitted, we'll run forever.
    """

    spatial_pts = []
    for time_pt in time_points:
        pseudo_tuple = time_motor.PseudoPosition(delay=time_pt)
        real_tuple = time_motor.forward(pseudo_tuple)
        spatial_pts.append(real_tuple.motor)

    space_delta = abs(spatial_pts[0] - spatial_pts[1])
    velo = space_delta/sweep_time

    def inner_delay_scan():
        yield from bps.abs_set(time_motor.motor.velocity, velo)
        return (yield from duration_scan(detectors, time_motor, time_points,
                                         duration=duration))

    return (yield from inner_delay_scan())


def daq_delay_scan(detectors, time_motor, time_points, sweep_time,
                   duration=math.inf, record=True):
    """
    Scan a laser delay timing motor with DAQ support.

    A delay scan is one that moves a
    `pcdsdevices.epics_motor.DelayNewport` back and forth.
    Underneath, this moves a physical motor that changes the path length
    of an optical laser, thus changing the timing of the laser shot by
    introducing a delay.

    This is a `duration_scan` in one dimension that also sets the stage
    velocity to match the configured sweep time and returns the motor to the
    starting position at the end of the scan. It is the `delay_scan` with
    the DAQ added.

    Unlike the majority of DAQ scans, this scan does not include the delay
    stage as a control variable in the DAQ. This is because the "points" of the
    scan are not relevant to the data: we only care about the intermediate
    shots. In fact, reconfiguring the DAQ with the new controls positions only
    slows us down and makes the data more annoying to analyze!

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    time_motor : `pcdsdevices.epics_motor.DelayNewport`
        The movable device in egu seconds.

    time_points : list of float
        The times in second to move between.

    sweep_time : float
        The duration we take to move from one end of the range to the other.

    duration : float, optional
        If provided, the time to run in seconds. If omitted, we'll run forever.

    record : bool, optional
        Whether or not to record the run in the DAQ. Defaults to True because
        we don't want to accidentally skip recording good runs.
    """

    @nbpp.daq_during_decorator(record=record)
    def inner_daq_delay_scan():
        return (yield from delay_scan(detectors, time_motor, time_points,
                                      sweep_time, duration=duration))

    return (yield from inner_daq_delay_scan())


# The rest of this file contains thin wrappers around bluesky built-ins.
# These exist to mimic an older hutch python API,
# easing the transition to bluesky.


@nbpp.daq_step_scan_decorator
def daq_count(detectors=None, num=1, delay=None, *, per_shot=None, md=None):
    """
    Take repeated DAQ runs with no motors.

    This is an LCLS-I DAQ version of ``bluesky``'s built-in
    `bluesky.plans.count` plan.

    Parameters
    ----------
    detectors : list, optional
        List of 'readable' objects to read at every step.

    num : int, optional
        Number of readings to take; default is 1.
        If None, capture data until canceled.

    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.

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

    per_shot : callable, optional
        Hook for customizing action of inner loop (messages per step).
        Expected signature ::

           def f(detectors: Iterable[OphydObj]) -> Generator[Msg]:
               ...

        See docstring of `bluesky.plan_stubs.one_shot` (the default)
        for details.

    md : dict, optional
        Additional metadata to include in the start document.

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    if not detectors:
        # count and daq_step_scan_decorator both need a detector to work
        # so if none are found, we pass the daq explicitly
        # otherwise, the decorator takes care of all the heavy lifting
        daq = nbpp._get_daq()
        detectors = [daq]

    return (yield from bp.count(detectors, num=num, delay=delay,
                                per_shot=per_shot, md=md))


@bpp.reset_positions_decorator()
@nbpp.daq_step_scan_decorator
def daq_scan(*args, num=None, per_step=None, md=None):
    """
    Scan through a multi-motor (start, end, num) trajectory with DAQ support.

    This is an LCLS-I DAQ version of ``bluesky``'s built-in
    `bluesky.plans.scan` plan. It also returns the motors to their starting
    points after the scan is complete.

    Parameters
    ----------
    detectors : list, optional
        List of 'readable' objects to read at every step.

    *args :
        For one dimension, ``motor, start, stop``.
        In general:

        .. code-block:: python

            motor1, start1, stop1,
            motor2, start2, start2,
            ...,
            motorN, startN, stopN

        Motors can be any 'settable' object (motor, temp controller, etc.)

    num : integer
        Number of points.

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

    per_step : callable, optional
        Hook for customizing action of inner loop (messages per step).
        See docstring of `bluesky.plan_stubs.one_nd_step` (the default)
        for details.

    md : dict, optional
        Additional metadata to include in the start document.

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    if isinstance(args[0], list):
        detectors = args[0]
        scan_args = args[1:]
    else:
        detectors = []
        scan_args = args

    return (yield from bp.scan(detectors, *scan_args, num=num,
                               per_step=per_step, md=md))


@bpp.reset_positions_decorator()
@nbpp.daq_step_scan_decorator
def daq_list_scan(*args, per_step=None, md=None):
    """
    Scan through a multi-motor list trajectory with DAQ support.

    This is an LCLS-I DAQ version of ``bluesky``'s built-in
    `bluesky.plans.list_scan` plan. It also returns the motors
    to their starting points after the scan is complete.

    Parameters
    ----------
    detectors : list, optional
        List of 'readable' objects to read at every step.

    *args :
        For one dimension, ``motor, [point1, point2, ....]``.
        In general:

        .. code-block:: python

            motor1, [point1, point2, ...],
            motor2, [point1, point2, ...],
            ...,
            motorN, [point1, point2, ...]

        Motors can be any 'settable' object (motor, temp controller, etc.)

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

    per_step : callable, optional
        Hook for customizing action of inner loop (messages per step).
        See docstring of `bluesky.plan_stubs.one_nd_step` (the default)
        for details.

    md : dict, optional
        Additional metadata to include in the start document.

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    if isinstance(args[0], list):
        detectors = args[0]
        scan_args = args[1:]
    else:
        detectors = []
        scan_args = args

    return (yield from bp.list_scan(detectors, *scan_args,
                                    per_step=per_step, md=md))


@bpp.reset_positions_decorator()
@nbpp.daq_step_scan_decorator
@nbpp.step_size_decorator
def daq_ascan(detectors, motor, start, end, n):
    """
    One-dimensional daq scan with absolute positions.

    This moves a motor from start to end in nsteps steps, taking data in the
    DAQ at every step, and returning the motor to its original position at
    the end of the scan.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    motor : Movable
        A movable object to scan.

    start : int or float
        The first point in the scan.

    end : int or float
        The last point in the scan.

    n : int or float
        if int, the number of points in the scan.
        if float, step size

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    yield from bp.scan(detectors, motor, start, end, n)


@bpp.reset_positions_decorator()
@bpp.relative_set_decorator()
@nbpp.daq_step_scan_decorator
@nbpp.step_size_decorator
def daq_dscan(detectors, motor, start, end, n):
    """
    One-dimensional daq scan with relative (delta) positions.

    This moves a motor from current_pos + start to current_pos + end
    in nsteps steps, taking data in the DAQ at every step, and
    returning the motor to its original position at the end of the scan.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    motor : Movable
        A movable object to scan.

    start : int or float
        The first point in the scan, relative to the current position.

    end : int or float
        The last point in the scan, relative to the current position.

    n : int or float
        if int, the number of points in the scan.
        if float, step size

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    yield from bp.scan(detectors, motor, start, end, n)


@bpp.reset_positions_decorator()
@nbpp.daq_step_scan_decorator
def daq_a2scan(detectors, m1, a1, b1, m2, a2, b2, nsteps):
    """
    Two-dimensional daq scan with absolute positions.

    This moves two motors from start to end in nsteps steps, taking data in
    the DAQ at every step, and returning the motors to their original positions
    at the end of the scan.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    m1 : Movable
        The first movable object to scan.

    a1 : int or float
        The first point in the scan for m1.

    b1 : int or float
        The last point in the scan for m1.

    m2 : Movable
        The second movable object to scan.

    a2 : int or float
        The first point in the scan for m2.

    b2 : int or float
        The last point in the scan for m2.

    nsteps : int
        The number of points in the scan.

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    yield from bp.scan(detectors, m1, a1, b1, m2, a2, b2, nsteps)


@bpp.reset_positions_decorator()
@bpp.relative_set_decorator()
@nbpp.daq_step_scan_decorator
def daq_d2scan(detectors, m1, a1, b1, m2, a2, b2, nsteps):
    """
    Two-dimensional daq scan with relative positions

    This moves two motors from start to end relative to their current positions
    in nsteps steps, taking data in the DAQ at every step, and returning the
    motors to their original positions at the end of the scan.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    m1 : Movable
        The first movable object to scan.

    a1 : int or float
        The first point in the scan for m1, relative to the current position.

    b1 : int or float
        The last point in the scan for m1, relative to the current position.

    m2 : Movable
        The second movable object to scan.

    a2 : int or float
        The first point in the scan for m2, relative to the current position.

    b2 : int or float
        The last point in the scan for m2, relative to the current position.

    nsteps : int
        The number of points in the scan.

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """
    yield from bp.scan(detectors, m1, a1, b1, m2, a2, b2, nsteps)


@bpp.reset_positions_decorator()
@nbpp.daq_step_scan_decorator
def daq_a3scan(detectors, m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps):
    """
    Three-dimensional daq scan with absolute positions.

    This moves three motors from start to end in nsteps steps, taking data in
    the DAQ at every step, and returning the motors to their original positions
    at the end of the scan.

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    m1 : Movable
        The first movable object to scan.

    a1 : int or float
        The first point in the scan for m1.

    b1 : int or float
        The last point in the scan for m1.

    m2 : Movable
        The second movable object to scan.

    a2 : int or float
        The first point in the scan for m2.

    b2 : int or float
        The last point in the scan for m2.

    m3 : Movable
        The third movable object to scan.

    a3 : int or float
        The first point in the scan for m3.

    b3 : int or float
        The last point in the scan for m3.

    nsteps : int
        The number of points in the scan.

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """

    yield from bp.scan(detectors, m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps)


@bpp.reset_positions_decorator()
@nbpp.daq_step_scan_decorator
def daq_anscan(detectors, *args):
    """
    N-dimensional daq scan with absolute positions.

    This moves N motors from start to end in nsteps steps, taking data in
    the DAQ at every step, and returning the motors to their original positions
    at the end of the scan.

    Takes an arbitrary number of motors, start and stop positions

    >> RE(daq_anscan([], m1, a1, b1,
                         m2, a2, b2, ... ,
                         mn, an, bn, nsteps,
                         events=10))

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    m1 : Movable
        The first movable object to scan.

    a1 : int or float
        The first point in the scan for m1.

    b1 : int or float
        The last point in the scan for m1.

    nsteps : int
        The number of points in the scan.

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """
    yield from bp.scan(detectors, *args)


@bpp.reset_positions_decorator()
@bpp.relative_set_decorator()
@nbpp.daq_step_scan_decorator
def daq_dnscan(detectors, *args):
    """
    N-dimensional daq scan with relative positions.

    This moves N motors from start to end in nsteps steps, taking data in
    the DAQ at every step, and returning the motors to their original positions
    at the end of the scan.

    Takes an arbitrary number of motors, start and stop positions

    >> RE(daq_dnscan([], m1, a1, b1,
                         m2, a2, b2, ... ,
                         mn, an, bn, nsteps,
                         events=10))

    Parameters
    ----------
    detectors : list of readables
        Objects to read into Python in the scan.

    m1 : Movable
        The first movable object to scan.

    a1 : int or float
        The first point in the scan for m1, relative to the current position.

    b1 : int or float
        The last point in the scan for m1, relative to the current position.

    nsteps : int
        The number of points in the scan.

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

    Note
    ----
    The events, duration, record, and use_l3t arguments come from the
    :py:func:`nabs.preprocessors.daq_step_scan_decorator`.
    """
    yield from bp.scan(detectors, *args)


def fixed_target_scan(sample, detectors, x_motor, y_motor, scan_motor, ss,
                      n_shots, path):
    """
    Scan over two variables in steps simultaneously.

    This is a ``nabs`` version of ``bluesky``'s built-in
    `bluesky.plans.list_scan` plan.
    This scan is designed to be used with 3 motors, the x and y motors that
    move to a designaget target on a sample wafer, and one scan_motor that can
    be delay time, laser power or some other motor positions.

    Parameters
    ----------
    sample : str
        The name of the sample we're interested in.
    detectors : list
        Objects to read into Python in the scan.
    x_motor : obj
        Motor object corresponding to the x axes.
    y_motor : obj
        Motor object corresponding to the y axes.
    scan_motor : obj
        The motor being scanned. It can be e.g., delay time, laser power, some
        other motor position, etc.
    ss : list
        List of all the points (samples) for the scan_motor to go through.
    n_shots : int
        Indicates how many shots should be taken, or how many samples should
        be scanned on the grid.
    path : str
        Path where the sample file is located.
    """
    detectors = list(detectors) + [scan_motor]

    xx, yy = get_sample_targets(sample, path)
    cycle_xx = cycle(xx)
    cycle_yy = cycle(yy)

    # find the index of the next target to be shot (status is False)
    next_index = next((index for (index, d) in enumerate(xx)
                      if d['status'] is False), None)
    if next_index is None:
        raise IndexError('Could not get a target index that has not been shot,'
                         ' probably all targets were shot from this sample?')

    if ((next_index - 1) + (n_shots * len(ss))) >= len(xx):
        raise IndexError('The number of last shot + n_shots * len(ss): '
                         f'{next_index - 1} + {n_shots} * {len(ss)}= '
                         f'{next_index - 1 + (n_shots * len(ss))}: '
                         f' bigger than the available samples: {len(xx)}. '
                         'Please provide a number in range.')

    @bpp.run_decorator()
    def inner_scan():
        try:
            for i in range(len(ss)):
                yield from bps.mv(scan_motor, ss[i])
                for j in range(n_shots):
                    x = (next(item['pos']
                         for item in cycle_xx if item["status"] is False))
                    y = (next(item['pos']
                         for item in cycle_yy if item["status"] is False))
                    yield from bpp.stub_wrapper(bp.list_scan(detectors,
                                                x_motor, [x], y_motor, [y]))
            update_sample(sample, path, (n_shots * len(ss)))
        except Exception:
            current_position = x_motor.position
            try:
                last_index = next((index for (index, d) in enumerate(xx)
                                  if np.isclose(d["pos"], current_position)))
                update_sample(sample, path, (last_index - next_index + 1))
            except Exception:
                logger.warning('Could not find the index in the targets list '
                               'for the current motor value: %d',
                               current_position)
    return (yield from inner_scan())


def fixed_target_multi_scan(sample, detectors, x_motor, y_motor, scan_motor,
                            ss, n_shots, path):
    """
    Scan over three variables in steps simultaneously.

    This function allows for multiple shots at the same target.

    This is a ``nabs`` version of ``bluesky``'s built-in
    `bluesky.plans.list_scan` plan.
    This scan is designed to be used with 3 motors, the x and y motors that
    move to a designaget target on a sample wafer, and one scan_motor that can
    be delay time, laser power or some other motor positions.

    Parameters
    ----------
    sample : str
        The name of the sample we're interested in.
    detectors : list
        Objects to read into Python in the scan.
    x_motor : obj
        Motor object corresponding to the x axes.
    y_motor : obj
        Motor object corresponding to the y axes.
    scan_motor : obj
        The motor being scanned. It can be e.g., delay time, laser power, some
        other motor position, etc.
    ss : list
        List of all the points (samples) for the scan_motor to go through.
    n_shots : int
        Indicates how many shots should be taken at one position.
    path : str
        Path where the sample file is located.
    """
    detectors = list(detectors) + [scan_motor]

    xx, yy = get_sample_targets(sample, path)
    # find the index of the next target to be shot (status is False)
    next_index = next((index for (index, d) in enumerate(xx)
                       if d['status'] is False), None)
    if next_index is None:
        raise IndexError('Could not get a target index that has not been shot,'
                         ' probably all targets were shot from this sample?')

    if ((next_index - 1) + (len(ss))) >= len(xx):
        raise IndexError('The number of next to be shot + n_shots * len(ss): '
                         f'{next_index} + {len(ss)}= '
                         f'{next_index + (len(ss))}: '
                         f' bigger than the available samples: {len(xx)}. '
                         'Please provide a number in range.')

    @bpp.run_decorator()
    def inner_scan():
        try:
            temp_index = next_index - 1
            for i in range(len(ss)):
                temp_index += 1
                yield from bps.mv(scan_motor, ss[i])
                for j in range(n_shots):
                    x = next((d['pos'] for (index, d) in enumerate(xx)
                              if index == temp_index))
                    y = next((d['pos'] for (index, d) in enumerate(yy)
                              if index == temp_index))
                    yield from bpp.stub_wrapper(bp.list_scan(detectors,
                                                x_motor, [x], y_motor, [y]))
            update_sample(sample, path, (len(ss)))
        except Exception:
            current_position = x_motor.position
            try:
                last_index = next((index for (index, d) in enumerate(xx)
                                   if np.isclose(d["pos"], current_position)))
                update_sample(sample, path, (last_index - next_index + 1))
            except Exception:
                logger.warning('Could not find the index in the targets list '
                               'for the current motor value: %s',
                               current_position)
    return (yield from inner_scan())


def daq_fixed_target_multi_scan(sample, detectors, x_motor, y_motor,
                                scan_motor, ss, n_shots, path, record=True,
                                events=None):

    control_devices = [x_motor, y_motor, scan_motor]

    @nbpp.daq_during_decorator(record=record, controls=control_devices)
    def inner_daq_fixed_target_scan():
        yield from fixed_target_multi_scan(sample=sample, detectors=detectors,
                                           x_motor=x_motor, y_motor=y_motor,
                                           scan_motor=scan_motor, ss=ss,
                                           n_shots=n_shots, path=path)

    return (yield from inner_daq_fixed_target_scan())


def daq_fixed_target_scan(sample, detectors, x_motor, y_motor, scan_motor, ss,
                          n_shots, path, record=True, events=None):
    """
    Scan over two variables in steps simultaneously with DAQ Support.

    This is a ``nabs`` version of ``bluesky``'s built-in
    `bluesky.plans.list_scan` plan. It takes in consideration the number of
    samples to be scanned out of the samples given in ``xx`` and ``yy``.

    Parameters
    ----------
    sample : str
        The name of the sample we're interested in.
    detectors : list
        Objects to read into Python in the scan.
    x_motor : obj
        Motor object corresponding to the x axes.
    y_motor : obj
        Motor object corresponding to the y axes.
    scan_motor : obj
        The motor being scanned. It can be e.g., delay time, laser power, some
        other motor position, etc.
    ss : list
        List of all the points (samples) for the scan_motor to go through.
    n_shots : int
        Indicates how many shots should be taken, or how many samples should
        be scanned on the grid.
    path : str
        Path where the sample file is located.
    record : bool, optional
        Whether or not to record the run in the DAQ. Defaults to True because
        we don't want to accidentally skip recording good runs.
    events : int, optional
        Number of events to take at each step. If omitted, uses the
        duration argument or the last configured value.
    """
    control_devices = [x_motor, y_motor, scan_motor]

    @nbpp.daq_during_decorator(record=record, controls=control_devices)
    def inner_daq_fixed_target_scan():
        yield from fixed_target_scan(sample=sample, detectors=detectors,
                                     x_motor=x_motor, y_motor=y_motor,
                                     scan_motor=scan_motor, ss=ss,
                                     n_shots=n_shots, path=path)

    return (yield from inner_daq_fixed_target_scan())

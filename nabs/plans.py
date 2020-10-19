"""
nabs.plans

Much like bluesky.plans, this module contain full standalone plans that can be
used to take full individual runs using a RunEngine.

Plans preceded by "daq_" incorporate standard daq step scan args and behavior.
"""
from bluesky.plans import scan
from bluesky.preprocessors import (relative_set_decorator,
                                   reset_positions_decorator)

from .preprocessors import daq_step_scan_decorator


@reset_positions_decorator
@daq_step_scan_decorator
def daq_ascan(motor, start, end, nsteps):
    """
    One-dimensional daq scan with absolute positions.

    This moves a motor from start to end in nsteps steps, taking data in the
    DAQ at every step, and returning the motor to its original position at
    the end of the scan.

    Parameters
    ----------
    motor : Movable
        A movable object to scan.

    start : int or float
        The first point in the scan.

    end : int or float
        The last point in the scan.

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
    """

    yield from scan([], motor, start, end, nsteps)


@relative_set_decorator
@reset_positions_decorator
@daq_step_scan_decorator
def daq_dscan(motor, start, end, nsteps):
    """
    One-dimensional daq scan with relative (delta) positions.

    This moves a motor from current_pos + start to current_pos + end
    in nsteps steps, taking data in the DAQ at every step, and
    returning the motor to its original position at the end of the scan.

    Parameters
    ----------
    motor : Movable
        A movable object to scan.

    start : int or float
        The first point in the scan, relative to the current position.

    end : int or float
        The last point in the scan, relative to the current position.

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
    """

    yield from scan([], motor, start, end, nsteps)


@reset_positions_decorator
@daq_step_scan_decorator
def daq_a2scan(m1, a1, b1, m2, a2, b2, nsteps):
    """
    Two-dimensional daq scan with absolute positions.

    This moves two motors from start to end in nsteps steps, taking data in
    the DAQ at every step, and returning the motors to their original positions
    at the end of the scan.

    Parameters
    ----------
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
    """

    yield from scan([], m1, a1, b1, m2, a2, b2, nsteps)


@reset_positions_decorator
@daq_step_scan_decorator
def daq_a3scan(m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps):
    """
    Three-dimensional daq scan with absolute positions.

    This moves three motors from start to end in nsteps steps, taking data in
    the DAQ at every step, and returning the motors to their original positions
    at the end of the scan.

    Parameters
    ----------
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
    """

    yield from scan([], m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps)

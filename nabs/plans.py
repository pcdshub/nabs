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
    yield from scan([], motor, start, end, nsteps)


@relative_set_decorator
@reset_positions_decorator
@daq_step_scan_decorator
def daq_dscan(motor, start, end, nsteps):
    yield from scan([], motor, start, end, nsteps)


@reset_positions_decorator
@daq_step_scan_decorator
def daq_a2scan(m1, a1, b1, m2, a2, b2, nsteps):
    yield from scan([], m1, a1, b1, m2, a2, b2, nsteps)


@reset_positions_decorator
@daq_step_scan_decorator
def daq_a3scan(m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps):
    yield from scan([], m1, a1, b1, m2, a2, b2, m3, a3, b3, nsteps)

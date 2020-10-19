import bluesky.plans as bp
import bluesky.plan_stubs as bps
from bluesky.suspenders import SuspendFloor
from ophyd.utils import AlarmSeverity
from pcdsdaq.plans import sequencer_mode  # In dev branch of pcdsdaq currently
from pcdsdevices.sequencer import EventSequencer
from pcdsdevices.beam_stats import BeamStats

from cxi.db import (daq, cxi_kb2_hx, cxi_kb2_hy, cxi_kb2_hl, cxi_kb2_hp,
                    cxi_kb2_hr, cxi_kb2_vx, cxi_kb2_vy, cxi_kb2_vp)


# Create EventSequencer. This should be loaded through happi in the future
sequencer = EventSequencer('ECS:SYS0:5', name='cxi_sequencer')

# Create BeamStats object. This should also be loaded by default in the future
beam_stats = BeamStats()

# This is to deal with the fact that the KB2 motors are not properly configured
# and raise a MINOR error on every move. This is simply an attribute that when
# set ignores MINOR alarms
for motor in (cxi_kb2_hx, cxi_kb2_hy, cxi_kb2_hl, cxi_kb2_hp, cxi_kb2_hr,
              cxi_kb2_vx, cxi_kb2_vy, cxi_kb2_vp):
    motor.tolerated_alarm = AlarmSeverity.MINOR


def imprint_row(*args, events=1, min_mj=0.5):
    """
    Run a single row of the imprint scan

    Parameters
    ----------
    args: passed to bluesky.plans.scan

    events: int
        The number of events to allow at each stopping point in the scan

    min_mj, float, optional
        The minimum energy the scan should continue to execute scans

    Example
    -------
    .. code::

        # Run a scan from -1, 1 in 10 steps with 40 shots at each step
        RE(imprint_row(pi_x, -1, 1, 10, events=40))

        # Run a scan with two motors from -1, 1 and 12, 20, in five steps with
        # 10 shots at each step. Pause if we have less than 1 mJ in the GDET
        RE(imprint_row(pi_x, -1, 1,
                       cxi.kb2.hl, 12, 20, 5,
                       events=10, min_mj=1))
    """
    # Create a new suspender
    suspender = SuspendFloor(beam_stats.mj_avg, min_mj)
    # Install the new suspender
    yield from bps.install_suspender(suspender)
    # Execute a scan first configuring the Sequencer and DAQ
    try:
        yield from sequencer_mode(daq, sequencer, events, sequence_wait=.25)
        yield from bp.scan([daq, sequencer], *args)
    # Always ensure we remove the suspender
    finally:
        yield from bps.remove_suspender(suspender)

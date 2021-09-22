import logging

import bluesky.plan_stubs as bps
import bluesky.plans as bp
import bluesky.preprocessors as bpp
import pytest
from ophyd.signal import Signal

from nabs.preprocessors import (daq_during_decorator, daq_step_scan_decorator,
                                daq_step_scan_standard_args)

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def daq_step_scan(daq):
    return daq_step_scan_decorator(bp.scan)


def test_daq_step_scan_args(hw, daq, daq_step_scan):
    """
    Basic args and message inspection tests.

    Can I decorate a scan?
    Can I call a decorated scan at all?
    Does a decorated scan produce the messages I expect?
    """
    logger.debug('test_daq_step_scan_args')

    def assert_daq_messages(msg_list, motor):
        """
        Make sure the msg_list is properly mutated.

        Checks for a daq configure message with controls arg
        Checks for a daq trigger/read in every bundle
        """
        found_configure = False
        found_trigger = False
        found_read = False

        for msg in msg_list:
            if msg.command == 'configure' and msg.obj is daq:
                found_configure = True
                assert msg.kwargs['controls'] == [motor]
            elif msg.command == 'trigger' and msg.obj is daq:
                found_trigger = True
            elif msg.command == 'read' and msg.obj is daq:
                found_read = True

        assert found_configure, 'Did not find daq configure in msg list.'
        assert found_trigger, 'Did not find daq trigger in msg list.'
        assert found_read, 'Did not find daq read in msg list.'

    daq_with_det = list(daq_step_scan([hw.det], hw.motor, 0, 10, 11, events=10,
                                      record=False, use_l3t=True))
    assert_daq_messages(daq_with_det, hw.motor)
    daq_none_det = list(daq_step_scan([], hw.motor, 0, 10, 11, events=10,
                                      record=False, use_l3t=True))
    assert_daq_messages(daq_none_det, hw.motor)
    daq_pseudopos = list(
        daq_step_scan(
            [], hw.no_op_pseudo.noop, 0, 10, 11,
            events=10,
            record=False,
            use_l3t=False
        )
    )
    assert_daq_messages(daq_pseudopos, hw.no_op_pseudo.noop)

    def assert_no_lost_msg(daq_msg_list, nodaq_msg_list):
        """
        Make sure no message from the original plan is lost.
        """
        daq_without_daq = [msg for msg in daq_msg_list if msg.obj is not daq]
        assert daq_without_daq == nodaq_msg_list

    nodaq_with_det = list(bp.scan([hw.det], hw.motor, 0, 10, 11))
    assert_no_lost_msg(nodaq_with_det, nodaq_with_det)

    nodaq_none_det = list(bp.scan([], hw.motor, 0, 10, 11))
    assert_no_lost_msg(nodaq_none_det, nodaq_none_det)


def test_daq_step_scan_run(RE, hw, daq_step_scan):
    """
    Actually run a scan and make sure it doesn't error out.
    """
    RE(daq_step_scan([hw.det], hw.motor, 0, 10, 11, events=10, record=False,
                     use_l3t=True))


def test_daq_step_scan_misconfigured(RE, hw, daq, daq_step_scan):
    """
    Check that we raise a TypeError when DAQ is passed as second detector.
    """
    with pytest.raises(TypeError):
        list(daq_step_scan([hw.det, daq], hw.motor, 0, 10, 11, events=10,
                           record=False, use_l3t=True))


def test_daq_during_decorator(RE, daq):
    """
    Run a daq during scan and make sure the daq is running during it.
    """
    logger.debug('test_daq_during_decorator')

    @daq_during_decorator()
    @bpp.run_decorator()
    def plan(reader):
        yield from bps.null()
        for i in range(10):
            assert daq.state == 'Running'
            yield from bps.trigger_and_read([reader])
        assert daq.state == 'Running'
        yield from bps.null()

    daq.connect()
    RE(plan(Signal(name='sig')))
    assert daq.state == 'Configured'


def test_noop_coverage():
    """
    Call the documentation function to cover the line.
    """
    logger.debug('test_noop_coverage')
    daq_step_scan_standard_args()

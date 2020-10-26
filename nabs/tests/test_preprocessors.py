import logging

import pytest
from bluesky.plans import scan

from nabs.preprocessors import (daq_during_decorator, daq_step_scan_decorator,
                                daq_step_scan_standard_args)

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def daq_step_scan(daq):
    return daq_step_scan_decorator(scan)


def test_daq_step_scan_args(hw, daq, daq_step_scan):
    logger.debug('test_daq_step_scan_args')

    def assert_daq_messages(msg_list):
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
                assert msg.kwargs['controls'] == [hw.motor]
            elif msg.command == 'trigger' and msg.obj is daq:
                found_trigger = True
            elif msg.command == 'read' and msg.obj is daq:
                found_read = True

        assert found_configure, 'Did not find daq configure in msg list.'
        assert found_trigger, 'Did not find daq trigger in msg list.'
        assert found_read, 'Did not find daq read in msg list.'

    with_det = list(daq_step_scan([hw.det], hw.motor, 0, 10, 11, events=10,
                                  record=False, use_l3t=True))
    assert_daq_messages(with_det)
    none_det = list(daq_step_scan(hw.motor, 0, 10, 11, events=10,
                                  record=False, use_l3t=True))
    assert_daq_messages(none_det)


def test_daq_during_decorator():
    # TODO write test
    daq_during_decorator()


def test_noop_coverage():
    logger.debug('test_noop_coverage')
    daq_step_scan_standard_args()

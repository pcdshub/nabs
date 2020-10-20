import logging

import pytest
from bluesky.plans import scan

from nabs.preprocessors import (daq_during_decorator, daq_step_scan_decorator,
                                daq_step_scan_standard_args)

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def daq_step_scan(daq):
    return daq_step_scan_decorator(scan)


def test_daq_step_scan_args(hw, daq_step_scan):
    logger.debug('test_daq_step_scan_args')

    def assert_daq_messages(msg_list):
        assert False  # TODO write test

    with_det = list(daq_step_scan([hw.det], hw.mot, 0, 10, 11, events=10,
                                  record=False, use_l3t=True))
    assert_daq_messages(with_det)
    none_det = list(daq_step_scan(hw.mot, 0, 10, 11, events=10,
                                  record=False, use_l3t=True))
    assert_daq_messages(none_det)


def test_daq_during_decorator():
    # TODO write test
    daq_during_decorator()


def test_noop_coverage():
    logger.debug('test_noop_coverage')
    daq_step_scan_standard_args()

import logging

from bluesky.callbacks import CallbackCounter
from bluesky.plan_stubs import open_run, close_run
import numpy as np
from ophyd.sim import SynGauss

from nabs.plan_stubs import measure_average, golden_section_search

logger = logging.getLogger(__name__)


def test_measure_average(RE, hw):
    logger.debug("test_measure_average")

    # Pseudo-plan to measure average and check values
    def measure_plan(detectors):
        yield from open_run()
        ret = yield from measure_average(detectors, num=250)
        assert ret['motor'] == 0.0
        assert ret['motor_setpoint'] == 0.0
        assert np.isclose(ret['noisy_det'], 1.0, atol=0.01)
        yield from close_run()

    # Execute plan
    cnt = CallbackCounter()
    RE(measure_plan([hw.motor, hw.noisy_det]), {'event': [cnt]})
    # Check that we saw the right number of events
    assert cnt.value == 250


def test_golden_section_search(RE, hw):
    logger.debug("test_golden_section_search")
    # Make our inverted detector
    sig = SynGauss('det', hw.motor, 'motor', center=0, Imax=-1, sigma=1)
    # Catch the reported limits
    global region_limits
    region_limits = None

    # Pseudo-plan to golden-section search
    def gss():
        global region_limits
        yield from open_run()
        region_limits = yield from golden_section_search(sig, hw.motor, 0.01,
                                                         limits=(-10, 5))
        yield from close_run()

    # Execute the plan
    RE(gss())
    # Check that the region we found is under the resolution
    assert (region_limits[1] - region_limits[0]) < 0.1
    # Check that the limits bound the center of the gaussian
    assert region_limits[1] > 0.
    assert region_limits[0] < 0.

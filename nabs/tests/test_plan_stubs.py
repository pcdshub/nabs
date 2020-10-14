import logging

import numpy as np
from bluesky.callbacks import CallbackCounter
from bluesky.plan_stubs import close_run, open_run

from nabs.plan_stubs import measure_average

logger = logging.getLogger(__name__)


def test_measure_average(RE, hw):
    logger.debug("test_measure_average")

    # Pseudo-plan to measure average and check values
    def measure_plan(detectors):
        yield from open_run()
        ret = yield from measure_average(detectors, num=250)
        logger.debug(ret)
        assert ret['motor'] == 0.0
        assert ret['motor_setpoint'] == 0.0
        assert np.isclose(ret['noisy_det'], 1.0, atol=0.01)
        yield from close_run()

    # Execute plan
    cnt = CallbackCounter()
    RE(measure_plan([hw.motor, hw.noisy_det]), {'event': [cnt]})
    # Check that we saw the right number of events
    assert cnt.value == 250

import logging
import time

from bluesky.callbacks import CallbackCounter, collector
from bluesky.plan_stubs import open_run, close_run
import numpy as np
import pytest

from nabs.plan_stubs import measure_average, monitor_events

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


@pytest.mark.timeout(10)
def test_monitor_events(RE, hw):
    logger.debug('test_monitor_events')

    def plan(detectors, events=None, duration=None):
        yield from open_run()
        yield from monitor_events(detectors, events=events, duration=duration)
        yield from close_run()

    detectors = [hw.det]

    # should take about 0.3s
    start = time.time()
    RE(plan(detectors, duration=0.3))
    delta = time.time() - start
    assert 0.3 < delta < 1.3

    for det in detectors:
        det.put(0)

    def bg(loop):
        logger.debug('bg')
        for det in detectors:
            value = det.get()
            det.put(value + 1)
        logger.debug(value)
        if value < 10:
            loop.call_later(0.1, bg, loop)

    def plan_bg(detectors, events=None, duration=None):
        loop = RE._loop
        loop.call_later(0.1, bg, loop)
        yield from plan(detectors, events=events, duration=duration)

    det_vals = []
    coll = collector(detectors[0].name, det_vals)
    RE.subscribe(coll, 'event')

    RE(plan_bg(detectors, events=7))
    assert len(det_vals) >= 7
    for det in detectors:
        assert det.value < 10

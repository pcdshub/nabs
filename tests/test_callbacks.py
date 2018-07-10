import logging

from bluesky.plan_stubs import (open_run, close_run, trigger_and_read,
                                wait_for, monitor, unmonitor)
import pytest

from nabs.callbacks import CallbackCounterFuture

logger = logging.getLogger(__name__)


def batch_mon(detectors):
    for det in detectors:
        yield from monitor(det)


def batch_unmon(detectors):
    for det in detectors:
        yield from unmonitor(det)


@pytest.mark.timeout(10)
@pytest.mark.parametrize('num_calls', [1, 10])
@pytest.mark.parametrize('num_dets', [1, 3])
@pytest.mark.parametrize('counting', ['each', 'total'])
@pytest.mark.parametrize('method', ['read', 'monitor'])
def test_counter_future(RE, hw, num_calls, num_dets, counting, method):
    logger.debug('test_counter_future')
    dets = [hw.det1, hw.det2, hw.det3]
    dets = dets[:num_dets]
    if counting == 'total':
        counter = CallbackCounterFuture(num_calls)
        RE.subscribe(counter, 'event')
    elif counting == 'each':
        counter = CallbackCounterFuture(num_calls, detectors=dets)
        RE.subscribe(counter)

    def plan():
        yield from open_run()
        i = 0
        if method == 'monitor':
            yield from batch_mon(dets)
        while True:
            i += 1
            if method == 'read':
                yield from trigger_and_read(dets)
            elif method == 'monitor':
                for det in dets:
                    det.put(i)
            logger.debug(counter.value)
            if counter.future.done():
                break
        if method == 'monitor':
            yield from batch_unmon(dets)
        assert counter.future.done()
        # make sure we can use it with the RE's loop
        yield from wait_for([counter.future])
        yield from close_run()

    RE(plan())
    if counting == 'each':
        assert counter.dets == {det.name: num_calls for det in dets}
    elif counting == 'total':
        assert num_calls <= counter.value < num_calls + num_dets

import logging

from bluesky.callbacks import CallbackCounter
from bluesky.plan_stubs import (trigger_and_read, create, save,
                                trigger, read, sleep)
from bluesky.preprocessors import run_wrapper
import pytest

from nabs.preprocessors import drop_wrapper

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def RE_counter(RE):
    counter = CallbackCounter()
    RE.subscribe(counter, name='event')
    RE.preprocessors.append(run_wrapper)
    return RE, counter


def gap_read(det1, det2, gap):
    yield from create()
    yield from trigger(det1)
    yield from read(det1)
    yield from sleep(gap)
    yield from trigger(det2)
    yield from read(det2)
    yield from save()


def test_no_drop(RE_counter, hw):
    logger.debug('test_no_drop')
    RE, counter = RE_counter
    # Normal read
    RE(trigger_and_read([hw.det]))
    assert counter.value == 1
    # Move det to "too low"
    hw.motor.set(1)
    RE(trigger_and_read([hw.det]))
    assert counter.value == 2
    # Take reads 0.5s apart
    RE(gap_read(hw.det1, hw.det2, 0.5))
    assert counter.value == 3


@pytest.mark.timeout(3)
def test_drop_filter(RE_counter, hw):
    logger.debug('test_drop_filter')
    RE, counter = RE_counter

    # Filter on det, value starts good
    def my_filter(reads):
        return reads['det']['value'] > 0.8

    RE(drop_wrapper(trigger_and_read([hw.det]), filters=my_filter))
    assert counter.value == 1
    # Move det to "too low"
    hw.motor.set(1)
    RE(drop_wrapper(trigger_and_read([hw.det]), filters=my_filter))
    assert counter.value == 1


@pytest.mark.timeout(3)
def test_dt_filter(RE_counter, hw):
    logger.debug('test_dt_filter')
    RE, counter = RE_counter
    # Filter on dt, first is ok
    RE(drop_wrapper(gap_read(hw.det1, hw.det2, 0.1), max_dt=0.4))
    assert counter.value == 1
    # Take reads 0.5s apart
    RE(drop_wrapper(gap_read(hw.det1, hw.det2, 0.5), max_dt=0.4))
    assert counter.value == 1

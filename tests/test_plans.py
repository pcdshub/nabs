import logging

from ophyd.status import wait as status_wait
import pytest

from nabs.plans import monitor_scan

logger = logging.getLogger(__name__)


@pytest.mark.timeout(5)
def test_monitor_scan(RE, hw):
    logger.debug('test_monitor_scan')
    num_steps = 11
    events = 3
    docs = []

    def collect_docs(name, doc):
        logger.debug('collect %s %s', name, doc)
        docs.append(doc)
    RE.subscribe(collect_docs, 'event')

    def trigger_det_outer(*args, **kwargs):
        RE._loop.call_later(0.1, trigger_det)

    def trigger_det(*args, **kwargs):
        logger.debug('trigger')
        for i in range(events - 1):
            status_wait(hw.det.trigger())

    hw.motor.readback.subscribe(trigger_det_outer, run=False)
    hw.det.trigger()
    RE(monitor_scan([hw.det], hw.motor, -3, 3, num_steps, events=events))

    n_mot = 0
    n_det = 0
    mot_pos = []
    for doc in docs:
        if hw.motor.name in doc['data']:
            n_mot += 1
            mot_pos.append(doc['data'][hw.motor.name])
        if hw.det.name in doc['data']:
            n_det += 1

    assert n_mot == num_steps
    assert n_det == num_steps * events
    assert min(mot_pos) == -3
    assert max(mot_pos) == 3

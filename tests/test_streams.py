from bluesky.callbacks import CallbackCounter
from bluesky.plans import scan
from bluesky.tests.utils import DocCollector
from nabs.streams import AverageStream


def test_average_stream(RE, hw):
    # Create callback chain
    avg = AverageStream(10)
    c = CallbackCounter()
    d = DocCollector()
    avg.subscribe(c)
    avg.subscribe(d.insert)
    # Run a basic plan
    RE(scan([hw.det], hw.motor, -5, 4, 10), {'all': avg})
    assert c.value == 1 + 1 + 2  # events, descriptor, start and stop
    # See that we made sensible descriptor
    start_uid = d.start[0]['uid']
    assert start_uid in d.descriptor
    desc_uid = d.descriptor[start_uid][0]['uid']
    assert desc_uid in d.event
    evt = d.event[desc_uid][0]
    assert evt['seq_num'] == 1
    assert all([key in d.descriptor[start_uid][0]['data_keys']
                for key in evt['data'].keys()])
    # See that we returned the correct average
    assert evt['data']['motor'] == -0.5  # mean of range(-5, 5)
    assert evt['data']['motor_setpoint'] == -0.5  # mean of range(-5, 5)
    assert start_uid in d.stop
    assert d.stop[start_uid]['num_events'] == {'primary': 1}

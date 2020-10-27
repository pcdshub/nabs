import logging

import numpy as np
import pytest
from ophyd.device import Component as Cpt
from ophyd.signal import Signal
from pcdsdevices.pseudopos import DelayBase
from pcdsdevices.sim import FastMotor

import nabs.plans as nbp

logger = logging.getLogger(__name__)


@pytest.mark.timeout(5)
def test_duration_scan(RE, hw):
    """
    Run the duration scan and check the messages it creates.
    """
    logger.debug('test_duration_scan')

    # These will generate as many messages as they can in 0.01s
    scan1 = list(nbp.duration_scan([hw.det], hw.motor, [0, 1], duration=0.01))
    scan2 = list(nbp.duration_scan([hw.det1, hw.det2], hw.motor1, [-1, 1],
                                   hw.motor2, [-2, 2], duration=0.01))

    # I won't check behavior, but they should not error out
    RE(scan1)
    RE(scan2)

    # Scan should cycle through positions
    scan1_moves = list(msg.args[0] for msg in scan1 if msg.command == 'set')
    assert scan1_moves[:4] == [0, 1, 0, 1]
    assert len(scan1_moves) > 20

    scan2_moves = list(msg.args[0] for msg in scan2 if msg.command == 'set')
    assert scan2_moves[:8] == [-1, -2, 1, 2, -1, -2, 1, 2]
    assert len(scan1_moves) > 20


class SimDelayMotor(FastMotor):
    velocity = Cpt(Signal, value=0)
    egu = 'm'


class SimDelayStage(DelayBase):
    motor = Cpt(SimDelayMotor)


@pytest.fixture(scope='function')
def time_motor():
    return SimDelayStage('SIM', name='sim', egu='s', n_bounces=1)


@pytest.mark.timeout(5)
def test_delay_scan(RE, time_motor):
    """
    Check the delay scan, verify that velo is set appropriately.
    """
    logger.debug('test_delay_scan')

    # Speed of light is more or less 3e8
    goal = 1/(3e8)
    msgs = nbp.delay_scan(time_motor, [0, goal], 1, duration=0.01)
    moves = list(msg.args[0] for msg in msgs if msg.command == 'set')
    # first point is the velo, which should be close to 1 with 1 bounce set
    assert np.isclose(moves[0], 1, rtol=1e-2)
    # next we move the time motor between zero and goal
    assert moves[1:5] == [0, goal, 0, goal]
    # scan should keep going
    assert len(moves) > 20
    # scan should not error if run
    RE(msgs)


@pytest.mark.timeout(5)
def test_daq_delay_scan(RE, daq, time_motor):
    """
    Check that daq_delay_scan's arguments all work.
    """
    logger.debug('test_daq_delay_scan')

    msgs = list(nbp.daq_delay_scan(time_motor, [0, 1], 1, duration=0.01,
                                   record=True))
    configure_message = None
    for msg in msgs:
        if msg.command == 'configure' and msg.obj is daq:
            configure_message = msg
            break
    assert configure_message is not None, 'Did not find daq configure message.'
    assert configure_message.kwargs['record'] is True
    assert configure_message.kwargs['controls'] == [time_motor]

    # Run the scan
    RE(msgs)


def assert_scan_has_daq(msgs, daq):
    """
    Go through a plan's messages and verify it runs the daq correctly.

    This is intended to be applied to any "standard" plan that is just a
    built-in bluesky plan with the daq added to it.

    We check for the following things:
    1. The DAQ is staged
    2. The DAQ is configured
    3. The DAQ is triggered
    4. The DAQ is read
    5. The DAQ is unstaged
    """
    logger.debug('assert_scan_has_daq')

    message_types = {msg.command for msg in msgs if msg.obj is daq}

    assert 'stage' in message_types, 'Scan does not stage daq.'
    assert 'configure' in message_types, 'Scan does not configure daq.'
    assert 'trigger' in message_types, 'Scan does not trigger daq.'
    assert 'read' in message_types, 'Scan does not read daq.'
    assert 'unstage' in message_types, 'Scan does not unstage daq.'


def daq_test(RE, daq, plan):
    """
    Check the messages for daq and try to run the plan with RE.
    """
    logger.debug('daq_test')
    msgs = list(plan)
    assert_scan_has_daq(msgs, daq)
    RE(msgs)
    return msgs


@pytest.mark.timeout(5)
def test_daq_count(RE, daq, hw):
    logger.debug('test_daq_count')
    daq_test(RE, daq, nbp.daq_count(events=10))
    daq_test(RE, daq, nbp.daq_count(num=5, events=20))
    daq_test(RE, daq, nbp.daq_count([hw.det], num=5, events=5))


@pytest.mark.timeout(5)
def test_daq_scan(RE, daq, hw):
    logger.debug('test_daq_scan')
    daq_test(RE, daq, nbp.daq_scan(hw.motor, 0, 10, 11, events=15))
    daq_test(RE, daq, nbp.daq_scan([hw.det], hw.motor, 0, 10, 11, events=5))
    daq_test(RE, daq, nbp.daq_scan([hw.det1, hw.det2],
                                   hw.motor1, 0, 10,
                                   hw.motor2, 0, 10, 11,
                                   events=20))


@pytest.mark.timeout(5)
def test_daq_list_scan(RE, daq, hw):
    logger.debug('test_daq_list_scan')
    daq_test(RE, daq, nbp.daq_list_scan(hw.motor, list(range(10)), events=10))
    daq_test(RE, daq, nbp.daq_list_scan([hw.det], hw.motor, list(range(10)),
                                        events=20))
    daq_test(RE, daq, nbp.daq_list_scan([hw.det1, hw.det2],
                                        hw.motor1, list(range(10)),
                                        hw.motor2, list(range(10)),
                                        events=15))


@pytest.mark.timeout(5)
def test_daq_ascan(RE, daq, hw):
    logger.debug('test_daq_ascan')
    daq_test(RE, daq, nbp.daq_ascan(hw.motor, 0, 10, 11, events=10))


@pytest.mark.timeout(5)
def test_daq_dscan(RE, daq, hw):
    logger.debug('test_daq_dscan')
    daq_test(RE, daq, nbp.daq_dscan(hw.motor, 0, 10, 11, events=20))

    # Quick sanity check on the deltas
    hw.motor.move(42)
    msgs = list(nbp.daq_dscan(hw.motor, 0, 10, 11, events=30))
    moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    assert moves == list(range(42 + 11)) + [42]


@pytest.mark.timeout(5)
def test_daq_a2scan(RE, daq, hw):
    logger.debug('test_daq_a2scan')
    daq_test(RE, daq, nbp.daq_a2scan(hw.motor1, 0, 10, hw.motor2, 0, 10, 11,
                                     events=15))


@pytest.mark.timeout(5)
def test_daq_a3scan(RE, daq, hw):
    logger.debug('test_daq_a3scan')
    daq_test(RE, daq, nbp.daq_a3scan(hw.motor1, 0, 10,
                                     hw.motor2, 0, 10,
                                     hw.motor3, 0, 10, 11,
                                     events=20))

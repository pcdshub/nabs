import logging
from collections import defaultdict

import numpy as np
import pytest
from bluesky.simulators import summarize_plan
from ophyd.device import Component as Cpt
from ophyd.signal import Signal
from pcdsdevices.pseudopos import DelayBase
from pcdsdevices.sim import FastMotor

import nabs.plans as nbp
from nabs.utils import orange

PLAN_TIMEOUT = 60
logger = logging.getLogger(__name__)


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_duration_scan(RE, hw):
    """Run the duration scan and check the messages it creates."""
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


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_delay_scan(RE, hw, time_motor):
    """Check the delay scan, verify that velo is set appropriately."""
    logger.debug('test_delay_scan')

    # Speed of light is more or less 3e8
    goal = 1/(3e8)
    msgs = nbp.delay_scan([hw.det], time_motor, [0, goal], 1, duration=0.01)
    moves = list(msg.args[0] for msg in msgs if msg.command == 'set')
    # first point is the velo, which should be close to 1 with 1 bounce set
    assert np.isclose(moves[0], 1, rtol=1e-2)
    # next we move the time motor between zero and goal
    assert moves[1:5] == [0, goal, 0, goal]
    # scan should keep going
    assert len(moves) > 20
    # scan should not error if run
    RE(msgs)


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_delay_scan(RE, daq, hw, time_motor):
    """Check that daq_delay_scan's arguments all work."""
    logger.debug('test_daq_delay_scan')

    msgs = list(nbp.daq_delay_scan([hw.det], time_motor, [0, 1], 1,
                                   duration=0.01, record=True))
    configure_message = None
    for msg in msgs:
        if msg.command == 'configure' and msg.obj is daq:
            configure_message = msg
            break
    assert configure_message is not None, 'Did not find daq configure message.'
    assert configure_message.kwargs['record'] is True
    assert configure_message.kwargs.get('controls') is None

    # Run the scan
    RE(msgs)


def assert_scan_has_daq(msgs, daq):
    """
    Go through a plan's messages and verify it runs the daq correctly.

    This is intended to be applied to any "standard" plan that is just a
    built-in bluesky plan with the daq added to it.

    We check for the following things:
    1. The DAQ is staged (exactly once)
    2. The DAQ is configured (exactly once)
    3. The DAQ is triggered
    4. The DAQ is read
    5. The DAQ is unstaged (exactly once)
    """

    logger.debug('assert_scan_has_daq')

    message_types = defaultdict(int)

    for msg in msgs:
        if msg.obj is daq:
            message_types[msg.command] = message_types[msg.command] + 1

    assert 'stage' in message_types, 'Scan does not stage daq.'
    assert 'configure' in message_types, 'Scan does not configure daq.'
    assert 'trigger' in message_types, 'Scan does not trigger daq.'
    assert 'read' in message_types, 'Scan does not read daq.'
    assert 'unstage' in message_types, 'Scan does not unstage daq.'

    assert message_types['stage'] == 1, 'Scan stages daq multiple times.'
    assert message_types['configure'] == 1, ('Scan configures daq multiple '
                                             'times.')
    assert message_types['unstage'] == 1, 'Scan unstages daq multiple times.'


def daq_test(RE, daq, plan):
    """Check the messages for daq and try to run the plan with RE."""
    logger.debug('daq_test')
    msgs = list(plan)
    assert_scan_has_daq(msgs, daq)
    RE(msgs)
    return msgs


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_count(RE, daq, hw):
    logger.debug('test_daq_count')
    daq_test(RE, daq, nbp.daq_count(events=1))
    daq_test(RE, daq, nbp.daq_count(num=5, events=1))
    daq_test(RE, daq, nbp.daq_count([hw.det], num=5, events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_scan(RE, daq, hw):
    logger.debug('test_daq_scan')
    daq_test(RE, daq, nbp.daq_scan(hw.motor, 0, 10, 11, events=1))
    daq_test(RE, daq, nbp.daq_scan([hw.det], hw.motor, 0, 10, 11, events=1))
    daq_test(RE, daq, nbp.daq_scan([hw.det1, hw.det2],
                                   hw.motor1, 0, 10,
                                   hw.motor2, 0, 10, 11,
                                   events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_list_scan(RE, daq, hw):
    logger.debug('test_daq_list_scan')
    daq_test(RE, daq, nbp.daq_list_scan(hw.motor, list(range(10)), events=1))
    daq_test(RE, daq, nbp.daq_list_scan([hw.det], hw.motor, list(range(10)),
                                        events=1))
    daq_test(RE, daq, nbp.daq_list_scan([hw.det1, hw.det2],
                                        hw.motor1, list(range(10)),
                                        hw.motor2, list(range(10)),
                                        events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_ascan(RE, daq, hw):
    logger.debug('test_daq_ascan')
    daq_test(RE, daq, nbp.daq_ascan([hw.det], hw.motor, 0, 10, 11, events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_dscan(RE, daq, hw):
    logger.debug('test_daq_dscan')
    daq_test(RE, daq, nbp.daq_dscan([hw.det], hw.motor, 0, 10, 11, events=1))

    # Quick sanity check on the deltas
    hw.motor.set(42)
    msgs = list(nbp.daq_dscan([hw.det], hw.motor, 0, 10, 11, events=1))
    moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    assert moves == list(range(42, 42 + 11)) + [42]


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_a2scan(RE, daq, hw):
    logger.debug('test_daq_a2scan')
    daq_test(RE, daq, nbp.daq_a2scan([hw.det], hw.motor1, 0, 10, hw.motor2, 0,
                                     10, 11, events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_a3scan(RE, daq, hw):
    logger.debug('test_daq_a3scan')
    daq_test(RE, daq, nbp.daq_a3scan([hw.det],
                                     hw.motor1, 0, 10,
                                     hw.motor2, 0, 10,
                                     hw.motor3, 0, 10, 11,
                                     events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_d2scan(RE, daq, hw):
    logger.debug('test_daq_d2scan')
    daq_test(RE, daq, nbp.daq_d2scan([hw.det],
                                     hw.motor1, 0, 10,
                                     hw.motor2, 0, 10, 11,
                                     events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_anscan(RE, daq, hw):
    logger.debug('test_daq_anscan')
    daq_test(RE, daq, nbp.daq_anscan([hw.det],
             hw.motor1, 0, 10, 11,
             events=1))

    daq_test(RE, daq, nbp.daq_anscan([hw.det],
             hw.motor1, 0, 10,
             hw.motor2, 0, 10, 11,
             events=1))

    daq_test(RE, daq, nbp.daq_anscan([hw.det],
             hw.motor1, 0, 10,
             hw.motor2, 0, 10,
             hw.motor3, 0, 10, 11,
             events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_dnscan(RE, daq, hw):
    logger.debug('test_daq_dnscan')
    daq_test(RE, daq, nbp.daq_dnscan([hw.det],
             hw.motor1, 0, 10, 11,
             events=1))

    daq_test(RE, daq, nbp.daq_dnscan([hw.det],
             hw.motor1, 0, 10,
             hw.motor2, 0, 10, 11,
             events=1))

    daq_test(RE, daq, nbp.daq_dnscan([hw.det],
             hw.motor1, 0, 10,
             hw.motor2, 0, 10,
             hw.motor3, 0, 10, 11,
             events=1))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_fixed_target_scan(RE, hw, sample_file):
    logger.debug('test_fixed_target_scan')
    ss = [1, 2]

    msgs = list(nbp.fixed_target_scan(sample='test_sample', detectors=[hw.det],
                                      x_motor=hw.motor1, y_motor=hw.motor2,
                                      scan_motor=hw.motor3, ss=ss,
                                      n_shots=3, path=sample_file))
    expected_moves = [1,                    # scan_motor[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      -20.342057291666624,  # x[1]
                      26.412369791666656,   # y[1]
                      -20.090364583333283,  # x[2]
                      26.41028645833332,    # y[2]
                      2,                    # scan_motor[1]
                      -19.838671874999946,  # x[3]
                      26.408203124999986,   # y[3]
                      -19.834546874999948,  # x[4]
                      26.664453124999994,   # y[4]
                      -20.08622265624995,   # x[5]
                      26.66232812499999]    # y[5]

    moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    assert moves == expected_moves

    RE(msgs)
    summarize_plan(msgs)

    with pytest.raises(IndexError):
        RE(nbp.fixed_target_scan(sample='test_sample', detectors=[hw.det],
                                 x_motor=hw.motor1, y_motor=hw.motor2,
                                 scan_motor=hw.motor3, ss=ss,
                                 n_shots=10, path=sample_file))


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_fixed_target_multi_scan(RE, hw, sample_file):
    logger.debug('test_fixed_target_multi_scan')
    ss = [1, 2]

    msgs = list(nbp.fixed_target_multi_scan(sample='test_sample',
                                            detectors=[hw.det],
                                            x_motor=hw.motor1,
                                            y_motor=hw.motor2,
                                            scan_motor=hw.motor3, ss=ss,
                                            n_shots=3, path=sample_file))
    expected_moves = [1,                    # scan_motor[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      2,                    # scan_motor[1]
                      -20.342057291666624,  # x[1]
                      26.412369791666656,
                      -20.342057291666624,  # x[1]
                      26.412369791666656,
                      -20.342057291666624,  # x[1]
                      26.412369791666656]   # y[1]

    moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    reads = [msg for msg in msgs if msg.command == 'read']
    assert moves == expected_moves
    assert len(reads) == 24

    RE(msgs)
    summarize_plan(msgs)


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_fixed_target_scan(RE, daq, hw, sample_file):
    logger.debug('test_daq_fixed_target_scan')
    ss = [1, 2]

    msgs = list(nbp.daq_fixed_target_scan(sample='test_sample',
                                          detectors=[hw.det],
                                          x_motor=hw.motor1, y_motor=hw.motor2,
                                          scan_motor=hw.motor3, ss=ss,
                                          n_shots=3, path=sample_file,
                                          record=True, events=1))
    configure_message = None
    for msg in msgs:
        if msg.command == 'configure' and msg.obj is daq:
            configure_message = msg
            break

    assert configure_message.kwargs['record'] is True
    assert configure_message.kwargs['controls'] == [hw.motor1, hw.motor2,
                                                    hw.motor3]
    RE(msgs)
    summarize_plan(msgs)


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_daq_fixed_target_multi_scan(RE, daq, hw, sample_file):
    logger.debug('test_daq_fixed_target_scan')
    ss = [1, 2]

    msgs = list(nbp.daq_fixed_target_multi_scan(sample='test_sample',
                                                detectors=[hw.det],
                                                x_motor=hw.motor1,
                                                y_motor=hw.motor2,
                                                scan_motor=hw.motor3, ss=ss,
                                                n_shots=3, path=sample_file,
                                                record=True, events=1))
    configure_message = None
    for msg in msgs:
        if msg.command == 'configure' and msg.obj is daq:
            configure_message = msg
            break

    assert configure_message.kwargs['record'] is True
    assert configure_message.kwargs['controls'] == [hw.motor1, hw.motor2,
                                                    hw.motor3]

    expected_moves = [1,                    # scan_motor[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      -20.59374999999996,   # x[0]
                      26.41445312499999,    # y[0]
                      2,                    # scan_motor[1]
                      -20.342057291666624,  # x[1]
                      26.412369791666656,
                      -20.342057291666624,  # x[1]
                      26.412369791666656,
                      -20.342057291666624,  # x[1]
                      26.412369791666656]   # y[1]

    moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    reads = [msg for msg in msgs if msg.command == 'read']
    assert moves == expected_moves
    assert len(reads) == 24
    RE(msgs)
    summarize_plan(msgs)


@pytest.mark.timeout(PLAN_TIMEOUT)
@pytest.mark.parametrize(
    'start, stop, num, n_reads',
    [
     (-5, 5, 11, 33),    # expect 3 reads / point (det, motor, daq)
     (-5, 5, float(1.), 33),    # step size, include endpoint
     (-1, 1, np.float128(0.2), 33),   # step size, end point not close
     (1, -1, -0.4, 18),  # positive to negative direction
     (1, -1, np.float64(0.4), 18),   # ignore step sign
     (-1, 0, np.float32(0.1), 33),  # close to 0, end near start
    ]
)
def test_daq_step_size(daq, hw, start, stop, num, n_reads):
    x_start = 1
    # absolute scan
    hw.motor1.set(x_start)
    msgs = list(nbp.daq_ascan([hw.det], hw.motor1,
                              start, stop, num, events=1))

    a_moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    reads = [msg for msg in msgs if msg.command == 'read']

    a_expected_moves = orange(start, stop, num)

    assert len(reads) == n_reads
    # move back to start after plan end
    assert np.isclose(a_moves, a_expected_moves + [x_start]).all()

    # relative scan
    hw.motor1.set(x_start)
    msgs = list(nbp.daq_dscan([hw.det], hw.motor1,
                              start, stop, num, events=1))

    # daq_dscan applies the relative shift after the steps are
    # computed, so we do here too.  This avoids some weird floating
    # point mistakes near zero
    d_expected_moves = orange(start, stop, num)
    d_expected_moves = [x+x_start for x in d_expected_moves]

    d_moves = [msg.args[0] for msg in msgs if msg.command == 'set']
    reads = [msg for msg in msgs if msg.command == 'read']

    assert len(reads) == n_reads
    assert np.isclose(d_moves, d_expected_moves + [x_start]).all()


@pytest.mark.timeout(PLAN_TIMEOUT)
def test_bad_step_size(RE, hw):
    with pytest.raises(TypeError):
        # bad step type
        RE(nbp.daq_ascan([hw.det], hw.motor1, 0, 1, 'a', events=1))

    with pytest.raises(ValueError):
        # step size bigger than range
        RE(nbp.daq_ascan([hw.det], hw.motor1, 0, 1, 20., events=1))

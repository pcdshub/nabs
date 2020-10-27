import pytest

import nabs.plans as nbp


@pytest.mark.timeout(5)
def test_duration_scan(RE, hw):
    """
    Run the duration scan and check the messages it creates.
    """
    # These will generate as many messages as they can in 0.01s
    scan1 = list(nbp.duration_scan([hw.det], hw.motor, [0, 1], duration=0.01))
    scan2 = list(nbp.duration_scan([hw.det1, hw.det2], hw.motor1, [-1, 1],
                                   hw.motor2, [-2, 2], duration=0.01))

    # I won't check these explicitly, but they should not error out
    RE(scan1)
    RE(scan2)

    # Scan should cycle through positions
    scan1_moves = list(msg.args[0] for msg in scan1 if msg.command == 'set')
    assert scan1_moves[:4] == [0, 1, 0, 1]

    scan2_moves = list(msg.args[0] for msg in scan2 if msg.command == 'set')
    assert scan2_moves[:8] == [-1, -2, 1, 2, -1, -2, 1, 2]

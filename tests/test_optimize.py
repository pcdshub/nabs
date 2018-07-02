import logging

from bluesky.plan_stubs import open_run, close_run
from ophyd.sim import SynGauss, SynAxis
import numpy as np
import pytest

from nabs.optimize import maximize, minimize, optimize


logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def inverted_gauss():
    motor = SynAxis(name='motor')
    # Make our inverted detector
    sig = SynGauss('det', motor, 'motor', center=0, Imax=-1, sigma=1)
    return (sig, motor)


def test_optimize(RE, inverted_gauss):
    logger.debug('test_optimize')
    # Respect motor limits
    (det, motor) = inverted_gauss
    setattr(motor, 'limits', (-2., -1.))
    RE(optimize(det, motor, 0.05, method='golden'))
    assert -2 <= motor.position <= -1.
    # No limits, no scan
    setattr(motor, 'limits', (0., 0.))
    with pytest.raises(ValueError):
        RE(optimize(det, motor, 0.05, method='golden'))
    # Unknown optimization method
    with pytest.raises(ValueError):
        RE(optimize(det, motor, 0.05, limits=(-1., 1), method='jump around'))


def test_minimize(RE, inverted_gauss):
    logger.debug("test_minimize")
    (det, motor) = inverted_gauss
    # Run the plan
    RE(minimize(det, motor, 0.05, limits=(-5, 10), method='golden'))
    # Should at least be within the tolerance at the end
    assert np.isclose(motor.position, 0.0, atol=0.05)


def test_maximize(RE, hw):
    logger.debug("test_maximize")
    # Run the plan
    RE(maximize(hw.det, hw.motor, 0.05, limits=(-9, 13), method='golden'))
    # Should at least be within the tolerance at the end
    assert np.isclose(hw.motor.position, 0.0, atol=0.05)

import logging

import numpy as np
import pytest
from bluesky.plan_stubs import close_run, open_run
from ophyd.sim import SynAxis, SynGauss, SynSignal

from nabs.optimize import (golden_section_search, maximize, minimize, optimize,
                           walk_to_target)

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def inverted_gauss():
    motor = SynAxis(name='motor')
    # Make our inverted detector
    sig = SynGauss('det', motor, 'motor', center=0, Imax=-1, sigma=1)
    return (sig, motor)


@pytest.fixture(scope='function')
def linear():
    motor = SynAxis(name='motor')
    # Make our linear detector
    sig = SynSignal(func=lambda: 4*motor.position, name='det')
    return (sig, motor)


def test_optimize(RE, inverted_gauss):
    logger.debug('test_optimize')
    # Respect motor limits
    (det, motor) = inverted_gauss
    setattr(motor, 'limits', (-2., -1.))
    RE(optimize(det.val, motor, 0.05, method='golden'))
    assert -2 <= motor.position <= -1.
    # No limits, no scan
    setattr(motor, 'limits', (0., 0.))
    with pytest.raises(ValueError):
        RE(optimize(det.val, motor, 0.05, method='golden'))
    # Unknown optimization method
    with pytest.raises(ValueError):
        RE(optimize(det.val, motor, 0.05, limits=(-1., 1),
                    method='jump around'))


def test_minimize(RE, inverted_gauss):
    logger.debug("test_minimize")
    (det, motor) = inverted_gauss
    # Run the plan
    RE(minimize(det.val, motor, 0.05, limits=(-5, 10), method='golden'))
    # Should at least be within the tolerance at the end
    assert np.isclose(motor.position, 0.0, atol=0.05)


def test_maximize(RE, hw):
    logger.debug("test_maximize")
    # Run the plan
    RE(maximize(hw.det.val, hw.motor, 0.05, limits=(-9, 13), method='golden'))
    # Should at least be within the tolerance at the end
    assert np.isclose(hw.motor.position, 0.0, atol=0.05)


def test_walk_to_target(RE, linear):
    logger.debug("test_walk_to_target")
    (det, motor) = linear
    # Run the plan
    RE(walk_to_target(det, motor, 16.0, 0.05,
                      limits=(-12, 18), method='golden'))
    assert np.isclose(motor.position, 4.0, atol=0.05)


def test_golden_section_search(RE, hw, inverted_gauss):
    logger.debug("test_golden_section_search")
    (sig, motor) = inverted_gauss
    # Catch the reported limits
    global region_limits
    region_limits = None

    # Pseudo-plan to golden-section search
    def gss():
        global region_limits
        yield from open_run()
        region_limits = yield from golden_section_search(sig, motor, 0.01,
                                                         limits=(-10, 5))
        yield from close_run()

    # Execute the plan
    RE(gss())
    # Check that the region we found is under the resolution
    assert (region_limits[1] - region_limits[0]) < 0.1
    # Check that the limits bound the center of the gaussian
    assert region_limits[1] > 0.
    assert region_limits[0] < 0.

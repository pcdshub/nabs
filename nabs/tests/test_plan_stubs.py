import logging

import numpy as np
import pytest
from bluesky.callbacks import CallbackCounter
from bluesky.plan_stubs import close_run, open_run

from nabs.plan_stubs import get_sample_targets, measure_average, update_sample

logger = logging.getLogger(__name__)


def test_measure_average(RE, hw):
    logger.debug("test_measure_average")

    # Pseudo-plan to measure average and check values
    def measure_plan(detectors):
        yield from open_run()
        ret = yield from measure_average(detectors, num=250)
        logger.debug('Test received %s from measure_average', str(ret))
        assert ret['motor'] == 0.0
        assert ret['motor_setpoint'] == 0.0
        assert np.isclose(ret['noisy_det'], 1.0, atol=0.1)
        yield from close_run()

    # Execute plan
    cnt = CallbackCounter()
    RE(measure_plan([hw.motor, hw.noisy_det]), {'event': [cnt]})
    # Check that we saw the right number of events
    assert cnt.value == 250


def test_update_sample(sample_file):
    # current sample name: test_sample
    sample = 'test_sample'
    xx, yy = get_sample_targets(
        sample_name=sample, path=sample_file)
    # expected values:
    xx_expected = [{"pos": -20.59374999999996, "status": True},
                   {"pos": -20.342057291666624, "status": True},
                   {"pos": -20.090364583333283, "status": True},
                   {"pos": -19.838671874999946, "status": True},
                   {"pos": -19.834546874999948, "status": False},
                   {"pos": -20.08622265624995, "status": False},
                   {"pos": -20.33789843749996, "status": False},
                   {"pos": -20.589574218749963, "status": False}]
    yy_expected = [{"pos": 26.41445312499999, "status": True},
                   {"pos": 26.412369791666656, "status": True},
                   {"pos": 26.41028645833332, "status": True},
                   {"pos": 26.408203124999986, "status": True},
                   {"pos":  26.664453124999994, "status": False},
                   {"pos":  26.66232812499999, "status": False},
                   {"pos":  26.660203124999992, "status": False},
                   {"pos":  26.65807812499999, "status": False}]
    update_sample(sample_name=sample,
                  path=sample_file, n_shots=4)
    xx, yy = get_sample_targets(
        sample_name=sample, path=sample_file)
    assert xx == xx_expected
    assert yy == yy_expected


def test_get_sample_targets(sample_file):
    # expected values:
    xx_expected = [{"pos": -20.59374999999996, "status": False},
                   {"pos": -20.342057291666624, "status": False},
                   {"pos": -20.090364583333283, "status": False},
                   {"pos": -19.838671874999946, "status": False},
                   {"pos": -19.834546874999948, "status": False},
                   {"pos": -20.08622265624995, "status": False},
                   {"pos": -20.33789843749996, "status": False},
                   {"pos": -20.589574218749963, "status": False}]
    yy_expected = [{"pos": 26.41445312499999, "status": False},
                   {"pos": 26.412369791666656, "status": False},
                   {"pos": 26.41028645833332, "status": False},
                   {"pos": 26.408203124999986, "status": False},
                   {"pos":  26.664453124999994, "status": False},
                   {"pos":  26.66232812499999, "status": False},
                   {"pos":  26.660203124999992, "status": False},
                   {"pos":  26.65807812499999, "status": False}]
    xx, yy = get_sample_targets(
        sample_name='test_sample', path=sample_file)
    assert xx == xx_expected
    assert yy == yy_expected

    with pytest.raises(Exception):
        get_sample_targets(
            sample_name='bad_test_sample_name', path=sample_file)
    with pytest.raises(Exception):
        get_sample_targets(
            sample_name='test_sample', path='bad_file_path')

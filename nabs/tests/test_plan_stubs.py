import logging

import numpy as np
import pytest
from bluesky.callbacks import CallbackCounter
from bluesky.plan_stubs import close_run, open_run

from nabs.plan_stubs import measure_average, update_sample, get_sample_info

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
    # the current index is -1
    # current sample name: test_sample
    sample = 'test_sample'
    current_last_shot_index = get_sample_info(
        sample_name=sample, path=sample_file)[2]
    assert current_last_shot_index == -1
    update_sample(sample_name=sample,
                  path=sample_file, last_shot_index=4)
    updated_last_shot_index = get_sample_info(
        sample_name=sample, path=sample_file)[2]
    assert updated_last_shot_index == 4


def test_get_sample_info(sample_file):
    # expected values:
    m_points_expected = 101
    n_points_expected = 4
    last_shot_index_expected = -1
    xx_expected = [-20.59374999999996,
                   - 20.342057291666624,
                   - 20.090364583333283,
                   - 19.838671874999946,
                   - 20.589574218749963,
                   - 20.33789843749996,
                   - 20.08622265624995,
                   - 19.834546874999948]
    yy_expected = [26.41445312499999,
                   26.412369791666656,
                   26.41028645833332,
                   26.408203124999986,
                   26.664453124999994,
                   26.66232812499999,
                   26.660203124999992,
                   26.65807812499999]
    m_points, n_points, last_shot_index, xx, yy = get_sample_info(
        sample_name='test_sample', path=sample_file)
    assert m_points == m_points_expected
    assert n_points == n_points_expected
    assert last_shot_index == last_shot_index_expected
    assert xx == xx_expected
    assert yy == yy_expected

    with pytest.raises(Exception):
        get_sample_info(
            sample_name='bad_test_sample_name', path=sample_file)
    with pytest.raises(Exception):
        get_sample_info(
            sample_name='test_sample', path='bad_file_path')

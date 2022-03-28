import bluesky.plan_stubs as bps
import bluesky.plans as bp
import bluesky.preprocessors as bpp
import numpy as np
import pytest
from ophyd.sim import SynAxis, hw

import nabs.plans as nbp
from nabs.simulators import validate_plan

hw = hw()


class LimitedMotor(SynAxis):
    def check_value(self, value, **kwargs):
        if np.abs(value) > 10:
            raise ValueError("value out of bounds")


limit_motor = LimitedMotor(name='limit_motor', labels={'motors'})


@bpp.set_run_key_decorator("run_2")
@bpp.run_decorator(md={})
def sim_plan_inner(npts=2):
    for j in range(npts):
        yield from bps.mov(hw.motor1, j * 0.1 + 1,
                           hw.motor2, j * 0.2 - 2)
        yield from bps.trigger_and_read([hw.motor1, hw.motor2,
                                         hw.det2])


@bpp.set_run_key_decorator("run_1")
@bpp.run_decorator(md={})
def sim_plan_outer(npts):
    for j in range(int(npts/2)):
        yield from bps.mov(hw.motor, j * 0.2)
        yield from bps.trigger_and_read([hw.motor, hw.det])

    yield from sim_plan_inner(npts + 1)

    for j in range(int(npts/2), npts):
        yield from bps.mov(hw.motor, j * 0.2)
        yield from bps.trigger_and_read([hw.motor, hw.det])


def bad_limits():
    yield from bps.open_run()
    yield from bps.sleep(1)
    yield from bps.mv(limit_motor, 100)
    yield from bps.sleep(1)
    yield from bps.close_run()


def bad_nesting():
    yield from bps.open_run()
    yield from bp.count([])
    yield from bps.close_run()


def bad_call():
    yield from bps.open_run()
    limit_motor.set(10)
    yield from bps.close_run()


def bad_stage():
    yield from bps.stage(hw.det)


@pytest.mark.parametrize(
    'plan',
    [
     bad_limits(),
     bad_nesting(),
     bad_call(),
    ]
)
def test_bad_plans(plan):
    success, _ = validate_plan(plan)
    assert success is False


@pytest.mark.parametrize(
    'plan',
    [
     sim_plan_outer(4),
     bp.count([hw.det], num=2),
     bp.scan([hw.det, hw.det2, hw.motor],
             hw.motor, 0, 1, hw.motor2, 1, 20, 10),
     nbp.daq_dscan([hw.det], hw.motor, 1, 0, 2, events=1)
    ]
)
def test_good_plans(plan, daq):
    success, _ = validate_plan(plan)
    assert success is True

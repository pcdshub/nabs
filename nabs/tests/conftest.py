import asyncio

import pytest
from bluesky import RunEngine
from ophyd.sim import hw as sim_hw
from pcdsdaq.daq import Daq
from pcdsdaq.sim import set_sim_mode


@pytest.fixture(scope='function')
def RE():
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    RE = RunEngine({}, loop=loop)

    yield RE

    if RE.state != 'idle':
        RE.halt()


@pytest.fixture(scope='function')
def hw():
    return sim_hw()


@pytest.fixture(scope='function')
def daq(RE):
    set_sim_mode(True)
    yield Daq(RE=RE, hutch='tst')
    set_sim_mode(False)

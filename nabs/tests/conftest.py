import asyncio

import pytest
from bluesky import RunEngine


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
    from ophyd.sim import hw
    return hw()

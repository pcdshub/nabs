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
    yield Daq(RE=RE, hutch_name='tst')
    set_sim_mode(False)


@pytest.fixture(scope='function')
def sample_file(tmp_path):
    path = tmp_path / "sub"
    path.mkdir()
    sample_file = path / "samples.yml"
    sample_file.write_text("""
test_sample:
  time_created: '2021-01-22 14:29:29.681059'
  top_left:
  - -20.59374999999996
  - 26.41445312499999
  top_right:
  - -19.838671874999946
  - 26.408203124999986
  bottom_right:
  - -19.426171874999945
  - 51.39570312500023
  bottom_left:
  - -20.176171875000115
  - 51.414453125000215
  M: 2
  N: 4
  coefficients:
  - -20.59374999999996
  - 0.7550781250000149
  - 0.4175781249998458
  - -0.005078124999844391
  - 26.41445312499999
  - -0.006250000000004974
  - 25.000000000000224
  - -0.012499999999977973
  last_shot_index: -1
  xx:
  - -20.59374999999996
  - -20.342057291666624
  - -20.090364583333283
  - -19.838671874999946
  - -20.589574218749963
  - -20.33789843749996
  - -20.08622265624995
  - -19.834546874999948
  yy:
  - 26.41445312499999
  - 26.412369791666656
  - 26.41028645833332
  - 26.408203124999986
  - 26.664453124999994
  - 26.66232812499999
  - 26.660203124999992
  - 26.65807812499999
    """)
    return sample_file

import asyncio

import pytest
from bluesky import RunEngine
from ophyd.device import Component as Cpt
from ophyd.positioner import SoftPositioner
from ophyd.pseudopos import (PseudoPositioner, PseudoSingle,
                             pseudo_position_argument, real_position_argument)
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


class NoOpPseudo(PseudoPositioner):
    softpos = Cpt(SoftPositioner)
    noop = Cpt(PseudoSingle)

    @pseudo_position_argument
    def forward(self, pseudo_pos):
        return self.RealPosition(pseudo_pos.noop)

    @real_position_argument
    def inverse(self, real_pos):
        return self.PseudoPosition(real_pos.softpos)


@pytest.fixture(scope='function')
def hw():
    # Everything from ophyd
    standard_hw = sim_hw()
    # Add some extras that we want
    standard_hw.no_op_pseudo = NoOpPseudo('', name='noop')
    return standard_hw


@pytest.fixture(scope='function')
def daq(RE):
    set_sim_mode(True)
    yield Daq(RE=RE, hutch_name='tst')
    set_sim_mode(False)


@pytest.fixture(scope='function')
def elog():
    class MockELog:
        def __init__(self, *args, **kwargs):
            self.posts = list()
            self.enable_run_posts = True

        def post(self, *args, **kwargs):
            self.posts.append((args, kwargs))

    return MockELog('TST')


@pytest.fixture(scope='function')
def ipython():
    class MockIPython:
        def __init__(self, *args, **kwargs):
            self.user_ns = dict(In=[""])

    return MockIPython()


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
  M: 101
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
  xx:
  - pos: -20.59374999999996
    status: false
  - pos: -20.342057291666624
    status: false
  - pos: -20.090364583333283
    status: false
  - pos: -19.838671874999946
    status: false
  - pos: -19.834546874999948
    status: false
  - pos: -20.08622265624995
    status: false
  - pos: -20.33789843749996
    status: false
  - pos: -20.589574218749963
    status: false
  yy:
  - pos: 26.41445312499999
    status: false
  - pos: 26.412369791666656
    status: false
  - pos: 26.41028645833332
    status: false
  - pos: 26.408203124999986
    status: false
  - pos: 26.664453124999994
    status: false
  - pos: 26.66232812499999
    status: false
  - pos: 26.660203124999992
    status: false
  - pos: 26.65807812499999
    status: false
    """)
    return sample_file

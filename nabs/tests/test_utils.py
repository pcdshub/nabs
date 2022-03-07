from ophyd.device import Component as Cpt
from ophyd.device import Device
from pcdsdevices.device import GroupDevice

from nabs.utils import post_ophyds_to_elog


class StatusDevice(Device):
    """ simulate a device with a status method """
    def status(self):
        return self.name


class BasicGroup(StatusDevice, GroupDevice):
    one = Cpt(StatusDevice, ':BASIC')
    two = Cpt(StatusDevice, ':COMPLEX')


class SomeDevice(StatusDevice):
    some = Cpt(StatusDevice, ':SOME')
    where = Cpt(StatusDevice, ':WHERE')


def test_ophyd_to_elog(elog):
    # make some devices

    group = BasicGroup('GROUP', name='group')
    some = SomeDevice('SOME', name='some')

    post_ophyds_to_elog([group, some], hutch_elog=elog)
    assert len(elog.posts) == 1
    # count number of content entries
    assert elog.posts[-1][0][0].count('<pre>') == 2

    post_ophyds_to_elog([group.one, some.some], hutch_elog=elog)
    assert len(elog.posts) == 1  # no children allowed by default

    post_ophyds_to_elog([[group, some], group.one, some.some],
                        allow_child=True, hutch_elog=elog)
    assert len(elog.posts) == 2
    assert elog.posts[-1][0][0].count('<pre>') == 4
    # two list levels
    assert elog.posts[-1][0][0].count("class='parent'") == 2

    # half-hearted html validation
    for post in elog.posts:
        for tag in ['pre', 'div', 'button']:
            assert post[0][0].count('<'+tag) == post[0][0].count('</'+tag)

import asyncio
import logging

from bluesky.callbacks import CallbackCounter

logger = logging.getLogger(__name__)


class CallbackCounterFuture(CallbackCounter):
    """
    A callback counter that marks a Future when the count reaches max_count.

    This will wait to recieve the number of events related to each of the
    given detectors. Some detectors may get extra events, but this will
    wait until they all have enough.

    Parameters
    ----------
    max_count: ``int``
        The number of events to wait for
    detectors: ``list``, optional
        The detectors to wait for events on. If omitted, we'll just wait
        for a total number of events.
    """
    def __init__(self, max_count, detectors=None):
        super().__init__(self)
        self.max_count = max_count
        if detectors is None:
            self.dets = None
        else:
            self.dets = {det.name: 0 for det in detectors}
        loop = asyncio.get_event_loop()
        self.future = loop.create_future()

    def __call__(self, name, doc):
        super().__call__(self, name, doc)
        if not self.future.done():
            if self.dets is None:
                if self.value >= self.max_count:
                    self.future.set_result('reached {}'.format(self.value))
            else:
                try:
                    data = doc['data']
                except KeyError:
                    logger.debug(('used detectors arg and had callback on '
                                  'non-event doc'))
                    return
                for name in self.dets.keys():
                    if name in data:
                        self.dets[name] += 1
                if all(val >= self.max_count for val in self.dets.values()):
                    self.future.set_result(('reached {} for all '
                                            'dets'.format(self.max_count)))

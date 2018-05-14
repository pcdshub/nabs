import logging
import time

from bluesky.plan_stubs import drop, save
from bluesky.preprocessors import plan_mutator
from bluesky.utils import make_decorator

logger = logging.getLogger(__name__)


class DropWrapper:
    """
    Replaces ``save`` messages with ``drop`` if the event is bad.

    Parameters
    ----------
    filters: ``dict``, optional
        A dictionary mapping from read key to function of one argument. This
        is an "is_bad_value(value)" function that should return ``True`` if the
        value is bad.

    max_dt: ``float``, optional
        If provided, we'll ``drop`` events if the time from before the first
        read to after the last read is greater than this number.
    """
    def __init__(self, filters=None, max_dt=None):
        self.filters = filters
        self.max_dt = max_dt

    def __call__(self, plan):
        yield from plan_mutator(plan, self._msg_proc)

    def _msg_proc(self, msg):
        if msg.command == 'create':
            self.ret = {}
            self.first_read_time = None
            self.last_read_time = None
            return None, None
        elif msg.command == 'read':
            return self._cache_read(msg), None
        elif msg.command == 'save':
            return self._filter_save(), None

    def _cache_read(self, msg):
        if self.first_read_time is None:
            self.first_read_time = time.time()
        ret = yield msg
        self.ret.update(ret)
        self.last_read_time = time.time()
        return ret

    def _filter_save(self):
        dt = self.last_read_time - self.first_read_time
        if self.max_dt is not None and dt > self.max_dt:
            logger.info(('Event took %ss to bundle, readings are desynced. '
                         'Dropping'), dt)
            return (yield from drop())
        elif self.filters is not None:
            for key, filt in self.filters.items():
                try:
                    value = self.ret[key]
                except KeyError:
                    logger.debug('Read bundle did not have filter key %s', key)
                    value = None
                if value is not None and filt[value]:
                    logger.info('Event had bad value %s=%s. Dropping',
                                key, value)
                    return (yield from drop())
        return (yield from save())


def drop_wrapper(plan, filters, max_dt):
    """
    Replaces ``save`` messages with ``drop`` if the event is bad.

    Parameters
    ----------
    plan: ``plan``
        The plan to wrap.

    filters: ``dict``, optional
        A dictionary mapping from read key to function of one argument. This
        is an "is_bad_value(value)" function that should return ``True`` if the
        value is bad.

    max_dt: ``float``, optional
        If provided, we'll ``drop`` events if the time from before the first
        read to after the last read is greater than this number.
    """
    yield from DropWrapper(filters, max_dt)(plan)


drop_decorator = make_decorator(drop_wrapper)

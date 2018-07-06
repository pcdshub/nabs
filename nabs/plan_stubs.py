import logging

from bluesky.plans import count
from bluesky.plan_stubs import (subscribe, unsubscribe, monitor, unmonitor,
                                sleep, checkpoint, abs_set, wait as wait_uid,
                                wait_for as wait_future)
from bluesky.preprocessors import stub_wrapper
from bluesky.utils import short_uid

from nabs.callbacks import CallbackCounterFuture
from nabs.streams import AverageStream


logger = logging.getLogger(__name__)


def measure_average(detectors, num, delay=None, stream=None):
    """
    Measure an average over a number of shots from a set of detectors

    Parameters
    ----------
    detectors : list
        List of detectors to read

    num : int
        Number of shots to average together

    delay: iterable or scalar, optional
        Time delay between successive readings. See ``bluesky.count`` for more
        details

    stream : AverageStream, optional
        If a plan will call :func:`.measure_average` multiple times, a single
        ``AverageStream`` instance can be created and then passed in on each
        call. This allows other callbacks to subscribe to the averaged data
        stream. If no ``AverageStream`` is provided then one is created for the
        purpose of this function.

    Returns
    -------
    averaged_event : dict
        A dictionary of all the measurements taken from the list of detectors
        averaged for ``num`` shots. The keys follow the same naming convention
        as that will appear in the event documents i.e "{name}_{field}"

    Notes
    -----
    The returned average dictionary will only contain keys for 'number' or
    'array' fields. Field types that can not be averaged such as 'string' will
    be ignored, do not expect them in the output.
    """
    # Create a stream and subscribe if not given one
    if not stream:
        stream = AverageStream(num=num)
        yield from subscribe('all', stream)
        # Manually kick the LiveDispatcher to emit a start document because we
        # will not see the original one since this is subscribed after open_run
        stream.start({'uid': None})
    # Ensure we sync our stream with request if using a prior one
    else:
        stream.num = num
    # Measure our detectors
    yield from stub_wrapper(count(detectors, num=num, delay=delay))
    # Return the measured average as a dictionary for use in adaptive plans
    return stream.last_event


def move_per_step(detectors, step, pos_cache):
    """
    The motion portion of the per_step hook.

    Use this inside of other per_step hooks to avoid rewriting the move part.
    """
    yield from checkpoint()
    grp = short_uid('set')
    for motor, pos in step.items():
        if pos == pos_cache[motor]:
            continue
        yield from abs_set(motor, pos, group=grp)
        pos_cache[motor] = pos
    yield from wait_uid(group=grp)


def monitor_step(events=None, duration=None):
    """
    Create bluesky per_step hook for monitoring detectors at every point.

    Parameters
    ----------
    events: ``int``, optional
        If provided, we'll monitor until we have enough events.
    duration: ``float``, optional
        If provided, we'll monitor for this fixed duration in seconds.
        If both arguments are provided, then we'll wait for both to be true,
        so we'll have a minimum elapsed time and a minimum number of events.

    Returns
    -------
    inner_monitor_step: ``function``
        A function that is usable as a bluesky per_step hook
    """
    if events is None and duration is None:
        raise ValueError(('Must pass events or duration kwarg to '
                          'monitor_step'))

    def inner_monitor_step(detectors, step, pos_cache):
        yield from move_per_step(detectors, step, pos_cache)

        if events is not None:
            counter = CallbackCounterFuture(events)
            sub_id = yield from subscribe(counter, 'event')

        for det in detectors:
            yield from monitor(det)

        if duration is not None:
            yield from sleep(duration)
        if events is not None:
            yield from wait_future(counter.future)
            yield from unsubscribe(sub_id)

        for det in detectors:
            yield from unmonitor(det)

    return inner_monitor_step
